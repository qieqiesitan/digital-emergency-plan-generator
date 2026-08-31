"""migration_runner 纯逻辑单测：mock DB 连接（不依赖真实 PG）。

覆盖任务 7 规格五条行为 + 语句拆分 + main.py 启动接线回归守护：
- 脚本按文件名排序扫描；
- 首次（无记录）→ 全部记为 baseline、不执行（MIGRATE_FRESH=1 时全部执行并记录）；
- 已有记录 → 仅应用未记录脚本、每个脚本一个事务、成功才记录；
- 已记录脚本跳过；
- advisory lock 获取失败 → 不执行任何脚本并抛出；
- finally 释放 advisory lock；
- main.py 启动流程真实调用 run_migrations（防 ImportError 守卫残留）。
"""

import re

import pytest

import app.services.migration_runner as mr


SCRIPT_A = "CREATE TABLE alpha (id int);"
SCRIPT_B = (
    "BEGIN;\n"
    "CREATE TABLE beta (id int);\n"
    "INSERT INTO beta VALUES (1);\n"
    "COMMIT;"
)
SCRIPT_C = "CREATE TABLE gamma (id int);"

SCRIPT_CONTENTS = {
    "db_migration_a.sql": SCRIPT_A,
    "db_migration_b.sql": SCRIPT_B,
    "db_migration_c.sql": SCRIPT_C,
}


class _FakeResult:
    """模拟 SQLAlchemy CursorResult：仅支持 .scalars().all()。"""

    def __init__(self, names):
        self._names = names

    def scalars(self):
        return _FakeScalars(self._names)


class _FakeScalars:
    def __init__(self, names):
        self._names = names

    def all(self):
        return list(self._names)


class _FakeConn:
    """内存 fake 连接：记录 execute 调用，按 SQL 分类返回结果。

    - pg_advisory_lock / pg_advisory_unlock → 空结果（可配置获取失败抛错）；
    - CREATE TABLE IF NOT EXISTS schema_migrations → 空结果；
    - SELECT script_name FROM schema_migrations → 返回预置已记录集合；
    - INSERT INTO schema_migrations → 记入 records（bookkeeping，不算脚本执行）；
    - 其它 → 记入 executed（脚本内容语句）。
    """

    def __init__(self, applied_names=(), fail_lock=False, fail_statement=None):
        self.applied = set(applied_names)
        self.calls = []  # (sql_text, params)
        self.records = []
        self.executed = []
        self.begin_entered = 0
        self.commits = 0
        self.closed = False
        self.fail_lock = fail_lock
        self.fail_statement = fail_statement

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.calls.append((sql, params))
        if self.fail_lock and "pg_advisory_lock" in sql:
            raise RuntimeError("advisory lock unavailable")
        if "pg_advisory_lock" in sql or "pg_advisory_unlock" in sql:
            return _FakeResult([])
        if "CREATE TABLE IF NOT EXISTS schema_migrations" in sql:
            return _FakeResult([])
        if "SELECT script_name FROM schema_migrations" in sql:
            return _FakeResult(sorted(self.applied))
        if "INSERT INTO schema_migrations" in sql:
            self.records.append(params["script_name"])
            return _FakeResult([])
        if self.fail_statement is not None and self.fail_statement in sql:
            raise RuntimeError(f"script statement failed: {sql[:80]}")
        self.executed.append(sql)
        return _FakeResult([])

    def begin(self):
        return _FakeBegin(self)

    async def commit(self):
        self.commits += 1

    async def close(self):
        self.closed = True


class _FakeBegin:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        self._conn.begin_entered += 1
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakeEngine:
    def __init__(self, conn):
        self._conn = conn

    async def connect(self):
        return self._conn


@pytest.fixture
def script_dir(tmp_path, monkeypatch):
    """把运行器的脚本目录指到临时目录，覆盖 backend/ 真实 glob。"""
    monkeypatch.setattr(mr, "migration_script_dir", lambda: tmp_path)
    return tmp_path


def _write_scripts(script_dir, names=("db_migration_a.sql", "db_migration_b.sql", "db_migration_c.sql")):
    for name in names:
        (script_dir / name).write_text(SCRIPT_CONTENTS[name], encoding="utf-8")


def _install_engine(monkeypatch, conn):
    monkeypatch.setattr(mr, "engine", _FakeEngine(conn))


def _install_fresh(monkeypatch, conn):
    monkeypatch.delenv("MIGRATE_FRESH", raising=False)
    _install_engine(monkeypatch, conn)


# ---------------------------------------------------------------------------
# 1) 脚本按文件名排序扫描


