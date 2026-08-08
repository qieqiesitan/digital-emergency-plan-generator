# 易用性整体优化 · 计划 A（基础层）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 完成基础层优化——管理员重置密码、英文文案中文化、乱码/死按钮修复、菜单权限与入口修正，为引导页等后续计划打底。

**架构：** 后端在 `admin_users.py` 增加管理员重置密码接口（复用 `hash_password`）；前端逐个修复文案与交互问题；`MainLayout`/`AuthContext` 修正菜单权限与入口。

**技术栈：** FastAPI + SQLAlchemy（后端）、React + Ant Design + TypeScript（前端）、pytest（后端测试）、tsc/vitest（前端验证）。

**规格依据：** `docs/superpowers/specs/2026-08-08-usability-enhancement-design.md` 第 11、12、4.4、5 节。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `backend/app/schemas/role.py` | 增加 `AdminResetPassword` 请求模型 | 修改 |
| `backend/app/routers/admin_users.py` | 增加 `POST /{user_id}/reset-password` 路由 | 修改 |
| `backend/tests/test_admin_user_reset_password.py` | 重置密码接口单元测试 | 新建 |
| `frontend/src/types/role.ts` | 增加 `AdminResetPasswordRequest` 类型 | 修改 |
| `frontend/src/services/userManageService.ts` | 增加 `resetUserPassword` | 修改 |
| `frontend/src/pages/Settings/UserManagePage.tsx` | 操作列增加「重置密码」弹窗 | 修改 |
| `frontend/src/pages/Settings/AIConfigPage.tsx` | 全页文案中文化 | 修改 |
| `frontend/src/pages/Settings/ProfilePage.tsx` | label/提示中文化 | 修改 |
| `frontend/src/pages/Plan/VersionListPage.tsx` | 标题/提示中文化 | 修改 |
| `frontend/src/components/plan/RichTextEditor.tsx` | Tooltip 中文化 | 修改 |
| `frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx` | 乱码 placeholder 修复 | 修改 |
| `frontend/src/pages/Enterprise/EnterpriseEditPage.tsx` | 乱码 placeholder 修复 | 修改 |
| `frontend/src/mobile/screens/LoginScreen.tsx` | 忘记密码死按钮改为联系管理员提示 | 修改 |
| `frontend/src/layouts/MainLayout.tsx` | 法规库权限过滤、移除 AI 助手菜单、权限失败提示 | 修改 |
| `frontend/src/contexts/AuthContext.tsx` | 菜单权限加载失败降级为核心菜单 | 修改 |

---

### 任务 1：后端管理员重置密码接口

**文件：**
- 修改：`backend/app/schemas/role.py`
- 修改：`backend/app/routers/admin_users.py`
- 测试：`backend/tests/test_admin_user_reset_password.py`

- [ ] **步骤 1：编写失败的测试**

新建 `backend/tests/test_admin_user_reset_password.py`：

```python
import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.routers.admin_users import reset_user_password
from app.schemas.role import AdminResetPassword


def test_reset_password_schema_rejects_short_password():
    with pytest.raises(Exception):
        AdminResetPassword(new_password="123")


def test_reset_password_accepts_valid_password():
    data = AdminResetPassword(new_password="newpass123")
    assert data.new_password == "newpass123"


def test_reset_password_raises_404_when_user_missing():
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(Exception) as exc:
        asyncio.run(reset_user_password("u1", AdminResetPassword(new_password="newpass123"), _=None, db=db))
    assert exc.value.status_code == 404


def test_reset_password_updates_hash():
    from app.services.auth_service import verify_password

    db = AsyncMock()
    user = MagicMock()
    user.password_hash = None
    db.execute.return_value.scalar_one_or_none.return_value = user
    asyncio.run(reset_user_password("u1", AdminResetPassword(new_password="newpass123"), _=None, db=db))
    assert verify_password("newpass123", user.password_hash)
    db.commit.assert_awaited_once()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_admin_user_reset_password.py -v`

预期：FAIL，报错 `ImportError: cannot import name 'reset_user_password'` 与 `AdminResetPassword` 未定义。

- [ ] **步骤 3：实现 schema 与路由**

在 `backend/app/schemas/role.py` 的 `AdminUserUpdate` 之后追加：

```python
class AdminResetPassword(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)
```

在 `backend/app/routers/admin_users.py` 的 `delete_user` 之后追加：

