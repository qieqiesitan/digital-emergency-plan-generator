# DataHub 数据接入适配层实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 建一条统一的数据落地通道：文件抽取 / 表格导入 / 系统对接三种来源，全部汇入同一张待确认队列，**人工确认后才写入正式业务表**。

**架构：** 不做通用 ETL。三种形态只是"进料口"不同，出料口统一为 `ingest_items`（`pending`）→ 人工确认 → 目标业务表。原始载荷永久保留、幂等键数据库级唯一约束、失败可重放。复用现有的 `services/file_parser.py`（csv/xlsx/docx/pdf → 文本）与 `third_party_config`（密钥）。

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x / PostgreSQL / openpyxl / React 18 + antd 5。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §8、§13.1

**依赖：** 计划 2（AI 网关，用于 schema matching 与质量校验）。纯代码任务可先做，AI 相关任务需计划 2 就绪。

**视觉走查确认的交互（必须遵守）：** 待确认队列 = **整批默认全选 + 勾掉错的**；高/中置信度默认勾选，**低置信度默认不勾**并注明原因；每条显示来源定位（文件 + 页码/条款）。**拒绝"高置信度自动入库"**——违背"无确认不入正式表"的红线。

---

## 文件结构

**后端**

| 文件 | 职责 |
|---|---|
| `backend/app/models/ingest.py`（新建） | 5 张表 ORM |
| `backend/db_migration_20260917_datahub.sql`（新建） | DDL |
| `backend/app/services/ingest_service.py`（新建） | 任务创建、条目状态流转、确认入库（核心） |
| `backend/app/services/ingest_reconcile.py`（新建） | 对账计算（纯函数） |
| `backend/app/services/chemical_validation.py`（新建） | **CAS 校验位**等数据质量校验 |
| `backend/app/schemas/ingest.py`（新建） | 出入参 |
| `backend/app/routers/ingest.py`（新建） | REST API |
| `backend/app/main.py`（修改） | 注册路由 |
| `backend/tests/test_chemical_validation.py`（新建） | CAS 校验位 |
| `backend/tests/test_ingest_migration.py`（新建） | 迁移 SQL 结构断言 |
| `backend/tests/test_ingest_service.py`（新建） | 幂等/状态流转/确认入库 |
| `backend/tests/test_ingest_reconcile.py`（新建） | 对账纯函数 |
| `backend/tests/test_ingest_api.py`（新建） | 端点测试 |

**前端**

| 文件 | 职责 |
|---|---|
| `frontend/src/types/ingest.ts`（新建） | 类型 |
| `frontend/src/services/ingestService.ts`（新建） | API 封装 |
| `frontend/src/pages/Settings/DataHubPage.tsx`（新建） | 数据源列表 + 任务列表 |
| `frontend/src/pages/Settings/DataHubReviewPage.tsx`（新建） | **待确认队列**（核心页面） |
| `frontend/src/routes/index.tsx`（修改） | 2 条路由 |

**既有约定**

- 迁移脚本放 `backend/` 根，幂等 + 确定性 UUID5 + `ON CONFLICT (id) DO NOTHING`
- 模型用 `Mapped[...] = mapped_column(...)`，主键 `UUID(as_uuid=False)`
- 前端 service 写法见 `frontend/src/services/riskManagementService.ts`

---

## 数据模型（5 张表）

| 表 | 关键字段 |
|---|---|
| `ingest_sources` | `source_type`(file/sheet/api_push/api_pull/manual)、`name`、`config`(JSONB)、`secret_ref`(指向 `third_party_config` 的键名，**不存明文**)、`target_entity`、`is_active` |
| `field_mappings` | `source_id`、`target_entity`、`mapping`(JSONB：源列→目标字段)、`transforms`(JSONB：单位换算/枚举字典/日期格式)、`required_fields`(JSONB 数组)、`status` |
| `ingest_jobs` | `source_id`、`trigger`、`status`(running/succeeded/failed/partial)、`total`/`imported`/`skipped`/`failed`/`pending_review` 计数、`error_summary`、起止时间 |
| `ingest_items` | `job_id`、**`idempotency_key`（唯一）**、`raw_payload`(JSONB，永久保留)、`target_entity`、`target_id`、`status`(pending/imported/skipped/failed/needs_review)、`source_locator`、`confidence`(high/medium/low)、`review_note`、`reviewed_by`/`reviewed_at` |
| `ingest_reconciliations` | `source_id`、`expected_count`、`actual_count`、`diff_note`、`checksum`、`checked_at` |

**四条硬规则（写死在服务层）：**

1. `raw_payload` 只增不改不删
2. `status='pending'` 的条目**不可能出现在正式业务表里**——只有 `confirm_items()` 这一条路径会写正式表
3. `idempotency_key` 数据库级唯一约束，重复推送跳过
4. 失败项保留 `raw_payload` 与 `error`，可重放

---

## 任务 1：数据质量校验工具（CAS 校验位）

**文件：**

- 创建：`backend/app/services/chemical_validation.py`
- 测试：`backend/tests/test_chemical_validation.py`

**背景：** CAS 登记号自带校验位，可程序化验证。该算法已在 `scripts/extract_gb18218_tables.py` 里实现并在 82 条真实标准数据上验证通过，此处提炼成应用层服务供导入校验复用——**不要重新实现**。

- [ ] **步骤 1：编写失败的测试**

