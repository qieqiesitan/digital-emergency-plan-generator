# Codex Custom Subagents task handoff v1

Task: t09_review_quality

## 任务：代码质量审查 —— 任务 9（部署手册）

你是一个代码质量审查子智能体。验证文档质量。规格合规性已通过，本次只审文档质量。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。范围：BASE `d78254c` → HEAD `49e0d39`，仅 `docs/deploy/README-DEPLOY.md`（126 行新增）。

### 审查要点

- 文档结构是否清晰、命令是否可复制执行（含 `--project-directory .`）；
- 与已实现配置的一致性：VITE_BASE_PATH 用法、postgres:16 Debian、拆分 location 网关模板、`/api/health`（手册不应出现 `/api/v1/health` 作为验证命令）、deploy-check.sh 用法；
- 是否存在自相矛盾或误导（如引用了不存在的脚本/路径——注意 `scripts/backup.sh` 被 §9 引用但当前仓库不存在，协调者已安排任务 10 补建，可在报告中备注确认该安排覆盖）；
- 中文排版、表格完整性。不要修改文件，只审查。

### 汇报格式

返回：优点、问题（关键/重要/次要，附章节/行）、评估结论（✅ 通过 / ❌ 需修复）。
