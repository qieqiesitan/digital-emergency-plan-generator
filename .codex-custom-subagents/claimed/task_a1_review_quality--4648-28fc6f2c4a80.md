# Codex Custom Subagents task handoff v1

Task: task_a1_review_quality

## 任务：代码质量审查——task_a1_reset_password（规格审查已通过）

你是一个代码质量审查子智能体。目的：验证实现是否构建良好（整洁、有测试、可维护）。规格合规性已由前序审查通过，本任务只关注代码质量。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。

BASE_SHA（任务开始前）：4ec3523；HEAD_SHA（当前）：068c028。

审查命令：cd 到 worktree 后运行 git diff 4ec3523..068c028 并阅读实际代码。

### 实现内容（实现者汇报）

- backend/app/schemas/role.py：新增 AdminResetPassword（new_password 长度 6-128）
- backend/app/routers/admin_users.py：新增 POST /{user_id}/reset-password 路由（require_admin 鉴权、404、hash_password、commit+refresh、返回 AdminUserResponse），更新导入
- backend/tests/test_admin_user_reset_password.py：新建 4 个单元测试
- 提交 068c028，仅 3 个文件；任务测试 4/4 PASS

### 审查重点

除标准代码质量关注点（命名、整洁、可维护、错误处理）外，检查：

1. 每个文件是否有单一明确的职责和定义清晰的接口？
2. 实现是否遵循了代码库已有模式（admin_users.py 现有路由风格、role.py schema 风格、后端测试风格）？
3. 测试是否真正验证了行为（而非只 mock 行为）？测试命名是否清晰？
4. 本次变更是否创建了已经很大的新文件，或显著增大了现有文件？（聚焦本次变更带来的影响）
5. 有无明显缺陷：密码长度下限与现有用户创建（min_length=6）是否一致、404 消息与现有路由风格是否一致、是否有安全隐患（如日志泄露密码——不应有）。

### 汇报格式

- 优点
- 问题（关键/重要/次要，带 file:line）
- 评估结论：✅ 通过 或 ❌ 需修复
