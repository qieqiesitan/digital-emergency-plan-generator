# 重大危险源 R 值法分级（后端核心）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 能在系统内建立重大危险源单元、录入单元内危险化学品与设计最大量、按 GB 18218-2018 确定性计算辨识指标 s 与分级指标 R、判定重大危险源等级、保存不可变计算快照，并把结论挂到法规条文。

**架构：** 计算引擎做成**纯函数**（`major_hazard_calc.py`，无任何 IO），临界量与校正系数由调用方注入，保证可离线单测、可复算、可审计；常量表与业务表分成两个模型文件，常量用"SQL 迁移 + 确定性 UUID5 + ON CONFLICT DO NOTHING"灌库（沿用 `db_migration_20260903_chemical_library_catalog.sql` 的既有范式）；计算快照只追加不修改，逐品种输入明细存 JSONB，标准修订后历史记录仍可复算。

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x（`Mapped` + `mapped_column`）/ PostgreSQL（`UUID(as_uuid=False)` + `JSONB`）/ Pydantic / pytest。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §4、§6

**范围说明：** 本计划是规格 §11.1 中「计划 1（P0）」的**后端核心部分**，覆盖 P0-1~P0-4 与 P0-7 的后端。P0-5（AI 抽取链路 + `llm_client` 增强）、P0-6（前端）、P0-7 的报告导出，另出计划 2——理由是每个计划必须能独立产出**可运行、可测试**的软件，把前端与 AI 链路塞进来会让单个计划无法被一次完整执行与审查。

---

## 文件结构

**新建**

| 文件 | 职责 |
|---|---|
| `backend/app/services/major_hazard_calc.py` | GB 18218 计算引擎（纯函数，无 IO）：辨识指标 s、分级指标 R、等级判定 |
| `backend/app/models/standard_constants.py` | 标准常量 ORM（4 张：临界量、β、α、分级） |
| `backend/app/models/major_hazard.py` | 业务 ORM（4 张：单元、单元品种、计算快照、档案） |
| `backend/app/models/evidence.py` | 依据层多态表 `evidence_refs` |
| `backend/app/services/major_hazard_service.py` | 业务编排：读常量 → 调引擎 → 写不可变快照；单元/档案读写 |
| `backend/app/services/evidence_service.py` | 依据层读写（挂条文、按归属查条文） |
| `backend/app/schemas/major_hazard.py` | Pydantic 出入参 |
| `backend/app/routers/major_hazard.py` | REST API（单元/品种/计算/快照/档案/依据） |
| `backend/db_migration_20260917_standard_constants.sql` | 常量表 DDL + GB 18218 表1~表6 种子数据 |
| `backend/db_migration_20260917_major_hazard.sql` | 业务表 DDL + `evidence_refs` DDL |
| `backend/db_migration_20260917_chemical_storage_numeric.sql` | 危化品存量结构化字段（保留旧字段） |
| `scripts/gen_major_hazard_seed_sql.py` | 由 `docs/标准数据-GB18218-2018/*.json` 生成常量种子 SQL（可复现） |
| `backend/tests/test_major_hazard_calc.py` | 计算引擎单测（含标准边界值） |
| `backend/tests/test_major_hazard_models.py` | 常量表与业务表结构断言 |
| `backend/tests/test_major_hazard_service.py` | 快照不可变、可复算 |
| `backend/tests/test_major_hazard_api.py` | API 测试（TestClient + 依赖覆盖） |
| `backend/tests/test_evidence_service.py` | 依据层测试 |

**修改**

| 文件 | 改动 |
|---|---|
| `backend/app/main.py:253-293` | 在 `app.include_router(data_dicts.router, prefix="/api/v1")` 之后追加 `major_hazard` 路由注册 |
| `backend/app/models/hazardous_chemicals.py` | 新增 `storage_amount` / `storage_unit` 两列，**保留** `max_storage` |

**既有约定（务必遵守）**

- 迁移脚本放在 `backend/` 根，文件名 `db_migration_*.sql`，由 `app/services/migration_runner.py` 启动时按 **文件名排序**自动执行，执行记录写 `schema_migrations`。**新脚本不要加进 `BASELINE_MIGRATIONS`**。
- 种子数据用确定性 UUID5：`uuid.uuid5(uuid.NAMESPACE_URL, "<命名空间>/<自然键>")`，配 `ON CONFLICT (id) DO NOTHING`，保证可重复执行。
- 模型统一用 `Mapped[...] = mapped_column(...)`；主键 `UUID(as_uuid=False)` + `default=lambda: str(uuid4())`。
- 测试路径 `backend/tests/`，纯服务测试用 `MagicMock`，API 测试用 `FastAPI()` + `app.dependency_overrides`。

---

## 任务 1：R 值法计算引擎（纯函数）

**文件：**

- 创建：`backend/app/services/major_hazard_calc.py`
- 测试：`backend/tests/test_major_hazard_calc.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""GB 18218-2018 R 值法计算引擎单测。"""

import pytest

from app.services.major_hazard_calc import (
    FORMULA_VERSION,
    CalcInputError,
    ChemicalInput,
    alpha_for_population,
    compute,
    level_for_r,
)


def _chem(name="氯", q=1.0, Q=5.0, beta=4.0):
    return ChemicalInput(name=name, q_design_max=q, critical_quantity=Q, beta=beta)


def test_alpha_table5_boundaries():
    """表5 暴露人员校正系数 α 的分档边界。"""
    assert alpha_for_population(0) == 0.5
    assert alpha_for_population(1) == 1.0
    assert alpha_for_population(29) == 1.0
    assert alpha_for_population(30) == 1.2
    assert alpha_for_population(49) == 1.2
    assert alpha_for_population(50) == 1.5
    assert alpha_for_population(99) == 1.5
    assert alpha_for_population(100) == 2.0
    assert alpha_for_population(5000) == 2.0


def test_level_for_r_table6_boundaries():
    """表6 分级标准：一级 R>=100；二级 100>R>=50；三级 50>R>=10；四级 R<10。"""
    assert level_for_r(100.0) == "一级"
    assert level_for_r(99.999) == "二级"
    assert level_for_r(50.0) == "二级"
    assert level_for_r(49.999) == "三级"
    assert level_for_r(10.0) == "三级"
    assert level_for_r(9.999) == "四级"
    assert level_for_r(0.0) == "四级"


def test_single_chemical_below_threshold_is_not_major_hazard():
    """式(1) 单品种：q<Q 时不构成重大危险源，等级为空。"""
    r = compute([_chem(q=4.9, Q=5.0)], exposed_population=0)
    assert r.is_major_hazard is False
    assert r.level is None
    assert r.s_value == pytest.approx(0.98)


def test_single_chemical_equal_threshold_is_major_hazard():
    """式(1)：q 等于临界量即构成（"等于或超过"）。"""
    r = compute([_chem(q=5.0, Q=5.0)], exposed_population=0)
    assert r.is_major_hazard is True
    assert r.s_value == pytest.approx(1.0)


def test_multi_chemical_s_exactly_one():
    """式(1) 多品种：s 恰好等于 1 构成重大危险源。"""
    r = compute(
        [_chem("氯", q=2.5, Q=5.0), _chem("氨", q=5.0, Q=10.0)],
        exposed_population=0,
    )
    assert r.s_value == pytest.approx(1.0)
    assert r.is_major_hazard is True


def test_r_value_uses_alpha_and_beta():
    """式(2)：R = α × Σ βi × (qi/Qi)。"""
    # α=0.5（0 人），氯 β=4 q/Q=1.0 -> 4.0；氨 β=2 q/Q=0.5 -> 1.0；Σ=5.0；R=2.5
    r = compute(
        [_chem("氯", q=5.0, Q=5.0, beta=4.0), _chem("氨", q=5.0, Q=10.0, beta=2.0)],
        exposed_population=0,
    )
    assert r.alpha == 0.5
    assert r.r_value == pytest.approx(2.5)
    assert r.level == "四级"


def test_r_value_crosses_level_1():
    """暴露人员 100 人以上（α=2.0）时 R 翻四倍，跨到一级。"""
    r = compute([_chem("氯", q=250.0, Q=5.0, beta=4.0)], exposed_population=100)
    # q/Q = 50；β=4 -> 200；α=2.0 -> R=400
    assert r.r_value == pytest.approx(400.0)
    assert r.level == "一级"


def test_items_detail_is_recorded_for_each_chemical():
    """快照明细逐品种记录 q/Q/β/qQ 与结论依据。"""
    r = compute([_chem("氯", q=5.0, Q=5.0, beta=4.0)], exposed_population=0)
    assert len(r.items) == 1
    item = r.items[0]
    assert item["name"] == "氯"
    assert item["q"] == pytest.approx(5.0)
    assert item["Q"] == pytest.approx(5.0)
    assert item["beta"] == pytest.approx(4.0)
    assert item["q_over_Q"] == pytest.approx(1.0)
    assert item["beta_times_q_over_Q"] == pytest.approx(4.0)


def test_formula_version_is_pinned():
    assert FORMULA_VERSION == "GB18218-2018"


@pytest.mark.parametrize(
    "bad",
    [
        [_chem(q=-1.0)],
        [_chem(Q=0.0)],
        [_chem(beta=0.0)],
    ],
)
def test_invalid_input_raises(bad):
    """q 为负、Q 为 0、β 为 0 均属输入错误，必须显式报错而不是静默出结果。"""
    with pytest.raises(CalcInputError):
        compute(bad, exposed_population=0)


def test_empty_chemical_list_raises():
    """单元内没有品种时不能计算——空单元不是"不构成重大危险源"，是数据未填。"""
    with pytest.raises(CalcInputError):
        compute([], exposed_population=0)


def test_negative_population_raises():
    with pytest.raises(CalcInputError):
        compute([_chem()], exposed_population=-1)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_calc.py -v
```

预期：收集阶段 FAIL，报错 `ModuleNotFoundError: No module named 'app.services.major_hazard_calc'`

- [ ] **步骤 3：编写最少实现代码**

