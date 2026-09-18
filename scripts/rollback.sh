#!/usr/bin/env bash
set -euo pipefail

# 自检：脚本被 Windows 编辑器/FTP 改出 UTF-8 BOM 时 shebang 会失效
if [[ "$(head -c3 "$0" 2>/dev/null | od -An -tx1 | tr -d ' \n')" == "efbbbf" ]]; then
  echo "错误: 本脚本含 UTF-8 BOM，无法正常执行。" >&2
  exit 1
fi

# CRLF 自检：Windows 检出后 shebang 会变成 "#!/usr/bin/env bash\r" 而无法执行
if head -1 "$0" | grep -q $'\r'; then
  echo "错误: 本脚本为 CRLF 行尾，Linux 下无法执行。" >&2
  echo "修复: sed -i 's/\r$//' scripts/*.sh  （或 git add --renormalize scripts）" >&2
  exit 1
fi

cd "$(cd "$(dirname "$0")" && pwd)/.."

STAMP="${1:-}"
if [[ -z "$STAMP" ]]; then
  STAMP="$(ls -1t backups/emergency_plan_*.dump 2>/dev/null | head -1 | sed -E 's#.*emergency_plan_(.*)\.dump#\1#')"
fi
DUMP="backups/emergency_plan_${STAMP}.dump"
FILES="backups/files_${STAMP}.tar.gz"

if [[ -z "$STAMP" || ! -f "$DUMP" ]]; then
  echo "错误: 未找到备份 $DUMP" >&2
  echo "可用备份:" >&2
  ls -1t backups/emergency_plan_*.dump 2>/dev/null | sed 's/^/  /' >&2 || true
  echo "用法: ./scripts/rollback.sh [备份时间戳，缺省用最新]" >&2
  exit 1
fi

echo "将回滚到备份时间戳: $STAMP"
echo "  数据库: $DUMP"
[[ -f "$FILES" ]] && echo "  文件资产: $FILES"
echo
echo "⚠ 这会覆盖当前数据库与 uploads/exports 内容！"
read -r -p "确认回滚请输入 ROLLBACK: " confirm
if [[ "$confirm" != "ROLLBACK" ]]; then
  echo "已取消。"
  exit 1
fi

DB_CONTAINER="emergency-plan-db"
BACKEND_CONTAINER="emergency-plan-backend"

echo "==> 1/4 停止后端（避免恢复期间写入）"
docker stop "$BACKEND_CONTAINER" >/dev/null 2>&1 || true

echo "==> 2/4 恢复数据库"
# --clean --if-exists：先删旧对象再重建；恢复前先做一份"回滚前快照"兜底
SAFETY="backups/pre_rollback_$(date +%Y%m%d_%H%M%S).dump"
# docker exec 无 -T 选项；失败要立即中止，避免留下 0 字节"安全快照"
if ! docker exec "$DB_CONTAINER" pg_dump -U postgres -d emergency_plan -Fc > "$SAFETY"; then
  echo "错误: 回滚前快照生成失败，已中止回滚。" >&2
  rm -f -- "$SAFETY"
  exit 1
fi
echo "    已先生成回滚前快照: $SAFETY"
docker exec -i "$DB_CONTAINER" pg_restore -U postgres -d emergency_plan --clean --if-exists --no-owner \
  < "$DUMP"

echo "==> 3/4 恢复文件资产"
if [[ -f "$FILES" ]]; then
  tar xzf "$FILES" -C .
  echo "    已还原 backend/uploads 与 backend/exports"
else
  echo "    无文件归档，跳过（仅数据库已恢复）"
fi

echo "==> 4/4 重启后端"
docker start "$BACKEND_CONTAINER" >/dev/null 2>&1 || \
  docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d backend
for i in $(seq 1 30); do
  # 用后端容器内的 python 探活：不依赖宿主机是否装了 curl（与 prod compose healthcheck 一致）
  if docker exec "$BACKEND_CONTAINER" python -c \
    "import urllib.request,sys; sys.exit(0 if b'\"status\"' in urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5).read() else 1)" \
    >/dev/null 2>&1; then
    echo "回滚完成，后端已就绪。"
    exit 0
  fi
  sleep 3
done
echo "后端未在 90 秒内就绪，请查看日志: docker logs $BACKEND_CONTAINER" >&2
exit 1
