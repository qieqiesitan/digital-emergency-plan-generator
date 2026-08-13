# Codex Custom Subagents task handoff v1

Task: t06_review_spec

## 任务：规格合规审查 —— 任务 6（frontend/nginx.conf 子路径 location）

你是一个规格合规审查子智能体。验证实现者是否构建了所要求的内容（不多不少）。**不要信任实现者的报告**，独立阅读实际代码逐项核对。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。相关提交：`7abd9ee`（`feat(deploy): add subpath location to frontend nginx config`），父提交 `b470cf1`。

### 要求的内容（任务 6 规格）

1. `frontend/nginx.conf`：在 `location /m/ { ... }` 块之后、`location / { ... }` 块之前插入：

```nginx
    # 应用子路径部署：dist 位于容器 html 根目录（alias 指向容器内路径，勿写宿主机路径）
    location /emergency-plan-migration/ {
        alias /usr/share/nginx/html/;
        try_files $uri $uri/ /emergency-plan-migration/index.html /emergency-plan-migration/m.html;
    }
```

2. 提交只含 `frontend/nginx.conf`，提交消息精确匹配；nginx 配置语法校验通过。

### 实现者声称

按规格插入；`nginx -t` 通过（本机无 stable-alpine 镜像且拉取超时，改用本地 nginx:alpine，加 `--add-host backend:127.0.0.1` 解决既有 proxy_pass 上游解析——环境问题非语法错误）；提交 7abd9ee 仅 1 文件 6+。

### 你的工作

1. `git show 7abd9ee --stat` 确认提交范围；
2. 通读 `git show 7abd9ee` 全量 diff，逐字对照上述 location 块（位置、alias、try_files 三行回退链）；
3. 若本机可运行 docker nginx，复跑语法校验（可用 nginx:alpine + `--add-host backend:127.0.0.1`）；若网络受限，记录即可；
4. 检查是否有规格外改动。

### 汇报格式

- ✅ 符合规格（经代码检查后一切匹配）
- ❌ 发现问题：[具体列出，附带 file:line]