```python
"""危化品数据质量校验：CAS 校验位。"""

import pytest

from app.services.chemical_validation import (
    cas_checksum_ok,
    find_cas_in_text,
    is_valid_cas_format,
)


@pytest.mark.parametrize(
    "cas",
    ["7664-41-7", "75-44-5", "50-00-0", "108-88-3", "7440-23-5", "9004-70-0"],
)
def test_valid_cas_numbers_pass(cas):
    """这些值取自 GB 18218 表1 实测数据，必须通过。"""
    assert cas_checksum_ok(cas) is True


@pytest.mark.parametrize("cas", ["7664-41-8", "75-44-4", "1234-56-7"])
def test_wrong_check_digit_fails(cas):
    assert cas_checksum_ok(cas) is False


def test_invalid_format_fails():
    assert is_valid_cas_format("abc") is False
    assert is_valid_cas_format("76-41-7") is False
    assert is_valid_cas_format("7664-41-7") is True
    assert is_valid_cas_format("7664417") is True


def test_find_cas_in_text_picks_candidates():
    text = "氯（CAS 7782-50-5）、光气 75-44-5，另一组 1234-56-7 是错的"
    found = find_cas_in_text(text)
    assert {f["cas"] for f in found} >= {"7782-50-5", "75-44-5"}
    assert any(f["cas"] == "1234-56-7" and f["ok"] is False for f in found)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_chemical_validation.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""危化品数据质量校验。

CAS 校验位算法移植自 scripts/extract_gb18218_tables.py（已在 82 条真实标准数据上验证），
此处作为应用层服务供 DataHub 导入校验复用。
"""

from __future__ import annotations

import re

_CAS_PATTERN = re.compile(r"\b(\d{2,7})-(\d{2})-(\d)\b")
_CAS_BARE = re.compile(r"^\d{5,10}$")


def is_valid_cas_format(cas: str) -> bool:
    """形如 2~7 位-2 位-1 位；也接受无连字符的纯数字串。"""
    if not cas:
        return False
    text = cas.strip()
    if _CAS_PATTERN.fullmatch(text):
        return True
    return bool(_CAS_BARE.fullmatch(text))


def cas_checksum_ok(cas: str) -> bool:
    """CAS 校验位验证：末位 = 前面各位从右向左依次×1,2,3… 之和 mod 10。"""
    if not cas:
        return False
    digits = re.sub(r"\D", "", cas)
    if len(digits) < 5:
        return False
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (i + 1) for i, d in enumerate(reversed(body)))
    return total % 10 == check


def find_cas_in_text(text: str) -> list[dict]:
    """从自由文本里挑出形似 CAS 的串并附校验结果。"""
    if not text:
        return []
    seen: set[str] = set()
    out: list[dict] = []
    for m in _CAS_PATTERN.finditer(text):
        cas = m.group(0)
        if cas in seen:
            continue
        seen.add(cas)
        out.append({"cas": cas, "ok": cas_checksum_ok(cas)})
    return out
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_chemical_validation.py -v
```

预期：`9 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/chemical_validation.py backend/tests/test_chemical_validation.py
git commit -m "feat(datahub): CAS 校验位等数据质量校验（提炼自标准数据脚本）（任务 1/7）"
```

---

## 任务 2：五张表 ORM + 迁移

**文件：**

- 创建：`backend/app/models/ingest.py`
- 创建：`backend/db_migration_20260917_datahub.sql`
- 测试：`backend/tests/test_ingest_migration.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""DataHub 表结构与迁移 SQL 断言。"""

import re
from pathlib import Path

from app.models.ingest import (
    FieldMapping,
    IngestItem,
    IngestJob,
    IngestReconciliation,
    IngestSource,
)

BACKEND = Path(__file__).resolve().parents[1]
SQL = (BACKEND / "db_migration_20260917_datahub.sql").read_text(encoding="utf-8")


def test_tablenames():
    assert IngestSource.__tablename__ == "ingest_sources"
    assert FieldMapping.__tablename__ == "field_mappings"
    assert IngestJob.__tablename__ == "ingest_jobs"
    assert IngestItem.__tablename__ == "ingest_items"
    assert IngestReconciliation.__tablename__ == "ingest_reconciliations"


def test_item_required_columns():
    cols = IngestItem.__table__.columns
    for name in ("job_id", "idempotency_key", "raw_payload", "status", "confidence"):
        assert name in cols, name
    assert cols["raw_payload"].nullable is False
    assert cols["status"].nullable is False


def test_source_never_stores_plaintext_secret():
    cols = IngestSource.__table__.columns
    assert "secret_ref" in cols
    for banned in ("secret", "password", "api_key", "token"):
        assert banned not in cols, f"数据源表不得直接存明文密钥字段：{banned}"


def test_migration_creates_five_tables():
    for t in (
        "ingest_sources",
        "field_mappings",
        "ingest_jobs",
        "ingest_items",
        "ingest_reconciliations",
    ):
        assert re.search(rf"CREATE TABLE IF NOT EXISTS\s+{t}\b", SQL), t


def test_migration_has_unique_idempotency_key():
    """幂等键必须是数据库级唯一约束，不能只靠应用层判断。"""
    assert re.search(r"UNIQUE\s*\(\s*idempotency_key\s*\)", SQL, re.I)


def test_migration_has_no_delete_or_update_on_items():
    upper = SQL.upper()
    assert "DELETE FROM INGEST_ITEMS" not in upper
    assert "UPDATE INGEST_ITEMS SET RAW_PAYLOAD" not in upper
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_migration.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.models.ingest'`

- [ ] **步骤 3：编写 ORM**

```python
"""DataHub 接入层 ORM：来源、字段映射、任务、条目、对账。

设计要点：
- `ingest_items.raw_payload` 永久保留，任何时候能回答"这条数据当初长什么样、来自哪一行"；
- `idempotency_key` 是数据库级唯一约束，重复推送不产生重复条目；
- 密钥只存 `secret_ref`（指向 third_party_config 的键名），本表绝不存明文。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IngestSource(Base):
    __tablename__ = "ingest_sources"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    secret_ref: Mapped[Optional[str]] = mapped_column(String(120))
    target_entity: Mapped[Optional[str]] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FieldMapping(Base):
    __tablename__ = "field_mappings"
    __table_args__ = (
        UniqueConstraint("source_id", "target_entity", name="uq_fm_source_entity"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingest_sources.id", ondelete="CASCADE"), nullable=False
    )
    target_entity: Mapped[str] = mapped_column(String(60), nullable=False)
    mapping: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    transforms: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    required_fields: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IngestJob(Base):
    __tablename__ = "ingest_jobs"
    __table_args__ = (Index("idx_ingest_jobs_source", "source_id", "created_at"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingest_sources.id", ondelete="SET NULL")
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )


class IngestItem(Base):
    __tablename__ = "ingest_items"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ingest_items_idem"),
        Index("idx_ingest_items_job_status", "job_id", "status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_entity: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    source_locator: Mapped[Optional[str]] = mapped_column(String(200))
    confidence: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    error: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestReconciliation(Base):
    __tablename__ = "ingest_reconciliations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("ingest_sources.id", ondelete="CASCADE"), nullable=False
    )
    expected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diff_note: Mapped[Optional[str]] = mapped_column(Text)
    checksum: Mapped[Optional[str]] = mapped_column(String(80))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **步骤 4：编写迁移 DDL**

```sql
-- 20260917 DataHub 数据接入适配层（来源/映射/任务/条目/对账）
-- 硬规则：raw_payload 永久保留；idempotency_key 数据库级唯一；密钥只存 secret_ref。

