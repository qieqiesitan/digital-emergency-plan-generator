#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "用法: VITE_BASE_PATH=/子路径/ ./scripts/package-release.sh <版本号>"
  exit 1
fi
if [[ ! "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "版本号只允许字母/数字/._-"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_PATH="${VITE_BASE_PATH:-/emergency-plan-migration/}"
OUT_ROOT="$ROOT/release"
STAGE="$OUT_ROOT/emergency-plan-migration-$VERSION"

echo "==> 1/4 构建前端（node:20 容器，VITE_BASE_PATH=$BASE_PATH）"
docker run --rm -v "$ROOT/frontend:/app" -w /app -e VITE_BASE_PATH="$BASE_PATH" \
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && npm ci && npm run build"

echo "==> 2/4 组装暂存目录"
mkdir -p "$OUT_ROOT"
if [[ -e "$STAGE" ]]; then
  rm -rf -- "$STAGE"
fi
mkdir -p "$STAGE"

cp -r "$ROOT/backend" "$STAGE/backend"
find "$STAGE/backend" -type d \( -name __pycache__ -o -name .venv \) -prune -exec rm -rf {} +
rm -rf "$STAGE/backend/uploads" "$STAGE/backend/exports"

mkdir -p "$STAGE/frontend"
cp -r "$ROOT/frontend/dist" "$STAGE/frontend/dist"
cp -r "$ROOT/deploy" "$STAGE/deploy"
mkdir -p "$STAGE/scripts"
cp "$ROOT/scripts/package-release.sh" "$ROOT/scripts/backup.sh" "$STAGE/scripts/"
if [[ -f "$ROOT/scripts/deploy-check.sh" ]]; then
  cp "$ROOT/scripts/deploy-check.sh" "$STAGE/scripts/"
fi
cp "$ROOT/.env.example" "$STAGE/.env.example"

if [[ -d "$ROOT/db-init" ]]; then
  cp -r "$ROOT/db-init" "$STAGE/db-init"
else
  echo "[提示] 未找到 db-init/，请自行放入数据库恢复 SQL（db-init/01_restore.sql）"
fi
if [[ -d "$ROOT/model-cache/chroma" ]]; then
  cp -r "$ROOT/model-cache" "$STAGE/model-cache"
else
  echo "[提示] 未找到 model-cache/chroma/，请从现有部署复制 ONNX 模型缓存"
fi

echo "==> 3/4 打包"
cd "$OUT_ROOT"
tar czf "emergency-plan-migration-$VERSION.tar.gz" "emergency-plan-migration-$VERSION"
sha256sum "emergency-plan-migration-$VERSION.tar.gz" > "emergency-plan-migration-$VERSION.tar.gz.sha256"

echo "==> 4/4 产物"
ls -lh "$OUT_ROOT/emergency-plan-migration-$VERSION.tar.gz" \
      "$OUT_ROOT/emergency-plan-migration-$VERSION.tar.gz.sha256"
