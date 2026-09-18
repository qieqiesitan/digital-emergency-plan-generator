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

# ============================================================
# 升级演练（2026-09-19 新增）：在独立 project 上空库跑一遍升级包核心路径
#
# 演练内容（全部在独立卷/端口上进行，不碰生产栈与生产数据）：
#   1. 用 deploy/docker-compose.rehearsal.yml 构建 backend 镜像（= 升级包内镜像构建路径）
#   2. 空库执行全部捆绑迁移（MIGRATE_FRESH=1）——历史事故多发点
#   3. 健康检查 + schema_migrations 账本与 db_migration_*.sql 数量核对
#   4. 关键表存在性抽查（users/enterprises/plan_projects/ai_configs/app_runtime_state）
#   5. 登录端点冒烟（401 = 正常；500 = 失败）+ 加密健康检查（只报不拦）
#   6. 清理（--keep 可保留现场）
#
# 用法: ./scripts/rehearsal.sh [--keep] [--no-build]
#   --keep      保留容器与卷（便于排查）
#   --no-build  不重新构建镜像，复用现有 ep-rehearsal-backend 镜像（低带宽/离线环境）
#              缺镜像时会尝试用 emergency-plan-backend 打标签；再缺则报错退出。
# ============================================================

KEEP=0
NO_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    --no-build) NO_BUILD=1 ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="deploy/docker-compose.rehearsal.yml"
PROJECT="ep-rehearsal"

PASS=0
FAIL=0
pass() { echo "PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL  $1"; FAIL=$((FAIL + 1)); }
warn() { echo "WARN  $1"; }

cleanup() {
  if [[ "$KEEP" == "1" ]]; then
    echo "==> --keep：保留容器与卷（清理命令：docker compose -p $PROJECT -f $COMPOSE_FILE down -v）"
  else
    echo "==> 清理演练栈与卷"
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "==> 0/6 环境预检"
if ! docker compose version >/dev/null 2>&1; then
  echo "错误: 需要 docker compose v2（docker compose version 失败）" >&2
  exit 2
fi
[[ -f "$COMPOSE_FILE" ]] || { echo "错误: 缺少 $COMPOSE_FILE" >&2; exit 2; }
pass "docker compose 可用、演练 compose 存在"

MIGRATION_FILES="$(ls backend/db_migration_*.sql 2>/dev/null | wc -l | tr -d ' ')"
echo "    仓库内 db_migration_*.sql：$MIGRATION_FILES 个"

echo "==> 1/6 构建并启动演练栈（端口 18000 / 15432，独立卷）"
UP_ARGS=(-d)
if [[ "$NO_BUILD" == "1" ]]; then
  if ! docker image inspect ep-rehearsal-backend >/dev/null 2>&1; then
    # 依次尝试常见本地镜像名（可用 REHEARSAL_SOURCE_IMAGE 覆盖，如 REHEARSAL_SOURCE_IMAGE=2-backend:latest）
    found=""
    for cand in "${REHEARSAL_SOURCE_IMAGE:-}" emergency-plan-backend 2-backend:latest; do
      [[ -z "$cand" ]] && continue
      if docker image inspect "$cand" >/dev/null 2>&1; then found="$cand"; break; fi
    done
    if [[ -z "$found" ]]; then
      echo "错误: --no-build 且找不到可复用镜像；请先执行不带 --no-build 的演练，" >&2
      echo "      或用 REHEARSAL_SOURCE_IMAGE=<本地 backend 镜像名> 指定" >&2
      exit 2
    fi
    docker tag "$found" ep-rehearsal-backend
    echo "    复用本地镜像 $found（已打标签 ep-rehearsal-backend）"
  fi
  UP_ARGS+=(--no-build)
else
  UP_ARGS+=(--build)
fi
if docker compose -p "$PROJECT" -f "$COMPOSE_FILE" up "${UP_ARGS[@]}" >/tmp/rehearsal-up.log 2>&1; then
  pass "演练栈启动${NO_BUILD:+（--no-build 复用镜像）}（日志: /tmp/rehearsal-up.log）"
else
  fail "演练栈启动失败"; tail -20 /tmp/rehearsal-up.log; exit 1
fi

echo "==> 2/6 等待后端健康检查（最多 180s）"
healthy=0
for _ in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:18000/api/health || true)"
  if [[ "$code" == "200" ]]; then healthy=1; break; fi
  sleep 3
