# Codex Custom Subagents task handoff v1

Task: task_a2_review_spec

## 任务：规格合规审查——task_a2_reset_password_ui 实现是否匹配任务要求

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `c094f39` 引入的改动：

git show c094f39 --stat 与 git show c094f39

### 要求的内容（任务 A2 原文）

前端重置密码弹窗：

1. frontend/src/types/role.ts：在 AdminUserUpdateRequest 之后追加 `export interface AdminResetPasswordRequest { new_password: string; }`。
2. frontend/src/services/userManageService.ts：
   - 末尾追加 `resetUserPassword(userId, data)`：`api.post(\`/admin/users/${userId}/reset-password\`, data).then(r => r.data.data)`，返回 Promise<AdminUserItem>
   - 顶部导入追加 AdminResetPasswordRequest
3. frontend/src/pages/Settings/UserManagePage.tsx：
   - 导入追加 resetUserPassword
   - 新增 resetTarget state、resetForm 表单、resetMut mutation（成功提示「密码已重置」关闭弹窗，失败「重置失败」）
   - 操作列「编辑」「删除」之间增加「重置密码」按钮
   - 追加重置密码 Modal：标题「重置密码 · 用户名」、临时密码字段（必填 + 至少 6 位）、confirmLoading、destroyOnClose
4. npx tsc --noEmit 无类型错误。
5. Commit 信息：feat(admin): add reset password modal in user management page。
6. 只改动上述 3 个文件。

### 实现者声称构建了什么

- role.ts 追加 AdminResetPasswordRequest
- userManageService.ts 追加 resetUserPassword + 导入
- UserManagePage.tsx 追加 state/mutation/按钮/Modal
- tsc 无类型错误；提交 c094f39，3 文件 +49/-1
- 自审说明：任务描述提到「ConfirmDeleteModal 之后」，但实际文件删除是内联 Popconfirm，弹窗按实际结构放在主 Modal 之后（意图一致）

### 你的工作

阅读实际代码并验证：

缺失的需求：是否实现了所有要求？
多余的工作：是否构建了未被要求的内容？
理解偏差：弹窗位置适配是否合理（实际文件确实无 ConfirmDeleteModal 组件）？按钮位置是否在编辑/删除之间？Mutation 行为是否与描述一致？

通过阅读代码来验证，而非信任报告。

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