```python
"""GB 18218-2018 危险化学品重大危险源 R 值法计算引擎（纯函数，无 IO）。

依据《危险化学品重大危险源辨识》GB 18218-2018：
- 4.2.1 辨识指标 式(1)：s = q1/Q1 + q2/Q2 + … + qn/Qn，s >= 1 即构成重大危险源
- 4.3.2 分级指标 式(2)：R = α × Σ βi × (qi/Qi)
- 4.3.3 分级标准 表6：一级 R>=100；二级 100>R>=50；三级 50>R>=10；四级 R<10
- 4.2.2 储罐及其他容器、设备或仓储区的实际存在量按设计最大量确定

本模块刻意不做任何数据库访问：临界量 Q 与校正系数 β 由调用方从常量表读出后注入，
以便离线单测，并满足"计算结果必须可复算"的审计要求。
"""

from __future__ import annotations

from dataclasses import dataclass

FORMULA_VERSION = "GB18218-2018"


class CalcInputError(ValueError):
    """计算输入不合法（数据未填或填错），与"不构成重大危险源"是两回事。"""


@dataclass(frozen=True)
class ChemicalInput:
    """单元内一种危险化学品的计算输入。q 与 Q 单位均为吨。"""

    name: str
    q_design_max: float
    critical_quantity: float
    beta: float


@dataclass(frozen=True)
class CalcResult:
    s_value: float
    r_value: float
    alpha: float
    is_major_hazard: bool
    level: str | None
    items: tuple[dict, ...]


def alpha_for_population(population: int) -> float:
    """表5 暴露人员校正系数 α（按厂区边界外扩 500m 内可能暴露人员数量）。"""
    if population < 0:
        raise CalcInputError("厂外可能暴露人员数量不能为负")
    if population >= 100:
        return 2.0
    if population >= 50:
        return 1.5
    if population >= 30:
        return 1.2
    if population >= 1:
        return 1.0
    return 0.5


def level_for_r(r_value: float) -> str:
    """表6 重大危险源级别与 R 值的对应关系。"""
    if r_value >= 100:
        return "一级"
    if r_value >= 50:
        return "二级"
    if r_value >= 10:
        return "三级"
    return "四级"


def _validate(chemicals: list[ChemicalInput], exposed_population: int) -> None:
    if not chemicals:
        raise CalcInputError("单元内没有任何危险化学品，无法计算")
    if exposed_population < 0:
        raise CalcInputError("厂外可能暴露人员数量不能为负")
    for c in chemicals:
        if not c.name:
            raise CalcInputError("危险化学品名称不能为空")
        if c.q_design_max < 0:
            raise CalcInputError(f"{c.name}：设计最大量不能为负")
        if c.critical_quantity <= 0:
            raise CalcInputError(f"{c.name}：临界量必须大于 0")
        if c.beta <= 0:
            raise CalcInputError(f"{c.name}：校正系数 β 必须大于 0")


def compute(
    chemicals: list[ChemicalInput],
    exposed_population: int,
) -> CalcResult:
    """按式(1) 辨识、式(2) 分级。返回结论与逐品种明细（供快照落库）。"""
    _validate(chemicals, exposed_population)

    items: list[dict] = []
    s_value = 0.0
    weighted = 0.0
    for c in chemicals:
        q_over_q = c.q_design_max / c.critical_quantity
        beta_term = c.beta * q_over_q
        s_value += q_over_q
        weighted += beta_term
        items.append(
            {
                "name": c.name,
                "q": c.q_design_max,
                "Q": c.critical_quantity,
                "beta": c.beta,
                "q_over_Q": q_over_q,
                "beta_times_q_over_Q": beta_term,
            }
        )

    alpha = alpha_for_population(exposed_population)
    r_value = alpha * weighted
    is_major_hazard = s_value >= 1.0
    return CalcResult(
        s_value=s_value,
        r_value=r_value,
        alpha=alpha,
        is_major_hazard=is_major_hazard,
        level=level_for_r(r_value) if is_major_hazard else None,
        items=tuple(items),
    )
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_calc.py -v
```

预期：`13 passed`（含 3 个参数化用例）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/major_hazard_calc.py backend/tests/test_major_hazard_calc.py
git commit -m "feat(major-hazard): GB18218 R 值法计算引擎（纯函数）+ 单测"
```

---

## 任务 2：标准常量表 DDL + 种子 SQL 生成器

**文件：**

- 创建：`scripts/gen_major_hazard_seed_sql.py`
- 创建：`backend/db_migration_20260917_standard_constants.sql`（由脚本生成）
- 测试：`backend/tests/test_major_hazard_constants_sql.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""常量迁移 SQL 的结构断言（不连数据库，只校验生成物内容）。"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SQL_PATH = BACKEND / "db_migration_20260917_standard_constants.sql"


def _sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8")


def test_sql_file_exists():
    assert SQL_PATH.exists(), "常量迁移脚本缺失"


