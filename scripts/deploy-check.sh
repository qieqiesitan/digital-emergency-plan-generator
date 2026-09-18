#!/usr/bin/env bash
set -euo pipefail

# CRLF 自检：Windows 检出后 shebang 会变成 "#!/usr/bin/env bash\r" 而无法执行
if head -1 "$0" | grep -q $'\r'; then
  echo "错误: 本脚本为 CRLF 行尾，Linux 下无法执行。" >&2
  echo "修复: sed -i 's/\r$//' scripts/*.sh  （或 git add --renormalize scripts）" >&2
  exit 1
fi

usage() {
  echo "用法: ./scripts/deploy-check.sh <站点URL> [API URL] [--skip-api]"
  echo "示例: ./scripts/deploy-check.sh https://deom2025.sxbych.com/emergency-plan-migration/ https://deom2025.sxbych.com"
  echo "      ./scripts/deploy-check.sh http://127.0.0.1:19090/emergency-plan-migration/ http://127.0.0.1:8000"
}

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
if curl -fs --max-time 10 -o /dev/null "$SITE/"; then pass "首页 $SITE/"; else fail "首页 $SITE/"; fi

# 2. 移动端（须返回 m.html：标题含「移动端」）
if curl -fs --max-time 10 "$SITE/m/dashboard" 2>/dev/null | grep -q '移动端'; then
  pass "移动端 /m/dashboard（m.html）"
else
  fail "移动端 /m/dashboard（应返回 m.html）"
fi

# 3. 静态资源（从 index.html 提取）
assets="$(curl -fs --max-time 10 "$SITE/" | grep -oE 'assets/[^"'"'"' ]+\.(js|css)' | sort -u || true)"
if [[ -z "$assets" ]]; then
  fail "未从 index.html 提取到静态资源"
else
  for a in $assets; do
    if curl -fs --max-time 10 -o /dev/null "$SITE/$a"; then pass "资源 $a"; else fail "资源 $a"; fi
  done
fi

# 4. PWA manifest（start_url/scope 须含部署子路径）
manifest_body="$(curl -fs --max-time 10 "$SITE/manifest.webmanifest" 2>/dev/null || true)"
base_path="$(echo "$SITE" | sed -E 's#^https?://[^/]+##')"
if [[ "$manifest_body" == *"start_url"* && "$manifest_body" == *"$base_path"* ]]; then
  pass "PWA manifest（含子路径 ${base_path:-/}）"
else
  fail "PWA manifest（start_url/scope 应含子路径 ${base_path:-/}）"
fi

# 5-6. API
if [[ "$SKIP_API" == "1" ]]; then
  echo "SKIP  API 检查（--skip-api）"
else
  API="${API_URL:-$(echo "$SITE" | sed -E 's#(/[^/]+)?/?$##')}"
  if curl -fs --max-time 10 "$API/api/health" 2>/dev/null | grep -q '"status"'; then
    pass "API /api/health（JSON 响应）"
  else
    fail "API /api/health（应返回 JSON 状态）"
  fi
  up_code="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "$API/uploads/" || true)"
  if [[ "$up_code" =~ ^[0-9]{3}$ && "$up_code" != "000" && "$up_code" != 5* ]]; then
    pass "上传 /uploads/ 返回 $up_code（非 5xx 可接受）"
  else
    fail "上传 /uploads/ 返回 $up_code（应非 5xx）"
  fi
fi

# 7. 深链接 SPA 回退（桌面端须返回 index.html：含「数字化预案系统」且不含「移动端」）
deep_body="$(curl -fs --max-time 10 "$SITE/enterprises" 2>/dev/null || true)"
if [[ "$deep_body" == *"数字化预案系统"* && "$deep_body" != *"移动端"* ]]; then
  pass "深链接 SPA 回退（桌面 index.html）"
else
  fail "深链接 SPA 回退（应返回桌面 index.html）"
fi

# 8. 无尾斜杠
no_slash="${SITE%/}"
ns_code="$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "$no_slash" || true)"
ns_loc="$(curl -s --max-time 10 -D - -o /dev/null "$no_slash" | grep -i '^location:' | tr -d '\r' | awk '{print $2}' || true)"
if [[ "$ns_code" == "301" || "$ns_code" == "308" ]] && [[ "$ns_loc" == */ ]]; then
  pass "无尾斜杠 301/308 → 带尾斜杠"
elif [[ "$ns_code" == "200" ]]; then
  pass "无尾斜杠直接 200（容器直连形态可接受）"
else
  fail "无尾斜杠返回 $ns_code"
fi

# 9. 网关上传体积（2026-09-19 新增）
# nginx 默认 client_max_body_size 1MB：>1MB 的上传会在网关被直接 413，后端毫无记录。
# 这里用公开的登录端点发 2MB 垃圾体：413 = 网关仍卡 1MB（FAIL）；其他状态码 = 请求已到应用（PASS）。
if [[ "$SKIP_API" == "1" ]]; then
  echo "SKIP  网关上传体积检查（--skip-api）"
else
  big_tmp="$(mktemp)"
  python3 - "$big_tmp" <<'PY' 2>/dev/null || head -c 2097152 /dev/zero > "$big_tmp"
import sys
with open(sys.argv[1], "wb") as fh:
    fh.write(b'{"email":"check@example.com","password":"' + b"x" * (2 * 1024 * 1024) + b'"}')
PY
  up_body_code="$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' \
    -H 'Content-Type: application/json' --data-binary "@$big_tmp" "$API/api/v1/auth/login" || true)"
  rm -f "$big_tmp"
  if [[ "$up_body_code" == "413" ]]; then
    fail "网关上传体积：2MB 请求被 413（nginx client_max_body_size 仍为默认 1MB，见 deploy/gateway-nginx.conf.example）"
  elif [[ "$up_body_code" =~ ^[0-9]{3}$ && "$up_body_code" != "000" ]]; then
    pass "网关上传体积：2MB 请求到达应用（返回 $up_body_code，非 413）"
  else
    fail "网关上传体积：请求失败（code=$up_body_code）"
  fi

  # 10. SSE 响应头透传（后端对所有 SSE 响应带 X-Accel-Buffering: no）
  sse_hdr="$(curl -s --max-time 10 -D - -o /dev/null "$API/api/v1/plans/__probe__/generate/__probe__" \
    | grep -i '^x-accel-buffering:' | tr -d '\r' || true)"
  if [[ -z "$sse_hdr" ]]; then
    echo "WARN  未在 SSE 端点响应上取到 X-Accel-Buffering（未登录时端点会先 401，属预期；可用 check-gateway-config.sh 做静态核对）"
  elif [[ "$sse_hdr" == *no* ]]; then
    pass "SSE 响应头透传（$sse_hdr）"
  else
    fail "SSE 响应头异常（$sse_hdr）"
  fi
fi

echo "----------------------------------------"
echo "通过 $PASS 项，失败 $FAIL 项"
if [[ "$FAIL" -gt 0 ]]; then
  echo "部署验证未通过"
  exit 1
fi
echo "部署验证通过"