done
if [[ "$healthy" == "1" ]]; then
  pass "后端 /api/health 200（空库迁移完成且应用可启动）"
else
  fail "后端健康检查超时（迁移失败最常见：查看 docker compose -p $PROJECT logs backend）"
  docker compose -p "$PROJECT" -f "$COMPOSE_FILE" logs --tail 40 backend || true
  exit 1
fi

echo "==> 3/6 迁移账本核对"
applied="$(docker compose -p "$PROJECT" -f "$COMPOSE_FILE" exec -T postgres \
  psql -U postgres -d emergency_plan -tAc "select count(*) from schema_migrations;" 2>/dev/null | tr -d '[:space:]')"
if [[ -z "${applied:-}" ]]; then
  fail "读取 schema_migrations 失败"
elif [[ "$applied" -eq "$MIGRATION_FILES" ]]; then
  pass "schema_migrations=$applied 与 db_migration_*.sql=$MIGRATION_FILES 一致"
elif [[ "$applied" -gt "$MIGRATION_FILES" ]]; then
  pass "schema_migrations=$applied ≥ 脚本数 $MIGRATION_FILES（含历史已合并迁移，视为一致）"
else
  fail "schema_migrations=$applied < 脚本数 $MIGRATION_FILES（存在未应用迁移）"
fi

echo "==> 4/6 关键表抽查"
tables="$(docker compose -p "$PROJECT" -f "$COMPOSE_FILE" exec -T postgres \
  psql -U postgres -d emergency_plan -tAc \
  "select string_agg(tablename, ',') from pg_tables where schemaname='public' and tablename in ('users','enterprises','plan_projects','ai_configs','app_runtime_state','schema_migrations');" 2>/dev/null)"
missing=""
for t in users enterprises plan_projects ai_configs app_runtime_state; do
  [[ "$tables" == *"$t"* ]] || missing="$missing $t"
done
if [[ -z "$missing" ]]; then
  pass "关键表齐全（$tables）"
else
  fail "缺少关键表：$missing"
fi

echo "==> 5/6 接口与加密健康"
login_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
  -H 'Content-Type: application/json' \
  --data '{"email":"nobody@example.com","password":"wrong-password"}' \
  http://127.0.0.1:18000/api/v1/auth/login || true)"
if [[ "$login_code" == "401" ]]; then
  pass "登录端点鉴权正常（401）"
elif [[ "$login_code" == "429" ]]; then
  warn "登录端点触发限流（429）——演练机限流状态可忽略"
else
  fail "登录端点异常返回 $login_code"
fi

if docker compose -p "$PROJECT" -f "$COMPOSE_FILE" exec -T backend \
     test -f /app/scripts/check_encryption_health.py 2>/dev/null; then
  enc_out="$(docker compose -p "$PROJECT" -f "$COMPOSE_FILE" exec -T backend \
    env PYTHONPATH=/app python /app/scripts/check_encryption_health.py 2>&1 || true)"
  if echo "$enc_out" | grep -q "加密健康检查通过"; then
    pass "加密健康检查通过（空库无坏密文）"
  else
    warn "加密健康检查提示（空库一般应通过；详见下方输出）"
    echo "$enc_out" | tail -4
  fi
else
  warn "镜像内无 check_encryption_health.py（--no-build 复用旧镜像时正常），跳过；重新构建后会自动包含"
fi

echo "==> 6/6 结果"
echo "----------------------------------------"
echo "通过 $PASS 项，失败 $FAIL 项"
if [[ "$FAIL" -gt 0 ]]; then
  echo "演练未通过：修复后重跑 ./scripts/rehearsal.sh" >&2
  exit 1
fi
echo "升级演练通过 ✅（可认为 0.3.x 升级包的迁移/启动路径可用）"
