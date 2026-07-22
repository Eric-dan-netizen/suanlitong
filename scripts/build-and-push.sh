#!/bin/bash
# 算力通 · Docker 镜像构建 & 推送
set -euo pipefail

VERSION="${1:-$(git rev-parse --short HEAD)}"
REGISTRY="registry.cn-beijing.aliyuncs.com/suanlitong"

echo "=== 构建镜像 version=${VERSION} ==="

docker build -t "${REGISTRY}/backend:${VERSION}" -t "${REGISTRY}/backend:latest" -f docker/Dockerfile.backend .
docker tag "${REGISTRY}/backend:${VERSION}" "${REGISTRY}/celery-worker:${VERSION}"
docker build -t "${REGISTRY}/nginx:${VERSION}" -t "${REGISTRY}/nginx:latest" -f docker/Dockerfile.nginx docker/

echo "=== 推送镜像 ==="
docker push "${REGISTRY}/backend:${VERSION}"
docker push "${REGISTRY}/backend:latest"
docker push "${REGISTRY}/celery-worker:${VERSION}"
docker push "${REGISTRY}/nginx:${VERSION}"

echo "=== 完成: ${VERSION} ==="
