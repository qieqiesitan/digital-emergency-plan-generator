# Codex Custom Subagents task handoff v1

Task: task_a2_reset_password_ui

## 任务：前端重置密码弹窗（易用性优化计划 A 任务 2）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含任务 A1 的提交（068c028）。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：增加类型与 service

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

同步更新 userManageService.ts 顶部导入：`import type { AdminUserListResponse, AdminUserItem, AdminUserCreateRequest, AdminUserUpdateRequest, AdminResetPasswordRequest } from "@/types/role";`

### 步骤 2：UserManagePage 增加「重置密码」按钮与弹窗

在 `frontend/src/pages/Settings/UserManagePage.tsx` 中：

1. 导入区追加 `resetUserPassword`（来自 `@/services/userManageService`）；`message` 已有导入不变；确认 `Form`、`Modal`、`Input`、`Button`、`Space`、`Popconfirm` 均已导入（现有文件已有）。
2. 组件内追加 state 与 mutation：

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

### 步骤 3：tsc 验证

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

### 步骤 4：Commit

```bash
git add frontend/src/types/role.ts frontend/src/services/userManageService.ts frontend/src/pages/Settings/UserManagePage.tsx
git commit -m "feat(admin): add reset password modal in user management page"
```

## 上下文

- 后端接口 `POST /admin/users/{id}/reset-password`（请求体 `{new_password}`）已由任务 A1 实现。
- 现有代码：`frontend/src/pages/Settings/UserManagePage.tsx` 已有 Table + 操作列（编辑/删除）+ `ConfirmDeleteModal`，使用 useMutation/useQueryClient；`frontend/src/services/userManageService.ts` 已有 fetchUsers/fetchUser/createUser/updateUser/deleteUser。
- 不要改动其它文件；若 tsc 报与任务无关的既有错误，记录并说明。

## 开始之前

对需求/方案/依赖有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述实现
2. 运行 tsc 验证（步骤 3）
3. 提交（步骤 4）
4. 自审（完整性/质量/纪律/测试），发现问题汇报前修复
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 实现了什么、tsc 结果、修改了哪些文件、提交 SHA、自审发现、任何疑虑
