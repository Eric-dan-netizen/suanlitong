#!/bin/bash
# 算力通 · 回滚到指定版本
set -euo pipefail

ECS_HOST="${ECS_HOST:?未设置 ECS_HOST}"
PREV_VERSION="${1:-}"

if [ -z "${PREV_VERSION}" ]; then
  echo "用法: rollback.sh <上一个正常版本>"
  echo "示例: rollback.sh a1b2c3d"
  exit 1
fi

echo "⏪ 回滚到 version=${PREV_VERSION}"

ssh "${ECS_HOST}" <<REMOTE
  set -e
  cd /opt/suanlitong
  sed -i "s/VERSION=.*/VERSION=${PREV_VERSION}/" .env
  docker-compose -f docker-compose.prod.yml pull || true
  docker-compose -f docker-compose.prod.yml up -d --remove-orphans
REMOTE

echo "⏪ 回滚完成，执行健康检查..."
bash scripts/health-check.sh
