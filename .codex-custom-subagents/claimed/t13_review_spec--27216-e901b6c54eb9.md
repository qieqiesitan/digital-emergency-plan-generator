# Codex Custom Subagents task handoff v1

Task: t13_review_spec

## 任务：规格合规审查 —— 任务 13（端到端演练）

你是一个规格合规审查子智能体。验证型任务，核对演练是否按要求执行、断言是否真实满足。**不要信任实现者的报告**，独立核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。HEAD 应为 `e4ff517`（任务 13 无代码改动，不应产生提交）。

### 要求的内容（任务 13 规格）

1. 子路径产物构建（资源带 `/emergency-plan-migration/` 前缀）；
2. 后端 `/api/health` 200（真实路由）；
3. 用 frontend/nginx.conf + nginx 容器模拟网关子路径托管，`deploy-check.sh` 全 PASS 且退出码 0（含 #2 移动端 m.html、#7 深链 index.html、#4 manifest 子路径断言）；
4. `package-release.sh 0.1.0-test` 产出 tar.gz + sha256，结构含 backend/frontend/dist/deploy/scripts/.env.example（db-init/model-cache 缺失时提示）；
5. 收尾门禁：`git diff --check` 干净、tsc 0、vitest 全绿（52）；
6. 不改任何代码，工作区无意外改动。

### 你的工作

1. `git log --oneline -2` 确认无新提交；
2. `git status --porcelain` 确认仅 `M TASKS.md`（+ 可能的前端构建日志等 untracked 杂物，记录即可）；
3. 抽查 `release/` 产物存在性与 tar 结构（`tar tzf` 前几项）；
4. 若后端仍在运行，`curl -fs http://127.0.0.1:8000/api/health` 复核 200；
5. 检查是否误改了代码。

### 汇报格式

- ✅ 符合规格（经检查后一切匹配）
- ❌ 发现问题：[具体列出，附带证据]