```python
@router.post("/{user_id}/reset-password", response_model=ApiResponse[AdminUserResponse])
async def reset_user_password(
    user_id: str,
    data: AdminResetPassword,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    await db.refresh(user)
    return ApiResponse(data=AdminUserResponse.model_validate(user))
```

同时更新 `admin_users.py` 顶部导入：`from app.schemas.role import AdminUserCreate, AdminUserUpdate, AdminUserResponse, AdminResetPassword`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_admin_user_reset_password.py -v`

预期：4 个测试全部 PASS。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/schemas/role.py backend/app/routers/admin_users.py backend/tests/test_admin_user_reset_password.py
git commit -m "feat(admin): add reset password endpoint for admin users"
```

---

### 任务 2：前端重置密码弹窗

**文件：**
- 修改：`frontend/src/types/role.ts`
- 修改：`frontend/src/services/userManageService.ts`
- 修改：`frontend/src/pages/Settings/UserManagePage.tsx`

- [ ] **步骤 1：增加类型与 service**

在 `frontend/src/types/role.ts` 的 `AdminUserUpdateRequest` 之后追加：

```ts
export interface AdminResetPasswordRequest {
  new_password: string;
}
```

在 `frontend/src/services/userManageService.ts` 末尾追加：

```ts
export function resetUserPassword(userId: string, data: AdminResetPasswordRequest): Promise<AdminUserItem> {
  return api.post(`/admin/users/${userId}/reset-password`, data).then(r => r.data.data);
}
```

同步更新导入：`import type { AdminUserListResponse, AdminUserItem, AdminUserCreateRequest, AdminUserUpdateRequest, AdminResetPasswordRequest } from "@/types/role";`

- [ ] **步骤 2：UserManagePage 增加「重置密码」按钮与弹窗**

在 `frontend/src/pages/Settings/UserManagePage.tsx` 中：

1. 导入区追加 `resetUserPassword`，并补 `message` 已有导入不变；追加 `Input.Password` 需要的 `Form` 已导入。
2. 组件 state 增加：

```tsx
const [resetTarget, setResetTarget] = useState<AdminUserItem | null>(null);
const [resetForm] = Form.useForm();

const resetMut = useMutation({
  mutationFn: ({ id, new_password }: { id: string; new_password: string }) =>
    resetUserPassword(id, { new_password }),
  onSuccess: () => {
    message.success("密码已重置");
    setResetTarget(null);
    resetForm.resetFields();
  },
  onError: () => message.error("重置失败"),
});
```

3. 操作列（columns 的 actions render）在「编辑」「删除」之间增加：

```tsx
<Button type="link" onClick={() => { setResetTarget(record); resetForm.resetFields(); }}>重置密码</Button>
```

4. 在 `ConfirmDeleteModal` 之后（返回 JSX 内）追加弹窗：

```tsx
<Modal
  title={`重置密码 · ${resetTarget?.name || ""}`}
  open={!!resetTarget}
  onCancel={() => setResetTarget(null)}
  onOk={() => resetForm.validateFields().then((v: { new_password: string }) => {
    if (!resetTarget) return;
    resetMut.mutate({ id: resetTarget.id, new_password: v.new_password });
  })}
  confirmLoading={resetMut.isPending}
  destroyOnClose
>
  <Form form={resetForm} layout="vertical" style={{ marginTop: 16 }}>
    <Form.Item
      name="new_password"
      label="临时密码"
      rules={[
        { required: true, message: "请输入临时密码" },
        { min: 6, message: "至少 6 位" },
      ]}
    >
      <Input.Password placeholder="设置后用户需用此密码登录并尽快修改" />
    </Form.Item>
  </Form>
</Modal>
```

