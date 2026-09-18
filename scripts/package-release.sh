#!/usr/bin/env bash
set -euo pipefail

# CRLF 自检：Windows 检出后 shebang 会变成 "#!/usr/bin/env bash\r" 而无法执行
if head -1 "$0" | grep -q $'\r'; then
  echo "错误: 本脚本为 CRLF 行尾，Linux 下无法执行。" >&2
  echo "修复: sed -i 's/\r$//' scripts/*.sh  （或 git add --renormalize scripts）" >&2
  exit 1
fi

MODE="full"
SKIP_BUILD=0
while [[ "$#" -gt 0 ]]; do
  case "${1:-}" in
    --upgrade) MODE="upgrade"; shift ;;
    --system) MODE="system"; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    *) break ;;
  esac
done

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "用法: VITE_BASE_PATH=/子路径/ ./scripts/package-release.sh [--upgrade] <版本号>"
  echo "  --upgrade  组装升级包（不含 db-init/、model-cache/、backend/uploads、backend/exports）"
  echo "  --system   组装系统包（含模型，不含 db-init 数据库数据、backend/uploads、backend/exports）"
  echo "  --skip-build 跳过前端构建，使用现有 frontend/dist"
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

NODE_IMAGE="${NODE_IMAGE:-node:20-alpine}"
if [[ "$SKIP_BUILD" == "1" ]]; then
  echo "==> 1/4 跳过前端构建（使用现有 frontend/dist）"
else
  echo "==> 1/4 构建前端（$NODE_IMAGE 容器，VITE_BASE_PATH=$BASE_PATH）"
  docker run --rm -v "$ROOT/frontend:/app" -w /app -e VITE_BASE_PATH="$BASE_PATH" \
    "$NODE_IMAGE" sh -c "npm config set registry https://registry.npmmirror.com && (npm ci 2>/dev/null || npm install) && npm run build"
fi

echo "==> 2/4 组装暂存目录（$PACK_NAME）"
mkdir -p "$OUT_ROOT"
if [[ -e "$STAGE" ]]; then
  rm -rf -- "$STAGE"
fi
mkdir -p "$STAGE"

# backend 只取 git 跟踪内容（避免把本机 gitignored 的本地索引、缓存等带进包）
# 升级包/系统包额外排除运行时数据目录 backend/uploads、backend/exports（含被 git 跟踪的样例数据）
mkdir -p "$STAGE/backend"
if [[ "$MODE" == "full" ]]; then
  git -C "$ROOT" ls-files backend | \
    git -C "$ROOT" checkout-index --prefix="$STAGE/" --stdin --force
else
  git -C "$ROOT" ls-files backend | grep -v -E '^backend/(uploads|exports)(/|$)' | \
    git -C "$ROOT" checkout-index --prefix="$STAGE/" --stdin --force
fi

if [[ "$MODE" == "system" ]]; then
  # 系统包追加本机 CLIP 视觉模型（git 忽略，AI 识别功能依赖，缺失时优雅降级）
  if [[ -d "$ROOT/backend/models" ]] && [[ -n "$(ls -A "$ROOT/backend/models" 2>/dev/null)" ]]; then
    mkdir -p "$STAGE/backend/models"
    cp "$ROOT/backend/models/"* "$STAGE/backend/models/"
    echo "  [system] 已附带 backend/models/（CLIP 视觉模型）"
  else
    echo "[警告] 未找到 backend/models/（CLIP 视觉模型），AI 图片识别将降级"
  fi
fi

mkdir -p "$STAGE/frontend"
cp -r "$ROOT/frontend/dist" "$STAGE/frontend/dist"
cp -r "$ROOT/deploy" "$STAGE/deploy"
if [[ "$MODE" != "full" ]]; then
  # 升级包/系统包随带完整 docs/（含部署手册「升级」章节）
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
if [[ "$MODE" != "full" && -f "$ROOT/scripts/upgrade.sh" ]]; then
  cp "$ROOT/scripts/upgrade.sh" "$STAGE/scripts/"
fi
cp "$ROOT/.env.example" "$STAGE/.env.example"

if [[ "$MODE" == "full" ]]; then
  if [[ -d "$ROOT/db-init" ]]; then
    cp -r "$ROOT/db-init" "$STAGE/db-init"
  else
    echo "[提示] 未找到 db-init/，请自行放入数据库恢复 SQL（db-init/01_restore.sql）"
  fi
fi

if [[ "$MODE" != "upgrade" ]]; then
  if [[ -d "$ROOT/model-cache/chroma" ]]; then
    cp -r "$ROOT/model-cache" "$STAGE/model-cache"
    echo "  [$( [[ "$MODE" == "system" ]] && echo system || echo full )] 已附带 model-cache/（chroma ONNX 模型缓存）"
  else
    echo "[提示] 未找到 model-cache/chroma/，请从现有部署复制 ONNX 模型缓存"
  fi
