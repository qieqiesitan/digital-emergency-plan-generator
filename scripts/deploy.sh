#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> 已从 .env.example 创建 .env"
  echo "    ⚠ 请务必先编辑 .env，修改 SECRET_KEY 与 POSTGRES_PASSWORD（生产环境不要用默认值）"
fi

echo "==> 1/3 构建并启动后端栈（postgres + backend）"
docker compose -f deploy/docker-compose.prod.yml --project-directory . up -d --build

echo "==> 2/3 等待后端就绪（GET /api/health）"
for i in $(seq 1 30); do
  if curl -fs --max-time 5 "http://127.0.0.1:8000/api/health" 2>/dev/null | grep -q '"status"'; then
    echo "后端已就绪: http://127.0.0.1:8000/api/health"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "后端未在 90 秒内就绪，请查看日志: docker compose logs -f backend"
    exit 1
  fi
  sleep 3
done

echo "==> 3/3 剩余部署步骤"
echo "  1) 前端静态发布: cp -r frontend/dist/* <网关静态目录>/emergency-plan-migration/"
echo "  2) 网关 nginx 按 deploy/gateway-nginx.conf.example 配置，然后 docker restart proxy"
echo "  3) 验证: ./scripts/deploy-check.sh <站点URL> <API URL>"
echo "完整步骤见 docs/deploy/README-DEPLOY.md"
