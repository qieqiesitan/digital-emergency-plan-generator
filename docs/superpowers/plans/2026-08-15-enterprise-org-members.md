# 企业组织与成员管理 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为双重预防机制（B 阶段）提供前置能力：企业「部门→班组→岗位」组织树结构化、成员账号绑定与企业角色（企业管理员/班组长/员工）、Excel 批量导入、AI 建树（文本通道），并保证既有 `org_structure` 消费者（预案签署/组织图/报告章节）兼容。

**架构：** 新增 `enterprise_members` 表承载账号绑定与角色；`enterprises.org_structure` JSONB 结构升级为 `{id,type,name,parent_id,members:[{name,user_id,position}]}` 树（向后兼容，写后镜像同步）；新增独立 router 与前端组织页；AI 建树复用 `llm_text_completion`（文本进/出，人工确认）。

**技术栈：** FastAPI + SQLAlchemy(async) + PostgreSQL、openpyxl（已有）、React 18 + Ant Design 5 + TanStack Query、Vitest、pytest。

**规格文档：** `docs/superpowers/specs/2026-08-14-hazard-management-design.md` §3.5/§3.7(#1)/§5.11（commit `422f202`）

**测试约定（沿用 A 阶段核实的项目现状）：** `backend/tests/conftest.py` 无 db fixture；模型测试用元数据/构造断言；服务/端点用 `unittest.mock` + `dependency_overrides`；async 测试必须 `@pytest.mark.asyncio`；前端 vitest 仅 service/utils。

---

## 文件结构

### 后端

| 文件 | 职责 |
|------|------|
| `backend/db_migration_enterprise_org.sql` | 新建：`enterprise_members` 表 + 索引（幂等） |
| `backend/app/models/enterprise_org.py` | 新建：EnterpriseMember 模型 |
| `backend/app/schemas/enterprise_org.py` | 新建：OrgNode / MemberCreate / MemberUpdate / MemberResponse / ImportResult |
| `backend/app/services/enterprise_org_service.py` | 新建：树校验、镜像同步、成员 CRUD、AI 建树（文本） |
| `backend/app/routers/enterprise_org.py` | 新建：org/nodes CRUD、members CRUD、import、available、ai-suggest |
| `backend/app/main.py` | 修改：注册 router |
| `backend/tests/test_enterprise_org.py` | 新建：模型/服务/端点测试 |

### 前端

| 文件 | 职责 |
|------|------|
| `frontend/src/types/enterpriseOrg.ts` | 新建：OrgNode / EnterpriseMember 类型 |
| `frontend/src/services/enterpriseOrgService.ts` | 新建：API 封装（箭头函数 + `.then(r=>r.data.data)`） |
| `frontend/src/services/enterpriseOrgService.test.ts` | 新建：URL/参数断言 |
| `frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx` | 新建：组织树 + 成员管理（角色/导入/AI 建树） |
| `frontend/src/routes/index.tsx` | 修改：`/enterprises/:id/org`（ProtectedRoute 内） |
| `frontend/src/pages/Enterprise/RiskManagementTab.tsx` | 修改：加「组织与人员」入口按钮 |

---

## 任务 1：迁移 + EnterpriseMember 模型

**文件：**
- 创建：`backend/db_migration_enterprise_org.sql`
- 创建：`backend/app/models/enterprise_org.py`
- 测试：`backend/tests/test_enterprise_org.py`

- [ ] **步骤 1：失败测试**（元数据/构造断言）

```python
from app.models.enterprise_org import EnterpriseMember

def test_enterprise_member_metadata():
    assert EnterpriseMember.__tablename__ == "enterprise_members"
    cols = EnterpriseMember.__table__.columns
    assert {"id", "enterprise_id", "user_id", "org_node_id", "position", "role", "enabled"} <= set(cols)

def test_enterprise_member_construct():
    m = EnterpriseMember(enterprise_id="e1", user_id="u1", role="team_leader", position="班组长")
    assert m.role == "team_leader"
    assert m.enabled is True
```

- [ ] **步骤 2：运行确认失败**

`python -m pytest tests/test_enterprise_org.py -v` → FAIL（模块不存在）

- [ ] **步骤 3：迁移与模型**

```sql
-- backend/db_migration_enterprise_org.sql
CREATE TABLE IF NOT EXISTS enterprise_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_node_id VARCHAR(64) NULL,
    position VARCHAR(100) NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'member',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (enterprise_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_enterprise_members_org_node ON enterprise_members(org_node_id);
```

模型：UUID 字符串主键、`role` 默认 `member`、`enabled` 用 `__init__` setdefault True（PlanSection 先例）、`enterprise_id`/`user_id` 显式 FK。

- [ ] **步骤 4：通过 + Commit**

`python -m pytest tests/test_enterprise_org.py -v` → PASS

```bash
git add backend/db_migration_enterprise_org.sql backend/app/models/enterprise_org.py backend/tests/test_enterprise_org.py
git commit -m "feat(org): add enterprise_members table and model"
```

---

## 任务 2：组织树校验与镜像同步服务

**文件：**
- 创建：`backend/app/services/enterprise_org_service.py`
- 测试：`backend/tests/test_enterprise_org.py`（追加）

- [ ] **步骤 1：失败测试**

```python
from app.services.enterprise_org_service import validate_org_tree, sync_org_structure

def test_validate_org_tree_ok():
    nodes = [
        {"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": []},
        {"id": "t1", "type": "team", "name": "甲班", "parent_id": "d1", "members": [{"name": "张三", "user_id": "u1"}]},
    ]
    assert validate_org_tree(nodes) == []

def test_validate_org_tree_rejects_duplicate_ids_and_bad_parent():
    nodes = [
        {"id": "d1", "type": "dept", "name": "A", "parent_id": None, "members": []},
        {"id": "d1", "type": "dept", "name": "B", "parent_id": None, "members": []},
        {"id": "t1", "type": "team", "name": "C", "parent_id": "missing", "members": []},
    ]
    errors = validate_org_tree(nodes)
    assert any("重复" in e for e in errors)
    assert any("parent" in e for e in errors)

def test_sync_org_structure_writes_mirror():
    ent = MagicMock()
    sync_org_structure(ent, [{"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": []}])
    assert ent.org_structure[0]["name"] == "生产部"
```

- [ ] **步骤 2：确认失败 → 步骤 3：实现**

- `validate_org_tree(nodes) -> list[str]`：校验节点 id 唯一、parent_id 存在（根为 None）、type ∈ {dept,team,position}、members 为列表且 name 非空；返回错误列表；
- `sync_org_structure(enterprise, nodes)`：把规范化后的树写入 `enterprise.org_structure`（结构向后兼容：保留 name/members[].name）；
- 规范化辅助 `normalize_org_nodes(nodes)`：为缺 id 的节点生成短 id（如 `node-<n>`）。

- [ ] **步骤 4：通过 + Commit**

```bash
git add backend/app/services/enterprise_org_service.py backend/tests/test_enterprise_org.py
git commit -m "feat(org): validate and normalize org tree with structure mirror sync"
```

---

## 任务 3：成员 CRUD 接口

**文件：**
- 创建：`backend/app/schemas/enterprise_org.py`
- 创建：`backend/app/routers/enterprise_org.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_enterprise_org.py`（追加端点测试，`dependency_overrides` 模式）

- [ ] **步骤 1：schema**

`OrgNode`：`{id, type, name, parent_id, members: [{name, user_id?, position?}]}`（校验 type 枚举）；`MemberCreate`：`{user_id, org_node_id?, position?, role: Literal["enterprise_admin","team_leader","member"]}`；`MemberUpdate`：全可选；`MemberResponse`：id/enterprise_id/user_id/org_node_id/position/role/enabled/email/name（email/name 来自 User join）。

- [ ] **步骤 2：端点（鉴权 `get_current_user` + 企业归属 `_get_ent` 同款本地校验）**

- `GET /enterprises/{id}/org/nodes` → 返回 `enterprise.org_structure`（数组）
- `PUT /enterprises/{id}/org/nodes` → body 整树；`validate_org_tree` 校验（422 返回错误列表）→ 存回 + `sync_org_structure` 镜像
- `POST /enterprises/{id}/members` → 绑定账号（user_id 必须存在）、role 默认 member、唯一 (enterprise_id,user_id) 冲突 409
- `PUT /enterprises/{id}/members/{member_id}` → 更新 org_node_id/position/role/enabled（exclude_unset）
- `DELETE /enterprises/{id}/members/{member_id}` → 解绑（软删 enabled=false 或硬删，选硬删并说明）
- `GET /enterprises/{id}/members` → 列表（join users 返回 email/name）
- 企业管理员校验：仅企业主（user_id=enterprise.user_id）可写（A 阶段无企业角色体系，写权限先按企业主，读权限放开给企业成员；说明该取舍）
- `main.py` 注册 `enterprise_org.router`

- [ ] **步骤 3：测试与门禁**

端点测试覆盖：nodes 读取/写入校验 422、member 创建 201/重复 409/user 不存在 404、更新/删除、非企业主写 403。`python -m pytest tests/test_enterprise_org.py -v` 全过；`python -m pytest tests/ -q` 无回归。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/schemas/enterprise_org.py backend/app/routers/enterprise_org.py backend/app/main.py backend/tests/test_enterprise_org.py
git commit -m "feat(org): org tree and member CRUD endpoints"
```

---

## 任务 4：Excel 导入成员 + 责任人选择器

**文件：**
- 修改：`backend/app/routers/enterprise_org.py`、`backend/app/services/enterprise_org_service.py`
- 测试：`backend/tests/test_enterprise_org.py`（追加）

- [ ] **步骤 1：失败测试**（导入解析纯函数）

```python
from app.services.enterprise_org_service import parse_member_rows, build_member_import_template

def test_parse_member_rows_ok():
    rows = [{"姓名": "张三", "邮箱": "zhang@x.com", "部门": "生产部", "班组": "甲班", "岗位": "班组长", "角色": "班组长"}]
    parsed = parse_member_rows(rows)
    assert parsed[0]["name"] == "张三"
    assert parsed[0]["role"] == "team_leader"

def test_build_member_import_template_has_headers():
    wb = build_member_import_template()
    assert wb.active["A1"].value == "姓名"
```

- [ ] **步骤 2：实现**

- `build_member_import_template()`：openpyxl 模板（姓名/邮箱/部门/班组/岗位/角色，角色列数据校验下拉 企业管理员/班组长/员工）；
- `parse_member_rows(rows)`：邮箱必填且格式校验、角色映射（企业管理员→enterprise_admin/班组长→team_leader/员工→member，缺省 member）；
- `POST /enterprises/{id}/members/import`：接收 xlsx（`UploadFile`）→ 解析 → 对每行：按邮箱找用户（不存在记录错误行）→ 按部门/班组名在 org_structure 中找/建节点 → 创建 EnterpriseMember；返回 `{imported, skipped, errors:[{row, reason}]}`；
- `GET /enterprises/{id}/members/available`：返回可用成员（enabled 且属于该企业，含 name/email/role/org 路径），供隐患模块责任人选择器复用。

- [ ] **步骤 3：测试 + Commit**

导入测试（mock 文件字节 + 用户查询）、available 测试；全量回归通过。

```bash
git add backend/app/routers/enterprise_org.py backend/app/services/enterprise_org_service.py backend/tests/test_enterprise_org.py
git commit -m "feat(org): excel member import and available member picker"
```

---

## 任务 5：AI 建树端点（文本通道）

**文件：**
- 修改：`backend/app/services/enterprise_org_service.py`、`backend/app/routers/enterprise_org.py`
- 测试：`backend/tests/test_enterprise_org.py`（追加，mock LLM）

- [ ] **步骤 1：失败测试**

```python
@pytest.mark.asyncio
async def test_ai_suggest_org_tree_ok():
    fake = {"nodes": [
        {"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": [{"name": "张三", "position": "班组长"}]},
        {"id": "t1", "type": "team", "name": "甲班", "parent_id": "d1", "members": []},
    ]}
    with patch("app.services.enterprise_org_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(fake, ensure_ascii=False))):
        out = await suggest_org_tree({"industry": "化工", "employee_count": 120}, None)
    assert out["available"] is True
    assert out["nodes"][0]["type"] == "dept"

@pytest.mark.asyncio
async def test_ai_suggest_org_tree_fallback():
    with patch("app.services.enterprise_org_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await suggest_org_tree({"industry": "化工"}, None)
    assert out["available"] is False
```

- [ ] **步骤 2：实现**

- `suggest_org_tree(enterprise_info, ai_config)`：prompt 输入企业基础信息（行业/人数/现有 org_structure 摘要）→ 输出 `{nodes:[{id,type,name,parent_id,members:[{name,position}]}]}`；邮箱不猜（members 无邮箱，留待补）；异常兜底 `available:false`；
- `POST /enterprises/{id}/org/ai-suggest`：鉴权 + `_get_ai_config`（失败转 None）→ 返回结果；前端分步确认后调 `PUT /org/nodes` 落库。

- [ ] **步骤 3：测试 + Commit**

```bash
git add backend/app/services/enterprise_org_service.py backend/app/routers/enterprise_org.py backend/tests/test_enterprise_org.py
git commit -m "feat(org): AI org tree suggestion (text-only)"
```

---

## 任务 6：前端组织页

**文件：**
- 创建：`frontend/src/types/enterpriseOrg.ts`
- 创建：`frontend/src/services/enterpriseOrgService.ts`、`frontend/src/services/enterpriseOrgService.test.ts`
- 创建：`frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx`
- 修改：`frontend/src/routes/index.tsx`、`frontend/src/pages/Enterprise/RiskManagementTab.tsx`

- [ ] **步骤 1：类型与 service**

`OrgNode`/`EnterpriseMember` 类型与后端一致；service 方法：`getOrgNodes`/`saveOrgNodes`/`listMembers`/`createMember`/`updateMember`/`deleteMember`/`importMembers(file)`（FormData）/`getAvailableMembers`/`suggestOrgTree`（箭头函数 + 解包）。

- [ ] **步骤 2：组织页**

- 左侧组织树（antd Tree，部门/班组/岗位节点可增删改，拖拽排序可不做）→「保存」调 `saveOrgNodes`（先 `JSON` 校验成员名）；
- 右上「AI 建树」：Modal 展示建议树 → 确认后填充 Tree（未保存）；
- 右侧成员列表 Table（姓名/邮箱/部门班组/岗位/角色 Tag/状态）+ 添加成员 Modal（绑定已有账号按邮箱搜索）/编辑/删除/停用；
- 「Excel 导入」按钮（下载模板 + 上传 xlsx + 结果 message：成功/跳过/错误行）；
- 变更后 refetch；返回按钮。

- [ ] **步骤 3：门禁 + Commit**

`npx tsc -b`、eslint、`npx vitest run`（含 service 测试）全过。

```bash
git add frontend/src/types/enterpriseOrg.ts frontend/src/services/enterpriseOrgService.ts frontend/src/services/enterpriseOrgService.test.ts frontend/src/pages/Enterprise/EnterpriseOrgPage.tsx frontend/src/routes/index.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx
git commit -m "feat(org): org and member management page"
```

---

## 任务 7：回归门禁

**文件：** 无

- [ ] 后端 `python -m pytest tests/ -q` 全绿（约 481 + 新增）；
- [ ] 前端 `npx tsc -b`、`npx vitest run`、eslint（分支改动文件零新增）；
- [ ] `git diff --check`；迁移 `db_migration_enterprise_org.sql` 本地幂等复跑两遍；
- [ ] 手工冒烟（供用户验证）：组织树保存/成员添加/Excel 导入/AI 建树；
- [ ] 如有缺陷修复提交（`fix(org): ...`）。

---

## 自检结论

**规格覆盖度**：B 规格 §3.5（树升级/成员/角色/镜像/AI 建树）→ 任务 1-6；§5.11 表 → 任务 1；§3.7 #1 AI 建树 → 任务 5；§14 members 接口 → 任务 3/4。

**占位符**：无 TODO；关键代码步骤均含实际代码或精确契约。

**依赖**：本计划独立可交付；隐患排查治理主体计划在其上叠加。
