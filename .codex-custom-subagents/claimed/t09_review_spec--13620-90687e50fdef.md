# Codex Custom Subagents task handoff v1

Task: t09_review_spec

## 任务：规格合规审查 —— 任务 9（部署手册 docs/deploy/README-DEPLOY.md）

你是一个规格合规审查子智能体。验证实现者是否创建了所要求的内容（不多不少）。**不要信任实现者的报告**，独立核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。相关提交：`49e0d39`（`docs(deploy): add deployment manual with preflight checklist and pitfalls`），父提交 `d78254c`。

### 要求的内容（任务 9 规格）

`docs/deploy/README-DEPLOY.md` 须包含 10 节：
1. 部署拓扑（网关 nginx 子路径 + 后端容器，文字/示意图）；
2. 部署前环境预检表（表格：OS/glibc、Docker、域名、子路径、宿主机 IP、端口、静态目录、镜像源、数据、ENCRYPTION_KEY、SECRET_KEY）；
3. 前端构建（node:20 容器 + npmmirror + VITE_BASE_PATH，含 CentOS 7 原因）；
4. 后端部署（`docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build`，db-init/已有库/ONNX 模型缓存说明）；
5. 静态文件发布（mkdir/cp/chmod o+x）；
6. 网关 nginx 配置（参照 deploy/gateway-nginx.conf.example，BOM 处理，三条铁律）；
7. 部署验证（deploy-check.sh 用法 + 浏览器冒烟清单）；
8. 踩坑记录（表格，≥7 条含 postgres alpine/BOM/权限/alias/proxy_pass/EBADENGINE/ECONNRESET）；
9. 回滚（dist/conf 备份、pg_dump、旧包回退）；
10. 常见问题（白屏/登录跳转 404/502/生成卡住）。

### 实现者声称

126 行 10 节全齐，与任务文本逐字一致（脚本比对 MATCH），提交 49e0d39 仅含该文件。

### 你的工作

1. `git show 49e0d39 --stat` 确认提交范围；
2. 通读 `git show 49e0d39` 内容，逐节对照上述 10 节要求（重点：预检表含 ENCRYPTION_KEY/SECRET_KEY；后端部署命令含 `--project-directory .`；验证指向 deploy-check.sh；踩坑 ≥7 条）；
3. 检查是否遗漏或多余内容。

### 汇报格式

- ✅ 符合规格（经检查后一切匹配）
- ❌ 发现问题：[具体列出，附带章节/行]
