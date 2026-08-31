#!/usr/bin/env bash
set -euo pipefail

MODE="full"
if [[ "${1:-}" == "--upgrade" ]]; then
  MODE="upgrade"
  shift
fi

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "用法: VITE_BASE_PATH=/子路径/ ./scripts/package-release.sh [--upgrade] <版本号>"
  echo "  --upgrade  组装升级包（不含 db-init/、model-cache/、backend/uploads、backend/exports）"
  exit 1
fi
if [[ ! "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "版本号只允许字母/数字/._-"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_PATH="${VITE_BASE_PATH:-/emergency-plan-migration/}"
OUT_ROOT="$ROOT/release"
PACK_NAME="emergency-plan-migration-$VERSION"
if [[ "$MODE" == "upgrade" ]]; then
  PACK_NAME="$PACK_NAME-upgrade"
fi
STAGE="$OUT_ROOT/$PACK_NAME"

echo "==> 1/4 构建前端（node:20 容器，VITE_BASE_PATH=$BASE_PATH）"
docker run --rm -v "$ROOT/frontend:/app" -w /app -e VITE_BASE_PATH="$BASE_PATH" \
  node:20 sh -c "npm config set registry https://registry.npmmirror.com && (npm ci 2>/dev/null || npm install) && npm run build"

echo "==> 2/4 组装暂存目录（$PACK_NAME）"
mkdir -p "$OUT_ROOT"
if [[ -e "$STAGE" ]]; then
  rm -rf -- "$STAGE"
fi
mkdir -p "$STAGE"

# backend 只取 git 跟踪内容（避免把本机 gitignored 的 models/、本地索引等带进包）
# 升级包额外排除运行时数据目录 backend/uploads、backend/exports（含被 git 跟踪的样例数据）
mkdir -p "$STAGE/backend"
if [[ "$MODE" == "upgrade" ]]; then
  git -C "$ROOT" ls-files backend | grep -v -E '^backend/(uploads|exports)(/|$)' | \
    git -C "$ROOT" checkout-index --prefix="$STAGE/" --stdin --force
else
  git -C "$ROOT" ls-files backend | git -C "$ROOT" checkout-index --prefix="$STAGE/" --stdin --force
fi

mkdir -p "$STAGE/frontend"
cp -r "$ROOT/frontend/dist" "$STAGE/frontend/dist"
cp -r "$ROOT/deploy" "$STAGE/deploy"
if [[ "$MODE" == "upgrade" ]]; then
  # 升级包随带完整 docs/（含部署手册「升级」章节）
  cp -r "$ROOT/docs" "$STAGE/docs"
else
  if [[ -f "$ROOT/docs/deploy/README-DEPLOY.md" ]]; then
    mkdir -p "$STAGE/docs/deploy"
    cp "$ROOT/docs/deploy/README-DEPLOY.md" "$STAGE/docs/deploy/"
  fi
fi

mkdir -p "$STAGE/scripts"
cp "$ROOT/scripts/package-release.sh" "$ROOT/scripts/backup.sh" "$ROOT/scripts/deploy.sh" "$STAGE/scripts/"
if [[ -f "$ROOT/scripts/deploy-check.sh" ]]; then
  cp "$ROOT/scripts/deploy-check.sh" "$STAGE/scripts/"
fi
if [[ "$MODE" == "upgrade" && -f "$ROOT/scripts/upgrade.sh" ]]; then
  cp "$ROOT/scripts/upgrade.sh" "$STAGE/scripts/"
fi
cp "$ROOT/.env.example" "$STAGE/.env.example"

if [[ "$MODE" == "full" ]]; then
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
fi

if [[ "$MODE" == "upgrade" ]]; then
  # 包根 VERSION + CHANGELOG.md（迁移说明引用部署手册「升级」章节）
  echo "$VERSION" > "$STAGE/VERSION"
  cat > "$STAGE/CHANGELOG.md" <<EOF
# CHANGELOG

## $VERSION（$(date +%Y-%m-%d)）

### 升级内容

- 升级包版本：$VERSION（backend 代码 + 前端静态资源 + deploy/ + docs/ + scripts/ + .env.example）。
- 不包含运行时数据：db-init/、model-cache/、backend/uploads、backend/exports，解压覆盖部署目录时不会触碰公司服务器数据。

### 数据库迁移

- 本包捆绑 backend/db_migration_*.sql 全部迁移脚本（随 backend 代码已含）。
- backend 启动时由迁移运行器自动应用：已有记录跳过、新脚本逐条事务执行、失败 fail-fast 回滚。
- 空库需执行全部捆绑迁移时使用逃生口 MIGRATE_FRESH=1，详见 .env.example。
- 迁移说明与升级步骤：见 docs/deploy/README-DEPLOY.md「升级」章节。

### 升级步骤

1. 在部署目录解压升级包覆盖旧代码：tar xzf emergency-plan-migration-$VERSION-upgrade.tar.gz -C <部署根目录> --strip-components=1
2. 执行升级：./scripts/upgrade.sh $VERSION [网关静态目录] [站点URL] [API URL]
3. 完整步骤、检查清单与回滚：见 docs/deploy/README-DEPLOY.md「升级」「回滚」章节。
EOF
fi

echo "==> 3/4 打包"
cd "$OUT_ROOT"
tar czf "$PACK_NAME.tar.gz" "$PACK_NAME"
sha256sum "$PACK_NAME.tar.gz" > "$PACK_NAME.tar.gz.sha256"

echo "==> 4/4 产物"
ls -lh "$OUT_ROOT/$PACK_NAME.tar.gz" \
      "$OUT_ROOT/$PACK_NAME.tar.gz.sha256"
