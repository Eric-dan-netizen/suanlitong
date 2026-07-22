---
name: deploy-suanlitong
description: 部署算力通到生产环境。触发场景：首次部署、更新生产服务、回滚版本、配置 CI/CD 部署流水线、搭建开发/预发环境。
---

# 算力通 · 部署 Skill

## 部署架构

```
                          ┌──────────┐
                          │  Vercel  │ ← 前端 React SPA（自动 HTTPS + CDN）
                          └────┬─────┘
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                    DNS (api.suanlitong.cn)           │
    └──────────────────────────┼──────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    阿里云 ECS（2c4g 起步）                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              docker-compose.prod.yml                  │    │
│  │                                                      │    │
│  │  ┌──────────────────┐  ┌──────────┐  ┌───────────┐  │    │
│  │  │ backend:8000     │  │ redis    │  │ postgres  │  │    │
│  │  │ FastAPI + Uvicorn│  │ :6379    │  │ :5432     │  │    │
│  │  │ 4 workers        │  │ 缓存/队列 │  │ 持久化    │  │    │
│  │  └──────────────────┘  └──────────┘  └───────────┘  │    │
│  │                                                      │    │
│  │  ┌──────────────────┐  ┌──────────────────────────┐  │    │
│  │  │ celery-worker    │  │ celery-beat              │  │    │
│  │  │ 异步任务          │  │ 定时任务（价格采集/巡检）  │  │    │
│  │  └──────────────────┘  └──────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    nginx :80/:443                     │    │
│  │        反向代理 → backend + Let's Encrypt 自动续期    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 环境矩阵

| 环境 | 用途 | 触发方式 | ECS 规格 | 域名 |
|------|------|----------|----------|------|
| `dev` | 本地开发 | `docker-compose up` | 本地 | localhost |
| `staging` | 预发验证 | PR merge → `staging` 分支 | 2c4g | staging.suanlitong.cn |
| `prod` | 生产环境 | Release tag `v*` | 4c8g+ | api.suanlitong.cn |

---

## 前置条件

部署前必须确认以下全部就绪：

- [ ] CI 流水线全绿（lint + test + deps-check）
- [ ] 阿里云容器镜像仓库已创建（`registry.cn-beijing.aliyuncs.com/suanlitong`）
- [ ] ECS 实例已开通，安全组放行 80/443/8000
- [ ] 域名已备案 + DNS 解析指向 ECS 公网 IP
- [ ] SSL 证书（Let's Encrypt）已配置
- [ ] 以下 GitHub Secrets 已配置：
  - `ALIYUN_REGISTRY_USER` / `ALIYUN_REGISTRY_PASSWORD`
  - `ECS_HOST` / `ECS_USER` / `ECS_SSH_KEY`
  - `PROD_DATABASE_URL` / `PROD_REDIS_URL`
  - 各云厂商 AccessKey（`ALIYUN_ACCESS_KEY_ID` 等）

---

## 工作流程

### Step 1：预部署验证

```bash
# 1.1 确认 CI 已通过（若未通过，先修复）
gh run list --branch main --limit 1 --json conclusion

# 1.2 本地冒烟测试
python3 -m pytest src/ -q
curl -f http://localhost:8000/health

# 1.3 检查 git 状态（确认在 main 且无脏文件）
git status --short && echo "✅ Clean" || echo "❌ Dirty — 先提交或 stash"
```

### Step 2：构建 Docker 镜像

```bash
#!/bin/bash
# 文件: scripts/build-and-push.sh
set -euo pipefail

VERSION="${1:-$(git rev-parse --short HEAD)}"
REGISTRY="registry.cn-beijing.aliyuncs.com/suanlitong"

echo "=== 构建镜像 version=${VERSION} ==="

# 2.1 构建 backend 镜像
docker build \
  -t "${REGISTRY}/backend:${VERSION}" \
  -t "${REGISTRY}/backend:latest" \
  -f docker/Dockerfile.backend .

# 2.2 构建 celery-worker 镜像（与 backend 同镜像，不同入口）
docker tag "${REGISTRY}/backend:${VERSION}" "${REGISTRY}/celery-worker:${VERSION}"

# 2.3 构建 nginx 镜像
docker build \
  -t "${REGISTRY}/nginx:${VERSION}" \
  -f docker/Dockerfile.nginx \
  docker/

echo "=== 推送镜像 ==="
docker push "${REGISTRY}/backend:${VERSION}"
docker push "${REGISTRY}/backend:latest"
docker push "${REGISTRY}/celery-worker:${VERSION}"
docker push "${REGISTRY}/nginx:${VERSION}"

echo "=== 完成: ${VERSION} ==="
```

### Step 3：部署到 ECS

```bash
#!/bin/bash
# 文件: scripts/deploy.sh
set -euo pipefail

VERSION="${1:-$(git rev-parse --short HEAD)}"
ECS_HOST="${ECS_HOST:?未设置 ECS_HOST}"
REGISTRY="registry.cn-beijing.aliyuncs.com/suanlitong"

echo "=== 部署 version=${VERSION} → ${ECS_HOST} ==="

