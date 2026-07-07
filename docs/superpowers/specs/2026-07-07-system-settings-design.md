# 系统设置功能设计方案：角色管理 + 用户管理

> 版本: v1.0 | 日期: 2026-07-07 | 状态: 待评审

## 一、需求概述

为「数字化预案自动生成系统」新增两套基础管理功能：

- **角色管理**：定义角色（如超级管理员、企业管理员、普通用户），为每个角色分配权限集
- **用户管理**：管理员可查看全量用户列表、创建/编辑/禁用用户、分配角色

### 核心约束
- 不修改现有 `users` 表核心字段，不破坏已有登录/注册/认证流程
- 现有 `role` 字段（`users.role`，默认 `"user"`）平滑迁移到新角色体系
- 所有新增端点需通过 `get_current_user` 鉴权，管理员端点额外校验 `role == "admin"`
- 前端菜单「系统管理」组内追加子菜单，不影响现有页面路由

---

## 二、现状分析

### 2.1 已有资产
| 层面 | 已有 | 说明 |
|------|------|------|
| 用户表 | `users(id, email, password_hash, name, role, …)` | `role` 为自由文本，默认 `"user"`，无外键约束 |
| 认证 | JWT access/refresh token，`get_current_user` 依赖注入 | 鉴权仅校验 token，不做角色校验 |
| 前端路由 | `/settings/system` → 系统配置页（KV 配置 CRUD） | 侧边栏「系统管理」分组仅有此项 |
| 前端权限 | 无 | 任何人登录后可见所有页面 |

### 2.2 缺口
- **无角色定义表**：`users.role` 是裸字符串，无约束、无权限关联
- **无用户管理 API**：`/users/me` 仅操作当前用户，没有管理员视角的用户 CRUD
- **无角色校验中间件**：任何已登录用户可调所有 API
- **前端无管理员页面**：没有用户列表、角色分配界面

---

## 三、数据模型设计

### 3.1 新增表

#### `roles` — 角色定义表
```sql
CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(50)  NOT NULL UNIQUE,
    code        VARCHAR(30)  NOT NULL UNIQUE,
    description VARCHAR(200),
    is_system   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

#### `permissions` — 权限定义表
```sql
CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(80) NOT NULL UNIQUE,
    name        VARCHAR(80) NOT NULL,
    resource    VARCHAR(40) NOT NULL,
    action      VARCHAR(20) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

#### `role_permissions` — 角色-权限关联表
```sql
CREATE TABLE role_permissions (
    role_id       UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
```

### 3.2 现有表调整

`users` 表 **不加减字段**。仅将 `users.role` 的值从自由文本改为必须匹配 `roles.code`：
- 部署时检查：若 `roles.code` 中不存在 `users.role` 的值，在日志 warning 提示
- 应用层校验：用户管理 API 在写 `role` 时校验 code 存在，返回明确错误

> **ponytail**: 不加外键约束，避免迁移锁表风险。应用层校验足够。

### 3.3 预设数据

```sql
-- 角色
INSERT INTO roles (code, name, is_system, description) VALUES
  ('super_admin', '超级管理员', TRUE, '系统最高权限，可管理所有资源'),
  ('admin',       '管理员',     TRUE, '可管理企业和用户'),
  ('user',        '普通用户',   TRUE, '基础权限，可创建和编辑自己的预案');

-- 权限
INSERT INTO permissions (code, name, resource, action) VALUES
  ('user:create',   '创建用户',   'user',   'create'),
  ('user:read',     '查看用户',   'user',   'read'),
  ('user:update',   '编辑用户',   'user',   'update'),
  ('user:delete',   '删除用户',   'user',   'delete'),
  ('role:manage',   '角色管理',   'system', 'manage'),
  ('system:config', '系统配置',   'system', 'manage');

-- 角色-权限分配: super_admin 全部 / admin 用户管理 / user 无
```

---

## 四、API 设计

### 4.1 角色管理 `GET/POST/PUT/DELETE /api/v1/roles`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/v1/roles` | 角色列表 | admin+ |
| GET | `/api/v1/roles/{role_id}` | 角色详情+拥有的权限 | admin+ |
| POST | `/api/v1/roles` | 创建角色 | super_admin |
| PUT | `/api/v1/roles/{role_id}` | 更新角色（名称/描述/权限集） | super_admin |
| DELETE | `/api/v1/roles/{role_id}` | 删除角色（is_system=true 禁止） | super_admin |

### 4.2 权限查询 `GET /api/v1/permissions`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/v1/permissions` | 全量权限列表（按 resource 分组） | admin+ |

> **ponytail**: 权限只读，预设数据覆盖所有场景。后续要动态编辑再加 PUT。

### 4.3 用户管理 `GET/POST/PUT/DELETE /api/v1/admin/users`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/v1/admin/users` | 用户列表（分页+搜索） | admin+ |
| GET | `/api/v1/admin/users/{user_id}` | 用户详情 | admin+ |
| POST | `/api/v1/admin/users` | 创建用户（管理员直接创建） | admin+ |
| PUT | `/api/v1/admin/users/{user_id}` | 编辑用户（姓名/角色） | admin+ |
| DELETE | `/api/v1/admin/users/{user_id}` | 删除用户（禁止删除自己） | super_admin |

> **ponytail**: 管理端点前缀 `/admin/` 清晰隔离。

### 4.4 依赖注入：角色校验

新增两个 FastAPI 依赖，位于 `backend/app/dependencies.py`：