- [ ] **步骤 3：tsc 验证**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/types/role.ts frontend/src/services/userManageService.ts frontend/src/pages/Settings/UserManagePage.tsx
git commit -m "feat(admin): add reset password modal in user management page"
```

---

### 任务 3：英文文案中文化

**文件：**
- 修改：`frontend/src/pages/Settings/AIConfigPage.tsx`
- 修改：`frontend/src/pages/Settings/ProfilePage.tsx`
- 修改：`frontend/src/pages/Plan/VersionListPage.tsx`
- 修改：`frontend/src/components/plan/RichTextEditor.tsx`

- [ ] **步骤 1：AIConfigPage 全页中文化**

在 `frontend/src/pages/Settings/AIConfigPage.tsx` 中逐项替换：

| 原（英文） | 改为（中文） |
|------------|--------------|
| `PageHeader title="AI config"` | `title="AI 配置"` |
| `Card title="model config"` | `title="模型配置"` |
| `label="provider"` | `label="服务商"` |
| `label="API Key"` | `label="API Key"`（保留，行业通用） |
| `label="model"` | `label="模型名称"` |
| `label="custom API URL"` | `label="接口地址"` |
| `label="Temperature"` | `label="温度"` |
| `label="Max Tokens"` | `label="最大 Token"` |
| `label="Top P"` | `label="Top P"`（保留） |
| `message.success("saved")` | `message.success("已保存")` |
| `message.error("save failed")` | `message.error("保存失败")` |
| `message.success("deleted")` | `message.success("已删除")` |
| `title="advanced"` | `title="高级参数"` |
| 按钮 `test connection` | `测试连接` |
| 按钮 `save` | `保存` |
| 按钮 `delete config` | `删除配置` |
| `Card title="connection status"` | `title="连接状态"` |
| `testResult.detail` 拼接 `"connected: "` | `"连接成功: "` |
| `"failed: "` | `"连接失败: "` |
| `"last test: "` | `"上次测试: "` |
| `"not tested"` | `"尚未测试"` |
| `"request failed"` | `"请求失败"` |

- [ ] **步骤 2：ProfilePage 中文化**

在 `frontend/src/pages/Settings/ProfilePage.tsx` 中替换：

- `message.success("done")` → `message.success("已保存")`
- `message.error("failed")` → `message.error("操作失败")`
- `message.success("password changed, please login again")` → `message.success("密码已修改，请重新登录")`
- `<Descriptions.Item label="name">` → `label="姓名"`
- `<Descriptions.Item label="email">` → `label="邮箱"`
- `<Descriptions.Item label="registered">` → `label="注册时间"`
- `label="confirm"` → `label="确认新密码"`

（若该文件还有其它英文 label 如 `old_password`/`new_password`，一并改为 `旧密码`/`新密码`。）

- [ ] **步骤 3：VersionListPage 中文化**

在 `frontend/src/pages/Plan/VersionListPage.tsx` 中替换：

- `message.success("rolled back")` → `message.success("已回滚")`
- `message.error("rollback failed")` → `message.error("回滚失败")`
- `PageHeader title="version history"` → `title="版本历史"`

- [ ] **步骤 4：RichTextEditor Tooltip 中文化**

在 `frontend/src/components/plan/RichTextEditor.tsx` 工具栏中逐项替换 Tooltip：

| 原 | 改为 |
|----|------|
| `title="Bold"` | `title="加粗"` |
| `title="Italic"` | `title="斜体"` |
| `title="Underline"` | `title="下划线"` |
| `title="Strikethrough"` | `title="删除线"` |
| `title="Bullet List"` | `title="无序列表"` |
| `title="Ordered List"` | `title="有序列表"` |
| `title="Table"` | `title="表格"` |
| `title="Left"` | `title="左对齐"` |
| `title="Center"` | `title="居中"` |
| `title="Right"` | `title="右对齐"` |
| `title="Undo"` | `title="撤销"` |
| `title="Redo"` | `title="重做"` |

（`H1`/`H2`/`H3` 按钮文本保留不变。）

- [ ] **步骤 5：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/pages/Settings/AIConfigPage.tsx frontend/src/pages/Settings/ProfilePage.tsx frontend/src/pages/Plan/VersionListPage.tsx frontend/src/components/plan/RichTextEditor.tsx
git commit -m "fix(i18n): localize AI config, profile, version list and editor tooltips"
```

---

### 任务 4：乱码 placeholder 与移动端死按钮修复

**文件：**
- 修改：`frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx`
- 修改：`frontend/src/pages/Enterprise/EnterpriseEditPage.tsx`
- 修改：`frontend/src/mobile/screens/LoginScreen.tsx`

- [ ] **步骤 1：修复「经济类型」乱码 placeholder**

在两个文件中将：

```tsx
placeholder="?????????"
```

替换为：

```tsx
placeholder="选择或输入经济类型"
```

- [ ] **步骤 2：修复移动端忘记密码死按钮**

在 `frontend/src/mobile/screens/LoginScreen.tsx` 中，将「忘记密码？」的 `<span>` 替换为静态提示（保留布局）：

```tsx
<div className="flex justify-end mt-sm">
  <span className="text-body-sm text-neutral-500">
    忘记密码？请联系管理员重置
  </span>
</div>
```

删除原 `text-primary-500 cursor-pointer` 样式，去掉可点击暗示。

