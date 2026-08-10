# Codex Custom Subagents task handoff v1

Task: task_final_fix_backend_review_spec

## 任务：规格合规审查——task_final_fix_backend

你是代码审查子智能体。请核验后端收敛修复是否符合规格要求。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD 2f3a2f0）。

审查命令：cd 到 worktree 后 `git log ca2e332..HEAD --oneline` + 逐提交 `git show`，逐文件阅读实际代码。

### 规格要求（对照 docs/superpowers/specs/2026-08-08-usability-enhancement-design.md）

1. **11.2 密码找回骨架**：`password_reset_tokens` 表（id/user_id/token/expires_at/created_at/used_at）+ `POST /auth/forgot-password` + `POST /auth/reset-password`；邮件发送留空；forgot 不泄露用户是否存在；reset 校验 token 有效/未过期/未使用；测试覆盖。
2. **GIS/平面图清除持久化**：PUT 允许显式 null 清空可空字段（gis/floor_plan），未传字段不更新；测试覆盖清除/保留/name null 防护。
3. **6.6 完成度跳过分摊**：报告跳过时风险评估报告权重归入 risk_chemical、资源调查报告权重归入 resources；percent 0-100；跳过通道（接口）幂等、生成中/已完成拒绝；测试覆盖全跳过达 100%。
4. **B1 配置回填迁移**：无系统配置时取最早用户配置复制为系统配置；幂等。

### 门禁

- `cd backend && .\.venv\Scripts\python -m pytest -q --ignore=_docker_test.py` 全绿
- `git diff --check` 干净；提交按修复项拆分且只含相关文件

### 汇报格式

```
结论：PASS / FAIL（✅ 符合规格 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