# 3.1 生成 .env.prod（从 GitHub Secrets 注入）
cat <<EOF > .env.prod
VERSION=${VERSION}
DATABASE_URL=${PROD_DATABASE_URL}
REDIS_URL=${PROD_REDIS_URL}
ALIYUN_ACCESS_KEY_ID=${ALIYUN_ACCESS_KEY_ID}
ALIYUN_ACCESS_KEY_SECRET=${ALIYUN_ACCESS_KEY_SECRET}
HUAWEI_ACCESS_KEY_ID=${HUAWEI_ACCESS_KEY_ID}
HUAWEI_ACCESS_KEY_SECRET=${HUAWEI_ACCESS_KEY_SECRET}
TENCENT_SECRET_ID=${TENCENT_SECRET_ID}
TENCENT_SECRET_KEY=${TENCENT_SECRET_KEY}
APP_HOST=0.0.0.0
APP_PORT=8000
EOF

# 3.2 上传 docker-compose 和 .env 到 ECS
scp docker-compose.prod.yml .env.prod "${ECS_HOST}:/opt/suanlitong/"
rm -f .env.prod

# 3.3 拉取新镜像并滚动更新
ssh "${ECS_HOST}" <<'REMOTE'
  set -e
  cd /opt/suanlitong
  mv .env.prod .env
  
  # 登录容器镜像仓库
  echo "${ALIYUN_REGISTRY_PASSWORD}" | \
    docker login registry.cn-beijing.aliyuncs.com -u "${ALIYUN_REGISTRY_USER}" --password-stdin
  
  # 拉取新镜像
  docker-compose -f docker-compose.prod.yml pull
  
  # 滚动重启（零停机）
  docker-compose -f docker-compose.prod.yml up -d --remove-orphans
  
  # 清理旧镜像（保留最近 3 个版本）
  docker image prune -af --filter "until=24h"
REMOTE

echo "=== 部署完成 ==="
```

### Step 4：健康检查 + 冒烟测试

```bash
#!/bin/bash
# 文件: scripts/health-check.sh
set -euo pipefail

API_URL="${1:-https://api.suanlitong.cn}"

echo "=== 健康检查 ${API_URL} ==="

