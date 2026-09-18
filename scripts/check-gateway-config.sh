#!/usr/bin/env bash
set -uo pipefail

# 自检：脚本被 Windows 编辑器/FTP 改出 UTF-8 BOM 时 shebang 会失效
if [[ "$(head -c3 "$0" 2>/dev/null | od -An -tx1 | tr -d ' \n')" == "efbbbf" ]]; then
  echo "错误: 本脚本含 UTF-8 BOM，无法正常执行。" >&2
  echo "修复: sed -i '1s/^\\xEF\\xBB\\xBF//' scripts/*.sh" >&2
  exit 1
fi

# CRLF 自检：Windows 检出后 shebang 会变成 "#!/usr/bin/env bash\r" 而无法执行
if head -1 "$0" | grep -q $'\r'; then
  echo "错误: 本脚本为 CRLF 行尾，Linux 下无法执行。" >&2
  echo "修复: sed -i 's/\r$//' scripts/*.sh  （或 git add --renormalize scripts）" >&2
  exit 1
fi
set -euo pipefail

# 网关 nginx 配置自检（2026-09-19 部署审计新增）
#
# 用法: ./scripts/check-gateway-config.sh /home/sxby/nginx/conf/root_domain.conf
#
# 检查项（缺失即 FAIL，退出码 1）：
#   1. 无 UTF-8 BOM（BOM 会导致 `unknown directive "﻿server"`，历史上踩过）
#   2. client_max_body_size ≥ 25m（nginx 默认 1MB，会把 >1MB 上传直接 413，
#      而应用侧上限是 20MB —— 用户表现是"上传失败"但后端日志毫无记录）
#   3. SSE 不被缓冲：proxy_buffering off + proxy_http_version 1.1 +
#      proxy_read_timeout ≥ 300s（默认 60s 会掐断长生成 → 502/504）
#   4. 真实 IP 透传：X-Real-IP / X-Forwarded-For
#   5. 子路径部署铁律：alias 指向【容器内】路径（出现 Windows 盘符或 127.0.0.1 代理即 FAIL）

CONF="${1:-}"
PASS=0
FAIL=0

pass() { echo "PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL  $1"; FAIL=$((FAIL + 1)); }
warn() { echo "WARN  $1"; }

if [[ -z "$CONF" ]]; then
  echo "用法: ./scripts/check-gateway-config.sh <nginx 配置文件路径>" >&2
  echo "示例: ./scripts/check-gateway-config.sh /home/sxby/nginx/conf/root_domain.conf" >&2
  exit 2
fi
if [[ ! -f "$CONF" ]]; then
  echo "错误: 找不到配置文件 $CONF" >&2
  exit 2
fi

echo "==> 检查网关配置: $CONF"

# 1) BOM
if head -c3 "$CONF" | od -An -tx1 | tr -d ' \n' | grep -qi '^efbbbf'; then
  fail "文件含 UTF-8 BOM（会导致 unknown directive；修复: sed -i '1s/^\\xEF\\xBB\\xBF//' '$CONF'）"
else
  pass "无 UTF-8 BOM"
fi

# 2) 上传体积
if grep -Eq '^[[:space:]]*client_max_body_size[[:space:]]+([0-9]+)m' "$CONF"; then
  # 注：无匹配时 grep 返回 1，配合 set -e/pipefail 会中断脚本，因此显式兜底
  size_mb="$(grep -Eo '^[[:space:]]*client_max_body_size[[:space:]]+[0-9]+m' "$CONF" 2>/dev/null | grep -Eo '[0-9]+' | sort -n | tail -1 || true)"
  if [[ "${size_mb:-0}" -ge 25 ]]; then
    pass "client_max_body_size=${size_mb}m（≥25m，覆盖应用 20MB 上限）"
  else
    fail "client_max_body_size=${size_mb}m < 25m：>${size_mb}MB 的上传会被网关直接 413（应用侧限 20MB）"
  fi
else
  fail "缺少 client_max_body_size（nginx 默认 1MB：>1MB 的 Excel/PDF/图片上传会被直接 413）"
fi

# 3) SSE 不缓冲
grep -Eq '^[[:space:]]*proxy_buffering[[:space:]]+off;' "$CONF" \
  && pass "proxy_buffering off（SSE 不缓冲）" \
  || fail "缺少 proxy_buffering off：SSE 会被攒满缓冲才下发，前端看不到流式增量"
grep -Eq '^[[:space:]]*proxy_http_version[[:space:]]+1\.1;' "$CONF" \
  && pass "proxy_http_version 1.1（SSE/chunked 必需）" \
  || fail "缺少 proxy_http_version 1.1：SSE 在 1.0 下无法按块下发"
timeout_val="$(grep -Eo '^[[:space:]]*proxy_read_timeout[[:space:]]+[0-9]+s' "$CONF" 2>/dev/null | grep -Eo '[0-9]+' | sort -n | tail -1 || true)"
if [[ -n "${timeout_val:-}" && "$timeout_val" -ge 300 ]]; then
  pass "proxy_read_timeout=${timeout_val}s（≥300s）"
else
  fail "proxy_read_timeout=${timeout_val:-未设置}（<300s）：长生成会被网关掐断成 502/504"
fi

# 4) 真实 IP
grep -Eq 'X-Real-IP[[:space:]]+\$remote_addr' "$CONF" \
  && pass "X-Real-IP 透传" \
  || fail "缺少 X-Real-IP：审计日志与限流会把所有用户算成网关 IP"
grep -Eq 'X-Forwarded-For[[:space:]]+\$proxy_add_x_forwarded_for' "$CONF" \
  && pass "X-Forwarded-For 透传" \
  || fail "缺少 X-Forwarded-For"

# 5) 子路径铁律
if grep -Eq '^[[:space:]]*alias[[:space:]]+[A-Za-z]:[\\/]' "$CONF"; then
  fail "alias 指向 Windows 盘符（必须是网关容器内路径）"
elif grep -Eq '^[[:space:]]*alias[[:space:]]+/' "$CONF"; then
  pass "alias 使用容器内绝对路径"
else
  warn "未检测到 alias（若本配置不托管前端静态文件可忽略）"
fi
if grep -Eq 'proxy_pass[[:space:]]+http://127\.0\.0\.1' "$CONF"; then
  fail "proxy_pass 使用 127.0.0.1（网关容器内会指向自身，需写宿主机 IP）"
else
  pass "proxy_pass 未使用 127.0.0.1"
fi

echo
echo "==> 结果: PASS=$PASS FAIL=$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo "配置未达标：请按 deploy/gateway-nginx.conf.example 补齐后重跑本脚本。" >&2
  exit 1
fi
echo "网关配置检查通过 ✅"
