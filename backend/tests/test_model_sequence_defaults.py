"""守护：列上的 nextval('X') 默认值必须有对应的 Sequence 声明。

2026-09-19 空库演练发现：`chat_messages.seq` 用裸文本 `nextval('chat_messages_seq')`
作 server_default，而没有任何地方创建该序列 → `Base.metadata.create_all()` 在空库
直接抛 UndefinedTableError，应用 fail-fast 无法启动（全新安装/灾难重建路径不可用）。

SQLAlchemy 只有把序列声明为 `Sequence(...)` 才会在 create_all 时先建序列。
"""

import re

from app.database import Base
from app.models import chat  # noqa: F401  确保模型已加载（其他模型由 tests/conftest 导入链路带入）

NEXTVAL_RE = re.compile(r"nextval\('(?P<name>[A-Za-z0-9_]+)'\)")


def test_nextval_defaults_have_declared_sequence():
    declared = {
        seq.name
        for seq in Base.metadata._sequences.values()  # type: ignore[attr-defined]
    }
    missing: list[str] = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            default = column.server_default
            if default is None:
                continue
            text_value = str(getattr(default, "arg", default))
            for match in NEXTVAL_RE.finditer(text_value):
                name = match.group("name")
                if name not in declared:
                    missing.append(f"{table.name}.{column.name} -> {name}")
    assert not missing, (
        "以下列使用 nextval() 默认值但缺少 Sequence 声明（空库 create_all 会失败）："
        + ", ".join(missing)
    )
