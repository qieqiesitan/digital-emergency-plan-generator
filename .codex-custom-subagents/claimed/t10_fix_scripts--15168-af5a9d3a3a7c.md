# Codex Custom Subagents task handoff v1

Task: t10_fix_scripts

## 任务：修复任务 10 —— backups/ 入 gitignore + 打包白名单化 + backup.sh 路径稳健

你是一个修复子智能体。任务 10 质量审查提出 2 项重要建议，按本文件修复并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。当前 HEAD `38a22d4`。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 未提交改动属正常）。

### 背景

1. `backup.sh` 把含生产数据的 pg_dump 写到仓库根 `backups/`，但 `.gitignore` 未忽略该目录，`git add -A` 会把数据带进仓库；
2. `package-release.sh` 的 `cp -r "$ROOT/scripts"` 会把 `scripts/archive/` 下的内部工具（含 query_users.sql / reset_pwd.sql 等敏感 SQL）复制进客户交付包；
3. `backup.sh` 的 `cd "$(dirname "$0")/.."` 依赖调用方式，不够稳健。

### 步骤 1：.gitignore 追加 backups/

在 `.gitignore` 的 `release/` 块附近追加：

```gitignore
# 数据库备份（pg_dump 产物，勿入库）
backups/
```

### 步骤 2：package-release.sh 复制 scripts 改为白名单

将 `scripts/package-release.sh` 中的：

```bash
cp -r "$ROOT/scripts" "$STAGE/scripts"
```

替换为：

```bash
mkdir -p "$STAGE/scripts"
cp "$ROOT/scripts/package-release.sh" "$ROOT/scripts/backup.sh" "$STAGE/scripts/"
if [[ -f "$ROOT/scripts/deploy-check.sh" ]]; then
  cp "$ROOT/scripts/deploy-check.sh" "$STAGE/scripts/"
fi
```

（`deploy-check.sh` 由任务 11 创建；存在才复制，避免任务顺序问题导致脚本失败。）

### 步骤 3：backup.sh 路径解析稳健化

将 `scripts/backup.sh` 中的：

```bash
cd "$(dirname "$0")/.."
```

替换为：

```bash
cd "$(cd "$(dirname "$0")" && pwd)/.."
```

### 步骤 4：验证 + Commit

```bash
bash -n scripts/package-release.sh scripts/backup.sh
rg -n "scripts/archive|query_users|reset_pwd" scripts/package-release.sh
```

预期：bash -n 通过；`rg` 无命中（交付包不再含 archive）。然后：

```bash
git add .gitignore scripts/package-release.sh scripts/backup.sh
git commit -m "fix(deploy): ignore backup dumps and whitelist packaged scripts"
```

### 门禁

1. `bash -n` 两脚本通过；
2. `rg` 确认 package-release.sh 不再复制 archive；
3. `git diff --check` 干净；
4. 提交只含上述 3 个文件，提交消息精确匹配步骤 4。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；修复内容；验证输出；修改的文件；任何疑虑。