fi

if [[ "$MODE" == "system" ]]; then
  # 系统包随带生产 compose（与 deploy/docker-compose.prod.yml 同源，供直接部署）
  cp "$ROOT/deploy/docker-compose.prod.yml" "$STAGE/docker-compose.yml"
fi

if [[ "$MODE" != "full" ]]; then
  # 包根 VERSION + CHANGELOG.md（迁移说明引用部署手册「升级」章节）
  echo "$VERSION" > "$STAGE/VERSION"
  if [[ "$MODE" == "system" ]]; then
    cat > "$STAGE/部署说明.txt" <<'EOF'
============================================
  数字化预案系统 系统包 · 傻瓜式部署说明
============================================

【场景 A：公司已有旧系统，只换系统（最常见，推荐）】

1) 上传本包到服务器部署目录，解压覆盖：
   tar xzf emergency-plan-migration-*.tar.gz -C . --strip-components=1

2) 执行一条命令（自动完成：备份 -> 换后端代码 -> 重启 -> 自检）：
   ./scripts/upgrade.sh

   如需同时自动发布前端静态文件，把网关静态目录填上：
   ./scripts/upgrade.sh 0.3.1 /home/www/html/emergency-plan-migration

3) 等命令跑完（最后会提示验证结果），打开网页登录即可。
   数据不会丢：数据库、上传文件、配置全部保留。

【场景 B：全新服务器安装】

1) 解压（同上）。
2) 生成配置并修改 2 个必填值：
   cp .env.example .env
   vi .env
   必改：SECRET_KEY、POSTGRES_PASSWORD
3) 一键启动（自动建库建表）：
   ./scripts/deploy.sh
4) 按脚本最后提示，把 frontend/dist/* 复制到网关静态目录，
   并参考 deploy/gateway-nginx.conf.example 配置 nginx 反向代理
   /api、/uploads、/signs 到后端 8000 端口。

【出问题怎么办】
- 数据库备份自动生成在 backups/ 目录，找开发即可回滚。
- 完整文档在 docs/deploy/README-DEPLOY.md，一般用不到。
============================================
EOF
  fi
  if [[ "$MODE" == "system" ]]; then
    cat > "$STAGE/CHANGELOG.md" <<EOF
# CHANGELOG

## $VERSION（$(date +%Y-%m-%d)）

### 本包内容（系统包）

- 系统包版本：$VERSION（backend 代码 + 前端静态资源 + deploy/ + docs/ + scripts/ + .env.example + 模型）。
- 附带模型：model-cache/chroma（chroma ONNX 向量模型缓存）、backend/models（CLIP 视觉模型）。
- 不包含数据库数据：db-init/、backend/uploads、backend/exports，解压覆盖部署目录不会触碰公司服务器数据。

### 数据库迁移

- 本包捆绑 backend/db_migration_*.sql 全部迁移脚本（随 backend 代码已含）。
- backend 启动时由迁移运行器自动应用：已有记录跳过、新脚本逐条事务执行、失败 fail-fast 回滚。
- 空库需执行全部捆绑迁移时使用逃生口 MIGRATE_FRESH=1，详见 .env.example。
- 迁移说明与升级步骤：见 docs/deploy/README-DEPLOY.md「升级」章节。

### 部署/替换步骤

1. 备份现有部署：./scripts/backup.sh（或手动备份数据卷 pgdata）。
2. 在部署目录解压本包覆盖旧系统：tar xzf emergency-plan-migration-$VERSION.tar.gz -C <部署根目录> --strip-components=1
3. 启动/升级：docker compose -f docker-compose.yml --project-directory . up -d --build（或 ./scripts/upgrade.sh $VERSION）
4. 完整步骤、检查清单与回滚：见 docs/deploy/README-DEPLOY.md「升级」「回滚」章节。
EOF
  else
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
fi

# 行尾规范化：Windows 检出可能是 CRLF/BOM，包内脚本/配置统一转 LF 并去除 BOM（Linux 部署必需）
find "$STAGE" -type f \( -name '*.sh' -o -name '.env.example' -o -name '*.yml' -o -name 'gateway-nginx.conf.example' \) \
  -exec sed -i -e 's/\r$//' -e '1s/^\xEF\xBB\xBF//' {} +

echo "==> 3/4 打包"
cd "$OUT_ROOT"
tar czf "$PACK_NAME.tar.gz" "$PACK_NAME"
sha256sum "$PACK_NAME.tar.gz" > "$PACK_NAME.tar.gz.sha256"

echo "==> 4/4 产物"
ls -lh "$OUT_ROOT/$PACK_NAME.tar.gz" \
      "$OUT_ROOT/$PACK_NAME.tar.gz.sha256"