def test_list_migration_scripts_sorted_by_filename(script_dir):
    _write_scripts(
        script_dir,
        ("db_migration_c.sql", "db_migration_a.sql", "db_migration_b.sql"),
    )
    names = [p.name for p in mr.list_migration_scripts()]
    assert names == [
        "db_migration_a.sql",
        "db_migration_b.sql",
        "db_migration_c.sql",
    ]


# ---------------------------------------------------------------------------
# 2) 首次（无记录）→ 全部 baseline、不执行


@pytest.mark.asyncio
async def test_first_run_baselines_all_scripts_without_executing(monkeypatch, script_dir):
    _write_scripts(script_dir)
    conn = _FakeConn()
    _install_fresh(monkeypatch, conn)

    await mr.run_migrations()

    assert sorted(conn.records) == [
        "db_migration_a.sql",
        "db_migration_b.sql",
        "db_migration_c.sql",
    ]
    assert conn.executed == []
    assert conn.begin_entered == 1  # 全部 baseline 一次事务
    assert conn.closed is True


# ---------------------------------------------------------------------------
# 3) MIGRATE_FRESH=1 → 全部执行并记录


@pytest.mark.asyncio
async def test_fresh_env_executes_all_scripts_and_records(monkeypatch, script_dir):
    _write_scripts(script_dir)
    conn = _FakeConn()
    _install_engine(monkeypatch, conn)
    monkeypatch.setenv("MIGRATE_FRESH", "1")

    await mr.run_migrations()

    assert conn.executed == [
        "CREATE TABLE alpha (id int)",
        "CREATE TABLE beta (id int)",
        "INSERT INTO beta VALUES (1)",
        "CREATE TABLE gamma (id int)",
    ]
    assert sorted(conn.records) == [
        "db_migration_a.sql",
        "db_migration_b.sql",
        "db_migration_c.sql",
    ]
    assert conn.begin_entered == 3  # 每个脚本一个事务


# ---------------------------------------------------------------------------
# 4) 已有记录 → 仅应用未记录脚本、成功才记录


@pytest.mark.asyncio
async def test_incremental_applies_only_unrecorded_scripts(monkeypatch, script_dir):
    _write_scripts(script_dir)
    conn = _FakeConn(applied_names=["db_migration_a.sql"])
    _install_fresh(monkeypatch, conn)

    await mr.run_migrations()

    # a 已记录被跳过；b/c 未记录被应用（b 自带的 BEGIN/COMMIT 包裹被剥离）
    assert conn.executed == [
        "CREATE TABLE beta (id int)",
        "INSERT INTO beta VALUES (1)",
        "CREATE TABLE gamma (id int)",
    ]
    assert conn.records == ["db_migration_b.sql", "db_migration_c.sql"]
    assert conn.begin_entered == 2  # b、c 各一个事务


# ---------------------------------------------------------------------------
# 5) 已记录脚本全部跳过


@pytest.mark.asyncio
async def test_recorded_scripts_skipped(monkeypatch, script_dir):
    _write_scripts(script_dir)
    conn = _FakeConn(
        applied_names=[
            "db_migration_a.sql",
            "db_migration_b.sql",
            "db_migration_c.sql",
        ]
    )
    _install_fresh(monkeypatch, conn)

    await mr.run_migrations()

    assert conn.executed == []
    assert conn.records == []
    assert conn.begin_entered == 0


# ---------------------------------------------------------------------------
# 6) advisory lock 获取失败 → 不执行任何脚本并抛出


@pytest.mark.asyncio
async def test_lock_failure_prevents_execution_and_reraises(monkeypatch, script_dir):
    _write_scripts(script_dir)
    conn = _FakeConn(fail_lock=True)
    _install_fresh(monkeypatch, conn)

    with pytest.raises(RuntimeError, match="advisory lock unavailable"):
        await mr.run_migrations()

    assert conn.executed == []
    assert conn.records == []
    # 未获取到锁，不应尝试 unlock
    assert not any("pg_advisory_unlock" in sql for sql, _ in conn.calls)
    assert conn.closed is True


# ---------------------------------------------------------------------------
# 7) finally 释放 advisory lock


@pytest.mark.asyncio
async def test_lock_released_after_successful_run(monkeypatch, script_dir):
    _write_scripts(script_dir, names=("db_migration_a.sql",))
    conn = _FakeConn()
    _install_fresh(monkeypatch, conn)

    await mr.run_migrations()

    assert any("pg_advisory_unlock" in sql for sql, _ in conn.calls)
    assert conn.closed is True


# ---------------------------------------------------------------------------
# 8) 脚本执行失败 → 该脚本不记录并向上抛（后续脚本不执行）


