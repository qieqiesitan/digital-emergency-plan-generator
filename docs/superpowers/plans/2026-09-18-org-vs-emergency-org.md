# 组织架构与应急组织拆分 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把混在 `enterprises.org_structure` 里的公司组织架构与应急组织拆成两套模型，使公司侧支持一人多岗、应急侧支持一人多任，并把预案生成/章节填充/导出签署页/预案质检的取数切到应急组织。

**架构：** 新增三张应急组织表（`emergency_org_units`/`emergency_org_roles`/`emergency_org_assignments`）与一张任职表（`member_positions`）；`enterprises.org_structure` 收敛为纯公司组织树，`enterprise_members.org_node_id` 降级为主岗镜像列；新增 `/enterprises/{id}/emergency-org` 整树读写接口，旧 `PUT /org-structure` 下线；存量数据用一次性幂等脚本搬迁，兼容「树格式」与「旧分组格式」两种形态。

**技术栈：** FastAPI + SQLAlchemy(async) + PostgreSQL（JSONB、部分唯一索引）、pytest、React 18 + Ant Design 6 + TanStack Query、Vitest。

**规格文档：** `docs/superpowers/specs/2026-09-18-org-vs-emergency-org-design.md`（commit `b902dd0`）

**执行约定（沿用本项目既有基线）：**

- 后端测试必须在**仓库根目录**运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_xxx.py -q`
- 前端验证走容器：`docker exec -w /app emergency-plan-frontend npx tsc -b`、`npx eslint <文件>`、`npx vitest run --reporter=basic`
- 数据库容器 `emergency-plan-db`（可用 psql），库 `emergency_plan`
- 迁移脚本由后端启动时的 `app/services/migration_runner.py` 自动按文件名顺序应用，记录在 `schema_migrations`；因此**新增迁移后需重启 `emergency-plan-backend` 容器**才会应用
- 只 `git add` 本任务涉及的文件，**严禁 `git add -A`**；`TASKS.md` 永不 commit
- 注释用中文，不要全角空格；React 不要用 effect 同步派生状态；antd 6 用 `titlePlacement`（Divider）等新 API
- 后端回归基线：1785 passed / 4 failed（4 个历史失败）；前端基线：274 passed + `tsc -b` exit 0

---

## 文件结构

### 后端

| 文件 | 职责 |
|------|------|
| `backend/db_migration_20260918_emergency_org_split.sql` | 新增：4 张表 + 索引（幂等） |
| `backend/app/models/emergency_org.py` | 新增：EmergencyOrgUnit / EmergencyOrgRole / EmergencyOrgAssignment |
| `backend/app/models/enterprise_org.py` | 修改：新增 MemberPosition |
| `backend/app/schemas/emergency_org.py` | 新增：UnitIn/UnitOut/RoleIn/RoleOut/EmergencyOrgUpdate/MemberBrief |
| `backend/app/services/org_tree_validate.py` | 新增：通用树校验（公司树与应急组织共用） |
| `backend/app/services/emergency_org_service.py` | 新增：整树读、整树写、兼容视图 |
| `backend/app/services/member_position_service.py` | 新增：任职写入与主岗镜像同步 |
| `backend/app/routers/emergency_org.py` | 新增：应急组织整树 GET/PUT |
| `backend/scripts/migrate_emergency_org_split.py` | 新增：存量数据搬迁（幂等、可 dry-run） |
| `backend/app/main.py` | 修改：注册 emergency_org router |
| `backend/app/routers/enterprise_sub.py` | 修改：GET 兼容视图、PUT 下线 410 |
| `backend/app/routers/enterprise_org.py` | 修改：校验复用、成员多任职、导入写任职 |
| `backend/app/routers/generation.py` | 修改：组织图与提示词改取应急组织 |
| `backend/app/routers/sections.py` | 修改：章节自动填充改取应急组织 |
| `backend/app/routers/export.py` | 修改：签署人改取应急组织 |
| `backend/app/services/chat_dispatch.py` | 修改：同上（对话通道） |
| `backend/app/services/plan_quality_service.py` | 修改：质检改查应急组织 |
| `backend/app/services/onboarding_service.py` | 修改：模块改名、完成度查应急组织 |
| `backend/app/services/resource_investigation_service.py` | 修改：AI 入参改带应急组织 |
| `backend/app/services/work_ticket_service.py` | 修改：会签按任职取人 |
| `backend/app/services/enterprise_org_service.py` | 修改：AI 建树改纯公司口径、校验委托通用函数 |
| `backend/tests/test_emergency_org.py` | 新增：模型/校验/服务/API |
| `backend/tests/test_member_positions.py` | 新增：一人多岗与主岗镜像 |
| `backend/tests/test_migrate_emergency_org_split.py` | 新增：迁移脚本两种形态与幂等 |

### 前端

| 文件 | 职责 |
|------|------|
| `frontend/src/types/emergencyOrg.ts` | 新增：应急组织类型 |
| `frontend/src/services/emergencyOrgService.ts` | 新增：整树 GET/PUT 封装 |
| `frontend/src/utils/emergencyOrgPreset.ts` | 新增：预置构造与增量合并 |
| `frontend/src/pages/Enterprise/EmergencyOrgPage.tsx` | 新增：应急组织页 |
| `frontend/src/components/enterprise/cockpit/ModuleNav.tsx` | 修改：新增应急组织入口 |
| `frontend/src/routes/index.tsx` | 修改：新增 `/enterprises/:id/emergency-org` |
| `frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx` | 修改：去预置播种、任职多选、任职列 |
| `frontend/src/pages/Onboarding/StepOrg.tsx` | 修改：改名应急组织、改调新接口 |
| `frontend/src/pages/Onboarding/OnboardingPage.tsx` | 修改：步骤标签改名 |
| `frontend/src/services/enterpriseService.ts` | 修改：删除 updateOrgStructure、getOrgStructure 改指新接口 |
| `frontend/src/services/enterpriseOrgService.ts` | 修改：成员多任职字段 |
| `frontend/src/types/enterprise.ts` | 修改：Enterprise.org_structure 类型改为组织树 |
| `frontend/src/components/enterprise/OrgStructureEditor.tsx` | 删除 |

---

## 任务 1：DDL 迁移与数据模型

**文件：**
- 创建：`backend/db_migration_20260918_emergency_org_split.sql`
- 创建：`backend/app/models/emergency_org.py`
- 修改：`backend/app/models/enterprise_org.py`
- 测试：`backend/tests/test_emergency_org.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_emergency_org.py
from app.models.emergency_org import (
    EmergencyOrgAssignment,
    EmergencyOrgRole,
    EmergencyOrgUnit,
)
from app.models.enterprise_org import EnterpriseMember, MemberPosition


def test_emergency_org_unit_metadata():
    assert EmergencyOrgUnit.__tablename__ == "emergency_org_units"
    cols = EmergencyOrgUnit.__table__.columns
    assert {"id", "enterprise_id", "parent_id", "name", "duties", "sort_order"} <= set(cols)


def test_emergency_org_role_metadata():
    assert EmergencyOrgRole.__tablename__ == "emergency_org_roles"
    cols = EmergencyOrgRole.__table__.columns
    assert {"id", "enterprise_id", "unit_id", "name", "duties", "sort_order", "is_required"} <= set(cols)
    assert EmergencyOrgRole.__table__.columns["is_required"].default.arg is False