def test_creates_four_constant_tables():
    sql = _sql()
    for table in (
        "critical_quantities",
        "hazard_beta_factors",
        "exposure_alpha_factors",
        "major_hazard_levels",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{table}\b", sql), table


def test_table1_has_85_rows():
    sql = _sql()
    rows = re.findall(r"INSERT INTO critical_quantities", sql)
    # 表1 85 条 + 表2 24 条（另有 2 行分组表头不灌）
    assert len(rows) == 109, f"预期 109 行常量，实际 {len(rows)}"


def test_all_inserts_are_idempotent():
    sql = _sql()
    inserts = re.findall(r"INSERT INTO [a-z_]+\s*\([^)]*\)\s*VALUES", sql)
    on_conflicts = re.findall(r"ON CONFLICT \(id\) DO NOTHING", sql)
    assert len(inserts) == len(on_conflicts) > 0


def test_seed_uses_deterministic_uuid5_namespace():
    """种子 id 必须来自固定命名空间，重复生成结果一致。"""
    gen = (BACKEND.parent / "scripts" / "gen_major_hazard_seed_sql.py").read_text(encoding="utf-8")
    assert "NAMESPACE_URL" in gen
    assert "major-hazard/GB18218-2018/" in gen


def test_chemical_names_are_not_corrupted():
    """防回归：序号 13 的煤气含下标 ₂/₄，序号 6 碳酰氯临界量 0.3。"""
    sql = _sql()
    assert "H₂" in sql and "CH₄" in sql
    assert "'碳酰氯'" in sql and "0.3" in sql
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_constants_sql.py -v
```

预期：FAIL，报错 `常量迁移脚本缺失` 与 `scripts/gen_major_hazard_seed_sql.py` 不存在

- [ ] **步骤 3：编写种子 SQL 生成器**

```python
"""由 docs/标准数据-GB18218-2018/*.json 生成常量迁移 SQL。

输出 backend/db_migration_20260917_standard_constants.sql：
- DDL：4 张常量表
- 种子：表1 85 条 + 表2 24 条 + 表3 14 条 + 表4 24 条 + 表5 5 条 + 表6 4 条

id 一律用 uuid5(NAMESPACE_URL, "major-hazard/GB18218-2018/<表>/<自然键>")，
配 ON CONFLICT (id) DO NOTHING，保证脚本可重复执行、幂等可重放。

用法：python scripts/gen_major_hazard_seed_sql.py
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "标准数据-GB18218-2018"
OUT = ROOT / "backend" / "db_migration_20260917_standard_constants.sql"
NS = uuid.NAMESPACE_URL
STANDARD = "GB18218-2018"


def _uid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"major-hazard/{STANDARD}/{kind}/{key}"))


def _q(value: str) -> str:
    """SQL 字符串字面量转义（单引号翻倍）。"""
    return "'" + str(value).replace("'", "''") + "'"


def _num(value: str) -> str:
    """把 '150(净重)' 这类带说明的临界量取出数值；纯数值原样返回。"""
    text = str(value).strip()
    if text in ("", "—", "-"):
        return "NULL"
    out, buf, dot = [], "", False
    for ch in text:
        if ch.isdigit():
            buf += ch
        elif ch == "." and not dot:
            buf += ch
            dot = True
        else:
            break
    return buf or "NULL"


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def build_sql() -> str:
    t1 = _load("gb18218-2018-table1-critical-quantities.json")
    t2 = _load("gb18218-2018-table2-critical-quantities.json")
    t3 = _load("gb18218-2018-table3-beta-gas.json")
    t4 = _load("gb18218-2018-table4-beta-class.json")
    t5 = _load("gb18218-2018-table5-alpha.json")
    t6 = _load("gb18218-2018-table6-levels.json")

    lines: list[str] = [
        "-- 20260917 GB 18218-2018《危险化学品重大危险源辨识》常量表与种子数据",
        "-- 本文件由 scripts/gen_major_hazard_seed_sql.py 生成，请勿手工编辑。",
        "-- 数据来源：docs/标准数据-GB18218-2018/（标准正本 PDF 抽取，CAS 校验位已逐条验证）。",
        "-- id 使用 uuid5(NAMESPACE_URL, 'major-hazard/GB18218-2018/<表>/<自然键>')，",
        "-- 配 ON CONFLICT (id) DO NOTHING，保证幂等可重放。",
        "",
        "CREATE TABLE IF NOT EXISTS critical_quantities (",
        "    id UUID PRIMARY KEY,",
        "    standard VARCHAR(40) NOT NULL,",
        "    table_no VARCHAR(4) NOT NULL,",
        "    chemical_name VARCHAR(500) NOT NULL,",
        "    alias VARCHAR(500),",
        "    cas_no VARCHAR(120),",
        "    category VARCHAR(80),",
        "    symbol VARCHAR(20),",
        "    critical_t NUMERIC(18, 6),",
        "    critical_note VARCHAR(80),",
        "    source_page INTEGER,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cq_table1_name",
        "    ON critical_quantities (standard, chemical_name) WHERE table_no = '1';",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cq_table2_symbol",
        "    ON critical_quantities (standard, symbol) WHERE table_no = '2';",
        "CREATE INDEX IF NOT EXISTS ix_cq_cas ON critical_quantities (cas_no);",
        "",
        "CREATE TABLE IF NOT EXISTS hazard_beta_factors (",
        "    id UUID PRIMARY KEY,",
        "    standard VARCHAR(40) NOT NULL,",
        "    source_table VARCHAR(4) NOT NULL,",
        "    chemical_name VARCHAR(200),",
        "    category VARCHAR(80),",
        "    symbol VARCHAR(20),",
        "    beta NUMERIC(6, 3) NOT NULL,",
        "    source_page INTEGER,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        "CREATE INDEX IF NOT EXISTS ix_hbf_name ON hazard_beta_factors (standard, chemical_name);",
        "CREATE INDEX IF NOT EXISTS ix_hbf_symbol ON hazard_beta_factors (standard, symbol);",
        "",
        "CREATE TABLE IF NOT EXISTS exposure_alpha_factors (",
        "    id UUID PRIMARY KEY,",
        "    standard VARCHAR(40) NOT NULL,",
        "    label VARCHAR(40) NOT NULL,",
        "    population_min INTEGER NOT NULL,",
        "    population_max INTEGER,",
        "    alpha NUMERIC(4, 2) NOT NULL,",
        "    source_page INTEGER,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_eaf_label",
        "    ON exposure_alpha_factors (standard, label);",
        "",
        "CREATE TABLE IF NOT EXISTS major_hazard_levels (",
        "    id UUID PRIMARY KEY,",
        "    standard VARCHAR(40) NOT NULL,",
        "    level_name VARCHAR(20) NOT NULL,",
        "    r_expression VARCHAR(60) NOT NULL,",
        "    r_min NUMERIC(12, 3),",
        "    r_max NUMERIC(12, 3),",
        "    source_page INTEGER,",
        "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        ");",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_mhl_level",
        "    ON major_hazard_levels (standard, level_name);",
        "",
    ]

    for r in t1:
        key = f"t1/{r['seq']}"
        cas = "；".join(r["cas"]) if r["cas"] else None
        note = None if str(r["critical_t"]).replace(".", "").isdigit() else str(r["critical_t"])
        lines.append(
            "INSERT INTO critical_quantities "
            "(id, standard, table_no, chemical_name, alias, cas_no, critical_t, critical_note, source_page) "
            f"VALUES ({_q(_uid('critical', key))}, {_q(STANDARD)}, '1', {_q(r['name'])}, "
            f"{_q(r['alias']) if r['alias'] else 'NULL'}, {_q(cas) if cas else 'NULL'}, "
            f"{_num(r['critical_t'])}, {_q(note) if note else 'NULL'}, {r['source_page']}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    for r in t2:
        if not r["symbol"] or r["symbol"].endswith("符号"):
            continue  # 跳过「健康危害 J」「物理危险 W」两行分组表头
        key = f"t2/{r['symbol']}"
        note = None if str(r["critical_t"]).replace(".", "").isdigit() else str(r["critical_t"])
        lines.append(
            "INSERT INTO critical_quantities "
            "(id, standard, table_no, chemical_name, category, symbol, critical_t, critical_note, source_page) "
            f"VALUES ({_q(_uid('critical', key))}, {_q(STANDARD)}, '2', {_q(r['description'])}, "
            f"{_q(r['category'])}, {_q(r['symbol'])}, {_num(r['critical_t'])}, "
            f"{_q(note) if note else 'NULL'}, {r['source_page']}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    for r in t3:
        key = f"t3/{r['name']}"
        lines.append(
            "INSERT INTO hazard_beta_factors "
            "(id, standard, source_table, chemical_name, beta, source_page) "
            f"VALUES ({_q(_uid('beta', key))}, {_q(STANDARD)}, '3', {_q(r['name'])}, "
            f"{_num(r['beta'])}, {r['source_page']}) ON CONFLICT (id) DO NOTHING;"
        )

    for r in t4:
        key = f"t4/{r['symbol']}"
        lines.append(
            "INSERT INTO hazard_beta_factors "
            "(id, standard, source_table, category, symbol, beta, source_page) "
            f"VALUES ({_q(_uid('beta', key))}, {_q(STANDARD)}, '4', {_q(r['category'])}, "
            f"{_q(r['symbol'])}, {_num(r['beta'])}, {r['source_page']}) ON CONFLICT (id) DO NOTHING;"
        )

    alpha_rows = [
        ("100人以上", 100, None, "2.0"),
        ("50~99人", 50, 99, "1.5"),
        ("30~49人", 30, 49, "1.2"),
        ("1~29人", 1, 29, "1.0"),
        ("0人", 0, 0, "0.5"),
    ]
    by_label = {r["exposed_population"]: r for r in t5}
    for label, lo, hi, alpha in alpha_rows:
        row = by_label.get(label, {})
        page = row.get("source_page", 11)
        lines.append(
            "INSERT INTO exposure_alpha_factors "
            "(id, standard, label, population_min, population_max, alpha, source_page) "
            f"VALUES ({_q(_uid('alpha', label))}, {_q(STANDARD)}, {_q(label)}, {lo}, "
            f"{hi if hi is not None else 'NULL'}, {_num(alpha)}, {page}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    level_bounds = {
        "一级": ("100", "NULL"),
        "二级": ("50", "100"),
        "三级": ("10", "50"),
        "四级": ("NULL", "10"),
    }
    for r in t6:
        lo, hi = level_bounds[r["level"]]
        lines.append(
            "INSERT INTO major_hazard_levels "
            "(id, standard, level_name, r_expression, r_min, r_max, source_page) "
            f"VALUES ({_q(_uid('level', r['level']))}, {_q(STANDARD)}, {_q(r['level'])}, "
            f"{_q(r['r_expression'])}, {lo}, {hi}, {r['source_page']}) "
            "ON CONFLICT (id) DO NOTHING;"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    sql = build_sql()
    OUT.write_text(sql, encoding="utf-8", newline="\n")
    print(f"已生成 {OUT.relative_to(ROOT)}（{len(sql.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **步骤 4：运行生成器并检查产物**

运行：

```bash
python scripts/gen_major_hazard_seed_sql.py
```

预期输出：`已生成 backend/db_migration_20260917_standard_constants.sql（约 160 行）`

再运行两次，确认输出**逐字节一致**（幂等性）：

```bash
python scripts/gen_major_hazard_seed_sql.py && sha256sum backend/db_migration_20260917_standard_constants.sql
python scripts/gen_major_hazard_seed_sql.py && sha256sum backend/db_migration_20260917_standard_constants.sql
```

预期：两次 sha256 完全相同

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_constants_sql.py -v
```

预期：`6 passed`

- [ ] **步骤 6：Commit**

```bash
git add scripts/gen_major_hazard_seed_sql.py backend/db_migration_20260917_standard_constants.sql backend/tests/test_major_hazard_constants_sql.py
git commit -m "feat(major-hazard): GB18218 常量表 DDL + 种子 SQL 生成器（幂等可重放）"
```

---

## 任务 3：标准常量 ORM 模型

**文件：**

- 创建：`backend/app/models/standard_constants.py`
- 测试：`backend/tests/test_major_hazard_models.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""常量表 ORM 结构断言。"""

from app.models.standard_constants import (
    CriticalQuantity,
    ExposureAlphaFactor,
    HazardBetaFactor,
    MajorHazardLevel,
)


def test_critical_quantity_table_shape():
    assert CriticalQuantity.__tablename__ == "critical_quantities"
    cols = CriticalQuantity.__table__.columns
    for name in ("id", "standard", "table_no", "chemical_name", "critical_t"):
        assert name in cols, name
    assert cols["standard"].nullable is False
    assert cols["chemical_name"].nullable is False
    assert cols["critical_t"].nullable is True  # 表2 的 J/W 分组行为 NULL


def test_beta_factor_table_shape():
    assert HazardBetaFactor.__tablename__ == "hazard_beta_factors"
    cols = HazardBetaFactor.__table__.columns
    assert cols["beta"].nullable is False


def test_alpha_factor_table_shape():
    assert ExposureAlphaFactor.__tablename__ == "exposure_alpha_factors"
    cols = ExposureAlphaFactor.__table__.columns
    assert cols["label"].nullable is False
    assert cols["population_min"].nullable is False
    assert cols["population_max"].nullable is True  # "100人以上" 无上界


def test_level_table_shape():
    assert MajorHazardLevel.__tablename__ == "major_hazard_levels"
    cols = MajorHazardLevel.__table__.columns
    assert cols["level_name"].nullable is False
    assert cols["r_expression"].nullable is False
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_models.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.models.standard_constants'`

- [ ] **步骤 3：编写最少实现代码**

```python
"""GB 18218-2018 标准常量 ORM。

这四张表存的是**标准原文**（临界量、校正系数、分级阈值），用于展示、审计与证据链；
计算引擎的判级逻辑写在 app/services/major_hazard_calc.py 里（纯函数），
并由 tests/test_major_hazard_calc.py 与 tests/test_major_hazard_models.py 双向对齐，
避免"数据驱动计算"在常量被误改时静默算错。
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CriticalQuantity(Base):
    """GB 18218-2018 表1/表2：危险化学品的临界量 Q（吨）。"""

    __tablename__ = "critical_quantities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    standard: Mapped[str] = mapped_column(String(40), nullable=False)
    table_no: Mapped[str] = mapped_column(String(4), nullable=False)  # '1' | '2'
    chemical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    alias: Mapped[Optional[str]] = mapped_column(String(500))
    cas_no: Mapped[Optional[str]] = mapped_column(String(120))
    category: Mapped[Optional[str]] = mapped_column(String(80))  # 表2 的类别
    symbol: Mapped[Optional[str]] = mapped_column(String(20))  # 表2 的符号（J1/W1.1）
    critical_t: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    critical_note: Mapped[Optional[str]] = mapped_column(String(80))  # 如"150(净重)"
    source_page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HazardBetaFactor(Base):
    """GB 18218-2018 表3/表4：校正系数 β。"""

    __tablename__ = "hazard_beta_factors"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    standard: Mapped[str] = mapped_column(String(40), nullable=False)
    source_table: Mapped[str] = mapped_column(String(4), nullable=False)  # '3' | '4'
    chemical_name: Mapped[Optional[str]] = mapped_column(String(200))  # 表3
    category: Mapped[Optional[str]] = mapped_column(String(80))  # 表4
    symbol: Mapped[Optional[str]] = mapped_column(String(20))  # 表4（J1/W5.2…）
    beta: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    source_page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExposureAlphaFactor(Base):
    """GB 18218-2018 表5：厂外可能暴露人员校正系数 α。"""

    __tablename__ = "exposure_alpha_factors"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    standard: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    population_min: Mapped[int] = mapped_column(Integer, nullable=False)
    population_max: Mapped[Optional[int]] = mapped_column(Integer)
    alpha: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    source_page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MajorHazardLevel(Base):
    """GB 18218-2018 表6：重大危险源级别与 R 值的对应关系。"""

    __tablename__ = "major_hazard_levels"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    standard: Mapped[str] = mapped_column(String(40), nullable=False)
    level_name: Mapped[str] = mapped_column(String(20), nullable=False)  # 一级/二级/三级/四级
    r_expression: Mapped[str] = mapped_column(String(60), nullable=False)  # 原文表达，如 "R≥100"
    r_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    r_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    source_page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_models.py -v
```

预期：`4 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/models/standard_constants.py backend/tests/test_major_hazard_models.py
git commit -m "feat(major-hazard): GB18218 标准常量 ORM（临界量/beta/alpha/分级）"
```

---

## 任务 4：重大危险源业务模型 + 迁移 DDL

**文件：**

- 创建：`backend/app/models/major_hazard.py`
- 创建：`backend/db_migration_20260917_major_hazard.sql`
- 测试：`backend/tests/test_major_hazard_models.py`（追加）

- [ ] **步骤 1：编写失败的测试（追加到既有测试文件末尾）**

```python
import re
from pathlib import Path

from app.models.major_hazard import (
    MajorHazardCalculation,
    MajorHazardRecord,
    MajorHazardUnit,
    MajorHazardUnitChemical,
)


def _migration_sql() -> str:
    return (
        Path(__file__).resolve().parents[1] / "db_migration_20260917_major_hazard.sql"
    ).read_text(encoding="utf-8")


def test_unit_table_shape():
    assert MajorHazardUnit.__tablename__ == "major_hazard_units"
    cols = MajorHazardUnit.__table__.columns
    assert cols["enterprise_id"].nullable is False
    assert cols["name"].nullable is False
    assert cols["unit_type"].nullable is False
    for name in ("floor_id", "polygon", "risk_object_id", "responsible_person"):
        assert name in cols, name


def test_unit_chemical_table_shape():
    assert MajorHazardUnitChemical.__tablename__ == "major_hazard_unit_chemicals"
    cols = MajorHazardUnitChemical.__table__.columns
    assert cols["unit_id"].nullable is False
    assert cols["q_design_max"].nullable is False
    assert cols["critical_quantity_t"].nullable is False
    assert cols["beta"].nullable is False
    assert cols["beta_source"].nullable is False


def test_calculation_snapshot_table_shape():
    assert MajorHazardCalculation.__tablename__ == "major_hazard_calculations"
    cols = MajorHazardCalculation.__table__.columns
    for name in (
        "unit_id",
        "seq",
        "s_value",
        "r_value",
        "alpha",
        "exposed_population",
        "is_major_hazard",
        "level",
        "formula_version",
        "inputs_snapshot",
    ):
        assert name in cols, name
    assert cols["inputs_snapshot"].nullable is False
    assert cols["level"].nullable is True  # 不构成重大危险源时无级别


def test_record_table_shape():
    assert MajorHazardRecord.__tablename__ == "major_hazard_records"
    cols = MajorHazardRecord.__table__.columns
    for name in ("unit_id", "hazard_code", "filing_status"):
        assert name in cols, name
    for prefix in ("chief", "tech", "oper"):
        for suffix in ("name", "post", "phone"):
            assert f"{prefix}_{suffix}" in cols, f"{prefix}_{suffix}"


def test_migration_sql_declares_all_tables():
    sql = _migration_sql()
    for table in (
        "major_hazard_units",
        "major_hazard_unit_chemicals",
        "major_hazard_calculations",
        "major_hazard_records",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{table}\b", sql), table


def test_migration_has_no_update_or_delete_on_snapshots():
    """快照表只允许 INSERT/SELECT——迁移脚本不得出现对它的 UPDATE/DELETE。"""
    upper = _migration_sql().upper()
    assert "UPDATE MAJOR_HAZARD_CALCULATIONS" not in upper
    assert "DELETE FROM MAJOR_HAZARD_CALCULATIONS" not in upper
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_models.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.models.major_hazard'`

- [ ] **步骤 3：编写业务 ORM**

```python
"""重大危险源业务 ORM：单元、单元内品种、计算快照、档案。

设计要点：
- `q_design_max` 是「设计最大量」——GB 18218-2018 4.2.2 规定实际存在量按设计最大量确定，
  因此它是计算的取值来源，不是参考字段。
- `critical_quantity_t` 与 `beta` 存在单元品种上是「当前计算口径」；
  每次计算把它们连同 q 一起复制进 `major_hazard_calculations.inputs_snapshot`，
  这样标准修订后历史结论依然可复算。
- `major_hazard_calculations` 只追加不修改：应用层只提供新增与查询，不提供更新/删除。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MajorHazardUnit(Base):
    """重大危险源单元。GB 18218 3.5/3.6：生产单元、储存单元。"""

    __tablename__ = "major_hazard_units"
    __table_args__ = (Index("idx_mhu_enterprise", "enterprise_id", "is_active"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False)  # production | storage
    boundary_desc: Mapped[Optional[str]] = mapped_column(Text)
    floor_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprise_floors.id", ondelete="SET NULL")
    )
    polygon: Mapped[Optional[dict]] = mapped_column(JSONB)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    department: Mapped[Optional[str]] = mapped_column(String(255))
    responsible_person: Mapped[Optional[str]] = mapped_column(String(100))
    responsible_phone: Mapped[Optional[str]] = mapped_column(String(50))
    risk_object_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    established_at: Mapped[Optional[date]] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chemicals = relationship(
        "MajorHazardUnitChemical", back_populates="unit", cascade="all, delete-orphan", lazy="selectin"
    )
    record = relationship(
        "MajorHazardRecord", back_populates="unit", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


class MajorHazardUnitChemical(Base):
    """单元内的一种危险化学品及其存量（计算输入）。"""

    __tablename__ = "major_hazard_unit_chemicals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("major_hazard_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chemical_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hazardous_chemicals.id", ondelete="SET NULL")
    )
    chemical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    physical_state: Mapped[Optional[str]] = mapped_column(String(200))
    storage_location: Mapped[Optional[str]] = mapped_column(String(300))
    q_design_max: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    q_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    critical_quantity_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("critical_quantities.id", ondelete="SET NULL")
    )
    critical_quantity_t: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    beta: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    beta_source: Mapped[str] = mapped_column(String(10), nullable=False)  # table3 | table4 | manual
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    unit = relationship("MajorHazardUnit", back_populates="chemicals", lazy="selectin")


class MajorHazardCalculation(Base):
    """计算快照。只追加、不修改——保证任何历史结论都能原样复算。"""

    __tablename__ = "major_hazard_calculations"
    __table_args__ = (UniqueConstraint("unit_id", "seq", name="uq_mhc_unit_seq"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("major_hazard_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    s_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    r_value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    alpha: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    exposed_population: Mapped[int] = mapped_column(Integer, nullable=False)
    is_major_hazard: Mapped[bool] = mapped_column(Boolean, nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(20))
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    inputs_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    calculated_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MajorHazardRecord(Base):
    """重大危险源档案与备案：包保责任人、备案信息、附件资料。"""

    __tablename__ = "major_hazard_records"
    __table_args__ = (UniqueConstraint("enterprise_id", "hazard_code", name="uq_mhr_ent_code"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("major_hazard_units.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hazard_code: Mapped[Optional[str]] = mapped_column(String(64))
    filing_status: Mapped[str] = mapped_column(String(20), nullable=False, default="未备案")
    filing_no: Mapped[Optional[str]] = mapped_column(String(100))
    filing_date: Mapped[Optional[date]] = mapped_column(Date)
    chief_name: Mapped[Optional[str]] = mapped_column(String(100))
    chief_post: Mapped[Optional[str]] = mapped_column(String(100))
    chief_phone: Mapped[Optional[str]] = mapped_column(String(50))
    tech_name: Mapped[Optional[str]] = mapped_column(String(100))
    tech_post: Mapped[Optional[str]] = mapped_column(String(100))
    tech_phone: Mapped[Optional[str]] = mapped_column(String(50))
    oper_name: Mapped[Optional[str]] = mapped_column(String(100))
    oper_post: Mapped[Optional[str]] = mapped_column(String(100))
    oper_phone: Mapped[Optional[str]] = mapped_column(String(50))
    attachments: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    completeness: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    unit = relationship("MajorHazardUnit", back_populates="record", lazy="selectin")
```

- [ ] **步骤 4：编写迁移 DDL**

```sql
-- 20260917 重大危险源业务表（单元 / 单元品种 / 计算快照 / 档案）
-- 说明：计算快照表只追加不修改；应用层不提供 UPDATE/DELETE 接口。

CREATE TABLE IF NOT EXISTS major_hazard_units (
    id UUID PRIMARY KEY,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    unit_type VARCHAR(20) NOT NULL,
    boundary_desc TEXT,
    floor_id UUID REFERENCES enterprise_floors(id) ON DELETE SET NULL,
    polygon JSONB,
    address VARCHAR(500),
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    department VARCHAR(255),
    responsible_person VARCHAR(100),
    responsible_phone VARCHAR(50),
    risk_object_id UUID REFERENCES risk_objects(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    established_at DATE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_mhu_enterprise_id ON major_hazard_units (enterprise_id);
CREATE INDEX IF NOT EXISTS idx_mhu_enterprise ON major_hazard_units (enterprise_id, is_active);

CREATE TABLE IF NOT EXISTS major_hazard_unit_chemicals (
    id UUID PRIMARY KEY,
    unit_id UUID NOT NULL REFERENCES major_hazard_units(id) ON DELETE CASCADE,
    chemical_id UUID REFERENCES hazardous_chemicals(id) ON DELETE SET NULL,
    chemical_name VARCHAR(500) NOT NULL,
    physical_state VARCHAR(200),
    storage_location VARCHAR(300),
    q_design_max NUMERIC(18, 6) NOT NULL,
    q_actual NUMERIC(18, 6),
    critical_quantity_id UUID REFERENCES critical_quantities(id) ON DELETE SET NULL,
    critical_quantity_t NUMERIC(18, 6) NOT NULL,
    beta NUMERIC(6, 3) NOT NULL,
    beta_source VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_mhuc_unit_id ON major_hazard_unit_chemicals (unit_id);

CREATE TABLE IF NOT EXISTS major_hazard_calculations (
    id UUID PRIMARY KEY,
    unit_id UUID NOT NULL REFERENCES major_hazard_units(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    s_value NUMERIC(18, 6) NOT NULL,
    r_value NUMERIC(18, 6) NOT NULL,
    alpha NUMERIC(4, 2) NOT NULL,
    exposed_population INTEGER NOT NULL,
    is_major_hazard BOOLEAN NOT NULL,
    level VARCHAR(20),
    formula_version VARCHAR(40) NOT NULL,
    inputs_snapshot JSONB NOT NULL,
    calculated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_mhc_unit_seq UNIQUE (unit_id, seq)
);
CREATE INDEX IF NOT EXISTS ix_mhc_unit_id ON major_hazard_calculations (unit_id);

CREATE TABLE IF NOT EXISTS major_hazard_records (
    id UUID PRIMARY KEY,
    unit_id UUID NOT NULL UNIQUE REFERENCES major_hazard_units(id) ON DELETE CASCADE,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    hazard_code VARCHAR(64),
    filing_status VARCHAR(20) NOT NULL DEFAULT '未备案',
    filing_no VARCHAR(100),
    filing_date DATE,
    chief_name VARCHAR(100),
    chief_post VARCHAR(100),
    chief_phone VARCHAR(50),
    tech_name VARCHAR(100),
    tech_post VARCHAR(100),
    tech_phone VARCHAR(50),
    oper_name VARCHAR(100),
    oper_post VARCHAR(100),
    oper_phone VARCHAR(50),
    attachments JSONB NOT NULL DEFAULT '{}'::jsonb,
    completeness JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_mhr_ent_code UNIQUE (enterprise_id, hazard_code)
);
CREATE INDEX IF NOT EXISTS ix_mhr_enterprise_id ON major_hazard_records (enterprise_id);
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_models.py -v
```

预期：`10 passed`

- [ ] **步骤 6：验证迁移可重复执行**

先用 `docker ps` 查出本机 PostgreSQL 容器名（下文以 `<db>` 代替），然后：

```bash
docker exec -i <db> psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend/db_migration_20260917_standard_constants.sql
docker exec -i <db> psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend/db_migration_20260917_major_hazard.sql
docker exec -i <db> psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend/db_migration_20260917_major_hazard.sql
docker exec <db> psql -U postgres -d emergency_plan -c "SELECT (SELECT count(*) FROM critical_quantities) AS cq, (SELECT count(*) FROM hazard_beta_factors) AS beta;"
```

预期：第二次执行同样无报错（幂等），查询返回 `cq | beta` = `109 | 38`

- [ ] **步骤 7：Commit**

```bash
git add backend/app/models/major_hazard.py backend/db_migration_20260917_major_hazard.sql backend/tests/test_major_hazard_models.py
git commit -m "feat(major-hazard): 单元/品种/计算快照/档案数据模型与迁移"
```

---

## 任务 5：计算编排服务（读常量 → 调引擎 → 写不可变快照）

**文件：**

- 创建：`backend/app/services/major_hazard_service.py`
- 测试：`backend/tests/test_major_hazard_service.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""计算编排服务测试：β 规则选取、快照递增、可复算。"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.major_hazard_service import (
    MajorHazardRuleError,
    compute_unit_snapshot,
    replay_snapshot,
    resolve_beta,
)


def _beta_row(name=None, symbol=None, beta="4.0", table="3"):
    r = MagicMock()
    r.chemical_name = name
    r.symbol = symbol
    r.beta = Decimal(beta)
    r.source_table = table
    return r


def test_resolve_beta_prefers_table3_by_name():
    """GB 18218 4.3.2：表3（毒性气体按名称）优先于表4（按危险性类别）。"""
    rows = [_beta_row(name="氯", beta="4.0", table="3")]
    beta, source = resolve_beta(rows, chemical_name="氯", hazard_symbol="W1.1")
    assert beta == Decimal("4.0")
    assert source == "table3"


def test_resolve_beta_falls_back_to_table4_by_symbol():
    rows = [
        _beta_row(name="氯", beta="4.0", table="3"),
        _beta_row(symbol="W5.1", beta="1.5", table="4"),
    ]
    beta, source = resolve_beta(rows, chemical_name="甲醇", hazard_symbol="W5.1")
    assert beta == Decimal("1.5")
    assert source == "table4"


def test_resolve_beta_raises_when_not_found():
    """两边都查不到必须显式报错，不能默认成 1.0 静默算错。"""
    with pytest.raises(MajorHazardRuleError):
        resolve_beta([], chemical_name="未知物质", hazard_symbol="W99")


def test_replay_snapshot_reproduces_result():
    """审计要求：用快照里的输入重算，结果必须与原结论一致。"""
    snapshot = {
        "exposed_population": 60,
        "chemicals": [
            {"name": "氯", "q": 5.0, "Q": 5.0, "beta": 4.0},
            {"name": "氨", "q": 5.0, "Q": 10.0, "beta": 2.0},
        ],
    }
    out = replay_snapshot(snapshot)
    # α=1.5；(4×1.0 + 2×0.5)=5.0；R=7.5 -> 四级
    assert out["s_value"] == 1.5
    assert out["r_value"] == 7.5
    assert out["level"] == "四级"


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._items[0] if self._items else None


def _unit():
    u = MagicMock()
    u.id = "u1"
    u.enterprise_id = "e1"
    return u


def _chem():
    c = MagicMock()
    c.chemical_name = "氯"
    c.q_design_max = Decimal("5.0")
    c.critical_quantity_t = Decimal("5.0")
    c.beta = Decimal("4.0")
    c.beta_source = "table3"
    return c


def _db(added, unit=None, chemicals=None):
    db = MagicMock()
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit] if unit is not None else [])
        if "major_hazard_unit_chemicals" in text:
            return _Result(chemicals if chemicals is not None else [])
        if "major_hazard_calculations" in text:
            return _Result([])  # 尚无快照 -> seq 从 1 开始
        return _Result([])

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_compute_unit_snapshot_persists_snapshot():
    added = []
    db = _db(added, unit=_unit(), chemicals=[_chem()])
    snap = await compute_unit_snapshot(db, unit_id="u1", exposed_population=0, user_id="user1")

    assert snap["seq"] == 1
    assert snap["is_major_hazard"] is True
    assert snap["level"] == "四级"
    assert snap["formula_version"] == "GB18218-2018"
    assert added, "必须写入一条快照记录"
    assert added[0].unit_id == "u1"
    assert added[0].inputs_snapshot["chemicals"][0]["name"] == "氯"


@pytest.mark.asyncio
async def test_compute_unit_snapshot_rejects_empty_unit():
    added = []
    db = _db(added, unit=_unit(), chemicals=[])
    with pytest.raises(MajorHazardRuleError):
        await compute_unit_snapshot(db, unit_id="u1", exposed_population=0)


@pytest.mark.asyncio
async def test_compute_unit_snapshot_rejects_missing_unit():
    added = []
    db = _db(added, unit=None, chemicals=[_chem()])
    with pytest.raises(MajorHazardRuleError):
        await compute_unit_snapshot(db, unit_id="nope", exposed_population=0)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_service.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.major_hazard_service'`

- [ ] **步骤 3：编写实现代码**

```python
"""重大危险源计算编排：读常量 → 调纯函数引擎 → 写不可变快照。

与 app/services/major_hazard_calc.py 的分工：
- calc 模块只做数学，不认识数据库；
- 本模块负责把 DB 里的临界量 Q 与校正系数 β 取出来喂给引擎，并落快照。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.major_hazard import (
    MajorHazardCalculation,
    MajorHazardUnit,
    MajorHazardUnitChemical,
)
from app.models.standard_constants import HazardBetaFactor
from app.services.major_hazard_calc import (
    FORMULA_VERSION,
    CalcInputError,
    ChemicalInput,
    compute,
)

STANDARD = "GB18218-2018"


class MajorHazardRuleError(ValueError):
    """标准规则无法套用（如 β 查不到）或数据不完整，必须显式失败而不是取默认值。"""


def resolve_beta(
    rows: Sequence[HazardBetaFactor],
    *,
    chemical_name: str,
    hazard_symbol: str | None,
) -> tuple[Decimal, str]:
    """按 GB 18218 4.3.2 选取校正系数 β：先查表3（按名称），再查表4（按类别符号）。"""
    for r in rows:
        if r.source_table == "3" and r.chemical_name == chemical_name:
            return Decimal(r.beta), "table3"
    if hazard_symbol:
        for r in rows:
            if r.source_table == "4" and r.symbol == hazard_symbol:
                return Decimal(r.beta), "table4"
    raise MajorHazardRuleError(
        f"危险化学品「{chemical_name}」在表3/表4 中均查不到校正系数 β，请先补齐危险性类别"
    )


async def _next_seq(db: AsyncSession, unit_id: str) -> int:
    res = await db.execute(
        select(func.max(MajorHazardCalculation.seq)).where(MajorHazardCalculation.unit_id == unit_id)
    )
    current = res.scalar()
    return int(current or 0) + 1


async def compute_unit_snapshot(
    db: AsyncSession,
    *,
    unit_id: str,
    exposed_population: int,
    user_id: str | None = None,
) -> dict:
    """对指定单元执行一次计算并写入不可变快照，返回快照内容。"""
    unit_res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = unit_res.scalar_one_or_none()
    if unit is None:
        raise MajorHazardRuleError("重大危险源单元不存在")

    chem_res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    chemicals = list(chem_res.scalars().all())
    if not chemicals:
        raise MajorHazardRuleError("该单元尚未录入危险化学品，无法计算")

    try:
        result = compute(
            [
                ChemicalInput(
                    name=c.chemical_name,
                    q_design_max=float(c.q_design_max),
                    critical_quantity=float(c.critical_quantity_t),
                    beta=float(c.beta),
                )
                for c in chemicals
            ],
            exposed_population=exposed_population,
        )
    except CalcInputError as exc:
        raise MajorHazardRuleError(str(exc)) from exc

    seq = await _next_seq(db, unit_id)
    snapshot = {
        "seq": seq,
        "s_value": round(result.s_value, 6),
        "r_value": round(result.r_value, 6),
        "alpha": result.alpha,
        "exposed_population": exposed_population,
        "is_major_hazard": result.is_major_hazard,
        "level": result.level,
        "formula_version": FORMULA_VERSION,
        "standard": STANDARD,
        "chemicals": list(result.items),
    }
    db.add(
        MajorHazardCalculation(
            unit_id=unit_id,
            seq=seq,
            s_value=Decimal(str(snapshot["s_value"])),
            r_value=Decimal(str(snapshot["r_value"])),
            alpha=Decimal(str(result.alpha)),
            exposed_population=exposed_population,
            is_major_hazard=result.is_major_hazard,
            level=result.level,
            formula_version=FORMULA_VERSION,
            inputs_snapshot=snapshot,
            calculated_by=user_id,
        )
    )
    await db.commit()
    return snapshot


def replay_snapshot(snapshot: dict) -> dict:
    """用快照里保存的输入重算一遍（审计核对用）。结果应与快照一致。"""
    result = compute(
        [
            ChemicalInput(
                name=item["name"],
                q_design_max=float(item["q"]),
                critical_quantity=float(item["Q"]),
                beta=float(item["beta"]),
            )
            for item in snapshot.get("chemicals", [])
        ],
        exposed_population=int(snapshot["exposed_population"]),
    )
    return {
        "s_value": round(result.s_value, 6),
        "r_value": round(result.r_value, 6),
        "is_major_hazard": result.is_major_hazard,
        "level": result.level,
    }
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_service.py -v
```

预期：`7 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/major_hazard_service.py backend/tests/test_major_hazard_service.py
git commit -m "feat(major-hazard): 计算编排服务与不可变快照（含 β 规则与复算）"
```

---

## 任务 6：Pydantic Schemas + API 路由

**文件：**

- 创建：`backend/app/schemas/major_hazard.py`
- 创建：`backend/app/routers/major_hazard.py`
- 修改：`backend/app/main.py`（在 `app.include_router(data_dicts.router, prefix="/api/v1")` 之后追加一行）
- 测试：`backend/tests/test_major_hazard_api.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""重大危险源 API 测试（TestClient + 依赖覆盖，沿用 test_risk_conversion_api.py 范式）。"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import major_hazard


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._items[0] if self._items else None


def _client(handler):
    app = FastAPI()
    app.include_router(major_hazard.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        db.delete = AsyncMock()
        yield db

    async def _user():
        u = MagicMock()
        u.id = "user1"
        u.is_admin = True
        return u

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_list_units_returns_items():
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    unit.name = "罐区 A"
    unit.unit_type = "storage"
    unit.is_active = True
    unit.address = None
    unit.department = None
    unit.responsible_person = None
    unit.responsible_phone = None
    unit.risk_object_id = None
    unit.created_at = None

    async def handler(stmt, *a, **k):
        return _Result([unit])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/units", params={"enterprise_id": "e1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"][0]["name"] == "罐区 A"


def test_critical_quantity_lookup_filters_by_keyword():
    row = MagicMock()
    row.chemical_name = "氯"
    row.alias = "液氯；氯气"
    row.cas_no = "7782-50-5"
    row.critical_t = 5
    row.critical_note = None
    row.table_no = "1"
    row.source_page = 5

    async def handler(stmt, *a, **k):
        return _Result([row])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/definitions/critical-quantities", params={"keyword": "氯"})
    assert resp.status_code == 200
    item = resp.json()["data"][0]
    assert item["chemical_name"] == "氯"
    assert item["critical_t"] == 5


def test_compute_returns_rule_error_as_422():
    """单元不存在时返回 422 与可读原因，不返回 500。"""

    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post("/api/v1/major-hazard/units/u-missing/compute", json={"exposed_population": 0})
    assert resp.status_code == 422
    assert "单元" in resp.json()["detail"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_api.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.routers.major_hazard'`

- [ ] **步骤 3：编写 Schemas**

```python
"""重大危险源 API 出入参。"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class UnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    unit_type: str = Field(pattern="^(production|storage)$")
    boundary_desc: Optional[str] = None
    floor_id: Optional[str] = None
    polygon: Optional[dict] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    department: Optional[str] = None
    responsible_person: Optional[str] = None
    responsible_phone: Optional[str] = None
    risk_object_id: Optional[str] = None
    is_active: bool = True


class UnitOut(BaseModel):
    id: str
    enterprise_id: str
    name: str
    unit_type: str
    address: Optional[str] = None
    department: Optional[str] = None
    responsible_person: Optional[str] = None
    responsible_phone: Optional[str] = None
    risk_object_id: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UnitChemicalIn(BaseModel):
    chemical_name: str = Field(min_length=1, max_length=500)
    chemical_id: Optional[str] = None
    physical_state: Optional[str] = None
    storage_location: Optional[str] = None
    q_design_max: Decimal = Field(ge=0)
    q_actual: Optional[Decimal] = Field(default=None, ge=0)
    critical_quantity_t: Decimal = Field(gt=0)
    beta: Decimal = Field(gt=0)
    beta_source: str = Field(default="manual", pattern="^(table3|table4|manual)$")


class UnitChemicalOut(UnitChemicalIn):
    id: str
    unit_id: str

    model_config = {"from_attributes": True}


class ComputeIn(BaseModel):
    exposed_population: int = Field(ge=0)


class CalculationOut(BaseModel):
    id: str
    seq: int
    s_value: Decimal
    r_value: Decimal
    alpha: Decimal
    exposed_population: int
    is_major_hazard: bool
    level: Optional[str] = None
    formula_version: str
    calculated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CriticalQuantityOut(BaseModel):
    chemical_name: str
    alias: Optional[str] = None
    cas_no: Optional[str] = None
    critical_t: Optional[Decimal] = None
    critical_note: Optional[str] = None
    table_no: str
    source_page: Optional[int] = None

    model_config = {"from_attributes": True}
```

**同时**在 `backend/app/schemas/major_hazard.py` 追加依据层的请求模型（不要直接用服务层的 dataclass 当请求体）：

```python
class EvidenceIn(BaseModel):
    """挂载法规依据的请求项。"""

    article_anchor: str = Field(min_length=1, max_length=200)
    regulation_id: Optional[str] = Field(default=None, max_length=64)
    relation: str = Field(default="依据", max_length=20)
    note: Optional[str] = None
```

- [ ] **步骤 4：编写路由**

```python
"""重大危险源 API：单元、单元品种、计算、快照、常量查询。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.major_hazard import (
    MajorHazardCalculation,
    MajorHazardUnit,
    MajorHazardUnitChemical,
)
from app.models.standard_constants import CriticalQuantity
from app.schemas.major_hazard import (
    CalculationOut,
    ComputeIn,
    CriticalQuantityOut,
    UnitChemicalIn,
    UnitChemicalOut,
    UnitIn,
    UnitOut,
)
from app.services.major_hazard_service import MajorHazardRuleError, compute_unit_snapshot

router = APIRouter(prefix="/major-hazard", tags=["MajorHazard"])

STANDARD = "GB18218-2018"


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.get("/definitions/critical-quantities")
async def list_critical_quantities(
    keyword: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """按名称/别名/CAS 检索 GB 18218 表1/表2 的临界量，供前端选物质。"""
    stmt = select(CriticalQuantity).where(CriticalQuantity.standard == STANDARD)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                CriticalQuantity.chemical_name.ilike(like),
                CriticalQuantity.alias.ilike(like),
                CriticalQuantity.cas_no.ilike(like),
            )
        )
    stmt = stmt.order_by(CriticalQuantity.table_no, CriticalQuantity.chemical_name).limit(limit)
    res = await db.execute(stmt)
    rows = res.scalars().all()
    return _ok([CriticalQuantityOut.model_validate(r) for r in rows])


@router.get("/units")
async def list_units(
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(MajorHazardUnit)
        .where(MajorHazardUnit.enterprise_id == enterprise_id)
        .order_by(MajorHazardUnit.sort_order, MajorHazardUnit.created_at)
    )
    return _ok([UnitOut.model_validate(u) for u in res.scalars().all()])


@router.post("/units")
async def create_unit(
    enterprise_id: str = Query(...),
    payload: UnitIn,
    db: AsyncSession = Depends(get_db),
):
    unit = MajorHazardUnit(enterprise_id=enterprise_id, **payload.model_dump())
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return _ok(UnitOut.model_validate(unit))


@router.put("/units/{unit_id}")
async def update_unit(
    unit_id: str,
    payload: UnitIn,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise HTTPException(404, "重大危险源单元不存在")
    for key, value in payload.model_dump().items():
        setattr(unit, key, value)
    await db.commit()
    return _ok(UnitOut.model_validate(unit))


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    unit = res.scalar_one_or_none()
    if unit is None:
        raise HTTPException(404, "重大危险源单元不存在")
    await db.delete(unit)
    await db.commit()
    return _ok({"id": unit_id})


@router.get("/units/{unit_id}/chemicals")
async def list_unit_chemicals(unit_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    return _ok([UnitChemicalOut.model_validate(c) for c in res.scalars().all()])


@router.put("/units/{unit_id}/chemicals")
async def replace_unit_chemicals(
    unit_id: str,
    payload: list[UnitChemicalIn],
    db: AsyncSession = Depends(get_db),
):
    """整体替换单元内品种清单（前端一次提交整个表格）。"""
    res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    if res.scalar_one_or_none() is None:
        raise HTTPException(404, "重大危险源单元不存在")
    existing = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    for row in existing.scalars().all():
        await db.delete(row)
    for item in payload:
        db.add(MajorHazardUnitChemical(unit_id=unit_id, **item.model_dump()))
    await db.commit()
    return _ok({"unit_id": unit_id, "count": len(payload)})


@router.post("/units/{unit_id}/compute")
async def compute_unit(
    unit_id: str,
    payload: ComputeIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """执行一次 R 值法计算并写入不可变快照。"""
    try:
        snapshot = await compute_unit_snapshot(
            db,
            unit_id=unit_id,
            exposed_population=payload.exposed_population,
            user_id=getattr(user, "id", None),
        )
    except MajorHazardRuleError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(snapshot)


@router.get("/units/{unit_id}/calculations")
async def list_calculations(unit_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(MajorHazardCalculation)
        .where(MajorHazardCalculation.unit_id == unit_id)
        .order_by(MajorHazardCalculation.seq.desc())
    )
    return _ok([CalculationOut.model_validate(c) for c in res.scalars().all()])
```

- [ ] **步骤 5：注册路由**

修改 `backend/app/main.py`：

1. 在第 253 行的 `from app.routers import ...` 长导入列表里加入 `major_hazard`（放在 `data_dicts, third_party_config` 之后即可，保持一行追加）。
2. 在第 293 行 `app.include_router(third_party_config.router, prefix="/api/v1")` 之后追加：

```python
app.include_router(major_hazard.router, prefix="/api/v1")
```

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_api.py -v
```

预期：`3 passed`

- [ ] **步骤 7：跑全量后端回归**

运行：

```bash
cd backend && python -m pytest tests/ -q
```

预期：全绿，且数量 ≥ 既有基线（不新增失败）

- [ ] **步骤 8：Commit**

```bash
git add backend/app/schemas/major_hazard.py backend/app/routers/major_hazard.py backend/app/main.py backend/tests/test_major_hazard_api.py
git commit -m "feat(major-hazard): schemas 与 REST API（单元/品种/计算/快照/常量检索）"
```

---

## 任务 7：依据层 `evidence_refs`（模型 + 迁移 + 服务 + 接入重大危险源）

**文件：**

- 创建：`backend/app/models/evidence.py`
- 创建：`backend/app/services/evidence_service.py`
- 测试：`backend/tests/test_evidence_service.py`
- 修改：`backend/db_migration_20260917_major_hazard.sql`（追加 `evidence_refs` 建表语句）
- 修改：`backend/app/routers/major_hazard.py`（追加依据读写两个端点）

- [ ] **步骤 1：编写失败的测试**

```python
"""依据层服务测试：挂条文、查条文、去重。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.evidence_service import (
    EvidenceInput,
    attach_evidence,
    list_evidence,
)


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


def _db(existing=None):
    added = []
    db = MagicMock()
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        return _Result(existing or [])

    db.execute = execute
    db._added = added
    return db


@pytest.mark.asyncio
async def test_attach_evidence_creates_rows():
    db = _db()
    await attach_evidence(
        db,
        owner_type="major_hazard_unit",
        owner_id="u1",
        items=[EvidenceInput(regulation_id="gb18218", article_anchor="GB 18218-2018 4.2.1", note="辨识指标")],
        user_id="user1",
    )
    assert len(db._added) == 1
    row = db._added[0]
    assert row.owner_type == "major_hazard_unit"
    assert row.owner_id == "u1"
    assert row.article_anchor == "GB 18218-2018 4.2.1"
    assert row.relation == "依据"


@pytest.mark.asyncio
async def test_attach_evidence_is_idempotent():
    """同一 owner + 同一条文锚点重复挂载时不产生重复行。"""
    existing = MagicMock()
    existing.id = "ex1"
    existing.owner_type = "major_hazard_unit"
    existing.owner_id = "u1"
    existing.article_anchor = "GB 18218-2018 4.2.1"
    existing.relation = "依据"
    db = _db(existing=[existing])
    await attach_evidence(
        db,
        owner_type="major_hazard_unit",
        owner_id="u1",
        items=[EvidenceInput(regulation_id="gb18218", article_anchor="GB 18218-2018 4.2.1")],
    )
    assert db._added == [], "重复挂载不应新增行"


@pytest.mark.asyncio
async def test_attach_evidence_rejects_empty_owner():
    db = _db()
    with pytest.raises(ValueError):
        await attach_evidence(db, owner_type="", owner_id="u1", items=[])


@pytest.mark.asyncio
async def test_list_evidence_returns_rows():
    row = MagicMock()
    row.article_anchor = "GB 18218-2018 4.3.2"
    row.regulation_id = "gb18218"
    row.relation = "依据"
    row.note = "分级指标"
    db = _db(existing=[row])
    out = await list_evidence(db, owner_type="major_hazard_unit", owner_id="u1")
    assert out[0]["article_anchor"] == "GB 18218-2018 4.3.2"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_evidence_service.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.evidence_service'`

- [ ] **步骤 3：编写 ORM**

```python
"""依据层：把任何一条业务数据挂到具体法规条文上。

多态设计（owner_type + owner_id）避免给每个业务表加外键，
条文原文不冗余存储——实时按 article_anchor 从法规体系取，
避免法规修订后引用内容过期。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvidenceRef(Base):
    __tablename__ = "evidence_refs"
    __table_args__ = (
        UniqueConstraint(
            "owner_type", "owner_id", "article_anchor", "relation", name="uq_evidence_owner_anchor"
        ),
        Index("idx_evidence_owner", "owner_type", "owner_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    owner_type: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    regulation_id: Mapped[Optional[str]] = mapped_column(String(64))
    article_anchor: Mapped[str] = mapped_column(String(200), nullable=False)
    relation: Mapped[str] = mapped_column(String(20), nullable=False, default="依据")
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

追加到 `backend/db_migration_20260917_major_hazard.sql` 末尾：

```sql
-- 依据层：任意业务数据挂到法规条文（多态引用，不给每个业务表加外键）
CREATE TABLE IF NOT EXISTS evidence_refs (
    id UUID PRIMARY KEY,
    owner_type VARCHAR(40) NOT NULL,
    owner_id UUID NOT NULL,
    regulation_id VARCHAR(64),
    article_anchor VARCHAR(200) NOT NULL,
    relation VARCHAR(20) NOT NULL DEFAULT '依据',
    note TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_evidence_owner_anchor UNIQUE (owner_type, owner_id, article_anchor, relation)
);
CREATE INDEX IF NOT EXISTS idx_evidence_owner ON evidence_refs (owner_type, owner_id);
```

- [ ] **步骤 4：编写服务**

```python
"""依据层读写服务。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import EvidenceRef


@dataclass(frozen=True)
class EvidenceInput:
    article_anchor: str
    regulation_id: str | None = None
    relation: str = "依据"
    note: str | None = None


async def _existing_anchors(db: AsyncSession, owner_type: str, owner_id: str) -> set[str]:
    res = await db.execute(
        select(EvidenceRef).where(
            EvidenceRef.owner_type == owner_type, EvidenceRef.owner_id == owner_id
        )
    )
    return {f"{r.article_anchor}|{r.relation}" for r in res.scalars().all()}


async def attach_evidence(
    db: AsyncSession,
    *,
    owner_type: str,
    owner_id: str,
    items: list[EvidenceInput],
    user_id: str | None = None,
) -> int:
    """挂载依据；同一 owner + 同一条文 + 同一关系已存在时跳过（幂等）。返回新增条数。"""
    if not owner_type or not owner_id:
        raise ValueError("owner_type 与 owner_id 不能为空")
    seen = await _existing_anchors(db, owner_type, owner_id)
    created = 0
    for item in items:
        key = f"{item.article_anchor}|{item.relation}"
        if key in seen:
            continue
        db.add(
            EvidenceRef(
                owner_type=owner_type,
                owner_id=owner_id,
                regulation_id=item.regulation_id,
                article_anchor=item.article_anchor,
                relation=item.relation,
                note=item.note,
                created_by=user_id,
            )
        )
        seen.add(key)
        created += 1
    if created:
        await db.commit()
    return created


async def list_evidence(db: AsyncSession, *, owner_type: str, owner_id: str) -> list[dict]:
    res = await db.execute(
        select(EvidenceRef)
        .where(EvidenceRef.owner_type == owner_type, EvidenceRef.owner_id == owner_id)
        .order_by(EvidenceRef.created_at)
    )
    return [
        {
            "id": r.id,
            "regulation_id": r.regulation_id,
            "article_anchor": r.article_anchor,
            "relation": r.relation,
            "note": r.note,
        }
        for r in res.scalars().all()
    ]
```

- [ ] **步骤 5：在 `major_hazard` 路由末尾追加两个端点**

```python
@router.get("/units/{unit_id}/evidence")
async def list_unit_evidence(unit_id: str, db: AsyncSession = Depends(get_db)):
    """查看该重大危险源单元挂载的法规依据。"""
    data = await list_evidence(db, owner_type="major_hazard_unit", owner_id=unit_id)
    return _ok(data)


@router.post("/units/{unit_id}/evidence")
async def attach_unit_evidence(
    unit_id: str,
    payload: list[EvidenceIn],
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    created = await attach_evidence(
        db,
        owner_type="major_hazard_unit",
        owner_id=unit_id,
        items=[EvidenceInput(**item.model_dump()) for item in payload],
        user_id=getattr(user, "id", None),
    )
    return _ok({"created": created})
```

同时在 `backend/app/routers/major_hazard.py` 顶部的 import 区追加：

```python
from app.schemas.major_hazard import EvidenceIn
from app.services.evidence_service import EvidenceInput, attach_evidence, list_evidence
```

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_evidence_service.py tests/test_major_hazard_api.py -v
```

预期：`7 passed`

- [ ] **步骤 7：Commit**

```bash
git add backend/app/models/evidence.py backend/app/services/evidence_service.py backend/db_migration_20260917_major_hazard.sql backend/app/routers/major_hazard.py backend/tests/test_evidence_service.py
git commit -m "feat(evidence): 依据层 evidence_refs（多态挂法条）+ 重大危险源接入"
```

---

## 任务 8：危化品存量字段结构化（保留旧字段）

**文件：**

- 修改：`backend/app/models/hazardous_chemicals.py`（新增两列，**不删** `max_storage`）
- 创建：`backend/db_migration_20260917_chemical_storage_numeric.sql`
- 测试：`backend/tests/test_hazardous_chemicals_storage.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""危化品存量结构化字段测试：新字段存在、旧字段保留、解析函数行为。"""

from app.models.hazardous_chemicals import HazardousChemical
from app.services.chemical_storage_parser import parse_storage_text


def test_new_columns_exist_and_old_is_kept():
    cols = HazardousChemical.__table__.columns
    assert "storage_amount" in cols
    assert "storage_unit" in cols
    assert "max_storage" in cols, "旧字段必须保留，避免破坏既有数据与接口"


def test_parse_common_text_forms():
    assert parse_storage_text("50t") == (50.0, "t")
    assert parse_storage_text("50 吨") == (50.0, "t")
    assert parse_storage_text("最大储存量 12.5吨") == (12.5, "t")
    assert parse_storage_text("3000kg") == (3.0, "t")
    assert parse_storage_text("2.5m³") == (2.5, "m³")


def test_parse_unknown_returns_none_instead_of_guessing():
    """解析不出来就返回 None，交人工确认——绝不猜测数值。"""
    assert parse_storage_text("见台账") == (None, None)
    assert parse_storage_text("") == (None, None)
    assert parse_storage_text(None) == (None, None)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_hazardous_chemicals_storage.py -v
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.chemical_storage_parser'`

- [ ] **步骤 3：编写解析器**

```python
"""危化品存量文本解析：把"最大储存量 12.5吨"这类自然语言转成数值+单位。

只做能确定的解析：识别不出来一律返回 (None, None)，由人工确认——
存量数值会直接进入 R 值法计算，猜错比留空危险得多。
"""

from __future__ import annotations

import re

_UNIT_ALIASES = {
    "t": "t",
    "吨": "t",
    "kg": "t",  # 千克统一折算成吨
    "千克": "t",
    "公斤": "t",
    "m3": "m³",
    "m³": "m³",
    "立方米": "m³",
    "l": "L",
    "升": "L",
}

_PATTERN = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>t|吨|kg|千克|公斤|m³|m3|立方米|L|升)",
    re.IGNORECASE,
)


def parse_storage_text(text: str | None) -> tuple[float | None, str | None]:
    """返回 (吨或原始单位数值, 归一化单位)；无法解析时返回 (None, None)。"""
    if not text:
        return None, None
    match = _PATTERN.search(str(text))
    if not match:
        return None, None
    value = float(match.group("num"))
    unit = _UNIT_ALIASES.get(match.group("unit").lower())
    if unit is None:
        return None, None
    if unit == "t" and match.group("unit").lower() in ("kg", "千克", "公斤"):
        value = value / 1000.0
    return value, unit
```

- [ ] **步骤 4：新增模型列**

在 `backend/app/models/hazardous_chemicals.py` 的 `max_storage` 行之后追加：

```python
    # 结构化存量（R 值法计算输入）；max_storage 保留为原始文本，兼容既有数据与接口
    storage_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 6))
    storage_unit: Mapped[Optional[str]] = mapped_column(String(20))
```

并在该文件顶部的 `from sqlalchemy import ...` 中加入 `Numeric`，`from decimal import Decimal`（若用 Decimal 类型标注则一并调整 import）。

- [ ] **步骤 5：编写迁移（含尽力而为的回填）**

```sql
-- 20260917 危化品存量结构化：新增数值列并尽力回填，无法解析的留 NULL 人工确认。
-- 旧字段 max_storage 保留不动。

ALTER TABLE hazardous_chemicals
    ADD COLUMN IF NOT EXISTS storage_amount NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS storage_unit VARCHAR(20);

-- 回填：仅处理"数字 + 单位"能明确识别的文本；其余留空等待人工确认。
DO $$
DECLARE
    rec RECORD;
    m TEXT[];
    val NUMERIC;
    un TEXT;
BEGIN
    FOR rec IN
        SELECT id, max_storage FROM hazardous_chemicals
         WHERE max_storage IS NOT NULL
           AND storage_amount IS NULL
    LOOP
        m := regexp_match(rec.max_storage, '([0-9]+(?:\.[0-9]+)?)\s*(吨|t|千克|公斤|kg)', 'i');
        IF m IS NOT NULL THEN
            val := m[1]::NUMERIC;
            un := lower(m[2]);
            IF un IN ('千克', '公斤', 'kg') THEN
                val := val / 1000;
            END IF;
            UPDATE hazardous_chemicals
               SET storage_amount = val, storage_unit = 't'
             WHERE id = rec.id;
        END IF;
    END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS ix_hc_storage_amount ON hazardous_chemicals (storage_amount);
```

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_hazardous_chemicals_storage.py -v
```

预期：`3 passed`

- [ ] **步骤 7：验证迁移与回填**

```bash
docker exec -i <db> psql -U postgres -d emergency_plan -v ON_ERROR_STOP=1 < backend/db_migration_20260917_chemical_storage_numeric.sql
docker exec <db> psql -U postgres -d emergency_plan -c "SELECT count(*) FILTER (WHERE storage_amount IS NOT NULL) AS filled, count(*) FILTER (WHERE max_storage IS NOT NULL AND storage_amount IS NULL) AS need_review FROM hazardous_chemicals;"
```

预期：`filled` 为可解析的条数，`need_review` 为其余条数（两者之和等于有 `max_storage` 的总数）

- [ ] **步骤 8：Commit**

```bash
git add backend/app/models/hazardous_chemicals.py backend/app/services/chemical_storage_parser.py backend/db_migration_20260917_chemical_storage_numeric.sql backend/tests/test_hazardous_chemicals_storage.py
git commit -m "feat(chemicals): 危化品存量结构化字段与解析器（保留 max_storage 旧字段）"
```

---

## 任务 9：档案与备案 API（补齐 P0-4）

**文件：**

- 修改：`backend/app/schemas/major_hazard.py`（追加档案模型）
- 修改：`backend/app/routers/major_hazard.py`（追加档案端点）
- 修改：`backend/tests/test_major_hazard_api.py`（追加两例）

- [ ] **步骤 1：编写失败的测试（追加到 `backend/tests/test_major_hazard_api.py` 末尾）**

```python
def _record():
    r = MagicMock()
    r.id = "rec1"
    r.unit_id = "u1"
    r.enterprise_id = "e1"
    r.hazard_code = "TYKJ001"
    r.filing_status = "已备案"
    r.filing_no = None
    r.filing_date = None
    r.chief_name = "张峰"
    r.chief_post = None
    r.chief_phone = None
    r.tech_name = None
    r.tech_post = None
    r.tech_phone = None
    r.oper_name = None
    r.oper_post = None
    r.oper_phone = None
    r.attachments = {}
    r.completeness = {}
    return r


def test_get_record_returns_existing():
    async def handler(stmt, *a, **k):
        return _Result([_record()])

    client = _client(handler)
    resp = client.get("/api/v1/major-hazard/units/u1/record")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["hazard_code"] == "TYKJ001"
    assert data["chief_name"] == "张峰"


def test_put_record_creates_when_missing():
    created = []

    async def handler(stmt, *a, **k):
        return _Result([])

    app = FastAPI()
    app.include_router(major_hazard.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = lambda obj: created.append(obj)
        yield db

    async def _user():
        u = MagicMock()
        u.id = "user1"
        return u

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app)

    resp = client.put(
        "/api/v1/major-hazard/units/u1/record",
        params={"enterprise_id": "e1"},
        json={"hazard_code": "TYKJ030", "filing_status": "未备案"},
    )
    assert resp.status_code == 200
    assert created and created[0].unit_id == "u1"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_api.py -v
```

预期：新增两例 FAIL（404 Not Found，因为端点还不存在）

- [ ] **步骤 3：追加档案 Schemas**

在 `backend/app/schemas/major_hazard.py` 末尾追加：

```python
class RecordIn(BaseModel):
    """档案与备案入参。未提供的字段保持原值。"""

    hazard_code: Optional[str] = Field(default=None, max_length=64)
    filing_status: Optional[str] = Field(default=None, max_length=20)
    filing_no: Optional[str] = Field(default=None, max_length=100)
    filing_date: Optional[date] = None
    chief_name: Optional[str] = None
    chief_post: Optional[str] = None
    chief_phone: Optional[str] = None
    tech_name: Optional[str] = None
    tech_post: Optional[str] = None
    tech_phone: Optional[str] = None
    oper_name: Optional[str] = None
    oper_post: Optional[str] = None
    oper_phone: Optional[str] = None
    attachments: Optional[dict] = None
    completeness: Optional[dict] = None


class RecordOut(BaseModel):
    id: str
    unit_id: str
    enterprise_id: str
    hazard_code: Optional[str] = None
    filing_status: str
    filing_no: Optional[str] = None
    filing_date: Optional[date] = None
    chief_name: Optional[str] = None
    chief_post: Optional[str] = None
    chief_phone: Optional[str] = None
    tech_name: Optional[str] = None
    tech_post: Optional[str] = None
    tech_phone: Optional[str] = None
    oper_name: Optional[str] = None
    oper_post: Optional[str] = None
    oper_phone: Optional[str] = None
    attachments: dict = Field(default_factory=dict)
    completeness: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}
```

并在该文件顶部把 `from datetime import datetime` 改为 `from datetime import date, datetime`。

- [ ] **步骤 4：追加档案端点**

在 `backend/app/routers/major_hazard.py` 的 import 区补充：

```python
from app.models.major_hazard import MajorHazardRecord
from app.schemas.major_hazard import RecordIn, RecordOut
```

并在文件末尾追加：

```python
@router.get("/units/{unit_id}/record")
async def get_unit_record(unit_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MajorHazardRecord).where(MajorHazardRecord.unit_id == unit_id))
    record = res.scalar_one_or_none()
    if record is None:
        raise HTTPException(404, "该单元尚未建立档案")
    return _ok(RecordOut.model_validate(record))


@router.put("/units/{unit_id}/record")
async def upsert_unit_record(
    unit_id: str,
    payload: RecordIn,
    enterprise_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """档案不存在则创建，存在则按提供的字段局部更新。"""
    unit_res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    if unit_res.scalar_one_or_none() is None:
        raise HTTPException(404, "重大危险源单元不存在")

    res = await db.execute(select(MajorHazardRecord).where(MajorHazardRecord.unit_id == unit_id))
    record = res.scalar_one_or_none()
    if record is None:
        record = MajorHazardRecord(unit_id=unit_id, enterprise_id=enterprise_id)
        db.add(record)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(record, key, value)
    await db.commit()
    await db.refresh(record)
    return _ok(RecordOut.model_validate(record))
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_api.py -v
```

预期：`5 passed`

注意：`upsert_unit_record` 里的 `db.refresh(record)` 在真实会话下会重新查库；在 mock 测试中它是 `AsyncMock`，不会覆盖已设置字段，因此断言使用的是内存对象。这是既有测试范式的固有限制，真实验证放在步骤 6。

- [ ] **步骤 6：端到端手工验证（真实数据库）**

启动后端后依次执行（`<token>` 与 `<ent>` 用真实值替换）：

```bash
curl -s -X POST "http://localhost:8000/api/v1/major-hazard/units?enterprise_id=<ent>" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"name":"罐区A","unit_type":"storage"}'

curl -s -X PUT "http://localhost:8000/api/v1/major-hazard/units/<unit>/chemicals" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '[{"chemical_name":"氯","q_design_max":"5.0","critical_quantity_t":"5.0","beta":"4.0","beta_source":"table3"}]'

curl -s -X POST "http://localhost:8000/api/v1/major-hazard/units/<unit>/compute" \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"exposed_population":0}'

curl -s "http://localhost:8000/api/v1/major-hazard/units/<unit>/calculations" \
  -H "Authorization: Bearer <token>"
```

预期：第三条返回 `s_value=1.0, r_value=4.0, is_major_hazard=true, level="四级"`；第四条能查到该快照

- [ ] **步骤 7：Commit**

```bash
git add backend/app/schemas/major_hazard.py backend/app/routers/major_hazard.py backend/tests/test_major_hazard_api.py
git commit -m "feat(major-hazard): 档案与备案 API（补齐 P0-4）"
```

---

## 验收清单

全部任务完成后，逐条确认：

- [ ] `cd backend && python -m pytest tests/ -q` 全绿，数量不低于既有基线
- [ ] `python scripts/gen_major_hazard_seed_sql.py` 连跑两次输出逐字节一致
- [ ] 三个迁移脚本连续执行两次均无报错（幂等）
- [ ] `critical_quantities` = 109 行、`hazard_beta_factors` = 38 行
- [ ] 建一个单元 → 录 2 种物质 → 调 `/compute` → 返回 `s_value/r_value/level`，且 `major_hazard_calculations` 新增一行
- [ ] 用同一输入再调 `/compute`，新快照 `seq` 递增，旧快照内容不变
- [ ] 用快照里的输入手工复算，结果与快照一致（`replay_snapshot` 测试覆盖）
- [ ] `/units/{id}/evidence` 能返回挂载的 GB 18218 条文
- [ ] 危化品存量回填后，`storage_amount IS NULL` 的记录可在页面上人工补录（本计划只保证字段与回填，前端在计划 2）