- [ ] **步骤 3：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/pages/Enterprise/EnterpriseCreatePage.tsx frontend/src/pages/Enterprise/EnterpriseEditPage.tsx frontend/src/mobile/screens/LoginScreen.tsx
git commit -m "fix(ui): repair garbled placeholder and dead forgot-password text"
```

---

### 任务 5：菜单与权限修正（MainLayout + AuthContext）

**文件：**
- 修改：`frontend/src/layouts/MainLayout.tsx`
- 修改：`frontend/src/contexts/AuthContext.tsx`

- [ ] **步骤 1：AuthContext 菜单权限失败降级**

在 `frontend/src/contexts/AuthContext.tsx` 中：

1. `AuthContextValue` 增加字段 `menuLoadFailed: boolean`。
2. `AuthState` 增加 `menuLoadFailed: boolean`，初始 `false`。
3. `loadMenuPermissions` 的 catch 改为：

```tsx
} catch {
  // 菜单权限加载失败：降级为核心菜单（工作台/企业/预案/个人资料），并标记提示
  setState((prev) => ({
    ...prev,
    menuPermissions: ["menu:dashboard", "menu:enterprises", "menu:plans", "menu:profile"],
    menuLoadFailed: true,
  }));
}
```

4. `login` / `register` 成功后设置 `menuLoadFailed: false`；`logout` 与 `auth:logout` handler 重置 `menuLoadFailed: false`。

- [ ] **步骤 2：MainLayout 增加权限失败提示、法规库权限过滤、移除 AI 助手菜单**

在 `frontend/src/layouts/MainLayout.tsx` 中：

1. 从 `useAuth()` 解构增加 `menuLoadFailed`。
2. 在 `<Content>` 顶部（`<Outlet />` 前）增加可关闭提示：

```tsx
{menuLoadFailed && (
  <Alert
    type="warning"
    showIcon
    closable
    message="部分菜单加载失败，已显示核心菜单"
    style={{ marginBottom: 16 }}
  />
)}
```

3. 顶部导入追加 `Alert`（Ant Design）。
4. 菜单项移除 AI 助手：

```tsx
const menuItems = [
  ...(hasMenu("/dashboard") ? [{ key: "/dashboard", icon: <DashboardOutlined />, label: "工作台" }] : []),
  ...(hasMenu("/enterprises") ? [{ key: "/enterprises", icon: <BankOutlined />, label: "企业管理" }] : []),
  ...(hasMenu("/plans") ? [{ key: "/plans", icon: <FileTextOutlined />, label: "预案列表" }] : []),
  ...
];
```

删除 `{ key: "/chat", icon: <RobotOutlined />, label: "AI 助手" }` 及其 onClick 分支（`/chat` 不再需要特殊处理，菜单 onClick 统一 `navigate(key)`）；`RobotOutlined` 导入可删除（若不再使用）。

5. 「法规库管理」纳入权限过滤：

```tsx
...(hasMenu("/settings/regulations") ? [{ key: "/settings/regulations", icon: <FileTextOutlined />, label: "法规库管理" }] : []),
```

- [ ] **步骤 3：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/layouts/MainLayout.tsx frontend/src/contexts/AuthContext.tsx
git commit -m "fix(menu): filter regulations menu, remove AI assistant entry, degrade menus on permission load failure"
```

---

### 任务 6：全量验证收尾

**文件：** 无新增修改

- [ ] **步骤 1：后端全量测试**

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（含新增 4 个重置密码测试）。

- [ ] **步骤 2：前端全量验证**

运行：`cd frontend && npx tsc --noEmit && npx vitest run`

预期：tsc 无错误，现有 vitest 全部通过。

- [ ] **步骤 3：Commit（如无改动则跳过）**

```bash
git status --short
```

如有未提交文件，按内容分类提交；若干净则无操作。

---

## 计划 A 自检

**规格覆盖度：** 第 11 节密码找回（管理员重置）→ 任务 1/2；第 12 节文案清单 → 任务 3/4；第 4.4 节权限补全 → 任务 5；第 5 节 AI 助手入口去重 → 任务 5。无遗漏。

**占位符扫描：** 无 TODO/待定/占位符；所有步骤含完整代码或精确替换表。

**类型一致性：** `AdminResetPassword`（后端 schema）与 `AdminResetPasswordRequest`（前端 type）字段一致（`new_password`）；`resetUserPassword(userId, data)` 对应 `POST /admin/users/{user_id}/reset-password`；`menuLoadFailed` 在 AuthContext 与 MainLayout 中命名一致。
