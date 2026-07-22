#!/bin/bash
# 算力通 · 生产部署脚本
set -euo pipefail

VERSION="${1:-$(git rev-parse --short HEAD)}"
ECS_HOST="${ECS_HOST:?未设置 ECS_HOST}"
REGISTRY="registry.cn-beijing.aliyuncs.com/suanlitong"

echo "=== 部署 version=${VERSION} → ${ECS_HOST} ==="

cat <<EOF > .env.prod
VERSION=${VERSION}
DATABASE_URL=${PROD_DATABASE_URL}
REDIS_URL=${PROD_REDIS_URL}
ALIYUN_ACCESS_KEY_ID=${ALIYUN_ACCESS_KEY_ID:-}
ALIYUN_ACCESS_KEY_SECRET=${ALIYUN_ACCESS_KEY_SECRET:-}
HUAWEI_ACCESS_KEY_ID=${HUAWEI_ACCESS_KEY_ID:-}
HUAWEI_ACCESS_KEY_SECRET=${HUAWEI_ACCESS_KEY_SECRET:-}
TENCENT_SECRET_ID=${TENCENT_SECRET_ID:-}
TENCENT_SECRET_KEY=${TENCENT_SECRET_KEY:-}
APP_HOST=0.0.0.0
APP_PORT=8000
EOF

scp docker-compose.prod.yml .env.prod "${ECS_HOST}:/opt/suanlitong/"
rm -f .env.prod

ssh "${ECS_HOST}" <<'REMOTE'
  set -e
  cd /opt/suanlitong
  mv .env.prod .env
  docker-compose -f docker-compose.prod.yml pull
  docker-compose -f docker-compose.prod.yml up -d --remove-orphans
  docker image prune -af --filter "until=24h"
REMOTE

echo "=== 部署完成 ==="
