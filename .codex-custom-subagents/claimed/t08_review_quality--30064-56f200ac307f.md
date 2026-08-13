# Codex Custom Subagents task handoff v1

Task: t08_review_quality

## 任务：代码质量审查 —— 任务 8（生产 compose + .env.example + 网关 nginx 模板）

你是一个代码质量审查子智能体。验证实现是否构建良好（模板可用、注释到位、无隐患）。规格合规性已通过，本次只审代码质量。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。范围：BASE `ea96f51` → HEAD `a87b0a8`，新增 3 文件（`deploy/docker-compose.prod.yml`、`.env.example`、`deploy/gateway-nginx.conf.example`）。

### 实现了什么

生产后端 compose（postgres:16 + backend）、环境变量模板、网关 nginx 子路径模板（拆分 location 修正版 + 三条铁律注释）。

### 审查要点

- compose：变量化是否完整（无硬编码密钥）、挂载路径与镜像内路径是否一致、生产形态是否避免依赖宿主机源码热更（未挂 `./backend/app`）；
- .env.example：与 compose 默认值/占位是否一致、注释是否防误改（ENCRYPTION_KEY 不可改）；
- 网关模板：占位符清晰、三条铁律注释准确、拆分 location 语义正确（与任务 6 修复一致）；
- `.gitignore` 的 `.env.*` 忽略模式对 `.env.example` 的影响（入库后已跟踪无碍，但可评估是否需 `!.env.example` 豁免，属建议项）；
- 是否有规格外内容。不要修改代码，只审查。

### 汇报格式

返回：优点、问题（关键/重要/次要，附 file:line）、评估结论（✅ 通过 / ❌ 需修复）。
