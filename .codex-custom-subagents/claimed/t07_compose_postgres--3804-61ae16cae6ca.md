# Codex Custom Subagents task handoff v1

Task: t07_compose_postgres

## 任务：部署可交付性计划任务 7 —— docker-compose.yml postgres 镜像换 Debian 版

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成实现并提交。不要修改任务范围之外的文件。不要读计划文件——本任务文件已包含完整任务文本。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。

### 背景

`postgres:16-alpine` 在公司 CentOS 7 服务器（XFS + overlay2）上任何外部卷挂载都会导致 initdb 报 Operation not permitted；根 `docker-compose.yml` 仍在使用该镜像。改为 Debian 版 `postgres:16`。本地开发数据在命名卷 `shuzihuayuan_pgdata`（external）中，PG16 主版本不变，重建容器数据不丢。

### 步骤 1：替换镜像

文件：`docker-compose.yml`（第 3 行附近）。

将：

```yaml
    image: postgres:16-alpine
```

改为：

```yaml
    image: postgres:16
```

### 步骤 2：compose 配置校验

在 worktree 根目录执行：

```bash
docker compose config -q
```

预期：退出码 0（无输出）。注意：根 compose 引用了 external 卷 `shuzihuayuan_pgdata`，若本机该卷不存在，`config -q` 仍应通过（config 只解析不校验卷存在性）；若因其他原因失败，如实记录。

### 步骤 3：Commit

```bash
git add docker-compose.yml
git commit -m "fix(docker): use postgres:16 Debian image to avoid CentOS 7 volume mount failure"
```

### 门禁

1. `docker compose config -q` 通过（或如实记录阻塞原因）；
2. `git diff --check` 干净；
3. 提交只含 `docker-compose.yml`，提交消息精确匹配步骤 3。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；你实现了什么；验证结果；修改的文件；自审发现；任何疑虑。
