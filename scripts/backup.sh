#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p backups
stamp=$(date +%Y%m%d_%H%M%S)

docker compose -f deploy/docker-compose.prod.yml --project-directory . \
  exec -T postgres pg_dump -U postgres -d emergency_plan -Fc \
  > "backups/emergency_plan_${stamp}.dump"

echo "已备份: backups/emergency_plan_${stamp}.dump"