@pytest.mark.asyncio
async def test_script_failure_aborts_without_record(monkeypatch, script_dir):
    _write_scripts(script_dir)
    conn = _FakeConn(
        applied_names=["db_migration_a.sql"],
        fail_statement="CREATE TABLE gamma",
    )
    _install_fresh(monkeypatch, conn)

    with pytest.raises(RuntimeError, match="script statement failed"):
        await mr.run_migrations()

    # beta 成功已记录；gamma 失败未记录（事务回滚）
    assert conn.records == ["db_migration_b.sql"]
    assert conn.closed is True


# ---------------------------------------------------------------------------
# 9) SQL 语句拆分：美元引用 / 注释 / 单引号内的分号不参与拆分


def test_split_sql_statements_handles_dollar_quotes_comments_and_strings():
    sql = """
-- line comment ;
/* block ; comment */
CREATE FUNCTION f() RETURNS text AS $$
  SELECT 'a;b';
$$ LANGUAGE sql;
DO $$
BEGIN
  RAISE NOTICE 'x;y';
END
$$;
INSERT INTO t (v) VALUES ('it''s;ok');
INSERT INTO t2 (v) VALUES ('--not a comment; /* nor this */');
"""
    stmts = mr._split_sql_statements(sql)
    assert len(stmts) == 4
    assert stmts[0].startswith("CREATE FUNCTION f()")
    assert stmts[1].startswith("DO $$")
    assert stmts[2] == "INSERT INTO t (v) VALUES ('it''s;ok')"
    assert stmts[3] == "INSERT INTO t2 (v) VALUES ('--not a comment; /* nor this */')"


def test_split_sql_statements_raises_on_unclosed_block_comment():
    """未闭合 /* 块注释 → 抛错而非静默截断剩余 SQL。"""
    with pytest.raises(ValueError, match="块注释未闭合"):
        mr._split_sql_statements("SELECT 1; /* never closed")


def test_split_sql_statements_handles_all_bundled_scripts():
    """守卫：全部捆绑 db_migration_*.sql 都能拆出可执行语句（美元引用/注释/BEGIN/COMMIT）。"""
    for script in mr.list_migration_scripts():
        stmts = mr._split_sql_statements(script.read_text(encoding="utf-8"))
        executable = [s for s in stmts if not mr._is_transaction_wrapper(s)]
        assert executable, f"{script.name}: 无任何可执行语句"
        assert all(s.strip() for s in stmts), f"{script.name}: 存在空语句"
        for stmt in stmts:
            tags = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", stmt)
            assert len(tags) % 2 == 0, f"{script.name}: 美元引用不平衡: {stmt[:60]}"


@pytest.mark.asyncio
async def test_apply_script_skips_begin_commit_wrappers(tmp_path):
    script_path = tmp_path / "db_migration_wrapped.sql"
    script_path.write_text("BEGIN;\nCREATE TABLE wrapped (id int);\nCOMMIT;\n", encoding="utf-8")
    conn = _FakeConn()
    await mr._apply_script(conn, script_path)
    assert conn.executed == ["CREATE TABLE wrapped (id int)"]


# ---------------------------------------------------------------------------
# 10) main.py 启动接线回归：run_migrations 必须真实被调用


def test_main_imports_run_migrations_directly():
    """守护：main.py 必须模块级直接导入（不允许 ImportError 守卫残留为 None）。"""
    import app.main as main_mod

    assert main_mod.run_migrations is mr.run_migrations


@pytest.mark.asyncio
async def test_main_lifespan_calls_run_migrations(monkeypatch):
    """守护：启动流程必须真实调用 run_migrations，防守卫导致迁移被静默跳过。"""
    import app.main as main_mod

    called = []

    async def _fake_run_migrations():
        called.append("run_migrations")

    async def _fake_import_seed_configs():
        called.append("import_seed_configs")

    class _FakeRunSyncConn:
        async def run_sync(self, fn):
            return None

    class _FakeBegin:
        async def __aenter__(self):
            return _FakeRunSyncConn()

        async def __aexit__(self, *exc):
            return False

    class _FakeEngine:
        def begin(self):
            return _FakeBegin()

    monkeypatch.setattr(main_mod, "engine", _FakeEngine())
    monkeypatch.setattr(main_mod, "run_migrations", _fake_run_migrations)
    import app.services.third_party_config as tpc_mod

    monkeypatch.setattr(tpc_mod, "import_seed_configs", _fake_import_seed_configs)
    # APScheduler 由 lifespan 内部 try/except 处理（缺失时告警降级，不影响本断言）。

    agen = main_mod.lifespan(main_mod.app)
    await agen.__aenter__()
    try:
        assert called == ["run_migrations", "import_seed_configs"]
    finally:
        await agen.__aexit__(None, None, None)