CREATE TABLE IF NOT EXISTS ingest_sources (
    id UUID PRIMARY KEY,
    source_type VARCHAR(20) NOT NULL,
    name VARCHAR(200) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    secret_ref VARCHAR(120),
    target_entity VARCHAR(60),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS field_mappings (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES ingest_sources(id) ON DELETE CASCADE,
    target_entity VARCHAR(60) NOT NULL,
    mapping JSONB NOT NULL DEFAULT '{}'::jsonb,
    transforms JSONB NOT NULL DEFAULT '{}'::jsonb,
    required_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_fm_source_entity UNIQUE (source_id, target_entity)
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id UUID PRIMARY KEY,
    source_id UUID REFERENCES ingest_sources(id) ON DELETE SET NULL,
    trigger VARCHAR(20) NOT NULL DEFAULT 'manual',
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    total INTEGER NOT NULL DEFAULT 0,
    imported INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    pending_review INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_source ON ingest_jobs (source_id, created_at);

CREATE TABLE IF NOT EXISTS ingest_items (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES ingest_jobs(id) ON DELETE CASCADE,
    idempotency_key VARCHAR(300) NOT NULL,
    raw_payload JSONB NOT NULL,
    target_entity VARCHAR(60) NOT NULL,
    target_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    source_locator VARCHAR(200),
    confidence VARCHAR(10) NOT NULL DEFAULT 'medium',
    review_note TEXT,
    error TEXT,
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ingest_items_idem UNIQUE (idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_ingest_items_job_status ON ingest_items (job_id, status);

CREATE TABLE IF NOT EXISTS ingest_reconciliations (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES ingest_sources(id) ON DELETE CASCADE,
    expected_count INTEGER NOT NULL DEFAULT 0,
    actual_count INTEGER NOT NULL DEFAULT 0,
    diff_note TEXT,
    checksum VARCHAR(80),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_migration.py -v
```

预期：`6 passed`

- [ ] **步骤 6：Commit**

```bash
git add backend/app/models/ingest.py backend/db_migration_20260917_datahub.sql backend/tests/test_ingest_migration.py
git commit -m "feat(datahub): 五张表 ORM 与迁移（幂等键唯一、密钥不落明文）（任务 2/7）"
```

---

## 任务 3：接入服务核心（幂等 + 确认链路）

**文件：**

- 创建：`backend/app/services/ingest_service.py`
- 测试：`backend/tests/test_ingest_service.py`

**这一任务的价值：** `confirm_items()` 是**唯一**会把数据写进正式业务表的入口。其他所有路径（文件解析、AI 抽取、外部推送）都只能产出 `status='pending'` 的条目。这条约束是"无确认不入正式表"红线的代码落点。

- [ ] **步骤 1：编写失败的测试**

```python
"""接入服务：幂等键、条目创建、确认入库、任务计数。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ingest_service import (
    IngestError,
    build_idempotency_key,
    confirm_items,
    create_item,
    register_target_writer,
    update_job_counts,
)


def _db(existing=None):
    added: list = []
    db = MagicMock()
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = existing
        return res

    db.execute = execute
    db._added = added
    return db


def test_idempotency_key_is_stable_and_source_scoped():
    a = build_idempotency_key(source_id="s1", target="chem", external_id="P12-3")
    b = build_idempotency_key(source_id="s1", target="chem", external_id="P12-3")
    c = build_idempotency_key(source_id="s2", target="chem", external_id="P12-3")
    assert a == b, "同源同键必须稳定"
    assert a != c, "不同来源不能撞键"
    assert len(a) <= 300


def test_idempotency_key_without_external_id_uses_payload_hash():
    k1 = build_idempotency_key(source_id="s1", target="t", external_id=None, payload={"a": 1})
    k2 = build_idempotency_key(source_id="s1", target="t", external_id=None, payload={"a": 1})
    k3 = build_idempotency_key(source_id="s1", target="t", external_id=None, payload={"a": 2})
    assert k1 == k2
    assert k1 != k3


def test_idempotency_key_requires_identifiable_input():
    with pytest.raises(IngestError):
        build_idempotency_key(source_id="s1", target="t", external_id=None, payload=None)


@pytest.mark.asyncio
async def test_create_item_skips_duplicate():
    existing = MagicMock()
    existing.id = "i1"
    db = _db(existing=existing)
    out = await create_item(
        db, job_id="j1", idempotency_key="k1", raw_payload={"a": 1}, target_entity="t"
    )
    assert out["created"] is False
    assert out["item_id"] == "i1"
    assert db._added == [], "重复键不得新增行"


@pytest.mark.asyncio
async def test_create_item_inserts_new_as_pending():
    db = _db(existing=None)
    out = await create_item(
        db,
        job_id="j1",
        idempotency_key="k2",
        raw_payload={"a": 1},
        target_entity="t",
        source_locator="报告.pdf P12",
        confidence="high",
    )
    assert out["created"] is True
    row = db._added[0]
    assert row.status == "pending", "新条目一律先进待确认队列"
    assert row.raw_payload == {"a": 1}
    assert row.source_locator == "报告.pdf P12"
    assert row.confidence == "high"


@pytest.mark.asyncio
async def test_confirm_items_only_processes_selected():
    """只入库被选中的条目——"整批默认全选 + 勾掉错的"的代码落点。"""
    item_ok = MagicMock()
    item_ok.id = "i1"
    item_ok.status = "pending"
    item_ok.target_entity = "unit_chemical"
    item_ok.raw_payload = {"chemical_name": "氯"}
    item_skip = MagicMock()
    item_skip.id = "i2"
    item_skip.status = "pending"

    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = item_ok if "i1" in str(stmt) else item_skip
        return res

    db.execute = execute

    async def _writer(dbc, payload, item):
        return "target-1"

    register_target_writer("unit_chemical", _writer)
    out = await confirm_items(db, item_ids=["i1"], approved_by="user1")

    assert out["confirmed"] == 1
    assert item_ok.status == "imported"
    assert item_ok.target_id == "target-1"
    assert item_ok.reviewed_by == "user1"
    assert item_skip.status == "pending", "未被选中的条目状态不变"


@pytest.mark.asyncio
async def test_confirm_items_rejects_already_reviewed():
    done = MagicMock()
    done.id = "i1"
    done.status = "imported"
    db = _db(existing=done)
    with pytest.raises(IngestError):
        await confirm_items(db, item_ids=["i1"], approved_by="u1")


@pytest.mark.asyncio
async def test_confirm_items_isolates_single_failure():
    """单条入库失败不能让整批回滚——失败的留在队列里可重试。"""
    bad = MagicMock()
    bad.id = "bad1"
    bad.status = "pending"
    bad.target_entity = "unit_chemical"
    bad.raw_payload = {}

    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = bad
        return res

    db.execute = execute

    async def _boom(dbc, payload, item):
        raise RuntimeError("目标表约束冲突")

    register_target_writer("unit_chemical", _boom)
    out = await confirm_items(db, item_ids=["bad1"], approved_by="u1")
    assert out["confirmed"] == 0
    assert out["failed"][0]["item_id"] == "bad1"
    assert bad.status == "failed"
    assert "约束冲突" in bad.error


@pytest.mark.asyncio
async def test_update_job_counts_derives_from_items():
    counts = {"pending": 3, "imported": 5, "skipped": 1, "failed": 2}
    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.all.return_value = list(counts.items())
        return res

    db.execute = execute
    job = MagicMock()
    job.id = "j1"
    out = await update_job_counts(db, job=job)
    assert out["total"] == 11
    assert out["pending_review"] == 3
    assert out["imported"] == 5
    assert job.status == "partial", "有失败项时任务状态为 partial"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_service.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.ingest_service'`

- [ ] **步骤 3：编写实现**

```python
"""DataHub 接入服务核心。

一条铁律：**只有 confirm_items() 会把数据写进正式业务表**。
文件解析、AI 抽取、外部推送一律只能产出 status='pending' 的 ingest_items。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Awaitable, Callable, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingest import IngestItem, IngestJob

logger = logging.getLogger("ingest_service")

TargetWriter = Callable[[AsyncSession, dict, IngestItem], Awaitable[str]]


class IngestError(ValueError):
    """接入流程中的数据或状态错误。"""


def build_idempotency_key(
    *,
    source_id: str,
    target: str,
    external_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> str:
    """幂等键：优先用来源侧外部 id；没有则用载荷内容 hash。

    必须同时带 source_id 与 target，避免不同来源/不同目标之间撞键。
    """
    if external_id:
        raw = f"{source_id}|{target}|{external_id}"
    elif payload:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        raw = f"{source_id}|{target}|{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
    else:
        raise IngestError("生成幂等键需要 external_id 或 payload 之一")
    return raw[:300]


async def create_item(
    db: AsyncSession,
    *,
    job_id: str,
    idempotency_key: str,
    raw_payload: dict,
    target_entity: str,
    source_locator: Optional[str] = None,
    confidence: str = "medium",
) -> dict:
    """写入一条待确认条目。命中幂等键则跳过（不新增行）。"""
    res = await db.execute(
        select(IngestItem).where(IngestItem.idempotency_key == idempotency_key)
    )
    existing = res.scalar_one_or_none()
    if existing is not None:
        return {"created": False, "item_id": existing.id}
    row = IngestItem(
        job_id=job_id,
        idempotency_key=idempotency_key,
        raw_payload=raw_payload,
        target_entity=target_entity,
        status="pending",
        source_locator=source_locator,
        confidence=confidence,
    )
    db.add(row)
    await db.commit()
    return {"created": True, "item_id": getattr(row, "id", None)}


# 目标实体 → 写库函数。新增目标实体时在此注册，不要在调用点写 if/else。
TARGET_WRITERS: dict[str, TargetWriter] = {}


def register_target_writer(target_entity: str, fn: TargetWriter) -> None:
    TARGET_WRITERS[target_entity] = fn


async def _persist_target(
    db: AsyncSession, *, target_entity: str, raw_payload: dict, item: IngestItem
) -> str:
    writer = TARGET_WRITERS.get(target_entity)
    if writer is None:
        raise IngestError(f"目标实体「{target_entity}」尚未注册写入器")
    return await writer(db, raw_payload, item)


async def confirm_items(
    db: AsyncSession,
    *,
    item_ids: Sequence[str],
    approved_by: Optional[str] = None,
) -> dict:
    """确认入库：只处理传入的 item_ids。

    已审过的条目直接拒绝——避免重复入库与重复计量。
    单条失败不影响其余条目，失败的留在队列里可重试。
    """
    if not item_ids:
        raise IngestError("没有选中任何条目")
    confirmed = 0
    failed: list[dict] = []
    for item_id in item_ids:
        res = await db.execute(select(IngestItem).where(IngestItem.id == item_id))
        item = res.scalar_one_or_none()
        if item is None:
            failed.append({"item_id": item_id, "reason": "条目不存在"})
            continue
        if item.status != "pending":
            raise IngestError(f"条目 {item_id} 当前状态为 {item.status}，不能重复确认")
        try:
            target_id = await _persist_target(
                db,
                target_entity=item.target_entity,
                raw_payload=item.raw_payload,
                item=item,
            )
            item.status = "imported"
            item.target_id = target_id
            item.reviewed_by = approved_by
            confirmed += 1
        except Exception as exc:
            logger.exception("入库失败 item=%s", item_id)
            item.status = "failed"
            item.error = str(exc)[:2000]
            failed.append({"item_id": item_id, "reason": str(exc)[:300]})
    await db.commit()
    return {"confirmed": confirmed, "failed": failed}


async def update_job_counts(db: AsyncSession, *, job: IngestJob) -> dict:
    """按条目实际状态回填任务计数。计数由数据推导，不靠调用方自己累加。"""
    res = await db.execute(
        select(IngestItem.status, func.count())
        .where(IngestItem.job_id == job.id)
        .group_by(IngestItem.status)
    )
    counts = {status: int(n) for status, n in res.all()}
    job.total = sum(counts.values())
    job.imported = counts.get("imported", 0)
    job.skipped = counts.get("skipped", 0)
    job.failed = counts.get("failed", 0)
    job.pending_review = counts.get("pending", 0) + counts.get("needs_review", 0)
    if job.failed:
        job.status = "partial"
    elif job.pending_review:
        job.status = "running"
    else:
        job.status = "succeeded"
    await db.commit()
    return {
        "total": job.total,
        "imported": job.imported,
        "skipped": job.skipped,
        "failed": job.failed,
        "pending_review": job.pending_review,
    }
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_service.py -v
```

预期：`9 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/ingest_service.py backend/tests/test_ingest_service.py
git commit -m "feat(datahub): 接入服务核心（幂等键 + 唯一确认入口 + 单条失败隔离）（任务 3/7）"
```

---

## 任务 4：三种来源适配

**文件：**

- 创建：`backend/app/services/ingest_adapters.py`
- 测试：`backend/tests/test_ingest_adapters.py`

**三种形态共用同一个出料口**（`create_item`），差别只在"怎么把原始输入拆成行"。

- [ ] **步骤 1：编写失败的测试**

```python
"""来源适配：文件 / 表格 / 对接，统一产出 pending 条目。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingest_adapters import (
    AdapterError,
    rows_from_file_text,
    rows_from_sheet,
)


def test_rows_from_file_text_keeps_source_locator():
    """每条抽出的行都要带来源定位——可疑时能翻回原文。"""
    text = "一、罐区A\n罐区A 储存甲醇 79 吨，甲苯 12 吨。\n二、库房B\n库房B 存放丙酮。"
    rows = rows_from_file_text(text, "安全评价报告.pdf")
    assert rows, "应至少抽出一行"
    for r in rows:
        assert r["source_locator"].startswith("安全评价报告.pdf")
        assert r["raw_payload"]["text"]


def test_rows_from_file_text_empty_input():
    assert rows_from_file_text("", "x.pdf") == []
    assert rows_from_file_text(None, "x.pdf") == []


def test_rows_from_sheet_maps_columns_and_reports_required_missing():
    """表头映射 + 必填校验：缺必填列直接报错，不要把脏数据塞进队列。"""
    raw = [
        ["品种名称", "设计最大量(t)", "临界量(t)"],
        ["氯", "5", "5"],
        ["氨", "5", "10"],
    ]
    mapping = {"品种名称": "chemical_name", "设计最大量(t)": "q_design_max", "临界量(t)": "critical_quantity_t"}
    rows = rows_from_sheet(raw, mapping, required=["chemical_name", "q_design_max"])
    assert len(rows) == 2
    assert rows[0]["raw_payload"]["chemical_name"] == "氯"
    assert rows[0]["raw_payload"]["q_design_max"] == "5"
    assert rows[0]["source_locator"] == "第 2 行"


def test_rows_from_sheet_raises_on_missing_required_column():
    raw = [["品种名称"], ["氯"]]
    mapping = {"品种名称": "chemical_name"}
    with pytest.raises(AdapterError) as ei:
        rows_from_sheet(raw, mapping, required=["chemical_name", "q_design_max"])
    assert "q_design_max" in str(ei.value)


def test_rows_from_sheet_raises_on_unmapped_required_field():
    """映射表里没覆盖的必填字段也要报错——否则每行都会缺字段。"""
    raw = [["品名", "数量"], ["氯", "5"]]
    mapping = {"品名": "chemical_name"}  # 缺 q_design_max 的源列
    with pytest.raises(AdapterError):
        rows_from_sheet(raw, mapping, required=["chemical_name", "q_design_max"])


def test_rows_from_sheet_skips_blank_rows():
    raw = [["品名"], ["氯"], [""], ["  "], ["氨"]]
    rows = rows_from_sheet(raw, {"品名": "chemical_name"}, required=["chemical_name"])
    assert len(rows) == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_adapters.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.ingest_adapters'`

- [ ] **步骤 3：编写实现**

```python
"""三种来源适配：把原始输入拆成"带来源定位的行"。

共同契约：返回 [{source_locator, confidence, raw_payload}]，
由调用方交给 ingest_service.create_item 落成 pending 条目。
本模块**不接触数据库**，便于单测。
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence


class AdapterError(ValueError):
    """输入结构不满足适配要求（如缺必填列）。"""


def rows_from_file_text(text: Optional[str], filename: str) -> list[dict]:
    """文件抽取形态：把纯文本按段落切成候选行。

    真正的字段抽取由 AI 完成（见计划 6），本函数只负责**分段 + 标注来源定位**，
    保证每条后续抽取结果都能追溯回原文位置。
    """
    if not text or not text.strip():
        return []
    rows: list[dict] = []
    for idx, block in enumerate(re.split(r"\n\s*\n", text), start=1):
        block = block.strip()
        if not block:
            continue
        rows.append(
            {
                "source_locator": f"{filename} 段{idx}",
                "confidence": "low",  # 未经过 AI 抽取与人工确认，一律先标 low
                "raw_payload": {"text": block, "origin_file": filename},
            }
        )
    return rows


def rows_from_sheet(
    raw_rows: Sequence[Sequence],
    mapping: dict[str, str],
    required: Iterable[str] = (),
) -> list[dict]:
    """表格导入形态：首行作表头，按 mapping（源列名→目标字段）逐行转换。

    必填字段必须在 mapping 的值里出现，否则直接报错——不能等到每行都缺字段才发现。
    """
    if not raw_rows:
        return []
    header = [str(h).strip() if h is not None else "" for h in raw_rows[0]]
    required_set = set(required)
    mapped_targets = set(mapping.values())
    missing = required_set - mapped_targets
    if missing:
        raise AdapterError(f"必填字段未在映射表中覆盖：{sorted(missing)}")

    index_of = {name: i for i, name in enumerate(header) if name}
    for target in required_set:
        src = next((s for s, t in mapping.items() if t == target), None)
        if src is not None and src not in index_of:
            raise AdapterError(f"必填字段「{target}」对应的源列「{src}」不在表头中")

    rows: list[dict] = []
    for line_no, raw in enumerate(raw_rows[1:], start=2):
        if raw is None:
            continue
        values = list(raw)
        if not any(str(v).strip() for v in values if v is not None):
            continue  # 跳过空行
        payload: dict = {}
        for src_name, target in mapping.items():
            col = index_of.get(src_name)
            if col is None or col >= len(values):
                continue
            cell = values[col]
            payload[target] = cell.strip() if isinstance(cell, str) else cell
        rows.append(
            {
                "source_locator": f"第 {line_no} 行",
                "confidence": "high",  # 结构化表格直接映射，可信度高于文本抽取
                "raw_payload": payload,
            }
        )
    return rows


async def ingest_rows(
    db,
    *,
    job_id: str,
    source_id: str,
    target_entity: str,
    rows: Sequence[dict],
) -> dict:
    """把适配产出的行落成 pending 条目。返回 {created, skipped}。"""
    from app.services.ingest_service import build_idempotency_key, create_item

    created = skipped = 0
    for row in rows:
        key = build_idempotency_key(
            source_id=source_id,
            target=target_entity,
            external_id=row.get("source_locator"),
            payload=row.get("raw_payload"),
        )
        out = await create_item(
            db,
            job_id=job_id,
            idempotency_key=key,
            raw_payload=row["raw_payload"],
            target_entity=target_entity,
            source_locator=row.get("source_locator"),
            confidence=row.get("confidence", "medium"),
        )
        if out["created"]:
            created += 1
        else:
            skipped += 1
    return {"created": created, "skipped": skipped}
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_adapters.py -v
```

预期：`6 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/ingest_adapters.py backend/tests/test_ingest_adapters.py
git commit -m "feat(datahub): 文件/表格来源适配（带来源定位，必填列强校验）（任务 4/7）"
```

---

## 任务 5：对账服务（纯函数）

**文件：**

- 创建：`backend/app/services/ingest_reconcile.py`
- 测试：`backend/tests/test_ingest_reconcile.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""对账：期望 vs 实际，差异要能说清原因。"""

from app.services.ingest_reconcile import compare, payload_checksum


def test_compare_matches():
    out = compare(expected=100, actual=100)
    assert out["ok"] is True
    assert out["diff"] == 0


def test_compare_reports_shortfall_with_reason():
    out = compare(expected=100, actual=97, failed=2, skipped=1)
    assert out["ok"] is False
    assert out["diff"] == -3
    assert "失败 2" in out["diff_note"]
    assert "跳过 1" in out["diff_note"]


def test_compare_flags_unexplained_shortfall():
    """差额无法被失败/跳过解释时，必须显式说明"原因不明"，不能含糊过去。"""
    out = compare(expected=100, actual=95, failed=0, skipped=0)
    assert out["ok"] is False
    assert "原因不明" in out["diff_note"]


def test_payload_checksum_is_order_insensitive():
    a = payload_checksum([{"x": 1}, {"y": 2}])
    b = payload_checksum([{"y": 2}, {"x": 1}])
    assert a == b


def test_payload_checksum_changes_on_content():
    a = payload_checksum([{"x": 1}])
    b = payload_checksum([{"x": 2}])
    assert a != b
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_reconcile.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""接入对账（纯函数，无 IO）。"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable


def compare(
    *,
    expected: int,
    actual: int,
    failed: int = 0,
    skipped: int = 0,
) -> dict:
    """比对期望条数与实际入队条数，并把差额归因。

    差额 = 实际 - 期望（负数表示少了）。
    能被 failed / skipped 解释的差额照实说明；解释不了的必须写明"原因不明"——
    含糊过去会让数据缺口永远查不出来。
    """
    diff = actual - expected
    if diff == 0:
        return {"ok": True, "diff": 0, "diff_note": None}

    explained = -(failed + skipped)
    parts: list[str] = []
    if failed:
        parts.append(f"失败 {failed} 条")
    if skipped:
        parts.append(f"跳过 {skipped} 条")

    if diff == explained and parts:
        note = "差额可由" + "、".join(parts) + "完整解释"
    else:
        note = (
            f"实际比期望{'少' if diff < 0 else '多'} {abs(diff)} 条；"
            + ("已知" + "、".join(parts) + "；" if parts else "")
            + "其余差额**原因不明**，需人工核查"
        )
    return {"ok": False, "diff": diff, "diff_note": note}


def payload_checksum(payloads: Iterable[dict]) -> str:
    """对一批载荷算稳定校验和（排序后 hash），用于跨次导入的内容一致性核对。"""
    normalized = json.dumps(
        sorted((json.dumps(p, ensure_ascii=False, sort_keys=True, default=str) for p in payloads)),
        ensure_ascii=False,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_reconcile.py -v
```

预期：`5 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/ingest_reconcile.py backend/tests/test_ingest_reconcile.py
git commit -m "feat(datahub): 对账纯函数（差额归因，解释不了就写"原因不明"）（任务 5/7）"
```

---

## 任务 6：Schemas + API + 路由注册

**文件：**

- 创建：`backend/app/schemas/ingest.py`
- 创建：`backend/app/routers/ingest.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_ingest_api.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""DataHub API 测试。"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import ingest


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


def _client(handler):
    app = FastAPI()
    app.include_router(ingest.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        db.add = MagicMock()
        yield db

    async def _user():
        u = MagicMock()
        u.id = "user1"
        return u

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    return TestClient(app)


def test_list_jobs_returns_rows():
    job = MagicMock()
    job.id = "j1"
    job.status = "running"
    job.total = 14
    job.imported = 0
    job.skipped = 3
    job.failed = 0
    job.pending_review = 11
    job.source_id = "s1"
    job.trigger = "manual"
    job.error_summary = None
    job.created_at = None

    async def handler(stmt, *a, **k):
        return _Result([job])

    client = _client(handler)
    resp = client.get("/api/v1/ingest/jobs")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["pending_review"] == 11


def test_review_list_defaults_low_confidence_unchecked():
    """低置信度默认不勾——这条是"整批默认全选+勾掉错的"的关键细节。"""
    hi = MagicMock()
    hi.id = "i1"
    hi.confidence = "high"
    hi.status = "pending"
    hi.raw_payload = {"chemical_name": "氯"}
    hi.source_locator = "报告.pdf P12"
    hi.target_entity = "major_hazard_unit_chemical"
    lo = MagicMock()
    lo.id = "i2"
    lo.confidence = "low"
    lo.status = "pending"
    lo.raw_payload = {"chemical_name": "?"}
    lo.source_locator = "报告.pdf P15"
    lo.target_entity = "major_hazard_unit_chemical"

    async def handler(stmt, *a, **k):
        return _Result([hi, lo])

    client = _client(handler)
    resp = client.get("/api/v1/ingest/items", params={"job_id": "j1"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["default_checked"] is True
    assert data[1]["default_checked"] is False


def test_confirm_endpoint_returns_counts():
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.post("/api/v1/ingest/items/confirm", json={"item_ids": []})
    assert resp.status_code == 422  # 空选择应被拒
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_api.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.routers.ingest'`

- [ ] **步骤 3：编写 schemas**

```python
"""DataHub 出入参。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SourceIn(BaseModel):
    source_type: str = Field(pattern="^(file|sheet|api_push|api_pull|manual)$")
    name: str = Field(min_length=1, max_length=200)
    config: dict = Field(default_factory=dict)
    secret_ref: Optional[str] = Field(default=None, max_length=120)
    target_entity: Optional[str] = Field(default=None, max_length=60)
    is_active: bool = True


class SourceOut(SourceIn):
    id: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    source_id: Optional[str] = None
    trigger: str
    status: str
    total: int
    imported: int
    skipped: int
    failed: int
    pending_review: int
    error_summary: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ItemOut(BaseModel):
    id: str
    job_id: str
    target_entity: str
    status: str
    confidence: str
    source_locator: Optional[str] = None
    raw_payload: dict
    error: Optional[str] = None
    """前端用于决定复选框默认状态：仅 high/medium 默认勾选。"""
    default_checked: bool = True


class ConfirmIn(BaseModel):
    item_ids: list[str] = Field(min_length=1)
```

- [ ] **步骤 4：编写路由**

```python
"""DataHub API：来源、任务、待确认队列、确认入库、对账。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ingest import IngestItem, IngestJob, IngestSource
from app.schemas.ingest import ConfirmIn, ItemOut, JobOut, SourceIn, SourceOut
from app.services.ingest_service import IngestError, confirm_items

router = APIRouter(prefix="/ingest", tags=["Ingest"])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.get("/sources")
async def list_sources(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(IngestSource).order_by(IngestSource.created_at.desc()))
    return _ok([SourceOut.model_validate(s) for s in res.scalars().all()])


@router.post("/sources")
async def create_source(payload: SourceIn, db: AsyncSession = Depends(get_db)):
    src = IngestSource(**payload.model_dump())
    db.add(src)
    await db.commit()
    await db.refresh(src)
    return _ok(SourceOut.model_validate(src))


@router.get("/jobs")
async def list_jobs(
    source_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(IngestJob).order_by(IngestJob.created_at.desc()).limit(limit)
    if source_id:
        stmt = stmt.where(IngestJob.source_id == source_id)
    res = await db.execute(stmt)
    return _ok([JobOut.model_validate(j) for j in res.scalars().all()])


@router.get("/items")
async def list_items(
    job_id: str = Query(...),
    status: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """待确认队列。返回 default_checked 供前端决定默认勾选状态。

    规则：仅 high/medium 默认勾选；low 默认不勾（低置信度不该被顺带入库）。
    """
    stmt = select(IngestItem).where(IngestItem.job_id == job_id)
    if status:
        stmt = stmt.where(IngestItem.status == status)
    stmt = stmt.order_by(IngestItem.confidence, IngestItem.created_at)
    res = await db.execute(stmt)
    out = []
    for it in res.scalars().all():
        row = ItemOut(
            id=it.id,
            job_id=it.job_id,
            target_entity=it.target_entity,
            status=it.status,
            confidence=it.confidence,
            source_locator=it.source_locator,
            raw_payload=it.raw_payload,
            error=it.error,
            default_checked=it.confidence in ("high", "medium") and it.status == "pending",
        )
        out.append(row)
    return _ok(out)


@router.post("/items/confirm")
async def confirm(
    payload: ConfirmIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """确认入库。只处理传入的 item_ids——前端"整批默认全选 + 勾掉错的"的落点。"""
    try:
        out = await confirm_items(
            db, item_ids=payload.item_ids, approved_by=getattr(user, "id", None)
        )
    except IngestError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(out)
```

- [ ] **步骤 5：注册路由**

在 `backend/app/main.py` 第 14 行的长 import 末尾追加 `, ingest`，并在 `app.include_router(major_hazard.router, prefix="/api/v1")` 之后追加：

```python
app.include_router(ingest.router, prefix="/api/v1")
```

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ingest_api.py -v
```

预期：`3 passed`

- [ ] **步骤 7：跑后端全量**

运行：

```bash
cd backend && python -m pytest tests/ -q
```

预期：失败数不高于 4 个既有失败

- [ ] **步骤 8：Commit**

```bash
git add backend/app/schemas/ingest.py backend/app/routers/ingest.py backend/app/main.py backend/tests/test_ingest_api.py
git commit -m "feat(datahub): schemas 与 REST API（默认勾选规则落在 ItemOut.default_checked）（任务 6/7）"
```

---

## 任务 7：前端待确认队列页

**文件：**

- 创建：`frontend/src/types/ingest.ts`
- 创建：`frontend/src/services/ingestService.ts`
- 创建：`frontend/src/pages/Settings/DataHubPage.tsx`
- 创建：`frontend/src/pages/Settings/DataHubReviewPage.tsx`
- 修改：`frontend/src/routes/index.tsx`

- [ ] **步骤 1：类型与 service**

```ts
// frontend/src/types/ingest.ts
export interface IngestSource {
  id: string;
  source_type: "file" | "sheet" | "api_push" | "api_pull" | "manual";
  name: string;
  config: Record<string, unknown>;
  secret_ref?: string | null;
  target_entity?: string | null;
  is_active: boolean;
  created_at?: string | null;
}

export interface IngestJob {
  id: string;
  source_id?: string | null;
  trigger: string;
  status: "running" | "succeeded" | "failed" | "partial";
  total: number;
  imported: number;
  skipped: number;
  failed: number;
  pending_review: number;
  error_summary?: string | null;
  created_at?: string | null;
}

export interface IngestItem {
  id: string;
  job_id: string;
  target_entity: string;
  status: "pending" | "imported" | "skipped" | "failed" | "needs_review";
  confidence: "high" | "medium" | "low";
  source_locator?: string | null;
  raw_payload: Record<string, unknown>;
  error?: string | null;
  /** 后端给的建议默认勾选状态：仅 high/medium 且 pending 时为 true */
  default_checked: boolean;
}

export interface ConfirmResult {
  confirmed: number;
  failed: Array<{ item_id: string; reason: string }>;
}
```

```ts
// frontend/src/services/ingestService.ts
import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { ConfirmResult, IngestItem, IngestJob, IngestSource } from "@/types/ingest";

const BASE = "/ingest";

export const listSources = () =>
  api.get<ApiResponse<IngestSource[]>>(`${BASE}/sources`).then((r) => r.data.data);

export const createSource = (payload: Partial<IngestSource>) =>
  api.post<ApiResponse<IngestSource>>(`${BASE}/sources`, payload).then((r) => r.data.data);

export const listJobs = (sourceId?: string) =>
  api
    .get<ApiResponse<IngestJob[]>>(`${BASE}/jobs`, {
      params: sourceId ? { source_id: sourceId } : undefined,
    })
    .then((r) => r.data.data);

export const listItems = (jobId: string, status?: string) =>
  api
    .get<ApiResponse<IngestItem[]>>(`${BASE}/items`, {
      params: { job_id: jobId, status },
    })
    .then((r) => r.data.data);

export const confirmItems = (itemIds: string[]) =>
  api
    .post<ApiResponse<ConfirmResult>>(`${BASE}/items/confirm`, { item_ids: itemIds })
    .then((r) => r.data.data);
```

- [ ] **步骤 2：实现任务列表页 `DataHubPage`**

照 `frontend/src/pages/Settings/` 下既有页面的风格（表格 + 工具条）：

- 「数据源」标签页：表格列 名称 / 类型（中文映射：文件抽取·表格导入·系统推送·定时拉取·人工录入）/ 目标实体 / 启用状态 / 创建时间；右上「+ 新建数据源」
- 「导入任务」标签页：表格列 来源 / 触发方式 / 状态（`Tag` 上色：running=processing、succeeded=success、partial=warning、failed=error）/ 总数 / 待确认 / 已入库 / 跳过 / 失败 / 创建时间 / 操作（「去确认」跳 review 页，仅当 `pending_review > 0` 时可点）

- [ ] **步骤 3：实现待确认队列页 `DataHubReviewPage`（核心）**

行为要求（逐条对应视觉走查确认的交互）：

1. 读 `listItems(jobId, "pending")`
2. **默认勾选 = 后端给的 `default_checked`**，前端不要自己重算这个规则
3. 顶部统计条：`抽取 N 条 ｜ 默认选中 M 条 ｜ 低置信度 K 条（默认不勾）`
4. 表格列：复选框 / 目标实体 / 抽取内容（把 `raw_payload` 的关键字段渲染成一行可读文本）/ **来源定位** / 置信度（`Tag`：high=绿、medium=金、low=红）/ 操作（展开看原始载荷 JSON）
5. 低置信度行**整行浅红底**，并在「抽取内容」列后追加原因提示（如"无法确定单元边界"来自 `review_note`）
6. 底部动作：「确认入库（N 条）」（N 为当前勾选数，为 0 时禁用）/「全选」「全不选」/「跳过选中」（把选中项标记 `skipped`）
7. 确认后 `message.success` 显示 `已入库 N 条`，若有 `failed` 则 `message.warning` 列出失败原因，并刷新列表
8. **明确不做**：不要提供"高置信度自动入库"的开关

```tsx
// 默认勾选初始化（关键片段）
const [checked, setChecked] = useState<string[]>([]);
useEffect(() => {
  if (!items) return;
  setChecked(items.filter((i) => i.default_checked).map((i) => i.id));
}, [items]);
```

- [ ] **步骤 4：注册路由**

在 `frontend/src/routes/index.tsx` 的 settings 区追加：

```
/settings/data-hub                 → DataHubPage
/settings/data-hub/:jobId/review   → DataHubReviewPage
```

并在 `frontend/src/utils/menuMap.ts` 加一个「数据接入」菜单项指向 `/settings/data-hub`。

- [ ] **步骤 5：验证**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
docker exec -w /app emergency-plan-frontend npx eslint src/pages/Settings/DataHubPage.tsx src/pages/Settings/DataHubReviewPage.tsx
```

预期：`tsc` exit 0；vitest 全绿；eslint 无新增错误

- [ ] **步骤 6：真实浏览器冒烟**

1. 用 psql 造一个 job + 3 条 item（1 条 high、1 条 medium、1 条 low）
2. 打开 `/settings/data-hub/<jobId>/review`，确认**只有 high/medium 被勾选**，low 未勾
3. 点「确认入库」→ 提示已入库 2 条，列表刷新后只剩 low 那条
4. psql 查 `ingest_items`，确认两条 `status='imported'`、一条仍 `pending`

- [ ] **步骤 7：Commit**

```bash
git add frontend/src/types/ingest.ts frontend/src/services/ingestService.ts frontend/src/pages/Settings/DataHubPage.tsx frontend/src/pages/Settings/DataHubReviewPage.tsx frontend/src/routes/index.tsx frontend/src/utils/menuMap.ts
git commit -m "feat(datahub): 数据源/任务列表页与待确认队列（低置信度默认不勾）（任务 7/7）"
```

---

## 验收清单

- [ ] `cd backend && python -m pytest tests/ -q` 失败数不高于 4 个既有失败
- [ ] `docker exec -w /app emergency-plan-frontend npx tsc -b` exit 0，vitest 全绿
- [ ] **无确认不入正式表**：仅创建 pending 条目（不做 confirm）后，目标业务表行数为 0
- [ ] **幂等**：同一来源同一 `source_locator` 连续导入两次，`ingest_items` 行数不变，第二次返回 `skipped`
- [ ] **低置信度默认不勾**：队列页打开时 low 行未勾选
- [ ] **单条失败隔离**：造一条会触发目标表约束冲突的数据，确认其余条目仍能入库
- [ ] **差额归因**：`ingest_reconciliations` 的 `diff_note` 在差额解释不了时写明"原因不明"
- [ ] **密钥不落明文**：`ingest_sources` 只有 `secret_ref`，`\d ingest_sources` 看不到任何密钥字段
- [ ] 迁移幂等：`db_migration_20260917_datahub.sql` 连跑两次无报错

## 未纳入本计划

- **AI 字段映射建议（schema matching）**：属计划 6（AI 抽取链路），本计划先支持手工配置 `field_mappings`
- **定时拉取（api_pull）的调度器**：本计划建了 `source_type` 与 `trigger` 字段，但调度接入属计划 6
- **双向同步**：设计明确只做单向入站
- **增量同步与断点续传**：当前按"整批导入 + 幂等去重"实现，够用