```python
async def require_admin(current_user = Depends(get_current_user)):
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(403, "需要管理员权限")
    return current_user

async def require_super_admin(current_user = Depends(get_current_user)):
    if current_user.role != "super_admin":
        raise HTTPException(403, "需要超级管理员权限")
    return current_user
```

### 4.5 后端文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/models/role.py` | Role + Permission + RolePermission SQLAlchemy 模型 |
| 新增 | `backend/app/schemas/role.py` | Pydantic schema |
| 新增 | `backend/app/routers/roles.py` | 角色 CRUD + 权限查询 |
| 新增 | `backend/app/routers/admin_users.py` | 管理员用户 CRUD |
| 新增 | `backend/app/seed_roles.sql` | 预设数据 SQL |
| 修改 | `backend/app/dependencies.py` | 追加 require_admin / require_super_admin |
| 修改 | `backend/app/main.py` | 注册两个新 router |

---

## 五、前端设计

### 5.1 新增页面

| 路由 | 页面组件 | 说明 |
|------|----------|------|
| `/settings/users` | `UserManagePage` | 用户列表（表格+搜索+创建/编辑弹窗+角色下拉） |
| `/settings/roles` | `RoleManagePage` | 角色列表（表格+权限勾选弹窗） |

### 5.2 侧边栏调整

在「系统管理」分组内追加：
```
系统管理
  ├─ 用户管理   → /settings/users
  ├─ 角色管理   → /settings/roles
  └─ 系统配置   → /settings/system   (已有)
```

仅 `role == "admin"` 或 `"super_admin"` 时渲染该分组。

### 5.3 前端文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `frontend/src/pages/Settings/UserManagePage.tsx` | 用户管理页 |
| 新增 | `frontend/src/pages/Settings/RoleManagePage.tsx` | 角色管理页 |
| 新增 | `frontend/src/services/userManageService.ts` | 管理员用户 API 调用 |
| 新增 | `frontend/src/services/roleService.ts` | 角色/权限 API 调用 |
| 新增 | `frontend/src/types/role.ts` | 角色/权限类型定义 |
| 修改 | `frontend/src/layouts/MainLayout.tsx` | 菜单追加两项，按 role 控制显示 |
| 修改 | `frontend/src/routes/index.tsx` | 注册两个新路由 |

### 5.4 移动端

移动端（`frontend/src/mobile/`）**本次不新增管理页面**。管理员功能桌面端操作即可。

> **ponytail**: 移动端已有 SettingsScreen，管理操作天然桌面端场景。

---

## 六、安全与兼容性保障

### 6.1 不破坏现有功能
- `users` 表结构零变更，现有应用层读取 `users.role` 逻辑不受影响
- `get_current_user` 签名和行为不变，所有现有路由无需修改
- 现有注册接口默认赋 `role = "user"`，匹配预设角色 `roles.code = "user"`
- 新路由使用独立 prefix（`/roles`、`/admin/users`），不与现有路由冲突

### 6.2 角色校验
- 新的 `require_admin` / `require_super_admin` 依赖仅在新增的管理端点上使用
- 每个管理端点通过依赖注入明确声明所需角色，无隐式校验
- 删除用户时校验 `user_id != current_user.id`

### 6.3 已有 admin 账户的处理
- 若数据库中已有 `role = "admin"` 的用户，无需迁移
- `roles` 表内置的 `code = "admin"` 即匹配之
- 若需要严格 RBAC，后续可跑一次脚本将现有用户 role 迁移

---

## 七、实施步骤

| 序号 | 步骤 | 预估工作量 |
|------|------|-----------|
| 1 | 创建数据库模型 `backend/app/models/role.py` | 小 |
| 2 | 创建 Pydantic Schema `backend/app/schemas/role.py` | 小 |
| 3 | 创建预设 SQL `backend/app/seed_roles.sql` | 小 |
| 4 | 追加依赖注入 `backend/app/dependencies.py` | 小 |
| 5 | 创建角色管理路由 `backend/app/routers/roles.py` | 中 |
| 6 | 创建管理员用户路由 `backend/app/routers/admin_users.py` | 中 |
| 7 | 更新 `backend/app/main.py` 注册路由 | 小 |
| 8 | 前端类型定义 + API 服务层 | 小 |
| 9 | 前端用户管理页 `UserManagePage.tsx` | 中 |
| 10 | 前端角色管理页 `RoleManagePage.tsx` | 中 |
| 11 | 更新侧边栏菜单 `MainLayout.tsx` | 小 |
| 12 | 更新前端路由 `routes/index.tsx` | 小 |
| 13 | 端到端验证 | 中 |

---

## 八、跳过与后续

| 跳过项 | 理由 | 何时补 |
|--------|------|--------|
| 接口级权限注解/装饰器 | 依赖注入校验足够 | 权限粒度到接口级且超过 20 个管理端点时 |
| 角色继承 | 三个角色扁平结构够用 | 角色类型超过 5 个时 |
| 操作日志/审计 | 目前无合规要求 | 对接外部系统或被审计时 |
| 移动端管理页面 | 管理员操作桌面端完成 | 移动端成为唯一终端时 |
| 前端路由级权限守卫 | 后端已校验，前端仅 UI 隐藏 | 需要更精细的前端体验控制时 |

---

## 九、疑问与待确认

1. **现有 `users.role` 中是否已有 `"admin"` 值？** 若有，确认其用户是否需要迁移到 `super_admin`。
2. **企业级权限是否需要？** 即按企业隔离用户可见范围。本次方案为系统级管理。
3. **是否需要"禁用用户"功能？** User 表目前无 `is_active` 字段，本次方案不新增列。可用删除代替禁用（软删除后续再加）。