# 4.1 基础健康检查
STATUS=$(curl -sf "${API_URL}/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
if [ "$STATUS" != "ok" ]; then
  echo "❌ /health 失败: status=${STATUS}"
  exit 1
fi
echo "✅ /health → ok"

# 4.2 价格 API 冒烟测试
PRICES=$(curl -sf "${API_URL}/api/v1/prices?gpu_type=A100")
COUNT=$(echo "$PRICES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
if [ "$COUNT" -eq 0 ]; then
  echo "⚠️  /api/v1/prices 返回空（可能数据尚未采集）"
else
  echo "✅ /api/v1/prices?gpu_type=A100 → ${COUNT} 条记录"
fi

# 4.3 实例 API 冒烟测试（不创建真实实例）
CODE=$(curl -so /dev/null -w "%{http_code}" "${API_URL}/api/v1/instances")
if [ "$CODE" -eq 200 ]; then
  echo "✅ /api/v1/instances → 200"
else
  echo "❌ /api/v1/instances → ${CODE}"
  exit 1
fi

echo "=== 健康检查全部通过 ==="
```

### Step 5：回滚（如健康检查失败）

```bash
#!/bin/bash
# 文件: scripts/rollback.sh
set -euo pipefail

ECS_HOST="${ECS_HOST:?未设置 ECS_HOST}"
PREV_VERSION="${1}"  # 上一个已知正常的版本

if [ -z "${PREV_VERSION}" ]; then
  echo "用法: rollback.sh <上一个正常版本>"
  echo "示例: rollback.sh a1b2c3d"
  exit 1
fi

echo "⏪ 回滚到 version=${PREV_VERSION}"

ssh "${ECS_HOST}" <<REMOTE
  set -e
  cd /opt/suanlitong
  
  # 修改 .env 中的版本号
  sed -i "s/VERSION=.*/VERSION=${PREV_VERSION}/" .env
  
  # 拉取旧版本镜像（通常已在本地缓存）
  docker-compose -f docker-compose.prod.yml pull || true
  
  # 切换到旧版本
  docker-compose -f docker-compose.prod.yml up -d --remove-orphans
REMOTE

echo "⏪ 回滚完成，请执行健康检查确认"
bash scripts/health-check.sh
```

---

## docker-compose.prod.yml 模板

```yaml
# 文件: docker-compose.prod.yml
version: "3.8"

services:
  nginx:
    image: registry.cn-beijing.aliyuncs.com/suanlitong/nginx:${VERSION:-latest}
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./certbot/www:/var/www/certbot:ro
      - ./certbot/conf:/etc/letsencrypt:ro
    depends_on:
      - backend
    restart: always

  backend:
    image: registry.cn-beijing.aliyuncs.com/suanlitong/backend:${VERSION:-latest}
    expose:
      - "8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - ALIYUN_ACCESS_KEY_ID=${ALIYUN_ACCESS_KEY_ID}
      - ALIYUN_ACCESS_KEY_SECRET=${ALIYUN_ACCESS_KEY_SECRET}
      - HUAWEI_ACCESS_KEY_ID=${HUAWEI_ACCESS_KEY_ID}
      - HUAWEI_ACCESS_KEY_SECRET=${HUAWEI_ACCESS_KEY_SECRET}
      - TENCENT_SECRET_ID=${TENCENT_SECRET_ID}
      - TENCENT_SECRET_KEY=${TENCENT_SECRET_KEY}
      - APP_HOST=0.0.0.0
      - APP_PORT=8000
    command: uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  redis:
    image: redis:7-alpine
    expose:
      - "6379"
    volumes:
      - redis_data:/data
    restart: always

  postgres:
    image: postgres:16-alpine
    expose:
      - "5432"
    environment:
      - POSTGRES_USER=suanlitong
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=suanlitong
    volumes:
      - pg_data:/var/lib/postgresql/data
    restart: always

  celery-worker:
    image: registry.cn-beijing.aliyuncs.com/suanlitong/celery-worker:${VERSION:-latest}
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    command: celery -A src.backend.app.tasks worker --loglevel=info --concurrency=2
    restart: always

  celery-beat:
    image: registry.cn-beijing.aliyuncs.com/suanlitong/celery-worker:${VERSION:-latest}
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    command: celery -A src.backend.app.tasks beat --loglevel=info
    restart: always

volumes:
  redis_data:
  pg_data:
```

---

## GitHub Actions 自动部署

```yaml
# 文件: .github/workflows/deploy.yml
name: Deploy

on:
  push:
    tags:
      - "v*"  # v1.0.0 触发生产部署
    branches:
      - staging  # staging 分支触发预发部署

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set env
        id: env
        run: |
          if [[ "${{ github.ref }}" == refs/tags/v* ]]; then
            echo "environment=prod" >> $GITHUB_OUTPUT
          else
            echo "environment=staging" >> $GITHUB_OUTPUT
          fi
          echo "version=$(git rev-parse --short HEAD)" >> $GITHUB_OUTPUT

      - name: Login to Aliyun Registry
        uses: docker/login-action@v3
        with:
          registry: registry.cn-beijing.aliyuncs.com
          username: ${{ secrets.ALIYUN_REGISTRY_USER }}
          password: ${{ secrets.ALIYUN_REGISTRY_PASSWORD }}

      - name: Build & Push
        run: bash scripts/build-and-push.sh ${{ steps.env.outputs.version }}

      - name: Deploy
        run: bash scripts/deploy.sh ${{ steps.env.outputs.version }}

      - name: Health Check
        run: |
          if [ "${{ steps.env.outputs.environment }}" = "prod" ]; then
            bash scripts/health-check.sh https://api.suanlitong.cn
          else
            bash scripts/health-check.sh https://staging-api.suanlitong.cn
          fi
```

---

## 首次部署 Checklist

首次部署（ECS 裸机 → 服务运行）:

```bash
# 1. SSH 到 ECS
ssh root@<ecs-ip>

# 2. 安装 Docker
curl -fsSL https://get.docker.com | bash
systemctl enable docker && systemctl start docker

# 3. 安装 docker-compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 4. 创建项目目录
mkdir -p /opt/suanlitong/{nginx/conf.d,certbot/{www,conf}}
chown -R 1000:1000 /opt/suanlitong

# 5. 配置 nginx（先 HTTP-only，后续 certbot 自动添加 HTTPS）
cat <<'NGINX' > /opt/suanlitong/nginx/conf.d/default.conf
server {
    listen 80;
    server_name api.suanlitong.cn;

    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    location /health {
        proxy_pass http://backend:8000/health;
    }
}
NGINX

# 6. 首次部署（通过 GitHub Actions 或手动）
# 手动方式: 上传 docker-compose.prod.yml 和 .env → docker-compose up -d
```

---

## 常见问题

### Q: 部署后价格 API 返回空？
→ Celery beat 定时采集任务可能未触发。手动触发：
```bash
ssh "${ECS_HOST}" "docker exec suanlitong-celery-worker-1 celery -A src.backend.app.tasks call fetch_all_prices"
```

### Q: ECS 磁盘空间不足？
```bash
# 查看磁盘使用
ssh "${ECS_HOST}" "df -h /opt/suanlitong"

# 清理 Docker：删除 24 小时前的未用镜像
ssh "${ECS_HOST}" "docker image prune -af --filter 'until=24h'"
```

### Q: 如何添加新的云厂商环境变量？
1. 在 `src/backend/app/config.py` 添加配置项
2. 在 `docker-compose.prod.yml` 的 `environment` 段添加对应的 `${VAR}`
3. 在 GitHub Secrets 添加生产值
4. 在 `scripts/deploy.sh` 的 `.env.prod` 生成段添加变量

### Q: Vercel 前端如何配置 API 地址？
在 Vercel 项目设置中添加环境变量：
- `VITE_API_BASE_URL=https://api.suanlitong.cn`

`vite.config.ts` 需读取此变量，`src/api/client.ts` 使用它作为 base URL。
