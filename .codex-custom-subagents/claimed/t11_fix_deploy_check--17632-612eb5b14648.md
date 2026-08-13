# Codex Custom Subagents task handoff v1

Task: t11_fix_deploy_check

## 任务：修复任务 11 —— deploy-check.sh 假阳性与健壮性

你是一个修复子智能体。任务 11 质量审查发现 3 项重要问题（均会误报「部署验证通过」）与若干健壮性建议，按本文件修复并提交。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness`。当前 HEAD `ec9b1ea`。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 未提交改动属正常）。

### 修复内容

对 `scripts/deploy-check.sh` 做以下修改（保持原有结构，仅替换相关段落）：

1. **参数解析改为先取选项再取位置参数**（避免 `--skip-api` 放首位时被当成 SITE_URL）。将当前参数解析段替换为：

```bash
SKIP_API=0
POS_ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--skip-api" ]]; then
    SKIP_API=1
  else
    POS_ARGS+=("$arg")
  fi
done
SITE_URL="${POS_ARGS[0]:-}"
API_URL="${POS_ARGS[1]:-}"
```

2. **#4 manifest 校验 start_url/scope 含子路径**（规格 D-5.4）。将当前 manifest 检查替换为：

```bash
# 4. PWA manifest（start_url/scope 须含部署子路径）
manifest_body="$(curl -fs --max-time 10 "$SITE/manifest.webmanifest" 2>/dev/null || true)"
base_path="$(echo "$SITE" | sed -E 's#^https?://[^/]+##')"
if [[ "$manifest_body" == *"start_url"* && "$manifest_body" == *"$base_path"* ]]; then
  pass "PWA manifest（含子路径 ${base_path:-/}）"
else
  fail "PWA manifest（start_url/scope 应含子路径 ${base_path:-/}）"
fi
```

3. **#5 API health 校验 JSON 响应体**（区分真实后端与 SPA 回退假阳性）。将当前 health 检查替换为：

```bash
  if curl -fs --max-time 10 "$API/api/health" 2>/dev/null | grep -q '"status"'; then
    pass "API /api/health（JSON 响应）"
  else
    fail "API /api/health（应返回 JSON 状态）"
  fi
```

4. **#6 uploads 检查排除连接失败（000）**。将当前 uploads 检查替换为：

```bash
  up_code="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "$API/uploads/" || true)"
  if [[ "$up_code" =~ ^[0-9]{3}$ && "$up_code" != "000" && "$up_code" != 5* ]]; then
    pass "上传 /uploads/ 返回 $up_code（非 5xx 可接受）"
  else
    fail "上传 /uploads/ 返回 $up_code（应非 5xx）"
  fi
```

5. **全部 curl 增加 `--max-time 10`**（除已在上文替换的之外，检查 #1/#2/#3/#7/#8 中的每个 curl）。

### 验证

```bash
bash -n scripts/deploy-check.sh
```

预期：退出码 0。若本机有 Git Bash/WSL，可用 `bash` 冒烟（本地起一个静态服务指向子路径产物，分别验证正常路径 PASS 与「API 指向静态站」时 #5 FAIL、uploads 连接失败时 #6 FAIL），如实记录结果。

### Commit

```bash
git add scripts/deploy-check.sh
git commit -m "fix(deploy): harden deploy-check against false positives and hangs"
```

### 门禁

1. `bash -n` 通过；
2. 五项修改均在位（可 `rg` 抽查 `--max-time`、`POS_ARGS`、`base_path`、`'"status"'`、`"000"`）；
3. `git diff --check` 干净；
4. 提交只含 `scripts/deploy-check.sh`，提交消息精确匹配。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；修复内容；验证/冒烟结果；修改的文件；任何疑虑。