def test_emergency_org_assignment_metadata():
    assert EmergencyOrgAssignment.__tablename__ == "emergency_org_assignments"
    cols = EmergencyOrgAssignment.__table__.columns
    assert {"id", "enterprise_id", "role_id", "member_id", "sort_order"} <= set(cols)
    uniques = [c for c in EmergencyOrgAssignment.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert any({col.name for col in u.columns} == {"role_id", "member_id"} for u in uniques)


def test_member_position_metadata():
    assert MemberPosition.__tablename__ == "member_positions"
    cols = MemberPosition.__table__.columns
    assert {"id", "enterprise_id", "member_id", "org_node_id", "is_primary"} <= set(cols)
    index_names = {ix.name for ix in MemberPosition.__table__.indexes}
    assert "uq_member_positions_primary" in index_names


def test_member_position_foreign_keys_cascade():
    """任职表的成员外键必须级联删除，避免成员删除后留下孤儿任职。"""
    fks = {
        fk.column.table.name: fk.ondelete
        for fk in MemberPosition.__table__.columns["member_id"].foreign_keys
    }
    assert fks == {"enterprise_members": "CASCADE"}
    ent_fks = {
        fk.column.table.name: fk.ondelete
        for fk in MemberPosition.__table__.columns["enterprise_id"].foreign_keys
    }
    assert ent_fks == {"enterprises": "CASCADE"}
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py -q`
预期：FAIL，`ModuleNotFoundError: No module named 'app.models.emergency_org'`

- [ ] **步骤 3：编写迁移脚本**

```sql
-- backend/db_migration_20260918_emergency_org_split.sql
-- 组织架构与应急组织拆分：应急组织三张表 + 成员任职表。全部幂等，可重复执行。

CREATE TABLE IF NOT EXISTS emergency_org_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    parent_id UUID NULL REFERENCES emergency_org_units(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    duties TEXT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_units_ent
    ON emergency_org_units(enterprise_id, parent_id, sort_order);

CREATE TABLE IF NOT EXISTS emergency_org_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    unit_id UUID NOT NULL REFERENCES emergency_org_units(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    duties TEXT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_roles_unit
    ON emergency_org_roles(unit_id, sort_order);

CREATE TABLE IF NOT EXISTS emergency_org_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES emergency_org_roles(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES enterprise_members(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (role_id, member_id)
);
CREATE INDEX IF NOT EXISTS idx_emergency_org_assignments_role
    ON emergency_org_assignments(role_id);
CREATE INDEX IF NOT EXISTS idx_emergency_org_assignments_member
    ON emergency_org_assignments(member_id);

CREATE TABLE IF NOT EXISTS member_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    member_id UUID NOT NULL REFERENCES enterprise_members(id) ON DELETE CASCADE,
    org_node_id VARCHAR(64) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (member_id, org_node_id)
);
CREATE INDEX IF NOT EXISTS idx_member_positions_member ON member_positions(member_id);
CREATE INDEX IF NOT EXISTS idx_member_positions_node ON member_positions(org_node_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_member_positions_primary
    ON member_positions(member_id) WHERE is_primary;
```

- [ ] **步骤 4：编写模型**

```python
# backend/app/models/emergency_org.py
"""应急组织：应急指挥部/应急小组（units）、组内角色（roles）、人员指派（assignments）。

与公司组织架构（enterprises.org_structure + enterprise_members）完全分离：
应急角色只引用成员 id，不引用公司组织节点，避免一人多岗/一人多任互相限制。
"""

from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmergencyOrgUnit(Base):
    __tablename__ = "emergency_org_units"
    __table_args__ = (
        Index("idx_emergency_org_units_ent", "enterprise_id", "parent_id", "sort_order"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("sort_order", 0)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("emergency_org_units.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    duties: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmergencyOrgRole(Base):
    __tablename__ = "emergency_org_roles"
    __table_args__ = (
        Index("idx_emergency_org_roles_unit", "unit_id", "sort_order"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("sort_order", 0)
        kwargs.setdefault("is_required", False)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("emergency_org_units.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    duties: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmergencyOrgAssignment(Base):
    __tablename__ = "emergency_org_assignments"
    __table_args__ = (
        Index("idx_emergency_org_assignments_role", "role_id"),
        Index("idx_emergency_org_assignments_member", "member_id"),
        Index("uq_emergency_org_assignments_role_member", "role_id", "member_id", unique=True),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("sort_order", 0)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("emergency_org_roles.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprise_members.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

在 `backend/app/models/enterprise_org.py` 末尾追加（唯一约束用唯一索引表达，与文件内既有的部分唯一索引风格一致）：

```python
class MemberPosition(Base):
    """成员任职关系：一人可挂多个组织节点（主岗唯一 + 若干兼岗）。

    enterprise_members.org_node_id 保留为主岗镜像列，由服务层同步维护，
    使只认主岗的既有消费方（隐患报表部门列等）零改动。
    """

    __tablename__ = "member_positions"
    __table_args__ = (
        Index("uq_member_positions_member_node", "member_id", "org_node_id", unique=True),
        Index(
            "uq_member_positions_primary",
            "member_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("is_primary", False)
        super().__init__(**kwargs)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("enterprise_members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_node_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

同时把该文件首行 import 补全为：`from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text, func`（`text` 原已导入，确认存在即可）。

注意：测试里断言的是「唯一约束」`UniqueConstraint`，而上面用唯一索引实现。因此把 `test_emergency_org_assignment_metadata` 的断言改为检查索引：

```python
def test_emergency_org_assignment_metadata():
    assert EmergencyOrgAssignment.__tablename__ == "emergency_org_assignments"
    cols = EmergencyOrgAssignment.__table__.columns
    assert {"id", "enterprise_id", "role_id", "member_id", "sort_order"} <= set(cols)
    unique_idx = [ix for ix in EmergencyOrgAssignment.__table__.indexes if ix.unique]
    assert any({c.name for c in ix.columns} == {"role_id", "member_id"} for ix in unique_idx)
```

- [ ] **步骤 5：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py -q`
预期：PASS（5 passed）

- [ ] **步骤 6：应用迁移并验证幂等**

运行：
```bash
docker restart emergency-plan-backend
sleep 12
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "\dt emergency_org_*"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "\d member_positions"
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "select script_name from schema_migrations where script_name like '%emergency_org_split%';"
```
预期：4 张表存在；`schema_migrations` 有 1 条 `db_migration_20260918_emergency_org_split.sql` 记录；`uq_member_positions_primary` 为部分唯一索引（`WHERE is_primary`）。再 `docker restart emergency-plan-backend` 一次，记录仍为 1 条（幂等）。

- [ ] **步骤 7：Commit**

```bash
git add backend/db_migration_20260918_emergency_org_split.sql backend/app/models/emergency_org.py backend/app/models/enterprise_org.py backend/tests/test_emergency_org.py
git commit -m "feat(org): 应急组织三表与成员任职表迁移与模型"
```

---

## 任务 2：通用组织树校验抽出

**文件：**
- 创建：`backend/app/services/org_tree_validate.py`
- 修改：`backend/app/services/enterprise_org_service.py:26-68`（`validate_org_tree` 改为委托）
- 测试：`backend/tests/test_emergency_org.py`

- [ ] **步骤 1：编写失败的测试**

```python
# 追加到 backend/tests/test_emergency_org.py
from app.services.org_tree_validate import (
    validate_tree,
    validate_emergency_units,
)


def test_validate_tree_rejects_cycle():
    nodes = [
        {"id": "a", "type": "dept", "name": "A", "parent_id": "b", "members": []},
        {"id": "b", "type": "dept", "name": "B", "parent_id": "a", "members": []},
    ]
    errors = validate_tree(nodes, allow_types={"dept", "team", "position"}, id_field="id", parent_field="parent_id")
    assert any("循环引用" in e for e in errors)


def test_validate_tree_rejects_missing_parent_and_empty_name():
    nodes = [{"id": "a", "type": "dept", "name": "  ", "parent_id": "ghost", "members": []}]
    errors = validate_tree(nodes, allow_types={"dept"}, id_field="id", parent_field="parent_id")
    assert any("名称不能为空" in e for e in errors)
    assert any("parent 不存在" in e for e in errors)


def test_validate_emergency_units_rejects_duplicate_role_name_and_bad_member():
    units = [
        {"id": "u1", "parent_id": None, "name": "应急指挥部", "roles": [
            {"id": "r1", "name": "总指挥", "member_ids": ["m1"]},
            {"id": "r2", "name": "总指挥", "member_ids": []},
        ]},
        {"id": "u2", "parent_id": "u1", "name": "抢险救灾组", "roles": [
            {"id": "r3", "name": "组长", "member_ids": ["m1", "m1", "outsider"]},
        ]},
    ]
    errors = validate_emergency_units(units, known_member_ids={"m1"})
    assert any("角色名重复" in e for e in errors)
    assert any("重复指派" in e for e in errors)
    assert any("不属于本企业" in e for e in errors)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py -q`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.org_tree_validate'`

- [ ] **步骤 3：编写通用校验**

```python
# backend/app/services/org_tree_validate.py
"""组织树通用校验：公司组织架构（dept/team/position）与应急组织（unit/role）共用。

从 enterprise_org_service.validate_org_tree 抽出，避免应急组织再抄一份规则。
"""

from typing import Iterable


def validate_tree(
    nodes: list,
    allow_types: set[str] | None,
    id_field: str = "id",
    parent_field: str = "parent_id",
    name_field: str = "name",
    require_members: bool = True,
) -> list[str]:
    """校验扁平树：id 唯一、name 非空、parent 存在、无自环与环、type 合法、members 为数组且成员有姓名。

    allow_types 为 None 时跳过 type 校验（应急组织不区分类型）。
    require_members 为 False 时跳过 members 校验（应急单元用 roles 承载成员）。
    """
    errors: list[str] = []
    ids = [n.get(id_field) for n in nodes if isinstance(n, dict)]
    by_id = {n.get(id_field): n for n in nodes if isinstance(n, dict) and n.get(id_field)}
    seen: set[str] = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"节点 {i + 1} 必须是对象")
            continue
        nid = n.get(id_field)
        if not nid:
            errors.append(f"节点 {i + 1} 缺少 {id_field}")
            continue
        if nid in seen:
            errors.append(f"节点 id 重复: {nid}")
        seen.add(nid)
        if allow_types is not None and n.get("type") not in allow_types:
            errors.append(f"节点 {nid} type 非法: {n.get('type')}")
        if not isinstance(n.get(name_field), str) or not str(n.get(name_field)).strip():
            errors.append(f"节点 {nid} 名称不能为空")
        parent = n.get(parent_field)
        if parent is not None and parent not in ids:
            errors.append(f"节点 {nid} parent 不存在: {parent}")
        elif parent == nid:
            errors.append(f"节点 {nid} 不能以自身为父节点")
        elif parent is not None:
            cur = parent
            walked: set[str] = set()
            while cur in by_id and cur not in walked:
                if cur == nid:
                    errors.append(f"节点 {nid} 存在循环引用")
                    break
                walked.add(cur)
                cur = by_id[cur].get(parent_field)
        if not require_members:
            continue
        members = n.get("members")
        if not isinstance(members, list):
            errors.append(f"节点 {nid} members 必须为数组")
        else:
            for m in members:
                if not isinstance(m, dict):
                    errors.append(f"节点 {nid} 存在非法成员")
                elif not isinstance(m.get("name"), str) or not m.get("name").strip():
                    errors.append(f"节点 {nid} 存在无姓名成员")
    return errors


def validate_emergency_units(units: Iterable[dict], known_member_ids: set[str]) -> list[str]:
    """校验应急组织：单元树规则 + 同单元角色名唯一 + 角色内成员不重复且属于本企业。"""
    unit_list = list(units)
    errors = validate_tree(
        unit_list, allow_types=None, id_field="id", parent_field="parent_id", require_members=False
    )
    for u in unit_list:
        if not isinstance(u, dict):
            continue
        uid = u.get("id")
        roles = u.get("roles")
        if not isinstance(roles, list):
            errors.append(f"单元 {uid} roles 必须为数组")
            continue
        seen_role_names: set[str] = set()
        for r in roles:
            if not isinstance(r, dict):
                errors.append(f"单元 {uid} 存在非法角色")
                continue
            rid = r.get("id")
            name = str(r.get("name") or "").strip()
            if not name:
                errors.append(f"角色 {rid} 名称不能为空")
            elif name in seen_role_names:
                errors.append(f"单元 {uid} 角色名重复: {name}")
            seen_role_names.add(name)
            member_ids = r.get("member_ids")
            if not isinstance(member_ids, list):
                errors.append(f"角色 {rid} member_ids 必须为数组")
                continue
            if len(set(member_ids)) != len(member_ids):
                errors.append(f"角色 {rid} 存在重复指派")
            for mid in member_ids:
                if mid not in known_member_ids:
                    errors.append(f"角色 {rid} 成员不属于本企业或已停用: {mid}")
    return errors
```

- [ ] **步骤 4：让既有校验委托通用实现**

把 `backend/app/services/enterprise_org_service.py` 中的 `validate_org_tree` 整体替换为：

```python
def validate_org_tree(nodes: list) -> list[str]:
    """校验公司组织树（规则见 org_tree_validate.validate_tree）。"""
    return validate_tree(nodes, allow_types=ORG_TYPES)
```

并在该文件 import 区加入：`from app.services.org_tree_validate import validate_tree`

- [ ] **步骤 5：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py backend/tests/test_enterprise_org.py -q`
预期：全部 PASS（原 `test_enterprise_org.py` 中针对 `validate_org_tree` 的既有用例同步通过，证明抽出未改变行为）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/org_tree_validate.py backend/app/services/enterprise_org_service.py backend/tests/test_emergency_org.py
git commit -m "refactor(org): 抽出通用组织树校验供公司树与应急组织复用"
```

---

## 任务 3：成员任职服务（一人多岗）

**文件：**
- 创建：`backend/app/services/member_position_service.py`
- 测试：`backend/tests/test_member_positions.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_member_positions.py
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.member_position_service import (
    sync_member_primary_node,
    sync_member_positions,
)


def _member(mid: str, node_id: str | None = None):
    return SimpleNamespace(id=mid, org_node_id=node_id, enterprise_id="e1")


@pytest.mark.asyncio
async def test_sync_member_positions_writes_all_and_mirrors_primary():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    member = _member("m1")
    await sync_member_positions(
        db, member, primary_node_id="n1", extra_node_ids=["n2", "n2", "n1"]
    )
    # 写库调用：先删旧任职，再插入去重后的 (主岗 + 兼岗)
    sql_texts = [str(c.args[0]) for c in db.execute.await_args_list]
    assert any("DELETE FROM member_positions" in s for s in sql_texts)
    insert_calls = [c for c in db.execute.await_args_list if "INSERT INTO member_positions" in str(c.args[0])]
    assert len(insert_calls) == 2
    assert insert_calls[0].args[1] == {"member_id": "m1", "ent": "e1", "node": "n1", "primary": True}
    assert insert_calls[1].args[1] == {"member_id": "m1", "ent": "e1", "node": "n2", "primary": False}
    # 主岗镜像列同步
    assert member.org_node_id == "n1"


@pytest.mark.asyncio
async def test_sync_member_primary_node_clears_when_none():
    db = AsyncMock()
    db.execute.return_value = MagicMock()
    member = _member("m1", node_id="n1")
    await sync_member_primary_node(db, member, None)
    assert member.org_node_id is None


@pytest.mark.asyncio
async def test_positions_for_members_groups_by_member_id():
    from app.services.member_position_service import positions_by_member
    db = AsyncMock()
    rows = [("m1", "n1", True), ("m1", "n2", False), ("m2", "n3", True)]
    db.execute.return_value = MagicMock(all=lambda: rows)
    out = await positions_by_member(db, "e1", ["m1", "m2"])
    assert out["m1"] == [{"org_node_id": "n1", "is_primary": True}, {"org_node_id": "n2", "is_primary": False}]
    assert out["m2"] == [{"org_node_id": "n3", "is_primary": True}]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_member_positions.py -q`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.member_position_service'`

- [ ] **步骤 3：编写服务**

```python
# backend/app/services/member_position_service.py
"""成员任职服务：一人多岗的唯一写入口。

约定：enterprise_members.org_node_id 始终等于 member_positions 中 is_primary 的那条，
由本模块在每次写入后同步，供只认主岗的既有消费方（隐患报表部门列等）继续工作。
"""

from typing import Iterable, Optional

from sqlalchemy import text


async def sync_member_positions(
    db,
    member,
    primary_node_id: Optional[str],
    extra_node_ids: Optional[Iterable[str]] = None,
) -> None:
    """整体替换某成员的任职：primary 为主岗，extra 为兼岗（自动去重、去主岗重复）。"""
    await db.execute(
        text("DELETE FROM member_positions WHERE member_id = :member_id"),
        {"member_id": member.id},
    )
    ordered: list[tuple[str, bool]] = []
    if primary_node_id:
        ordered.append((primary_node_id, True))
    seen = {primary_node_id} if primary_node_id else set()
    for node_id in extra_node_ids or []:
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        ordered.append((node_id, False))
    for node_id, is_primary in ordered:
        await db.execute(
            text(
                "INSERT INTO member_positions (enterprise_id, member_id, org_node_id, is_primary) "
                "VALUES (:ent, :member_id, :node, :primary)"
            ),
            {"member_id": member.id, "ent": member.enterprise_id, "node": node_id, "primary": is_primary},
        )
    member.org_node_id = primary_node_id


async def sync_member_primary_node(db, member, node_id: Optional[str]) -> None:
    """仅改主岗时复用整体替换（保留兼岗需调用方传入完整 extra 列表则用 sync_member_positions）。"""
    await sync_member_positions(db, member, node_id)


async def positions_by_member(db, enterprise_id: str, member_ids: list[str]) -> dict[str, list[dict]]:
    """批量取任职，按 member_id 分组，供列表接口一次查询避免 N+1。"""
    if not member_ids:
        return {}
    rows = (
        await db.execute(
            text(
                "SELECT member_id, org_node_id, is_primary FROM member_positions "
                "WHERE enterprise_id = :ent AND member_id = ANY(:ids) "
                "ORDER BY is_primary DESC, created_at"
            ),
            {"ent": enterprise_id, "ids": list(member_ids)},
        )
    ).all()
    out: dict[str, list[dict]] = {}
    for member_id, org_node_id, is_primary in rows:
        out.setdefault(str(member_id), []).append(
            {"org_node_id": org_node_id, "is_primary": bool(is_primary)}
        )
    return out
```

注意：`member_positions.member_id` 是 UUID 列，`:ids` 传字符串列表时 asyncpg 需要显式类型。若运行报 `invalid input for query argument`，把查询改为 `WHERE member_id::text = ANY(:ids)`，并在实现时同步修改测试桩（测试只断言 SQL 文本包含 `member_positions`，不受影响）。

- [ ] **步骤 4：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_member_positions.py -q`
预期：PASS（3 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/member_position_service.py backend/tests/test_member_positions.py
git commit -m "feat(org): 成员任职服务与主岗镜像同步"
```

---

## 任务 4：应急组织服务（纯函数 + 读写编排）

**文件：**
- 创建：`backend/app/services/emergency_org_service.py`
- 测试：`backend/tests/test_emergency_org.py`

- [ ] **步骤 1：编写失败的测试**

```python
# 追加到 backend/tests/test_emergency_org.py
from fastapi import HTTPException

from app.services.emergency_org_service import (
    build_legacy_groups,
    flatten_units,
    save_emergency_org,
)


def test_flatten_units_remaps_ids_and_parents():
    units = [
        {"id": "u1", "name": "应急组织机构", "roles": []},
        {"id": "u2", "parent_id": "u1", "name": "应急指挥部", "roles": [
            {"id": "r1", "name": "总指挥", "is_required": True, "member_ids": ["m1", "m2"]}]},
    ]
    unit_rows, role_rows, assignment_rows = flatten_units(units)
    assert len(unit_rows) == 2
    assert len(role_rows) == 1
    assert len(assignment_rows) == 2
    # 入参 id 不是 UUID，落库必须换成新 UUID 并重挂 parent
    assert unit_rows[0]["id"] != "u1"
    assert unit_rows[1]["parent_id"] == unit_rows[0]["id"]
    assert role_rows[0]["unit_id"] == unit_rows[1]["id"]
    assert role_rows[0]["is_required"] is True
    assert assignment_rows[0]["role_id"] == role_rows[0]["id"]
    assert assignment_rows[0]["member_id"] == "m1"
    assert assignment_rows[1]["sort_order"] == 1


def test_flatten_units_root_parent_is_none():
    unit_rows, role_rows, assignment_rows = flatten_units([{"id": "u1", "name": "应急组织机构"}])
    assert unit_rows[0]["parent_id"] is None
    assert unit_rows[0]["name"] == "应急组织机构"
    assert unit_rows[0]["sort_order"] == 0
    assert role_rows == []
    assert assignment_rows == []


def test_build_legacy_groups_maps_names_and_roles():
    units = [
        {"id": "u1", "parent_id": None, "name": "应急组织机构", "roles": []},
        {"id": "u2", "parent_id": "u1", "name": "应急指挥部", "duties": "统一指挥现场处置",
         "roles": [{"name": "总指挥", "duties": "全面负责", "members": [
             {"name": "刘昕野", "position": "总经理", "phone": "13800000000"}]}]},
        {"id": "u3", "parent_id": "u1", "name": "抢险救灾组",
         "roles": [{"name": "组长", "members": [{"name": "赵志龙", "position": "项目总监"}]}]},
    ]
    groups = build_legacy_groups(units)
    assert [g["group_name"] for g in groups] == ["应急指挥部", "抢险救灾组"]
    assert groups[0]["group_key"] == "headquarters"
    assert groups[0]["responsibilities"] == "统一指挥现场处置"
    assert groups[0]["members"][0]["role"] == "chief"
    assert groups[0]["members"][0]["name"] == "刘昕野"
    assert groups[0]["members"][0]["responsibilities"] == "全面负责"
    assert groups[1]["group_key"] == "rescue"
    assert groups[1]["members"][0]["role"] == "leader"


@pytest.mark.asyncio
async def test_save_emergency_org_rejects_unknown_member():
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalars=lambda: MagicMock(all=lambda: ["m1"]))
    units = [{"id": "u1", "name": "应急指挥部", "roles": [
        {"id": "r1", "name": "总指挥", "member_ids": ["ghost"]}]}]
    with pytest.raises(HTTPException) as ei:
        await save_emergency_org(db, "e1", units)
    assert ei.value.status_code == 422
    assert "不属于本企业" in ei.value.detail
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py -q`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.emergency_org_service'`

- [ ] **步骤 3：编写服务**

```python
# backend/app/services/emergency_org_service.py
"""应急组织读写：整树覆盖保存 + 展开读取 + 旧分组格式兼容视图。

入参 id 由前端生成（可能不是 UUID），落库统一换新 UUID 并重挂 parent_id/role_id；
纯函数（flatten_units / build_legacy_groups）与 DB 编排分离，便于单测。
"""

from typing import Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.models.emergency_org import (
    EmergencyOrgAssignment,
    EmergencyOrgRole,
    EmergencyOrgUnit,
)
from app.models.enterprise_org import EnterpriseMember
from app.services.org_tree_validate import validate_emergency_units


# 预置名称 → 旧分组 key（与前端 PRESET_EMERGENCY_GROUPS 一致）
GROUP_KEY_BY_NAME = {
    "应急指挥部": "headquarters",
    "抢险救灾组": "rescue",
    "疏散引导组": "evacuation",
    "医疗救护组": "medical",
    "通讯联络组": "communication",
    "后勤保障组": "logistics",
}

# 角色名 → 旧成员 role 码
ROLE_CODE_BY_NAME = {
    "总指挥": "chief",
    "副总指挥": "deputy",
    "组长": "leader",
    "副组长": "deputy_leader",
    "组员": "member",
    "成员": "member",
}


def flatten_units(units: Iterable[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """把带 roles/member_ids 的平铺单元拆成三张表的插入行，id 全部重新生成并重挂关系。"""
    unit_list = [u for u in units if isinstance(u, dict)]
    id_map: dict[str, str] = {}
    for ui, u in enumerate(unit_list):
        raw_id = str(u.get("id") or f"__idx_{ui}")
        id_map[raw_id] = str(uuid4())

    unit_rows: list[dict] = []
    role_rows: list[dict] = []
    assignment_rows: list[dict] = []
    for ui, u in enumerate(unit_list):
        raw_id = str(u.get("id") or f"__idx_{ui}")
        unit_id = id_map[raw_id]
        parent_raw = u.get("parent_id")
        unit_rows.append(
            {
                "id": unit_id,
                "parent_id": id_map.get(str(parent_raw)) if parent_raw else None,
                "name": str(u.get("name") or "").strip(),
                "duties": u.get("duties") or None,
                "sort_order": int(u.get("sort_order") if u.get("sort_order") is not None else ui),
            }
        )
        for ri, r in enumerate(u.get("roles") or []):
            if not isinstance(r, dict):
                continue
            role_id = str(uuid4())
            role_rows.append(
                {
                    "id": role_id,
                    "unit_id": unit_id,
                    "name": str(r.get("name") or "").strip(),
                    "duties": r.get("duties") or None,
                    "sort_order": int(r.get("sort_order") if r.get("sort_order") is not None else ri),
                    "is_required": bool(r.get("is_required")),
                }
            )
            for mi, mid in enumerate(r.get("member_ids") or []):
                assignment_rows.append({"role_id": role_id, "member_id": str(mid), "sort_order": mi})
    return unit_rows, role_rows, assignment_rows


def build_legacy_groups(units: Iterable[dict]) -> list[dict]:
    """应急组织 → 旧分组格式（GET /org-structure 兼容视图）。

    顶层单元（parent_id 为空）不输出，其直接子单元作为分组；
    分组角色下的成员摊平成 members 列表，role 用旧 role 码表达。
    """
    unit_list = [u for u in units if isinstance(u, dict)]
    groups: list[dict] = []
    for u in unit_list:
        if not u.get("parent_id"):
            continue
        members: list[dict] = []
        for r in u.get("roles") or []:
            if not isinstance(r, dict):
                continue
            role_name = str(r.get("name") or "").strip()
            for m in r.get("members") or []:
                if not isinstance(m, dict) or not m.get("name"):
                    continue
                members.append(
                    {
                        "name": m.get("name"),
                        "role": ROLE_CODE_BY_NAME.get(role_name, "member"),
                        "position": m.get("position") or "",
                        "phone": m.get("phone") or "",
                        "responsibilities": r.get("duties") or "",
                    }
                )
        name = str(u.get("name") or "应急小组")
        groups.append(
            {
                "group_key": GROUP_KEY_BY_NAME.get(name, name),
                "group_name": name,
                "responsibilities": u.get("duties") or "",
                "members": members,
            }
        )
    return groups


async def _known_member_ids(db, enterprise_id: str) -> set[str]:
    rows = (
        await db.execute(
            select(EnterpriseMember.id).where(
                EnterpriseMember.enterprise_id == enterprise_id,
                EnterpriseMember.enabled.is_(True),
            )
        )
    ).scalars().all()
    return {str(r) for r in rows}


async def load_emergency_org(db, enterprise_id: str) -> list[dict]:
    """整树读取：平铺 units（按 sort_order）→ 挂 roles → 挂成员简要信息。"""
    unit_rows = (
        await db.execute(
            select(EmergencyOrgUnit)
            .where(EmergencyOrgUnit.enterprise_id == enterprise_id)
            .order_by(EmergencyOrgUnit.sort_order)
        )
    ).scalars().all()
    role_rows = (
        await db.execute(
            select(EmergencyOrgRole)
            .where(EmergencyOrgRole.enterprise_id == enterprise_id)
            .order_by(EmergencyOrgRole.sort_order)
        )
    ).scalars().all()
    assignment_rows = (
        await db.execute(
            select(EmergencyOrgAssignment, EnterpriseMember)
            .join(EnterpriseMember, EnterpriseMember.id == EmergencyOrgAssignment.member_id)
            .where(EmergencyOrgAssignment.enterprise_id == enterprise_id)
            .order_by(EmergencyOrgAssignment.sort_order)
        )
    ).all()

    roles_by_unit: dict[str, list[dict]] = {}
    role_index: dict[str, dict] = {}
    for r in role_rows:
        item = {
            "id": r.id,
            "name": r.name,
            "duties": r.duties,
            "sort_order": r.sort_order,
            "is_required": r.is_required,
            "member_ids": [],
            "members": [],
        }
        role_index[r.id] = item
        roles_by_unit.setdefault(r.unit_id, []).append(item)
    for a, m in assignment_rows:
        role = role_index.get(a.role_id)
        if role is None:
            continue
        role["member_ids"].append(a.member_id)
        role["members"].append(
            {
                "id": m.id,
                "name": m.name,
                "phone": m.phone,
                "position": m.position,
                "email": m.email,
                "org_node_id": m.org_node_id,
            }
        )
    return [
        {
            "id": u.id,
            "parent_id": u.parent_id,
            "name": u.name,
            "duties": u.duties,
            "sort_order": u.sort_order,
            "roles": roles_by_unit.get(u.id, []),
        }
        for u in unit_rows
    ]


async def save_emergency_org(db, enterprise_id: str, units: list) -> list[dict]:
    """整树覆盖保存：校验 → 清空重建 → 返回新树。校验失败抛 422。"""
    errors = validate_emergency_units(units, known_member_ids=await _known_member_ids(db, enterprise_id))
    if errors:
        raise HTTPException(422, "；".join(errors))
    unit_rows, role_rows, assignment_rows = flatten_units(units)
    await db.execute(
        delete(EmergencyOrgAssignment).where(EmergencyOrgAssignment.enterprise_id == enterprise_id)
    )
    await db.execute(delete(EmergencyOrgRole).where(EmergencyOrgRole.enterprise_id == enterprise_id))
    await db.execute(delete(EmergencyOrgUnit).where(EmergencyOrgUnit.enterprise_id == enterprise_id))
    if unit_rows:
        await db.execute(
            EmergencyOrgUnit.__table__.insert(),
            [{"enterprise_id": enterprise_id, **row} for row in unit_rows],
        )
    if role_rows:
        await db.execute(
            EmergencyOrgRole.__table__.insert(),
            [{"enterprise_id": enterprise_id, **row} for row in role_rows],
        )
    if assignment_rows:
        await db.execute(
            EmergencyOrgAssignment.__table__.insert(),
            [{"enterprise_id": enterprise_id, **row} for row in assignment_rows],
        )
    await db.commit()
    return await load_emergency_org(db, enterprise_id)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py -q`
预期：PASS（9 passed）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/emergency_org_service.py backend/tests/test_emergency_org.py
git commit -m "feat(org): 应急组织整树读写服务与旧分组兼容视图"
```

---

## 任务 5：应急组织 API 与路由注册

**文件：**
- 创建：`backend/app/schemas/emergency_org.py`
- 创建：`backend/app/routers/emergency_org.py`
- 修改：`backend/app/main.py:15`、`:262`
- 测试：`backend/tests/test_emergency_org.py`

- [ ] **步骤 1：编写失败的测试**

```python
# 追加到 backend/tests/test_emergency_org.py
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import emergency_org as emergency_org_router


def _api_client(db):
    app = FastAPI()
    app.include_router(emergency_org_router.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def test_emergency_org_get_returns_404_when_enterprise_missing():
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)
    resp = _api_client(db).get("/api/v1/enterprises/e1/emergency-org")
    assert resp.status_code == 404


def test_emergency_org_routes_registered_in_main():
    from app.main import app as main_app
    paths = {r.path for r in main_app.routes}
    assert "/api/v1/enterprises/{enterprise_id}/emergency-org" in paths


def test_emergency_org_get_returns_empty_list_for_new_enterprise():
    """企业存在但尚无应急组织时返回空数组（前端据此显示空态）。"""
    ent = SimpleNamespace(id="e1")
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # units
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # roles
        MagicMock(all=lambda: []),                             # assignments
    ]
    resp = _api_client(db).get("/api/v1/enterprises/e1/emergency-org")
    assert resp.status_code == 200
    assert resp.json()["data"] == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py -q`
预期：FAIL，`ModuleNotFoundError: No module named 'app.routers.emergency_org'`

- [ ] **步骤 3：编写 schema**

```python
# backend/app/schemas/emergency_org.py
"""应急组织接口契约。字段名与前端 types/emergencyOrg.ts 一一对应。"""

from pydantic import BaseModel, Field


class EmergencyRoleIn(BaseModel):
    id: str | None = None
    name: str
    duties: str | None = None
    sort_order: int = 0
    is_required: bool = False
    member_ids: list[str] = Field(default_factory=list)


class EmergencyUnitIn(BaseModel):
    id: str | None = None
    parent_id: str | None = None
    name: str
    duties: str | None = None
    sort_order: int = 0
    roles: list[EmergencyRoleIn] = Field(default_factory=list)


class EmergencyOrgUpdate(BaseModel):
    units: list[EmergencyUnitIn] = Field(default_factory=list)


class EmergencyMemberBrief(BaseModel):
    id: str
    name: str | None = None
    phone: str | None = None
    position: str | None = None
    email: str | None = None
    org_node_id: str | None = None


class EmergencyRoleOut(EmergencyRoleIn):
    id: str
    member_ids: list[str] = Field(default_factory=list)
    members: list[EmergencyMemberBrief] = Field(default_factory=list)


class EmergencyUnitOut(EmergencyUnitIn):
    id: str
    roles: list[EmergencyRoleOut] = Field(default_factory=list)
```

- [ ] **步骤 4：编写 router**

```python
# backend/app/routers/emergency_org.py
"""应急组织整树读写。与 /enterprises/{id}/org/nodes（公司组织树）并列且互不影响。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.schemas.common import ApiResponse
from app.schemas.emergency_org import EmergencyOrgUpdate, EmergencyUnitOut
from app.services.emergency_org_service import load_emergency_org, save_emergency_org

router = APIRouter(prefix="/enterprises/{enterprise_id}/emergency-org", tags=["Emergency Org"])


async def _get_ent(enterprise_id: str, user_id: str, db: AsyncSession) -> Enterprise:
    """按 id 取企业并归属校验；非法 UUID 等数据层错误统一按 404 处理。"""
    try:
        ent = (
            await db.execute(
                select(Enterprise).where(
                    Enterprise.id == enterprise_id, Enterprise.user_id == user_id
                )
            )
        ).scalar_one_or_none()
    except Exception as exc:
        raise HTTPException(404, "企业不存在") from exc
    if not ent:
        raise HTTPException(404, "企业不存在")
    return ent


@router.get("", response_model=ApiResponse[list[EmergencyUnitOut]])
async def get_emergency_org(
    enterprise_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    return ApiResponse(data=await load_emergency_org(db, enterprise_id))


@router.put("", response_model=ApiResponse[list[EmergencyUnitOut]])
async def put_emergency_org(
    enterprise_id: str,
    data: EmergencyOrgUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_ent(enterprise_id, current_user.id, db)
    units = [u.model_dump() for u in data.units]
    return ApiResponse(data=await save_emergency_org(db, enterprise_id, units))
```

在 `backend/app/main.py` 的 router import 行末尾加入 `emergency_org`，并在 `app.include_router(enterprise_org.router, prefix="/api/v1")` 之后新增一行：

```python
app.include_router(emergency_org.router, prefix="/api/v1")
```

- [ ] **步骤 5：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py -q`
预期：PASS（12 passed）

- [ ] **步骤 6：真机连通验证**

运行：
```bash
docker restart emergency-plan-backend
sleep 12
docker exec emergency-plan-db psql -U postgres -d emergency_plan -t -c "select id from enterprises where name='西安宝岳空间科技有限公司';"
```
用返回的 id 调接口（token 从浏览器复用或不校验时直接 curl 容器内）：
```bash
docker exec emergency-plan-backend python -c "import json,urllib.request;print(urllib.request.urlopen('http://localhost:8000/api/v1/enterprises/<id>/emergency-org').read()[:200])"
```
预期：返回 `{"code":0,...,"data":[]}`（迁移前应急组织为空，属正常）。

- [ ] **步骤 7：Commit**

```bash
git add backend/app/schemas/emergency_org.py backend/app/routers/emergency_org.py backend/app/main.py backend/tests/test_emergency_org.py
git commit -m "feat(org): 应急组织整树 API 与路由注册"
```

---

## 任务 6：公司成员接口支持多任职

**文件：**
- 修改：`backend/app/routers/enterprise_org.py:200-300`（成员 CRUD）、`:405-437`（Excel 导入）、`:441-470`（可指派列表）
- 修改：`backend/app/schemas/enterprise_org.py`
- 测试：`backend/tests/test_member_positions.py`

- [ ] **步骤 1：编写失败的测试**

```python
# 追加到 backend/tests/test_member_positions.py
from app.schemas.enterprise_org import MemberCreate, MemberResponse, MemberUpdate


def test_member_schema_accepts_extra_node_ids():
    payload = MemberCreate(name="张三", org_node_id="n1", extra_node_ids=["n2", "n3"])
    assert payload.org_node_id == "n1"
    assert payload.extra_node_ids == ["n2", "n3"]


def test_member_update_accepts_extra_node_ids():
    payload = MemberUpdate(extra_node_ids=["n5"])
    assert payload.extra_node_ids == ["n5"]


def test_member_response_exposes_positions():
    resp = MemberResponse(
        id="m1", enterprise_id="e1", role="member", enabled=True,
        org_node_id="n1", positions=[{"org_node_id": "n2", "is_primary": False}],
    )
    assert resp.positions[0]["org_node_id"] == "n2"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_member_positions.py -q`
预期：FAIL，`TypeError`/`ValidationError`（`extra_node_ids`、`positions` 字段不存在）

- [ ] **步骤 3：扩展 schema**

在 `backend/app/schemas/enterprise_org.py` 中：

```python
class MemberCreate(BaseModel):
    user_id: str | None = None
    name: str = ""
    phone: str | None = None
    email: str | None = None
    org_node_id: str | None = None
    extra_node_ids: list[str] = Field(default_factory=list)  # 兼岗节点
    position: str | None = None
    role: Literal["enterprise_admin", "team_leader", "member"] = "member"


class MemberUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    org_node_id: str | None = None
    extra_node_ids: list[str] | None = None  # None 表示不改任职
    position: str | None = None
    role: Literal["enterprise_admin", "team_leader", "member"] | None = None
    enabled: bool | None = None


class MemberResponse(BaseModel):
    id: str
    enterprise_id: str
    user_id: str | None = None
    email: str | None = None
    name: str | None = None
    phone: str | None = None
    org_node_id: str | None = None
    positions: list[dict] = Field(default_factory=list)  # [{org_node_id, is_primary}]
    position: str | None = None
    role: str
    enabled: bool
    model_config = {"from_attributes": True}
```

`Field` 已在该文件 import（`from pydantic import BaseModel, Field`），无需新增。

- [ ] **步骤 4：成员创建/编辑写入任职**

在 `backend/app/routers/enterprise_org.py` 的创建成员处理中，创建 `EnterpriseMember` 并 `db.flush()`（拿到 member.id）后插入：

```python
    await sync_member_positions(db, member, data.org_node_id, data.extra_node_ids)
```

编辑成员处理中，位置/任职相关字段更新后调用（仅当 `org_node_id` 或 `extra_node_ids` 有传入）：

```python
    if "org_node_id" in data.model_fields_set or data.extra_node_ids is not None:
        await sync_member_positions(
            db, member, member.org_node_id, data.extra_node_ids or []
        )
```

文件顶部 import 区加入：`from app.services.member_position_service import positions_by_member, sync_member_positions`

- [ ] **步骤 5：成员列表返回任职**

在 `list_members` 组装响应处，用一次批量查询填充 `positions`：

```python
    positions = await positions_by_member(db, enterprise_id, [m.id for m in rows])
    items = []
    for m in rows:
        item = MemberResponse.model_validate(m)
        item.positions = positions.get(m.id, [])
        items.append(item)
    return ApiResponse(data=items)
```

- [ ] **步骤 6：Excel 导入写任职**

在 `import_members` 把成员落库后（`db.flush()` 之后），对每条导入记录调用：

```python
        await sync_member_positions(db, member, team_id or dept_id, [])
```

- [ ] **步骤 7：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_member_positions.py backend/tests/test_enterprise_org.py -q`
预期：全部 PASS

- [ ] **步骤 8：Commit**

```bash
git add backend/app/schemas/enterprise_org.py backend/app/routers/enterprise_org.py backend/tests/test_member_positions.py
git commit -m "feat(org): 公司成员支持主岗与兼岗多任职"
```

---

## 任务 7：存量数据搬迁脚本

**文件：**
- 创建：`backend/scripts/migrate_emergency_org_split.py`
- 测试：`backend/tests/test_migrate_emergency_org_split.py`

- [ ] **步骤 1：编写失败的测试**

```python
# backend/tests/test_migrate_emergency_org_split.py
"""迁移脚本的纯函数部分：形态识别、树格式拆分、旧分组拆分。"""

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "migrate_emergency_org_split.py"
    spec = importlib.util.spec_from_file_location("migrate_emergency_org_split", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_classify_tree_shape():
    m = _load_module()
    nodes = [{"id": "preset-org-root", "type": "dept", "name": "应急组织机构", "parent_id": None}]
    assert m.classify_shape(nodes) == "tree"


def test_classify_group_shape():
    m = _load_module()
    nodes = [{"group_key": "headquarters", "group_name": "应急指挥部", "members": []}]
    assert m.classify_shape(nodes) == "groups"


def test_classify_none_for_company_only_tree():
    m = _load_module()
    nodes = [{"id": "node-1", "type": "dept", "name": "安全部", "parent_id": None}]
    assert m.classify_shape(nodes) == "none"


def test_split_tree_separates_emergency_and_company_nodes():
    m = _load_module()
    nodes = [
        {"id": "preset-org-root", "type": "dept", "name": "应急组织机构", "parent_id": None},
        {"id": "preset-headquarters", "type": "team", "name": "应急指挥部", "parent_id": "preset-org-root"},
        {"id": "preset-headquarters-0", "type": "position", "name": "总指挥", "parent_id": "preset-headquarters"},
        {"id": "node-1", "type": "dept", "name": "公司", "parent_id": None},
        {"id": "node-2", "type": "dept", "name": "安全部", "parent_id": "node-1"},
    ]
    emergency_nodes, company_nodes = m.split_tree(nodes)
    assert {n["id"] for n in emergency_nodes} == {
        "preset-org-root", "preset-headquarters", "preset-headquarters-0"
    }
    assert {n["id"] for n in company_nodes} == {"node-1", "node-2"}


def test_tree_to_units_keeps_dept_typed_child_as_group():
    """实测存在 type=dept 但语义是应急小组的子节点，按 parent 关系而非 type 判定分组。"""
    m = _load_module()
    emergency_nodes = [
        {"id": "preset-org-root", "type": "dept", "name": "应急组织机构", "parent_id": None},
        {"id": "node-5", "type": "dept", "name": "应急指挥部", "parent_id": "preset-org-root"},
        {"id": "preset-rescue", "type": "team", "name": "抢险救灾组", "parent_id": "preset-org-root"},
        {"id": "preset-rescue-0", "type": "position", "name": "组长", "parent_id": "preset-rescue"},
    ]
    units = m.tree_to_units(emergency_nodes)
    assert [u["name"] for u in units] == ["应急组织机构", "应急指挥部", "抢险救灾组"]
    assert units[0]["parent_id"] is None
    assert units[1]["parent_id"] == units[0]["id"]
    assert units[2]["roles"][0]["name"] == "组长"
    assert units[2]["roles"][0]["is_required"] is False


def test_tree_to_units_marks_required_commander_roles():
    m = _load_module()
    units = m.tree_to_units([
        {"id": "root", "type": "dept", "name": "应急组织机构", "parent_id": None},
        {"id": "hq", "type": "team", "name": "应急指挥部", "parent_id": "root"},
        {"id": "hq-0", "type": "position", "name": "总指挥", "parent_id": "hq"},
        {"id": "hq-1", "type": "position", "name": "副总指挥", "parent_id": "hq"},
        {"id": "hq-2", "type": "position", "name": "成员", "parent_id": "hq"},
    ])
    roles = {r["name"]: r["is_required"] for r in units[1]["roles"]}
    assert roles == {"总指挥": True, "副总指挥": True, "成员": False}


def test_groups_to_units_derives_roles_from_role_codes():
    m = _load_module()
    groups = [
        {"group_key": "headquarters", "group_name": "应急指挥部", "members": [
            {"name": "辛华", "role": "chief", "position": "总经理", "phone": "133"},
            {"name": "苏小芳", "role": "deputy", "position": "行政主管", "phone": "183"},
            {"name": "樊悦", "role": "member", "position": "前端开发", "phone": "183"},
        ]},
    ]
    units = m.groups_to_units(groups)
    assert units[0]["name"] == "应急组织机构"
    hq = units[1]
    assert hq["name"] == "应急指挥部"
    roles = {r["name"]: r for r in hq["roles"]}
    assert set(roles) == {"总指挥", "副总指挥", "组员"}
    assert roles["总指挥"]["is_required"] is True
    assert roles["总指挥"]["members"] == [
        {"name": "辛华", "position": "总经理", "phone": "133"}
    ]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_migrate_emergency_org_split.py -q`
预期：FAIL，脚本文件不存在

- [ ] **步骤 3：编写脚本（纯函数部分 + CLI 编排）**

```python
# backend/scripts/migrate_emergency_org_split.py
"""把混在 enterprises.org_structure 里的应急组织搬迁到应急组织表，并从公司树中摘除。

支持两种存量形态：
- tree：含 preset-org-root（或根节点名为「应急组织机构」）的组织树
- groups：旧分组格式 [{group_key, group_name, members:[{role,name,...}]}]

幂等：已搬迁（应急组织表已有数据且公司树无应急节点）的企业跳过；支持 --dry-run 只打印计划。
运行（仓库根目录）：
    backend\\.venv\\Scripts\\python.exe backend/scripts/migrate_emergency_org_split.py --dry-run
    backend\\.venv\\Scripts\\python.exe backend/scripts/migrate_emergency_org_split.py --apply
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models.emergency_org import (  # noqa: E402
    EmergencyOrgAssignment,
    EmergencyOrgRole,
    EmergencyOrgUnit,
)
from app.models.enterprise import Enterprise  # noqa: E402
from app.models.enterprise_org import EnterpriseMember  # noqa: E402
from app.services.emergency_org_service import flatten_units  # noqa: E402

EMERGENCY_ROOT_NAME = "应急组织机构"
REQUIRED_ROLE_NAMES = {"总指挥", "副总指挥"}
ROLE_NAME_BY_CODE = {"chief": "总指挥", "deputy": "副总指挥", "leader": "组长", "member": "组员"}


def classify_shape(nodes: list) -> str:
    """判定存量形态：tree（组织树）/ groups（旧分组）/ none（纯公司树或空）。"""
    items = [n for n in (nodes or []) if isinstance(n, dict)]
    if any(n.get("group_key") or n.get("group_name") for n in items):
        return "groups"
    if any(n.get("id") == "preset-org-root" for n in items):
        return "tree"
    if any(
        n.get("parent_id") in (None, "") and n.get("name") == EMERGENCY_ROOT_NAME for n in items
    ):
        return "tree"
    return "none"


def split_tree(nodes: list) -> tuple[list, list]:
    """按预置根节点把组织树切成（应急节点, 公司节点），公司节点保持原顺序与原 parent。"""
    items = [n for n in (nodes or []) if isinstance(n, dict)]
    root_ids = {
        n.get("id")
        for n in items
        if n.get("id") == "preset-org-root"
        or (n.get("parent_id") in (None, "") and n.get("name") == EMERGENCY_ROOT_NAME)
    }
    emergency_ids = set(root_ids)
    changed = True
    while changed:
        changed = False
        for n in items:
            if n.get("id") in emergency_ids:
                continue
            if n.get("parent_id") in emergency_ids:
                emergency_ids.add(n.get("id"))
                changed = True
    return (
        [n for n in items if n.get("id") in emergency_ids],
        [n for n in items if n.get("id") not in emergency_ids],
    )


def tree_to_units(emergency_nodes: list) -> list[dict]:
    """树格式 → 应急组织单元：根为顶层，根的直接子节点一律建为分组（不按 type 过滤），叶子岗位建为角色。"""
    items = [n for n in emergency_nodes if isinstance(n, dict)]
    by_id = {n.get("id"): n for n in items if n.get("id")}
    roots = [
        n for n in items
        if n.get("id") == "preset-org-root"
        or (n.get("parent_id") in (None, "") and n.get("name") == EMERGENCY_ROOT_NAME)
    ]
    if not roots:
        return []
    root = roots[0]
    root_id = root.get("id")
    units: list[dict] = [
        {"id": root_id, "parent_id": None, "name": root.get("name"), "duties": "应急组织总览", "roles": []}
    ]
    for child in [n for n in items if n.get("parent_id") == root_id]:
        roles = []
        for leaf in [n for n in items if n.get("parent_id") == child.get("id")]:
            name = str(leaf.get("name") or "")
            roles.append(
                {
                    "id": leaf.get("id"),
                    "name": name,
                    "duties": "",
                    "sort_order": 0,
                    "is_required": name in REQUIRED_ROLE_NAMES,
                    "members": [],
                }
            )
        units.append(
            {
                "id": child.get("id"),
                "parent_id": root_id,
                "name": child.get("name"),
                "duties": child.get("duties") or "",
                "roles": roles,
            }
        )
    return units


def groups_to_units(groups: list) -> list[dict]:
    """旧分组 → 应急组织单元：按成员 role 码派生角色，角色内聚合同一角色的成员。"""
    units: list[dict] = [
        {"id": "__root__", "parent_id": None, "name": EMERGENCY_ROOT_NAME, "duties": "应急组织总览", "roles": []}
    ]
    for gi, g in enumerate(groups):
        if not isinstance(g, dict):
            continue
        role_map: dict[str, dict] = {}
        for m in g.get("members") or []:
            if not isinstance(m, dict) or not m.get("name"):
                continue
            role_name = ROLE_NAME_BY_CODE.get(str(m.get("role") or "").strip(), "组员")
            role = role_map.setdefault(
                role_name,
                {
                    "id": f"__role_{gi}_{role_name}",
                    "name": role_name,
                    "duties": "",
                    "sort_order": len(role_map),
                    "is_required": role_name in REQUIRED_ROLE_NAMES,
                    "members": [],
                },
            )
            role["members"].append(
                {
                    "name": m.get("name"),
                    "position": m.get("position") or "",
                    "phone": m.get("phone") or "",
                }
            )
        units.append(
            {
                "id": f"__group_{gi}",
                "parent_id": "__root__",
                "name": g.get("group_name") or "应急小组",
                "duties": g.get("responsibilities") or "",
                "roles": list(role_map.values()),
            }
        )
    return units


async def _upsert_units(db, enterprise_id: str, units: list[dict]) -> dict:
    """写入应急组织三表。roles[].members 里的内嵌成员由调用方先解析成 member_id。"""
    unit_rows, role_rows, assignment_rows = flatten_units(units)
    if unit_rows:
        await db.execute(
            EmergencyOrgUnit.__table__.insert(),
            [{"enterprise_id": enterprise_id, **r} for r in unit_rows],
        )
    if role_rows:
        await db.execute(
            EmergencyOrgRole.__table__.insert(),
            [{"enterprise_id": enterprise_id, **r} for r in role_rows],
        )
    if assignment_rows:
        await db.execute(
            EmergencyOrgAssignment.__table__.insert(),
            [{"enterprise_id": enterprise_id, **r} for r in assignment_rows],
        )
    return {
        "units": len(unit_rows),
        "roles": len(role_rows),
        "assignments": len(assignment_rows),
    }


async def _known_members(db, enterprise_id: str) -> dict[str, str]:
    """返回 {(姓名, 电话): member_id} 与 {"name:姓名": member_id}，用于旧分组成员匹配去重。"""
    rows = (
        await db.execute(
            select(EnterpriseMember).where(EnterpriseMember.enterprise_id == enterprise_id)
        )
    ).scalars().all()
    index: dict[str, str] = {}
    for m in rows:
        if m.name:
            index[f"{m.name}|{m.phone or ''}"] = m.id
            index.setdefault(f"name:{m.name}", m.id)
    return index


async def migrate_one(db, ent: Enterprise, apply: bool) -> dict:
    """搬迁单个企业，返回统计。apply=False 只统计不写库。"""
    nodes = list(ent.org_structure or [])
    shape = classify_shape(nodes)
    if shape == "none":
        return {"name": ent.name, "shape": "none", "skipped": True}
    result: dict = {"name": ent.name, "shape": shape, "skipped": False}
    if shape == "tree":
        emergency_nodes, company_nodes = split_tree(nodes)
        units = tree_to_units(emergency_nodes)
        # 成员挂到岗位节点的关系：org_node_id → role.id
        members = (
            await db.execute(
                select(EnterpriseMember).where(EnterpriseMember.enterprise_id == ent.id)
            )
        ).scalars().all()
        member_ids_by_node: dict[str, list[str]] = {}
        for m in members:
            if m.org_node_id:
                member_ids_by_node.setdefault(m.org_node_id, []).append(m.id)
        for u in units:
            for r in u["roles"]:
                r["member_ids"] = member_ids_by_node.get(str(r.get("id")), [])
        result["company_nodes_left"] = len(company_nodes)
        result["migrated_member_ids"] = sorted(
            {mid for ids in member_ids_by_node.values() for mid in ids}
        )
    else:
        units = groups_to_units(nodes)
        created = await _ensure_group_members(db, ent.id, units, apply)
        result["created_members"] = created
        result["company_nodes_left"] = 0
    if apply:
        counters = await _upsert_units(db, ent.id, units)
        result.update(counters)
        if shape == "tree":
            ent.org_structure = company_nodes
            await db.execute(
                text("UPDATE enterprise_members SET org_node_id = NULL WHERE enterprise_id = :ent"),
                {"ent": ent.id},
            )
        else:
            ent.org_structure = []
        await db.execute(
            text(
                "INSERT INTO member_positions (enterprise_id, member_id, org_node_id, is_primary) "
                "SELECT enterprise_id, id, org_node_id, TRUE FROM enterprise_members "
                "WHERE enterprise_id = :ent AND org_node_id IS NOT NULL "
                "ON CONFLICT DO NOTHING"
            ),
            {"ent": ent.id},
        )
    return result


async def _ensure_group_members(db, enterprise_id: str, units: list[dict], apply: bool) -> int:
    """旧分组形态：内嵌成员按 (姓名|电话) 去重，缺失则新建 enterprise_members，并回填 member_ids。"""
    index = await _known_members(db, enterprise_id)
    created = 0
    for u in units:
        for r in u["roles"]:
            ids: list[str] = []
            for m in r.get("members") or []:
                key = f"{m['name']}|{m.get('phone') or ''}"
                member_id = index.get(key) or index.get(f"name:{m['name']}")
                if not member_id:
                    if not apply:
                        ids.append(f"__new__{key}")
                        created += 1
                        continue
                    member = EnterpriseMember(
                        enterprise_id=enterprise_id,
                        name=m["name"],
                        phone=m.get("phone") or None,
                        position=m.get("position") or None,
                        role="member",
                        enabled=True,
                    )
                    db.add(member)
                    await db.flush()
                    member_id = member.id
                    index[key] = member_id
                    index.setdefault(f"name:{m['name']}", member_id)
                    created += 1
                ids.append(member_id)
            r["member_ids"] = ids
            r.pop("members", None)
    return created


async def main(apply: bool) -> None:
    backup_dir = Path("output/migrations")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"org_split_{stamp}.json"
    async with async_session() as db:
        ents = (await db.execute(select(Enterprise))).scalars().all()
        backup = {e.id: (e.org_structure or []) for e in ents}
        backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"备份写入 {backup_path}")
        for ent in ents:
            stats = await migrate_one(db, ent, apply=apply)
            print(json.dumps(stats, ensure_ascii=False))
        if apply:
            await db.commit()
        else:
            await db.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="真正写库；缺省为 dry-run")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划（默认行为）")
    args = parser.parse_args()
    asyncio.run(main(apply=bool(args.apply and not args.dry_run)))
```

- [ ] **步骤 4：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_migrate_emergency_org_split.py -q`
预期：PASS（7 passed）

- [ ] **步骤 5：dry-run 核对真实库**

运行：`backend\.venv\Scripts\python.exe backend/scripts/migrate_emergency_org_split.py --dry-run`
预期输出四行统计，与规格 §7.3 表格一致：
- 西安宝岳空间科技有限公司：`shape=tree`、`company_nodes_left=11`、`migrated_member_ids` 3 个
- 延长壳牌石油有限公司（西安明光路加油站）：`shape=tree`、`company_nodes_left=0`
- 陕西宝岳测绘有限公司：`shape=groups`、`created_members=28`、`company_nodes_left=0`
- 两次编辑测试：`shape=groups`

- [ ] **步骤 6：正式搬迁并连跑两次验证幂等**

运行：
```bash
backend\.venv\Scripts\python.exe backend/scripts/migrate_emergency_org_split.py --apply
docker exec emergency-plan-db psql -U postgres -d emergency_plan -c "select e.name, (select count(*) from emergency_org_units u where u.enterprise_id=e.id) units, (select count(*) from emergency_org_roles r where r.enterprise_id=e.id) roles, (select count(*) from emergency_org_assignments a where a.enterprise_id=e.id) assigns from enterprises e order by 2 desc;"
```
预期：西安宝岳 `units=8 roles=18 assigns=3`（顶层 + 7 子单元）；延长壳牌 `units=7 roles=18 assigns=0`；陕西宝岳 `units=7 roles=? assigns=28`；其余为 0。再次执行 `--apply`，数字不变（幂等）。

- [ ] **步骤 7：Commit**

```bash
git add backend/scripts/migrate_emergency_org_split.py backend/tests/test_migrate_emergency_org_split.py
git commit -m "feat(org): 存量应急组织搬迁脚本（两种形态、幂等、可 dry-run）"
```

---

## 任务 8：预案侧切源（生成 / 章节自动填充 / 导出签署页）

**文件：**
- 修改：`backend/app/services/emergency_org_service.py`（新增消费方分组格式）
- 修改：`backend/app/routers/generation.py:406-480`、`:600-615`
- 修改：`backend/app/routers/sections.py:72-80`
- 修改：`backend/app/routers/export.py:282-292`、`:380`、`:354`、`:453`
- 修改：`backend/app/services/chat_dispatch.py:1092`
- 测试：`backend/tests/test_emergency_org.py`、`backend/tests/test_plan_autofill.py`

- [ ] **步骤 1：编写失败的测试**

```python
# 追加到 backend/tests/test_emergency_org.py
from app.services.emergency_org_service import build_groups_for_consumers


def test_build_groups_for_consumers_shape():
    units = [
        {"id": "u1", "parent_id": None, "name": "应急组织机构", "roles": []},
        {"id": "u2", "parent_id": "u1", "name": "应急指挥部", "duties": "统一指挥",
         "roles": [{"name": "总指挥", "duties": "全面负责", "members": [
             {"name": "刘昕野", "position": "总经理", "phone": "13800000000", "email": None}]}]},
    ]
    groups = build_groups_for_consumers(units)
    assert len(groups) == 1
    g = groups[0]
    assert g["group_name"] == "应急指挥部"
    assert g["responsibilities"] == "统一指挥"
    assert g["members"] == [{
        "name": "刘昕野",
        "role": "chief",
        "role_name": "总指挥",
        "position": "总经理",
        "phone": "13800000000",
        "email": None,
        "responsibilities": "全面负责",
    }]
```

```python
# 追加到 backend/tests/test_plan_autofill.py
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import sections


def _autofill_client(db):
    app = FastAPI()
    app.include_router(sections.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def _plan_section_ent():
    plan = SimpleNamespace(id="p1", enterprise_id="e1", user_id="u1")
    section = SimpleNamespace(
        section_key="sec_3", auto_fill=True, auto_fill_source="org_structure",
        content="", ai_generated=False,
    )
    return plan, section, SimpleNamespace(id="e1")


def test_autofill_org_section_requires_emergency_org():
    """应急组织为空 → 400，文案为「请先维护应急组织」。"""
    plan, section, ent = _plan_section_ent()
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: plan),
        MagicMock(scalar_one_or_none=lambda: section),
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # units
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),  # roles
        MagicMock(all=lambda: []),                             # assignments
    ]
    resp = _autofill_client(db).post("/api/v1/plans/p1/sections/sec_3/autofill")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "请先维护应急组织"


def test_autofill_org_section_renders_emergency_members():
    """有应急组织 → 渲染 HTML 表格，含小组名与成员姓名。"""
    plan, section, ent = _plan_section_ent()
    unit = SimpleNamespace(id="u2", parent_id="u1", name="应急指挥部", duties="统一指挥", sort_order=0)
    role = SimpleNamespace(id="r1", unit_id="u2", name="总指挥", duties="全面负责",
                           sort_order=0, is_required=True)
    member = SimpleNamespace(id="m1", name="刘昕野", phone="13800000000", position="总经理",
                             email=None, org_node_id=None)
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: plan),
        MagicMock(scalar_one_or_none=lambda: section),
        MagicMock(scalar_one_or_none=lambda: ent),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [unit])),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [role])),
        MagicMock(all=lambda: [(SimpleNamespace(id="a1", role_id="r1", member_id="m1", sort_order=0), member)]),
    ]
    resp = _autofill_client(db).post("/api/v1/plans/p1/sections/sec_3/autofill")
    assert resp.status_code == 200
    content = resp.json()["data"]["content"]
    assert "<h4>应急指挥部</h4>" in content
    assert "刘昕野" in content
    assert "<td>总经理</td>" in content
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py backend/tests/test_plan_autofill.py -q`
预期：FAIL，`ImportError: cannot import name 'build_groups_for_consumers'`；autofill 用例仍走旧取数

- [ ] **步骤 3：新增消费方分组格式**

在 `backend/app/services/emergency_org_service.py` 末尾追加：

```python
def build_groups_for_consumers(units: Iterable[dict]) -> list[dict]:
    """应急组织 → 预案侧通用分组格式。

    返回 [{group_name, responsibilities, members:[{name, role, role_name, position, phone, email, responsibilities}]}]，
    与既有 run 生成/章节填充/导出签署页的输入结构一致（旧格式分支可直接消费），
    额外提供 role_name 供签署页把"应急角色"作为职务展示。
    """
    unit_list = [u for u in units if isinstance(u, dict)]
    groups: list[dict] = []
    for u in unit_list:
        if not u.get("parent_id"):
            continue
        members: list[dict] = []
        for r in u.get("roles") or []:
            if not isinstance(r, dict):
                continue
            role_name = str(r.get("name") or "").strip()
            for m in r.get("members") or []:
                if not isinstance(m, dict) or not m.get("name"):
                    continue
                members.append(
                    {
                        "name": m.get("name"),
                        "role": ROLE_CODE_BY_NAME.get(role_name, "member"),
                        "role_name": role_name,
                        "position": m.get("position") or "",
                        "phone": m.get("phone") or "",
                        "email": m.get("email"),
                        "responsibilities": r.get("duties") or "",
                    }
                )
        groups.append(
            {
                "group_name": str(u.get("name") or "应急小组"),
                "responsibilities": u.get("duties") or "",
                "members": members,
            }
        )
    return groups


async def load_emergency_groups(db, enterprise_id: str) -> list[dict]:
    """预案侧统一入口：加载应急组织并转成消费方分组格式。"""
    return build_groups_for_consumers(await load_emergency_org(db, enterprise_id))
```

同时把 `build_legacy_groups` 的实现改为复用本函数（保持旧接口兼容视图与消费方视图一致）：

```python
def build_legacy_groups(units: Iterable[dict]) -> list[dict]:
    """应急组织 → 旧分组格式（GET /org-structure 兼容视图）。"""
    groups = build_groups_for_consumers(units)
    return [
        {
            "group_key": GROUP_KEY_BY_NAME.get(g["group_name"], g["group_name"]),
            "group_name": g["group_name"],
            "responsibilities": g["responsibilities"],
            "members": [
                {
                    "name": m["name"],
                    "role": m["role"],
                    "position": m["position"],
                    "phone": m["phone"],
                    "responsibilities": m["responsibilities"],
                }
                for m in g["members"]
            ],
        }
        for g in groups
    ]
```

- [ ] **步骤 4：生成侧改用应急组织**

在 `backend/app/routers/generation.py`：

1. 删除 `_collect_enterprise_data` 中 `"org_structure": _merge_org_members(enterprise.org_structure, org_members),` 这一行，改为在函数内注入应急组织分组：

```python
        "org_structure": emergency_groups or [],
```

并把 `_collect_enterprise_data` 的签名加上 `emergency_groups: list | None = None` 参数（放在 `org_members` 之后，保持既有调用顺序兼容）。

2. 找到 `_collect_enterprise_data` 的调用点（`rg -n "_collect_enterprise_data" backend/app/routers/generation.py`），在调用前加载：

```python
    from app.services.emergency_org_service import load_emergency_groups
    emergency_groups = await load_emergency_groups(db, enterprise.id)
```

并作为 `emergency_groups=emergency_groups` 传入。

3. 删除 `_enrich_with_reports` 中「用成员表补 `org_structure` 节点成员」的整段循环（原 `:600-615`），因为应急组织分组已带成员。

4. `_normalize_org_groups` 与 `_build_org_chart_mermaid` 不改：注入的分组带 `group_name`，会命中原函数的旧格式分支直接通过。

5. `_merge_org_members` 函数保留（`backend/tests/test_enterprise_org.py` 仍有用例），但不再被生产代码调用。

- [ ] **步骤 5：章节自动填充改用应急组织**

把 `backend/app/routers/sections.py` 的 autofill 取数段替换为：

```python
    from app.services.emergency_org_service import load_emergency_groups

    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    groups = await load_emergency_groups(db, p.enterprise_id) if ent else []
    html = _render_org_structure_html(groups)
    if not html:
        raise HTTPException(400, "请先维护应急组织")
```

`_render_org_structure_html` 增加一行兼容：`responsibilities` 取成员级字段，成员级为空时回落到组级，实现时把该函数内成员行替换为：

```python
            f"<td>{_html.escape(str(m.get('responsibilities') or g.get('responsibilities') or ''), quote=True)}</td>"
```

（同时把该循环改为 `for g in org_structure or []` 与 `for i, m in enumerate(members)` 的既有结构不变，仅补 `g` 引用。）

- [ ] **步骤 6：导出签署页改用应急组织**

把 `backend/app/routers/export.py` 的 `_build_signers_from_org` 标题来源改为应急角色优先：

```python
def _build_signers_from_org(org_structure: list | None) -> list[dict]:
    """应急组织分组 → 签署人列表（跳过无姓名成员；职务优先取应急角色）。"""
    signers = []
    for g in org_structure or []:
        for m in g.get("members", []):
            if m.get("name"):
                signers.append(
                    {
                        "seq": len(signers) + 1,
                        "name": m["name"],
                        "title": m.get("role_name") or m.get("position", ""),
                    }
                )
    return signers
```

并在 `:380`（导出 DOCX）与 `:354`、`:453`（`check_plan` 调用处）之前加载应急组织：

```python
    from app.services.emergency_org_service import load_emergency_groups
    emergency_groups = await load_emergency_groups(db, enterprise.id)
    signers = _build_signers_from_org(emergency_groups)
```

`enterprise` 对象在这些函数里的变量名以实现时的实际代码为准（`rg -n "enterprise" backend/app/routers/export.py | head`）。

- [ ] **步骤 7：对话通道同步**

`backend/app/services/chat_dispatch.py:1092` 的 `_build_signers_from_org(ent.org_structure or [])` 改为：

```python
        from app.services.emergency_org_service import load_emergency_groups
        signers = _build_signers_from_org(await load_emergency_groups(db, ent.id))
```

- [ ] **步骤 8：运行测试验证通过**

运行：
```bash
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py backend/tests/test_plan_autofill.py backend/tests/test_generation_enterprise_data.py backend/tests/test_plan_diagram_prompts.py backend/tests/test_chat_generate_plan.py -q
```
预期：全部 PASS。若有用例断言「组织架构消失导致章节为空」，改为断言「应急组织为空 → 400 / 无图」。

- [ ] **步骤 9：Commit**

```bash
git add backend/app/services/emergency_org_service.py backend/app/routers/generation.py backend/app/routers/sections.py backend/app/routers/export.py backend/app/services/chat_dispatch.py backend/tests/test_emergency_org.py backend/tests/test_plan_autofill.py
git commit -m "feat(org): 预案生成/章节填充/导出签署页改从应急组织取数"
```

---

## 任务 9：质检、Onboarding、资源调查报告、作业票会签切源

**文件：**
- 修改：`backend/app/services/plan_quality_service.py:58-70`、`:176-200`、`:276-300`
- 修改：`backend/app/services/plan_review_service.py`、`backend/app/routers/export.py`（`check_plan` 调用点）
- 修改：`backend/app/services/onboarding_service.py:16-28`、`:44-50`、`:110-120`
- 修改：`backend/app/services/resource_investigation_service.py:84`
- 修改：`backend/app/services/work_ticket_service.py:379-429`
- 测试：`backend/tests/test_plan_quality.py`、`backend/tests/test_onboarding_completion.py`、`backend/tests/test_work_ticket_countersign.py`

- [ ] **步骤 1：编写失败的测试**

```python
# 追加到 backend/tests/test_plan_quality.py
def test_quality_reads_emergency_groups_for_commander_check():
    """关键岗位覆盖改为读应急组织：只有总指挥、缺副总指挥时报「应急组织缺副总指挥」。"""
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(
        plan,
        enterprise,
        [_section("sec_3", "应急组织机构及职责", "<p>总指挥：刘昕野</p>")],
        emergency_groups=[{
            "group_name": "应急指挥部",
            "responsibilities": "统一指挥现场处置",
            "members": [{
                "name": "刘昕野", "role": "chief", "role_name": "总指挥",
                "position": "总经理", "phone": "13800000000", "responsibilities": "全面负责",
            }],
        }],
    )
    warnings = [w["warning"] for w in result["warnings"]]
    assert any("应急组织缺副总指挥" in w for w in warnings)
    assert not any("企业组织架构" in w for w in warnings)


def test_quality_flags_missing_phone_from_emergency_groups():
    """应急组织成员缺电话要给出告警，且带上成员姓名与角色。"""
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(
        plan,
        enterprise,
        [],
        emergency_groups=[{
            "group_name": "应急指挥部",
            "responsibilities": "",
            "members": [{
                "name": "赵志龙", "role": "deputy", "role_name": "副总指挥",
                "position": "项目总监", "phone": "", "responsibilities": "",
            }],
        }],
    )
    assert any("赵志龙" in w["warning"] and "无联系电话" in w["warning"] for w in result["warnings"])
```

```python
# 追加到 backend/tests/test_work_ticket_countersign.py
@pytest.mark.asyncio
async def test_countersign_includes_member_with_secondary_position():
    """兼岗（member_positions 非主岗）落在会签单位时也要被取到。"""
    db = MagicMock()
    statements: list[str] = []

    async def execute(stmt, *a, **k):
        text = str(stmt)
        statements.append(text)
        res = MagicMock()
        if "member_positions" in text:
            # 兼岗记录：u9 通过 member_positions 挂到「水」部门节点
            res.all.return_value = [("u9", "n-water")]
        else:
            res.scalar_one_or_none.return_value = [
                {"id": "n-water", "type": "dept", "name": "水", "parent_id": None},
            ]
        return res

    db.execute = execute
    node = _node(units=["水"])
    users = await eligible_users_for_node(db, node, enterprise_id="e1")
    assert users == ["u9"]
    assert any("member_positions" in s for s in statements)


@pytest.mark.asyncio
async def test_countersign_falls_back_to_primary_column_when_positions_empty():
    """尚未回填 member_positions 的旧企业回落到 enterprise_members.org_node_id，行为不退化。"""
    db = MagicMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        res = MagicMock()
        if "member_positions" in text:
            res.all.return_value = []
        elif "enterprise_members" in text and "org_node_id" in text:
            res.all.return_value = [("u1", "n-water"), ("u2", "n-power")]
        else:
            res.scalar_one_or_none.return_value = [
                {"id": "n-water", "type": "dept", "name": "水", "parent_id": None},
                {"id": "n-power", "type": "dept", "name": "电", "parent_id": None},
            ]
        return res

    db.execute = execute
    node = _node(units=["水"])
    users = await eligible_users_for_node(db, node, enterprise_id="e1")
    assert users == ["u1"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_plan_quality.py backend/tests/test_work_ticket_countersign.py -q`
预期：新增用例 FAIL（仍读公司树 / 只取主岗）

- [ ] **步骤 3：质检改读应急组织**

`backend/app/services/plan_quality_service.py` 的 `check_plan` 签名加参数（放在 `has_risk` 之后）：

```python
def check_plan(plan, enterprise, sections, required_sections: list | None = None,
               resources: list | None = None, has_risk: bool = False,
               emergency_groups: list | None = None) -> dict:
```

把三处 `(getattr(enterprise, "org_structure", None) or [])` 全部替换为 `(emergency_groups or [])`，并把 C2 段（`:176-200`）的告警文案由「正文{role}与企业组织架构不符」改为：

```python
                "warning": f"正文{role}与应急组织不符",
```

E2 段（`:276-300`）的「档案缺岗位」文案改为：

```python
                "warning": f"应急组织缺{role}",
```

三个调用点（`backend/app/routers/export.py:354`、`:453`、`backend/app/services/plan_review_service.py`）在调用前加载并传入：

```python
    from app.services.emergency_org_service import load_emergency_groups
    emergency_groups = await load_emergency_groups(db, enterprise.id)
    quality = check_plan(plan, enterprise, sections, ..., emergency_groups=emergency_groups)
```

若某个调用点是同步函数无法 await，改为由其上层 async 调用方加载后传入（`plan_review_service.py` 内同名函数签名同步加 `emergency_groups` 参数）。

- [ ] **步骤 4：Onboarding 改口径**

`backend/app/services/onboarding_service.py`：

```python
# :28 模块标签改名（key 保持不变，避免前端与完成度 payload 大改）
    "org_structure": "应急组织",
```

```python
def _org_done(groups: list | None) -> bool:
    """完成度：应急组织里是否已有「总指挥」这类带头人。"""
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        for member in group.get("members") or []:
            if not isinstance(member, dict):
                continue
            role = str(member.get("role_name") or member.get("role") or "")
            if member.get("name") and ("总指挥" in role or role in ("chief", "commander")):
                return True
    return False
```

在 `:48` 的完成度组装处改为：

```python
    from app.services.emergency_org_service import load_emergency_groups
    done["org_structure"] = _org_done(await load_emergency_groups(db, ent.id))
```

- [ ] **步骤 5：资源调查报告改口径**

`backend/app/services/resource_investigation_service.py:84` 的 `"org_structure": enterprise.org_structure,` 改为在函数内先加载：

```python
    from app.services.emergency_org_service import load_emergency_groups
    emergency_groups = await load_emergency_groups(db, enterprise_id)
```

并写成 `"org_structure": emergency_groups,`。

- [ ] **步骤 6：作业票会签改按任职取人**

`backend/app/services/work_ticket_service.py` 的 `countersign_units` 分支，把成员查询改为 join 任职表：

```python
        from app.models.enterprise_org import MemberPosition

        res = await db.execute(
            select(EnterpriseMember.user_id, MemberPosition.org_node_id).join(
                MemberPosition, MemberPosition.member_id == EnterpriseMember.id
            ).where(
                EnterpriseMember.enterprise_id == enterprise_id,
                EnterpriseMember.enabled.is_(True),
                EnterpriseMember.user_id.is_not(None),
            )
        )
        members = list({(row[0], row[1]) for row in res.all()})
```

并把 docstring 中「成员通过 `enterprise_members.org_node_id` 挂到节点」改为「成员通过 `member_positions` 挂到节点（主岗 + 兼岗）」。

注意：`member_positions` 尚为空的旧企业会取不到人，因此在查询返回空时回落到读 `EnterpriseMember.org_node_id`：

```python
        if not members:
            res = await db.execute(
                select(EnterpriseMember.user_id, EnterpriseMember.org_node_id).where(
                    EnterpriseMember.enterprise_id == enterprise_id,
                    EnterpriseMember.enabled.is_(True),
                    EnterpriseMember.user_id.is_not(None),
                )
            )
            members = [(row[0], row[1]) for row in res.all()]
```

- [ ] **步骤 7：运行测试验证通过**

运行：
```bash
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_plan_quality.py backend/tests/test_onboarding_completion.py backend/tests/test_onboarding_routes.py backend/tests/test_work_ticket_service.py backend/tests/test_work_ticket_countersign.py backend/tests/test_plan_review_routes.py -q
```
预期：全部 PASS

- [ ] **步骤 8：Commit**

```bash
git add backend/app/services/plan_quality_service.py backend/app/services/plan_review_service.py backend/app/routers/export.py backend/app/services/onboarding_service.py backend/app/services/resource_investigation_service.py backend/app/services/work_ticket_service.py backend/tests/test_plan_quality.py backend/tests/test_work_ticket_countersign.py
git commit -m "feat(org): 质检/Onboarding/资源报告/会签改口径（会签支持兼岗）"
```

---

## 任务 10：旧接口下线与 AI 建树改公司口径

**文件：**
- 修改：`backend/app/routers/enterprise_sub.py:31-44`
- 修改：`backend/app/services/enterprise_org_service.py:141-200`（`suggest_org_tree`）
- 测试：`backend/tests/test_enterprise_org.py`、`backend/tests/test_emergency_org.py`

- [ ] **步骤 1：编写失败的测试**

```python
# 追加到 backend/tests/test_emergency_org.py
def test_put_org_structure_is_gone():
    from app.routers.enterprise_sub import router as sub_router
    app = FastAPI()
    app.include_router(sub_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    resp = TestClient(app).put("/api/v1/enterprises/e1/org-structure", json=[])
    assert resp.status_code == 410
    assert "应急组织" in resp.json()["detail"]


def test_get_org_structure_returns_legacy_groups_from_emergency_org(monkeypatch):
    """GET 保留兼容：读应急组织并转旧分组格式。"""
    # mock load_emergency_org 返回两个单元（顶层 + 应急指挥部，含总指挥刘昕野）
    # 断言响应 data == [{"group_key": "headquarters", "group_name": "应急指挥部",
    #   "responsibilities": ..., "members": [{"name": "刘昕野", "role": "chief", ...}]}]
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_emergency_org.py -q`
预期：FAIL（PUT 仍接受写入、GET 仍返回公司树）

- [ ] **步骤 3：下线 PUT、改造 GET**

把 `backend/app/routers/enterprise_sub.py` 的两个函数替换为：

```python
@router.get("/{enterprise_id}/org-structure")
async def get_org_structure(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    """兼容视图：读应急组织并转成旧分组格式，供历史调用方兜底。

    新代码请改用 GET /enterprises/{id}/emergency-org。
    """
    result = await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user.id))
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(404, "企业不存在")
    from app.services.emergency_org_service import build_legacy_groups, load_emergency_org

    return ApiResponse(data=build_legacy_groups(await load_emergency_org(db, enterprise_id)))


@router.put("/{enterprise_id}/org-structure")
async def update_org_structure(enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    """已下线：该接口与 /org/nodes 写同一字段但格式不同，是数据互相覆盖的根源。"""
    raise HTTPException(410, "该接口已下线，请改用 PUT /enterprises/{id}/emergency-org（应急组织）或 PUT /enterprises/{id}/org/nodes（公司组织架构）")
```

注意：原文件中该函数有 `data: list = Body(...)` 参数，替换后需同步删除未使用的 `Body` 导入（若文件其它处仍在使用则保留）。

- [ ] **步骤 4：AI 建树改公司口径**

`backend/app/services/enterprise_org_service.py` 的 `suggest_org_tree` 提示词，把「企业组织架构专家」段落改为纯公司口径：

```python
    prompt = (
        "你是企业组织架构专家。根据企业基础信息，建议合理的公司组织架构树。\n\n"
        f"企业信息：\n{json.dumps(info_for_prompt, ensure_ascii=False, indent=2)}\n"
        f"现有组织架构：{org_summary}\n\n"
    )
```

输出要求段落改为：

```python
    prompt += (
        '输出 JSON：{"nodes": [{"id": "唯一短 id", "type": "dept|team|position", '
        '"name": "部门/班组/岗位名称", "parent_id": "父节点 id 或 null", '
        '"members": [{"name": "姓名", "position": "岗位"}]}]}\n'
        "要求：只输出公司的部门（dept）、班组（team）、岗位（position），"
        "不要输出应急指挥部、应急小组等应急组织内容（应急组织在独立页面维护）；"
        "根节点 parent_id 为 null；members 只含姓名和岗位，不要编造邮箱；"
        "members 必须严格取自企业信息中提供的成员名单；若企业信息未提供任何成员名单，"
        "members 一律输出空数组 []，禁止编造或推断任何姓名（如张三、李四等示例名）；"
        "中文输出；只输出 JSON，不要任何解释。"
    )
```

- [ ] **步骤 5：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_enterprise_org.py backend/tests/test_emergency_org.py -q`
预期：全部 PASS。`test_enterprise_org.py` 中若有针对 `suggest_org_tree` 提示词内容的断言，同步更新为「包含 公司组织架构、不含 应急指挥部」。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/routers/enterprise_sub.py backend/app/services/enterprise_org_service.py backend/tests/test_enterprise_org.py backend/tests/test_emergency_org.py
git commit -m "feat(org): 旧 org-structure 写接口下线、AI 建树改纯公司口径"
```

---

## 任务 11：前端契约层（类型 / 服务 / 预置工具）

**文件：**
- 创建：`frontend/src/types/emergencyOrg.ts`
- 创建：`frontend/src/services/emergencyOrgService.ts`
- 创建：`frontend/src/services/emergencyOrgService.test.ts`
- 创建：`frontend/src/utils/emergencyOrgPreset.ts`
- 创建：`frontend/src/utils/emergencyOrgPreset.test.ts`
- 修改：`frontend/src/services/enterpriseOrgService.ts`、`frontend/src/types/enterpriseOrg.ts`
- 修改：`frontend/src/services/enterpriseService.ts`、`frontend/src/types/enterprise.ts`

- [ ] **步骤 1：编写失败的测试**

```typescript
// frontend/src/services/emergencyOrgService.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest";

const get = vi.fn();
const put = vi.fn();
vi.mock("@/services/api", () => ({ default: { get: (...a: unknown[]) => get(...a), put: (...a: unknown[]) => put(...a) } }));

import { getEmergencyOrg, saveEmergencyOrg } from "@/services/emergencyOrgService";

describe("emergencyOrgService", () => {
  beforeEach(() => {
    get.mockReset();
    put.mockReset();
  });

  it("getEmergencyOrg 调用应急组织 GET 并解包 data", async () => {
    get.mockResolvedValue({ data: { data: [{ id: "u1", name: "应急组织机构", roles: [] }] } });
    const out = await getEmergencyOrg("e1");
    expect(get).toHaveBeenCalledWith("/enterprises/e1/emergency-org");
    expect(out[0].name).toBe("应急组织机构");
  });

  it("saveEmergencyOrg PUT 整树并透传 skipGlobalError", async () => {
    put.mockResolvedValue({ data: { data: [] } });
    await saveEmergencyOrg("e1", [], { skipGlobalError: true });
    expect(put).toHaveBeenCalledWith("/enterprises/e1/emergency-org", { units: [] }, { skipGlobalError: true });
  });
});
```

```typescript
// frontend/src/utils/emergencyOrgPreset.test.ts
import { describe, expect, it } from "vitest";
import { buildPresetUnits, mergeEmergencyUnits } from "@/utils/emergencyOrgPreset";

describe("emergencyOrgPreset", () => {
  it("预置生成顶层 + 6 个小组 + 18 个角色", () => {
    const units = buildPresetUnits();
    expect(units).toHaveLength(7);
    const roles = units.flatMap(u => u.roles);
    expect(roles).toHaveLength(18);
    expect(units[1].name).toBe("应急指挥部");
    expect(units[1].roles.map(r => r.name)).toEqual(["总指挥", "副总指挥", "成员"]);
    expect(units[1].roles[0].is_required).toBe(true);
    expect(units[2].roles.map(r => r.name)).toEqual(["组长", "副组长", "组员"]);
  });

  it("增量合并不覆盖已有同名单元，只补缺失", () => {
    const existing = [
      { id: "keep", parent_id: null, name: "应急组织机构", roles: [] },
      { id: "keep-hq", parent_id: "keep", name: "应急指挥部", roles: [
        { id: "r1", name: "总指挥", is_required: true, member_ids: ["m1"] }] },
    ];
    const merged = mergeEmergencyUnits(existing, buildPresetUnits());
    const hq = merged.find(u => u.name === "应急指挥部")!;
    expect(hq.id).toBe("keep-hq");
    expect(hq.roles.find(r => r.name === "总指挥")!.member_ids).toEqual(["m1"]);
    expect(merged.some(u => u.name === "抢险救灾组")).toBe(true);
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`docker exec -w /app emergency-plan-frontend npx vitest run src/services/emergencyOrgService.test.ts src/utils/emergencyOrgPreset.test.ts --reporter=basic`
预期：FAIL，模块不存在

- [ ] **步骤 3：编写类型**

```typescript
// frontend/src/types/emergencyOrg.ts
// 应急组织类型（对应 backend/app/schemas/emergency_org.py）

export interface EmergencyMemberBrief {
  id: string;
  name?: string | null;
  phone?: string | null;
  position?: string | null;
  email?: string | null;
  org_node_id?: string | null;
}

export interface EmergencyRole {
  id?: string;
  name: string;
  duties?: string | null;
  sort_order?: number;
  is_required?: boolean;
  member_ids: string[];
  members?: EmergencyMemberBrief[];
}

export interface EmergencyUnit {
  id?: string;
  parent_id?: string | null;
  name: string;
  duties?: string | null;
  sort_order?: number;
  roles: EmergencyRole[];
}

/** 可指派成员（复用 /org/members/available）。 */
export interface AssignableMember {
  id: string;
  name: string;
  email: string | null;
  role: string;
  position: string | null;
  org_path: string;
}
```

- [ ] **步骤 4：编写服务**

```typescript
// frontend/src/services/emergencyOrgService.ts
import api from "./api";
import type { AxiosRequestConfig } from "axios";
import type { ApiResponse } from "@/types/common";
import type { EmergencyUnit } from "@/types/emergencyOrg";

/** 读取应急组织整树。 */
export const getEmergencyOrg = (enterpriseId: string) =>
  api
    .get<ApiResponse<EmergencyUnit[]>>(`/enterprises/${enterpriseId}/emergency-org`)
    .then(r => r.data.data);

/** 整树覆盖保存应急组织（字段名 units，与后端 schema 一致）。 */
export const saveEmergencyOrg = (
  enterpriseId: string,
  units: EmergencyUnit[],
  config?: AxiosRequestConfig,
) => {
  const req = config
    ? api.put<ApiResponse<EmergencyUnit[]>>(`/enterprises/${enterpriseId}/emergency-org`, { units }, config)
    : api.put<ApiResponse<EmergencyUnit[]>>(`/enterprises/${enterpriseId}/emergency-org`, { units });
  return req.then(r => r.data.data);
};
```

- [ ] **步骤 5：编写预置工具**

```typescript
// frontend/src/utils/emergencyOrgPreset.ts
import { PRESET_EMERGENCY_GROUPS } from "@/utils/constants";
import type { EmergencyUnit } from "@/types/emergencyOrg";

const HQ_KEY = "headquarters";

/** 预置应急组织：顶层「应急组织机构」→ 各应急小组 → 组内角色。 */
export function buildPresetUnits(): EmergencyUnit[] {
  const rootId = "preset-emergency-root";
  const units: EmergencyUnit[] = [{ id: rootId, parent_id: null, name: "应急组织机构", duties: "", roles: [] }];
  Object.entries(PRESET_EMERGENCY_GROUPS).forEach(([key, name], gi) => {
    const unitId = `preset-${key}`;
    const roleNames = key === HQ_KEY ? ["总指挥", "副总指挥", "成员"] : ["组长", "副组长", "组员"];
    units.push({
      id: unitId,
      parent_id: rootId,
      name,
      duties: "",
      sort_order: gi,
      roles: roleNames.map((roleName, ri) => ({
        id: `${unitId}-role-${ri}`,
        name: roleName,
        duties: "",
        sort_order: ri,
        is_required: roleName === "总指挥" || roleName === "副总指挥",
        member_ids: [],
      })),
    });
  });
  return units;
}

/**
 * 增量合并应急组织：保留已有单元与已有角色指派，只补缺失的单元与角色。
 * 单元按 (name, 父单元) 匹配，避免同名小组重复建树。
 */
export function mergeEmergencyUnits(existing: EmergencyUnit[], incoming: EmergencyUnit[]): EmergencyUnit[] {
  const result = existing.map(u => ({ ...u, roles: (u.roles ?? []).map(r => ({ ...r, member_ids: [...(r.member_ids ?? [])] })) }));
  const idMap = new Map<string, string>();
  for (const inc of incoming) {
    const parentId = inc.parent_id ? (idMap.get(inc.parent_id) ?? null) : null;
    const found = result.find(u => u.name === inc.name && (u.parent_id ?? null) === parentId);
    if (found) {
      idMap.set(inc.id ?? inc.name, found.id ?? inc.name);
      for (const role of inc.roles ?? []) {
        if (!(found.roles ?? []).some(r => r.name === role.name)) {
          found.roles = [...(found.roles ?? []), { ...role, member_ids: [] }];
        }
      }
      continue;
    }
    const newId = inc.id ?? `unit-${result.length + 1}`;
    result.push({ ...inc, id: newId, parent_id: parentId, roles: (inc.roles ?? []).map(r => ({ ...r, member_ids: [] })) });
    idMap.set(inc.id ?? inc.name, newId);
  }
  return result;
}
```

- [ ] **步骤 6：前端成员契约支持兼岗**

`frontend/src/types/enterpriseOrg.ts` 的 `EnterpriseMember` 增加：

```typescript
  /** 全部任职（主岗 + 兼岗）；后端由 member_positions 提供。 */
  positions?: Array<{ org_node_id: string; is_primary: boolean }>;
```

`frontend/src/services/enterpriseOrgService.ts` 的载荷接口增加：

```typescript
  /** 兼岗节点（主岗仍用 org_node_id）。 */
  extra_node_ids?: string[] | null;
```

并同时加到 `MemberCreatePayload` 与 `MemberUpdatePayload`。

同文件新增可指派成员导出（后端接口已存在，应急组织页用它做人员选择器：

```typescript
import type { AssignableMember } from "@/types/emergencyOrg";

/** 可指派成员（复用 /org/members/available，含主岗 org_path）。 */
export const listAvailableMembers = (enterpriseId: string) =>
  api
    .get<ApiResponse<AssignableMember[]>>(`/enterprises/${enterpriseId}/org/members/available`)
    .then(r => r.data.data);
```

`frontend/src/services/enterpriseService.ts` 删除 `updateOrgStructure`，`getOrgStructure` 改为：

```typescript
/** 兼容视图：后端已改为读应急组织并返回旧分组格式；新代码请用 emergencyOrgService。 */
export async function getOrgStructure(id: string): Promise<OrgGroup[]> {
  const res = await api.get<ApiResponse<OrgGroup[]>>(`/enterprises/${id}/org-structure`);
  return res.data.data;
}
```

`frontend/src/types/enterprise.ts` 中 `Enterprise.org_structure` 由 `OrgGroup[]` 改为 `OrgNode[]`（从 `@/types/enterpriseOrg` 导入），并把 `OrgGroup`/`OrgMember` 标记为仅供兼容视图使用：

```typescript
import type { OrgNode } from "@/types/enterpriseOrg";
// ...
  org_structure: OrgNode[];
```

- [ ] **步骤 7：运行测试验证通过**

运行：
```bash
docker exec -w /app emergency-plan-frontend npx vitest run src/services/emergencyOrgService.test.ts src/utils/emergencyOrgPreset.test.ts src/services/enterpriseOrgService.test.ts --reporter=basic
docker exec -w /app emergency-plan-frontend npx tsc -b
```
预期：vitest 全部 PASS；`tsc -b` exit 0。此步 `EnterpriseOrgPage.tsx`/`StepOrg.tsx` 可能因类型变更报错，如报错则在本任务内先做最小适配（去掉对 `updateOrgStructure` 的引用），完整页面改造在任务 12。

- [ ] **步骤 8：Commit**

```bash
git add frontend/src/types/emergencyOrg.ts frontend/src/services/emergencyOrgService.ts frontend/src/services/emergencyOrgService.test.ts frontend/src/utils/emergencyOrgPreset.ts frontend/src/utils/emergencyOrgPreset.test.ts frontend/src/services/enterpriseOrgService.ts frontend/src/types/enterpriseOrg.ts frontend/src/services/enterpriseService.ts frontend/src/types/enterprise.ts
git commit -m "feat(org): 前端应急组织类型、服务与预置工具"
```

---

## 任务 12：应急组织页与公司组织页改造、入口与 Onboarding

**文件：**
- 创建：`frontend/src/pages/Enterprise/EmergencyOrgPage.tsx`
- 修改：`frontend/src/routes/index.tsx:182` 区域
- 修改：`frontend/src/components/enterprise/cockpit/ModuleNav.tsx:22-26` 区域
- 修改：`frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`
- 修改：`frontend/src/pages/Onboarding/StepOrg.tsx`、`frontend/src/pages/Onboarding/OnboardingPage.tsx`
- 删除：`frontend/src/components/enterprise/OrgStructureEditor.tsx`

- [ ] **步骤 1：编写应急组织页**

```tsx
// frontend/src/pages/Enterprise/EmergencyOrgPage.tsx
import { useCallback, useMemo, useState } from "react";
import { App as AntApp, Button, Empty, Form, Input, Modal, Select, Space, Spin, Tag, Tree } from "antd";
import type { DataNode } from "antd/es/tree";
import { ApartmentOutlined, DeleteOutlined, EditOutlined, PlusOutlined, SaveOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { listAvailableMembers } from "@/services/enterpriseOrgService";
import { getEmergencyOrg, saveEmergencyOrg } from "@/services/emergencyOrgService";
import { buildPresetUnits, mergeEmergencyUnits } from "@/utils/emergencyOrgPreset";
import type { EmergencyUnit } from "@/types/emergencyOrg";

function buildTreeData(units: EmergencyUnit[], onAdd: (u: EmergencyUnit) => void, onRename: (u: EmergencyUnit) => void, onDelete: (u: EmergencyUnit) => void): DataNode[] {
  const byParent = new Map<string | null, EmergencyUnit[]>();
  for (const u of units) {
    const key = u.parent_id ?? null;
    byParent.set(key, [...(byParent.get(key) ?? []), u]);
  }
  const toData = (list: EmergencyUnit[] | undefined): DataNode[] =>
    (list ?? []).map(u => ({
      key: u.id ?? u.name,
      title: (
        <Space size={4}>
          <span>{u.name}</span>
          <Tag color="blue">{(u.roles ?? []).length} 角色</Tag>
          <Button size="small" type="text" icon={<PlusOutlined />} onClick={() => onAdd(u)} />
          <Button size="small" type="text" icon={<EditOutlined />} onClick={() => onRename(u)} />
          <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => onDelete(u)} />
        </Space>
      ),
      children: toData(byParent.get(u.id ?? u.name)),
    }));
  return toData(byParent.get(null));
}

export default function EmergencyOrgPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message, modal } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [localUnits, setLocalUnits] = useState<EmergencyUnit[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [saving, setSaving] = useState(false);

  const { data: fetched = [], isLoading } = useQuery({
    queryKey: ["emergency-org", enterpriseId],
    queryFn: () => getEmergencyOrg(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: available = [] } = useQuery({
    queryKey: ["org-available-members", enterpriseId],
    queryFn: () => listAvailableMembers(enterpriseId),
    enabled: !!enterpriseId,
  });

  const units = localUnits ?? fetched;
  const dirty = localUnits !== null;
  const selected = useMemo(() => units.find(u => u.id === selectedId), [units, selectedId]);

  const patchRoles = useCallback((roleIndex: number, memberIds: string[]) => {
    setLocalUnits(prev => {
      const base = prev ?? fetched;
      return base.map(u =>
        u.id === selectedId ? { ...u, roles: (u.roles ?? []).map((r, i) => (i === roleIndex ? { ...r, member_ids: memberIds } : r)) } : u,
      );
    });
  }, [fetched, selectedId]);

  const applyPreset = useCallback(() => {
    modal.confirm({
      title: "应用预置应急组织？",
      content: "将「应急组织机构 → 六个应急小组 → 组内角色」合并到当前应急组织：只补齐缺失的组与角色，已有指派保留。",
      okText: "应用",
      onOk: () => {
        setLocalUnits(mergeEmergencyUnits(units, buildPresetUnits()));
        message.info("已合并预置应急组织，请核对后点击「保存」");
      },
    });
  }, [message, modal, units]);

  const handleSave = useCallback(async () => {
    const payload = units.map((u, ui) => ({
      ...u,
      sort_order: u.sort_order ?? ui,
      roles: (u.roles ?? []).map((r, ri) => ({ ...r, sort_order: r.sort_order ?? ri })),
    }));
    setSaving(true);
    try {
      await saveEmergencyOrg(enterpriseId, payload, { skipGlobalError: true });
      setLocalUnits(null);
      message.success("应急组织已保存");
      queryClient.invalidateQueries({ queryKey: ["emergency-org", enterpriseId] });
      queryClient.invalidateQueries({ queryKey: ["onboarding-completion", enterpriseId] });
    } catch (e) {
      message.error(`保存失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setSaving(false);
    }
  }, [enterpriseId, message, queryClient, units]);

  const addUnit = useCallback((parent: EmergencyUnit) => {
    const name = window.prompt("应急小组名称");
    if (!name) return;
    const id = `unit-${Date.now()}`;
    setLocalUnits(prev => [...(prev ?? fetched), { id, parent_id: parent.id ?? null, name, duties: "", roles: [] }]);
  }, [fetched]);

  const renameUnit = useCallback((unit: EmergencyUnit) => {
    const name = window.prompt("单元名称", unit.name);
    if (!name) return;
    setLocalUnits(prev => (prev ?? fetched).map(u => (u.id === unit.id ? { ...u, name } : u)));
  }, [fetched]);

  const deleteUnit = useCallback((unit: EmergencyUnit) => {
    const ids = new Set([unit.id ?? unit.name]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const u of units) {
        if (u.parent_id && ids.has(u.parent_id) && !ids.has(u.id ?? u.name)) {
          ids.add(u.id ?? u.name);
          grew = true;
        }
      }
    }
    modal.confirm({
      title: `确认删除「${unit.name}」及其下级？`,
      content: "将同时移除该组下的角色与人员指派。",
      okText: "删除",
      okButtonProps: { danger: true },
      onOk: () => setLocalUnits((prev ?? fetched).filter(u => !ids.has(u.id ?? u.name))),
    });
  }, [fetched, modal, units]);

  return (
    <div>
      <PageHeader
        title="应急组织"
        subtitle="维护应急指挥部与各应急小组、组内角色及人员指派；同一人可担任多个应急角色"
        onBack={() => navigate(`/enterprises/${enterpriseId}`)}
        extra={
          <Space wrap>
            <Button icon={<ThunderboltOutlined />} type="primary" ghost onClick={applyPreset}>应用预置应急组织</Button>
            <Button icon={<SaveOutlined />} type="primary" disabled={!dirty} loading={saving} onClick={handleSave}>保存</Button>
          </Space>
        }
      />
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 340, background: "#fff", borderRadius: 8, padding: 12 }}>
          <Space style={{ marginBottom: 12 }} wrap>
            <Button icon={<ApartmentOutlined />} onClick={() => {
              const name = window.prompt("顶层单元名称（通常为「应急组织机构」）");
              if (!name) return;
              setLocalUnits(prev => [...(prev ?? fetched), { id: `unit-${Date.now()}`, parent_id: null, name, roles: [] }]);
            }}>添加顶层单元</Button>
            {dirty && <Tag color="orange">有未保存的修改</Tag>}
          </Space>
          {isLoading ? <Spin /> : units.length === 0 ? (
            <Empty description="暂无应急组织，可点击「应用预置应急组织」或手动添加" />
          ) : (
            <Tree
              key={units.map(u => u.id).join(",")}
              treeData={buildTreeData(units, addUnit, renameUnit, deleteUnit)}
              defaultExpandAll
              selectedKeys={selectedId ? [selectedId] : []}
              onSelect={keys => setSelectedId((keys[0] as string) ?? undefined)}
            />
          )}
        </div>
        <div style={{ flex: 2, background: "#fff", borderRadius: 8, padding: 12 }}>
          {!selected ? (
            <Empty description="请选择左侧单元查看角色与人员" />
          ) : (
            <Form layout="vertical">
              <Form.Item label="单元职责">
                <Input.TextArea
                  rows={2}
                  value={selected.duties ?? ""}
                  onChange={e => setLocalUnits(prev => (prev ?? fetched).map(u => (u.id === selected.id ? { ...u, duties: e.target.value } : u)))}
                />
              </Form.Item>
              {(selected.roles ?? []).map((role, ri) => (
                <Form.Item key={`${role.name}-${ri}`} label={role.is_required ? `${role.name}（必填）` : role.name}>
                  <Select
                    mode="multiple"
                    allowClear
                    placeholder="从企业成员中选择"
                    value={role.member_ids ?? []}
                    onChange={values => patchRoles(ri, values)}
                    options={available.map(m => ({
                      value: m.id,
                      label: `${m.name}${m.position ? `（${m.position}）` : ""}${m.org_path ? ` - ${m.org_path}` : ""}`,
                    }))}
                  />
                </Form.Item>
              ))}
            </Form>
          )}
        </div>
      </div>
    </div>
  );
}
```

（可指派成员 `listAvailableMembers` 已在任务 11 加入 `frontend/src/services/enterpriseOrgService.ts`，本页直接引用。）

- [ ] **步骤 2：注册路由与模块入口**

`frontend/src/routes/index.tsx` 在 `{ path: "/enterprises/:id/org", element: <EnterpriseOrgPage /> }` 之后新增：

```tsx
  { path: "/enterprises/:id/emergency-org", element: <EmergencyOrgPage /> },
```

并在文件顶部 import 区加入：`import EmergencyOrgPage from "@/pages/Enterprise/EmergencyOrgPage";`

`frontend/src/components/enterprise/cockpit/ModuleNav.tsx` 的 `MODULES` 中「组织架构」项之后插入：

```tsx
  {
    key: "emergencyOrg", label: "应急组织", en: "EMERGENCY", hot: true,
    to: (id) => `/enterprises/${id}/emergency-org`,
    icon: <AppIcon name="org" size={24} />,
  },
```

- [ ] **步骤 3：公司组织页去掉应急组织播种与预置按钮**

`frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`：

1. 删除 `buildPresetOrgNodes` 函数、`applyPresetOrg` 回调、以及 `useEffect` 空树播种整段（`:201-253`、`:360-372`）。
2. 删除按钮 `<Button icon={<ApartmentOutlined />} onClick={applyPresetOrg}>应用预置应急组织</Button>`（`:743` 附近）。
3. 删除不再使用的 import：`useEffect`、`PRESET_EMERGENCY_GROUPS`、`mergeOrgNodes`、`ThunderboltOutlined` 若其它处仍在用则保留。
4. 空态文案改为：`暂无组织架构，请添加部门/班组/岗位或使用 AI 建树`（原样保留即可）。
5. 页面副标题由「维护企业组织架构（部门/班组/岗位）与企业成员，支持 Excel 导入与 AI 建树」保持不变（本来就是公司口径）。

- [ ] **步骤 4：公司组织页支持任职多选与任职列**

成员弹窗（`openMemberModal` 与提交处）加入兼岗多选：

```tsx
        <Form.Item name="extra_node_ids" label="兼岗（可多选）">
          <Select
            mode="multiple"
            allowClear
            placeholder="选填：该成员兼任的其他部门/班组/岗位"
            options={nodeOptions.filter(o => o.value !== form.getFieldValue("org_node_id"))}
          />
        </Form.Item>
```

提交时透传 `extra_node_ids`；`openMemberModal("edit", member)` 用 `member.positions ?? []` 回填：

```tsx
        extra_node_ids: (member.positions ?? []).filter(p => !p.is_primary).map(p => p.org_node_id),
```

成员表列「部门班组」改为「任职」，渲染主岗 + 兼岗标签：

```tsx
      {
        title: "任职",
        dataIndex: "org_node_id",
        width: 260,
        render: (v: string | null, member) => {
          const items = member.positions?.length
            ? member.positions
            : v ? [{ org_node_id: v, is_primary: true }] : [];
          if (!items.length) return "-";
          return (
            <Space size={4} wrap>
              {items.map(p => (
                <Tag key={p.org_node_id} color={p.is_primary ? "blue" : "default"}>
                  {buildOrgPath(p.org_node_id, nodes) || p.org_node_id}
                  {p.is_primary ? "（主）" : "（兼）"}
                </Tag>
              ))}
            </Space>
          );
        },
      },
```

并保留原「岗位」列作为公司职位。

- [ ] **步骤 5：Onboarding 步骤改名并改调新接口**

`frontend/src/pages/Onboarding/StepOrg.tsx`：

1. 标题与说明改为：

```tsx
          <h3>应急组织</h3>
          <p style={{ color: "#666", fontSize: 13 }}>
            突发事件谁来指挥、谁负责什么——预案「应急组织机构及职责」章节直接用它。公司部门/班组/岗位请在「组织与人员管理」页维护
          </p>
```

2. 采纳逻辑由 `updateOrgStructure(enterpriseId, groups)` 改为「读现有应急组织 → 合并候选组 → 整树保存」：

```tsx
import { getEmergencyOrg, saveEmergencyOrg } from "@/services/emergencyOrgService";
import type { EmergencyUnit } from "@/types/emergencyOrg";

const unitsFromAccepted = (groups: OrgGroup[]): EmergencyUnit[] => {
  const rootId = "onboarding-emergency-root";
  return [
    { id: rootId, parent_id: null, name: "应急组织机构", duties: "", roles: [] },
    ...groups.map((g, gi) => ({
      id: `onboarding-${g.group_key || gi}`,
      parent_id: rootId,
      name: g.group_name,
      duties: (g as OrgCandidate).responsibilities ?? "",
      sort_order: gi,
      roles: [
        { id: `onboarding-${g.group_key || gi}-chief`, name: "总指挥", duties: "", sort_order: 0, is_required: true, member_ids: [] },
        { id: `onboarding-${g.group_key || gi}-member`, name: "组员", duties: "", sort_order: 1, is_required: false, member_ids: [] },
      ],
    })),
  ];
};
```

3. 采纳时把候选组的成员按姓名在企业成员里查找（`listMembers`），找到则填入 `member_ids`，找不到则不指派（成员档案由「组织与人员管理」页维护）。保存调用：

```tsx
      const current = await getEmergencyOrg(enterpriseId);
      const merged = mergeEmergencyUnits(current, unitsFromAccepted(mergedGroups));
      await saveEmergencyOrg(enterpriseId, merged, { skipGlobalError: true });
```

4. 「已采纳」区块的展示数据源由 `enterprise.org_structure` 改为 `getEmergencyOrg(enterpriseId)`，「全部取消采纳」改为清空应急组织（`saveEmergencyOrg(enterpriseId, [])`）。

5. 删除 `OrgStructureEditor` 的引用与「✍️ 手动填写」按钮（该组件在本任务删除），保留「📄 导入现有数据」。

`frontend/src/pages/Onboarding/OnboardingPage.tsx` 的步骤标签：把 `org` 步骤的显示名由「组织架构」改为「应急组织」（`STEP_LABELS` 或等价常量，实现时按实际代码定位）。

- [ ] **步骤 6：删除旧编辑器**

```bash
git rm frontend/src/components/enterprise/OrgStructureEditor.tsx
```

确认全仓无引用：`rg -n "OrgStructureEditor" frontend/src` 应无结果。

- [ ] **步骤 7：前端验证**

运行：
```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx eslint src/pages/Enterprise/EmergencyOrgPage.tsx src/pages/Enterprise/EnterpriseOrgPage.tsx src/pages/Onboarding/StepOrg.tsx src/utils/emergencyOrgPreset.ts src/services/emergencyOrgService.ts
docker exec -w /app emergency-plan-frontend npx vitest run --reporter=basic
```
预期：`tsc -b` exit 0；`eslint` exit 0；`vitest` 全绿（基线 274 passed，新增用例后更多）。

- [ ] **步骤 8：Commit**

```bash
git add frontend/src/pages/Enterprise/EmergencyOrgPage.tsx frontend/src/routes/index.tsx frontend/src/components/enterprise/cockpit/ModuleNav.tsx frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx frontend/src/pages/Onboarding/StepOrg.tsx frontend/src/pages/Onboarding/OnboardingPage.tsx frontend/src/services/enterpriseOrgService.ts
git rm --cached frontend/src/components/enterprise/OrgStructureEditor.tsx 2>/dev/null || true
git commit -m "feat(org): 应急组织页、公司组织页去预置与任职多选、Onboarding 改名"
```

---

## 任务 13：全量回归与端到端验收

**文件：** 无新增，只做验证与记录。

- [ ] **步骤 1：后端全量回归**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests -q`
预期：passed ≥ 1785 且 failed = 4（4 个历史失败），无新增失败。

- [ ] **步骤 2：前端全量回归**

运行：
```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run --reporter=basic
```
预期：`tsc -b` exit 0；vitest passed ≥ 274，0 failed。

- [ ] **步骤 3：迁移幂等复验**

运行：
```bash
backend\.venv\Scripts\python.exe backend/scripts/migrate_emergency_org_split.py --dry-run
```
预期：四家企业全部 `skipped`（已迁移），证明幂等。

- [ ] **步骤 4：真机冒烟（in-app browser）**

逐项核对并记录：
1. 企业驾驶舱 → 「应急组织」入口存在，进入 `/enterprises/:id/emergency-org`
2. 应急组织页：西安宝岳空间科技有限公司显示顶层 + 7 个子单元、18 个角色；「应急指挥部」下总指挥=刘昕野、副总指挥=赵志龙、成员=程磊
3. 同一人指派到第二个角色（如把刘昕野同时选为后勤保障组组长），保存后刷新仍在 → 一人多任成立
4. 「组织与人员管理」页：西安宝岳空间科技有限公司显示 11 个公司节点、无任何「应急」节点；成员表「任职」列显示主岗标签
5. 给某成员加一个兼岗节点，保存后「任职」列出现「（兼）」标签，刷新仍在 → 一人多岗成立
6. 预案章节「应急组织机构及职责」→ 自动填充，正文含应急指挥部与人员名单；应急组织清空时返回「请先维护应急组织」
7. 导出 DOCX 签署页：签署人姓名为应急组织成员，职务列为应急角色（如「总指挥」）
8. 作业票会签：把会签单位指向某部门，验证兼岗成员也能出现在审批人列表

- [ ] **步骤 5：图谱同步与收尾**

运行：
```bash
codegraph sync .
graphify update .
```
预期：两条命令成功；把最终统计（测试数、迁移数字、冒烟结论）更新到 `TASKS.md` 快照（`TASKS.md` 永不 commit）。

- [ ] **步骤 6：Commit（如有遗留改动）**

```bash
git status --short
# 仅 add 本计划涉及且尚未提交的文件
git commit -m "chore(org): 组织架构与应急组织拆分收尾"
```

---

## 验收清单（对照规格）

| 规格要求 | 对应任务 |
|---|---|
| 应急组织三表 + `member_positions` | 任务 1 |
| 通用树校验复用 | 任务 2 |
| 一人多岗（公司侧） | 任务 3、6、12 |
| 一人多任（应急侧） | 任务 4、5、12 |
| 应急组织整树 API | 任务 5 |
| 存量两种形态搬迁 + 幂等 + 可回滚 | 任务 7 |
| 预案生成/组织图改取应急组织 | 任务 8 |
| 章节自动填充改取应急组织 | 任务 8 |
| 导出签署页改取应急组织 | 任务 8 |
| 预案质检改查应急组织 | 任务 9 |
| Onboarding 改名与完成度改口径 | 任务 9、12 |
| 作业票会签支持兼岗 | 任务 9 |
| 旧 `PUT /org-structure` 下线、`GET` 兼容 | 任务 10 |
| AI 建树改纯公司口径 | 任务 10 |
| 应急组织页、公司组织页去预置、导航入口 | 任务 12 |
| 全量回归与真机冒烟 | 任务 13 |
