# Codex Custom Subagents task handoff v1

Task: t11_deploy_check_script

## 任务：部署可交付性计划任务 11 —— 验证脚本 scripts/deploy-check.sh

你是一个实现子智能体。严格按以下步骤在指定 worktree 内创建脚本并提交。不要修改任务范围之外的文件。不要读计划文件——本任务文件已包含完整任务文本与全部脚本内容。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\deploy-readiness`

git 分支 `codex/deploy-readiness` 的隔离 worktree。启动时 `cd` 到该目录，`git status` 确认工作区干净（TASKS.md 若有未提交改动属正常，不要动它）。

### 背景

部署后一键验证：首页/移动端/静态资源/PWA manifest/API health/uploads/深链接/无尾斜杠。全部 PASS 才算部署完成。

### 步骤 1：创建 scripts/deploy-check.sh

完整内容（一次性写入）：

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "用法: ./scripts/deploy-check.sh <站点URL> [API URL] [--skip-api]"
  echo "示例: ./scripts/deploy-check.sh https://deom2025.sxbych.com/emergency-plan-migration/ https://deom2025.sxbych.com"
  echo "      ./scripts/deploy-check.sh http://127.0.0.1:19090/emergency-plan-migration/ http://127.0.0.1:8000"
}

SITE_URL="${1:-}"
API_URL="${2:-}"
SKIP_API=0
for arg in "$@"; do
  if [[ "$arg" == "--skip-api" ]]; then SKIP_API=1; fi
done

if [[ -z "$SITE_URL" ]]; then
  usage
  exit 1
fi

SITE="${SITE_URL%/}"
PASS=0
FAIL=0

pass() { echo "PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL  $1"; FAIL=$((FAIL + 1)); }

# 1. 首页
if curl -fs -o /dev/null "$SITE/"; then pass "首页 $SITE/"; else fail "首页 $SITE/"; fi

# 2. 移动端（须返回 m.html：标题含「移动端」）
if curl -fs "$SITE/m/dashboard" 2>/dev/null | grep -q '移动端'; then
  pass "移动端 /m/dashboard（m.html）"
else
  fail "移动端 /m/dashboard（应返回 m.html）"
fi

# 3. 静态资源（从 index.html 提取）
assets="$(curl -fs "$SITE/" | grep -oE 'assets/[^"'"'"' ]+\.(js|css)' | sort -u || true)"
if [[ -z "$assets" ]]; then
  fail "未从 index.html 提取到静态资源"
else
  for a in $assets; do
    if curl -fs -o /dev/null "$SITE/$a"; then pass "资源 $a"; else fail "资源 $a"; fi
  done
fi

# 4. PWA manifest
if curl -fs -o /dev/null "$SITE/manifest.webmanifest"; then pass "PWA manifest"; else fail "PWA manifest"; fi

# 5-6. API
if [[ "$SKIP_API" == "1" ]]; then
  echo "SKIP  API 检查（--skip-api）"
else
  API="${API_URL:-$(echo "$SITE" | sed -E 's#(/[^/]+)?/?$##')}"
  if curl -fs -o /dev/null "$API/api/health"; then pass "API /api/health"; else fail "API /api/health"; fi
  up_code="$(curl -s -o /dev/null -w '%{http_code}' "$API/uploads/" || true)"
  if [[ "$up_code" != 5* ]]; then pass "上传 /uploads/ 返回 $up_code（非 5xx 可接受）"; else fail "上传 /uploads/ 返回 $up_code"; fi
fi

# 7. 深链接 SPA 回退（桌面端须返回 index.html：含「数字化预案系统」且不含「移动端」）
deep_body="$(curl -fs "$SITE/enterprises" 2>/dev/null || true)"
if [[ "$deep_body" == *"数字化预案系统"* && "$deep_body" != *"移动端"* ]]; then
  pass "深链接 SPA 回退（桌面 index.html）"
else
  fail "深链接 SPA 回退（应返回桌面 index.html）"
fi

# 8. 无尾斜杠
no_slash="${SITE%/}"
ns_code="$(curl -s -o /dev/null -w '%{http_code}' "$no_slash" || true)"
ns_loc="$(curl -s -D - -o /dev/null "$no_slash" | grep -i '^location:' | tr -d '\r' | awk '{print $2}' || true)"
if [[ "$ns_code" == "301" || "$ns_code" == "308" ]] && [[ "$ns_loc" == */ ]]; then
  pass "无尾斜杠 301/308 → 带尾斜杠"
elif [[ "$ns_code" == "200" ]]; then
  pass "无尾斜杠直接 200（容器直连形态可接受）"
else
  fail "无尾斜杠返回 $ns_code"
fi

echo "----------------------------------------"
echo "通过 $PASS 项，失败 $FAIL 项"
if [[ "$FAIL" -gt 0 ]]; then
  echo "部署验证未通过"
  exit 1
fi
echo "部署验证通过"
```

### 步骤 2：bash 语法校验 + 可执行权限

```bash
bash -n scripts/deploy-check.sh
chmod +x scripts/deploy-check.sh
```

预期：`bash -n` 无输出（退出码 0）。

### 步骤 3：Commit

```bash
git add scripts/deploy-check.sh
git commit -m "feat(deploy): add post-deploy verification script"
```

### 门禁

1. `bash -n scripts/deploy-check.sh` 通过；
2. 脚本内容与任务给定文本一致（可抽查关键行：usage、PASS/FAIL 计数、8 项检查、退出码）；
3. 提交只含 `scripts/deploy-check.sh`，提交消息精确匹配步骤 3。

### 汇报格式

完成后汇报：**状态：** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT；你创建了什么；验证结果；修改的文件；自审发现；任何疑虑。
