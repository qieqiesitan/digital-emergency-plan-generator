# Codex Custom Subagents task handoff v1

Task: task_12_regression

## 目标

执行「风险分级管控增强（A 阶段）」任务 12 回归门禁：后端全量测试、前端全量门禁、迁移幂等复跑验证、API 级冒烟（覆盖双等级/折算/清单/公示/AI 建议），如发现缺陷则修复并提交。**只做验证与必要修复，不做新功能。**

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`929e0dd`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 验证清单

1. **后端全量**：在 `backend` 目录 `python -m pytest tests/ -q`，预期全部 PASS（约 481+）；记录总数与任何失败/错误；
2. **前端门禁**：在 `frontend` 目录 `npx tsc -b`、`npx eslint src`（注意：全仓库有既有 error（约 262 个历史文件），以「本分支改动文件零新增」为口径，可跑 `git diff master...HEAD --name-only` 定位改动文件逐一 eslint）、`npx vitest run`（约 87 passed）；
3. **git 检查**：`git diff --check`、`git show --check HEAD`；
4. **迁移幂等**：对本地库（`localhost:5438/emergency_plan` 或项目实际连接配置）复跑本分支新增迁移：`backend/db_migration_data_dicts.sql`、`backend/db_migration_risk_control_enhancement.sql`、`backend/db_migration_data_dicts_permission.sql`——预期无报错、无重复插入（`IF NOT EXISTS`/`ON CONFLICT`）；若不便连库，以只读方式核对 SQL 幂等性并说明；
5. **API 级冒烟**（用既有测试与只读探针，不启动新服务）：确认关键链路测试存在且通过——双等级校验 422、折算参考端点、管控清单筛选/导出、公示 token 404/脱敏、公开页、AI 建议降级；如测试已覆盖则引用测试名，未覆盖的关键路径可补 1-2 个测试（属本任务允许的修复）；
6. 发现的缺陷：修复并提交（commit 消息 `fix(risk): regression fixes from dual prevention A-phase smoke test`，若有）。

## 输出

最终回复报告：各门禁结果（数字）、迁移幂等验证结论、冒烟覆盖清单、修复 commit（如有）、遗留风险清单。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_12_regression --claim-id <claim_id> --exit-code 0 --summary "回归门禁+冒烟完成"
```

## 规则

- 只做验证与必要缺陷修复；不要重构、不要新增功能；阻塞时停下汇报。
