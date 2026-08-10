# Codex Custom Subagents task handoff v1

Task: task_final_fix_backend

## 任务：最终收敛·批次 1（后端修复 4 项）

你是实现子智能体。最终整体审查发现 4 个后端相关缺口/遗留，请修复并提交。规格出处：`docs/superpowers/specs/2026-08-08-usability-enhancement-design.md`。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul，HEAD ca2e332）。必须 cd 到该目录操作，不要动主工作区。

### 修复项

**1. 规格 11.2 密码找回骨架（新增）**
- 新增 `password_reset_tokens` 表（字段：id、user_id FK、token、expires_at、created_at、used_at 可空；建议 migration SQL + 模型，参考项目既有 auth 表/迁移写法）。
- 新增 `POST /auth/forgot-password`（入参 email；骨架：查用户 → 生成 token 存表 → 邮件发送函数留空实现/注释待 SMTP 接入；返回成功提示，不泄露用户是否存在）。
- 新增 `POST /auth/reset-password`（入参 token + new_password；校验 token 存在/未过期/未使用 → 更新密码 → 标记 used；骨架实现即可）。
- 补 pytest 用例（至少：forgot 成功、reset 成功、token 无效/过期失败）。

**2. 企业编辑页 GIS/平面图「清除」不持久化（修复）**
- `backend/app/routers/enterprises.py` PUT 用 `model_dump(exclude_none=True)` 丢弃 null，前端清除后发送 null 但后端保留旧值。修法：显式字段白名单处理，允许 null 清空（gis/floor_plan 等可空字段）；保持「未传字段不更新」语义（避免整体改为全量替换）。
- 补/改 pytest：清除 gis/floor_plan 后 GET 应返回 null。

**3. 规格 6.6 完成度算法：报告跳过时权重分摊（修复）**
- 当前 `onboarding_service.py` compute_completion：报告模块跳过时直接不计 20 分（用户最高 80%）。规格要求：风险评估报告跳过 → 其权重（如 10%）归入「风险与危化品」；资源调查报告跳过 → 权重归入「应急资源」。
- 需先读现有实现确认「跳过」如何表达（接口/字段），设计最小改动：报告未生成/未跳过的判定 + 跳过标记传递（可能在 completion 查询或单独 skip 状态）。若现有无「跳过」概念，按规格补一个可表达跳过的通道（如 reports 状态或参数），并保证引导页/工作台卡片消费不变（percent 0-100、modules 结构兼容）。
- 补 pytest 覆盖：全部跳过报告时各模块权重正确且 percent 可达 100。

**4. B1 遗留：用户 AI 配置合并迁移（修复）**
- `backend/app/db/migrations/db_migration_ai_config_system.sql`（或实际路径）当前仅建 schema。补数据回填：若系统配置不存在，把首个（或默认）用户 ai_config 复制为系统配置（模型/base_url/api_key 等字段）；幂等（重复执行不产生重复）。若项目用代码迁移而非 SQL，按既有方式补。

### 质量门禁（必须全部通过）

1. 后端测试：`cd backend && .\.venv\Scripts\python -m pytest -q --ignore=_docker_test.py` 全绿（若环境缺依赖先说明）
2. `git diff --check` 干净
3. 新增代码无 any/类型逃逸（Python 侧按项目既有风格）
4. 单提交（或按修复项拆 2-4 个逻辑提交均可，每个提交信息清晰），只含相关文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、每项修法简述、测试验证输出摘要。

