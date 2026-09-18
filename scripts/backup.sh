#!/usr/bin/env bash
set -euo pipefail

# 自检：脚本被 Windows 编辑器/FTP 改出 UTF-8 BOM 时 shebang 会失效
if [[ "$(head -c3 "$0" 2>/dev/null | od -An -tx1 | tr -d ' \n')" == "efbbbf" ]]; then
  echo "错误: 本脚本含 UTF-8 BOM，无法正常执行。" >&2
  echo "修复: sed -i '1s/^\\xEF\\xBB\\xBF//' scripts/*.sh" >&2
  exit 1
fi

cd "$(cd "$(dirname "$0")" && pwd)/.."
mkdir -p backups
stamp=$(date +%Y%m%d_%H%M%S)

CONTAINER=""
while IFS= read -r line; do
  line="${line%$'\r'}"
  if [[ "$line" == "emergency-plan-db" ]]; then
    CONTAINER="$line"
    break
  fi
done < <(docker ps --format '{{.Names}}')
if [[ -z "$CONTAINER" ]]; then
  echo "错误: 未找到运行中的 postgres 容器（emergency-plan-db）。" >&2
  echo "  请确认:" >&2
  echo "  1) 数据库容器正在运行: docker ps" >&2
  echo "  2) 你是在【原部署目录】解压覆盖后执行的，而不是在新解压目录里（新目录与旧容器不在同一 compose 项目）。" >&2
  exit 1
fi

docker exec -T "$CONTAINER" pg_dump -U postgres -d emergency_plan -Fc \
  > "backups/emergency_plan_${stamp}.dump"

echo "已备份: backups/emergency_plan_${stamp}.dump"
