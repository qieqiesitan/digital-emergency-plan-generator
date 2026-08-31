#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"
GATEWAY_STATIC_DIR="${2:-}"
SITE_URL="${3:-}"
API_URL="${4:-}"

usage() {
  echo "用法: ./scripts/upgrade.sh <版本号> [网关静态目录] [站点URL] [API URL]"
  echo "示例: ./scripts/upgrade.sh 0.3.0 /home/sxby/html/emergency-plan-migration"
  echo "      ./scripts/upgrade.sh 0.3.0 /home/sxby/html/emergency-plan-migration https://deom2025.sxbych.com/emergency-plan-migration/ https://deom2025.sxbych.com"
  echo "说明: 需在解压后的升级包根目录执行（包根应含 VERSION 与 CHANGELOG.md）。"
}

if [[ -z "$VERSION" ]]; then
  usage
  exit 1
fi

# 1) 校验 VERSION 文件存在且与参数一致
echo "==> 1/6 校验 VERSION"
if [[ ! -f "$ROOT/VERSION" ]]; then
  echo "错误: 未找到 VERSION 文件。请确认已在部署目录解压升级包（包根应含 VERSION 与 CHANGELOG.md）。" >&2
  exit 1
fi
CURRENT_VERSION="$(cat "$ROOT/VERSION")"
if [[ "$CURRENT_VERSION" != "$VERSION" ]]; then
  echo "错误: VERSION 文件内容为 '$CURRENT_VERSION'，与参数 '$VERSION' 不一致。" >&2
  exit 1
fi
echo "    VERSION=$VERSION 校验通过"

# 2) 强制备份（失败即中止）
echo "==> 2/6 强制备份数据库（backups/）"
./scripts/backup.sh

# 3) 替换 backend 代码（保留 .env、数据卷、backups/、uploads/、exports/、model-cache/）
echo "==> 3/6 替换 backend 代码（保留运行时数据）"
if [[ ! -d "$ROOT/backend" ]]; then
  echo "错误: 未找到 backend/ 目录，请确认在解压后的升级包根目录执行。" >&2
  exit 1
fi
# 升级包不含 uploads/、exports/ 等运行时数据目录：解压覆盖部署目录后，
# 这些目录及其数据、以及 .env、backups/、model-cache/、compose 数据卷 pgdata 均原样保留。
# 兜底：清理旧版本遗留的 Python 编译产物，避免陈旧字节码干扰新代码。
find "$ROOT/backend" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
mkdir -p "$ROOT/backend/uploads" "$ROOT/backend/exports"
echo "    backend 代码已就绪（VERSION=$VERSION），运行时目录已保留"

# 4) 更新网关静态目录
echo "==> 4/6 更新网关静态目录"
if [[ -z "$GATEWAY_STATIC_DIR" ]]; then
  echo "    未提供网关静态目录参数。"
  echo "    请人工更新网关静态目录: cp -r frontend/dist/* <网关静态目录>/emergency-plan-migration/"
else
  if [[ ! -d "$ROOT/frontend/dist" ]]; then
    echo "错误: 未找到 frontend/dist/（升级包缺少前端构建产物）。" >&2
    exit 1
  fi
  mkdir -p "$GATEWAY_STATIC_DIR"
  # 注意：仅复制不清理旧文件，避免误删网关目录中其他内容；
  # 若需移除新版本已删除的旧静态资源，请人工清理目标目录后再复制。
  cp -r "$ROOT/frontend/dist/"* "$GATEWAY_STATIC_DIR/"
  echo "    已复制 frontend/dist/* 到 $GATEWAY_STATIC_DIR"
fi

# 5) 构建并启动后端栈
echo "==> 5/6 构建并启动后端栈（postgres + backend）"
docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build

# 6) 部署验证（缺参则提示）
echo "==> 6/6 部署验证"
if [[ -z "$SITE_URL" ]]; then
  read -r -p "    站点 URL（如 https://deom2025.sxbych.com/emergency-plan-migration/）: " SITE_URL || true
fi
if [[ -z "$API_URL" ]]; then
  read -r -p "    API URL（如 https://deom2025.sxbych.com）: " API_URL || true
fi
if [[ -z "$SITE_URL" || -z "$API_URL" ]]; then
  echo "    未提供站点/API URL，跳过自动部署验证。"
  echo "    请手动执行: ./scripts/deploy-check.sh <站点URL> <API URL>"
  echo "    如验证失败，可用 backups/ 中的最新备份回滚（见 docs/deploy/README-DEPLOY.md「回滚」章节）。"
else
  if ./scripts/deploy-check.sh "$SITE_URL" "$API_URL"; then
    echo "==> 部署验证通过，升级完成。"
  else
    echo "!! 部署验证未通过！"
    echo "!! 回滚提示：用 backups/ 中最新备份恢复数据库，并恢复旧版本代码/配置"
    echo "!!          （详见 docs/deploy/README-DEPLOY.md「回滚」章节）。"
    exit 1
  fi
fi
