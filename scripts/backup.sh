#!/usr/bin/env bash
set -euo pipefail

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

# 注意：`docker exec` 没有 -T 选项（那是 docker compose exec 的），历史脚本误用会
# 直接报 "unknown shorthand flag: 'T'"，并在重定向下留下 0 字节假备份。
dump_file="backups/emergency_plan_${stamp}.dump"
if ! docker exec "$CONTAINER" pg_dump -U postgres -d emergency_plan -Fc > "$dump_file"; then
  echo "错误: 数据库备份失败，已删除空文件。" >&2
  rm -f -- "$dump_file"
  exit 1
fi
if [[ ! -s "$dump_file" ]]; then
  echo "错误: 备份文件为 0 字节，视为失败。" >&2
  rm -f -- "$dump_file"
  exit 1
fi

# 文件资产（uploads 含企业证照/照片/楼层图；exports 含历史导出物）
# W3：只备份数据库不够——升级/误删时这些目录无法从 dump 恢复。
touch "backups/.keep"
tar czf "backups/files_${stamp}.tar.gz" \
  --exclude='backend/exports/_*' \
  --exclude='backend/exports/*.log' \
  backend/uploads backend/exports 2>/dev/null || {
    echo "警告: 文件资产归档失败（目录可能不存在），数据库备份已完成。" >&2
  }

# 保留策略：默认保留最近 10 份 dump + 10 份文件归档（可用 BACKUP_KEEP 覆盖）
KEEP="${BACKUP_KEEP:-10}"
ls -1t backups/emergency_plan_*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f -- "$old"; echo "已清理过期备份: $old"
done
ls -1t backups/files_*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f -- "$old"; echo "已清理过期文件归档: $old"
done

echo "已备份数据库: backups/emergency_plan_${stamp}.dump ($(du -h "backups/emergency_plan_${stamp}.dump" | cut -f1))"
[[ -f "backups/files_${stamp}.tar.gz" ]] && \
  echo "已备份文件资产: backups/files_${stamp}.tar.gz ($(du -h "backups/files_${stamp}.tar.gz" | cut -f1))"
echo "回滚用法: ./scripts/rollback.sh ${stamp}"
