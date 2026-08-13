# Codex Custom Subagents task handoff v1

Task: task_02_snapshot_model

## 实现任务 2：RiskNoticeCard 快照模型

### 任务描述（来自实现计划 2026-08-11-risk-notice-card.md 任务 2）

**文件：**
* 创建：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\app\models\risk_notice_card.py`
* 修改：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\db_migration_risk_notice_card.sql`（末尾追加快照表 DDL）
* 测试：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend\tests\test_risk_notice_card_service.py`（追加）

**步骤 1：编写失败测试（快照模型）**

在 `backend/tests/test_risk_notice_card_service.py` 追加：

```python
from app.models.risk_notice_card import RiskNoticeCard


def test_snapshot_model_columns():
    cols = {c.name for c in RiskNoticeCard.__table__.columns}
    assert {"object_id", "version", "content", "source"} <= cols
```

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py::test_snapshot_model_columns -v`
预期：FAIL（模块不存在）

**步骤 2：创建模型**

创建 `backend/app/models/risk_notice_card.py`：

```python
from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class RiskNoticeCard(Base):
    """风险告知卡快照（AI 优化结果）。每个风险点最多一条最新快照。"""

    __tablename__ = "risk_notice_cards"
    __table_args__ = (
        UniqueConstraint("object_id", name="uq_risk_notice_cards_object"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("risk_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="ai")
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**步骤 3：迁移 SQL 追加快照表**

在 `backend/db_migration_risk_notice_card.sql` 末尾（COMMIT 之前）追加：

```sql
-- 风险告知卡快照表
CREATE TABLE IF NOT EXISTS risk_notice_cards (
    id UUID PRIMARY KEY,
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    object_id UUID NOT NULL REFERENCES risk_objects(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    content JSONB NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'ai',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_risk_notice_cards_object UNIQUE (object_id)
);
CREATE INDEX IF NOT EXISTS idx_rnc_enterprise ON risk_notice_cards(enterprise_id);
```

注意：现有迁移文件已用 `BEGIN;` ... `COMMIT;` 包裹，追加内容必须放在 BEGIN/COMMIT 之间（COMMIT 之前）。

**步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_risk_notice_card_service.py -v`
预期：PASS（两个测试：模型字段 + 快照模型）

**步骤 5：Commit**

```bash
git add backend/app/models/risk_notice_card.py backend/db_migration_risk_notice_card.sql backend/tests/test_risk_notice_card_service.py
git commit -m "feat(risk-notice-card): add snapshot model and migration"
```

### 范围与限制

* 只做任务 2 定义的内容：快照模型、迁移追加快照表、测试追加。
* 不创建服务/路由/schemas，不修改其他文件。
* 提交前确认 worktree 内 `git status` 只含上述 3 个文件（TASKS.md 除外，按项目惯例不入库）。

### 上下文

* 项目 worktree：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card`（分支 codex/risk-notice-card）。
* 任务 1 已完成（commit 80a56ed + 88d28b5）：risk_objects 已加 4 字段，迁移文件已有 BEGIN/COMMIT 包裹。
* 设计规格：`docs/superpowers/specs/2026-08-11-risk-notice-card-design.md` §6.2（快照表字段定义）。
* 后续任务会扩展该测试文件与模型，本任务只做第二步。

---

## 追加指令（2026-08-11，控制者）：修复质量审查 2 项次要建议

你的任务 2 已通过规格审查和质量审查（✅ 通过），质量审查提出 2 项次要建议，请修复后提交：

### 修复 1（次要）：迁移 DDL 的 id 补 DEFAULT

`backend/db_migration_risk_notice_card.sql` 中快照表 DDL 的 `id UUID PRIMARY KEY` 改为 `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`（与项目既有迁移惯例一致）。

### 修复 2（次要）：模型 object_id 去掉冗余 index=True

`backend/app/models/risk_notice_card.py` 中 `object_id` 的 `index=True` 删除（唯一约束 uq_risk_notice_cards_object 已覆盖相等查询，避免与 DDL 产生双索引）。

### 验证

- `cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card\backend && python -m pytest tests/test_risk_notice_card_service.py -v` 仍 2 passed。
- `git -C C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\risk-notice-card show --check HEAD` 干净。
- 提交新 commit（不要 amend 原提交 1ef31a4），消息：`fix(risk-notice-card): align snapshot ddl and model index`

### 汇报

- 状态：DONE | BLOCKED | NEEDS_CONTEXT
- 修改的文件与行
- 测试结果
- 新提交 SHA
