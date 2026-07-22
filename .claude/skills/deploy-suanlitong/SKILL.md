---
name: deploy-suanlitong
description: 部署算力通到生产环境。当需要首次部署、更新生产服务、或回滚版本时触发。
---

# 部署 Skill

## 部署架构

```
┌─────────────────────────────────────┐
│          阿里云 ECS（2c4g）           │
│  ┌─────────────────────────────────┐│
│  │ docker-compose.prod.yml         ││
│  │  ├── backend (FastAPI) :8000    ││
│  │  ├── redis :6379                ││
│  │  └── postgres :5432             ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
         │
    ┌────▼────┐
    │  Vercel │  ← 前端静态资源托管
    └─────────┘
```

## 工作流程

### Step 1：构建 Docker 镜像

```bash
docker build -t suanlitong-backend:latest -f Dockerfile.backend .
docker tag suanlitong-backend:latest registry.cn-beijing.aliyuncs.com/suanlitong/backend:latest
docker push registry.cn-beijing.aliyuncs.com/suanlitong/backend:latest
```

### Step 2：部署到 ECS

```bash
ssh ecs "docker-compose -f docker-compose.prod.yml pull"
ssh ecs "docker-compose -f docker-compose.prod.yml up -d"
```

### Step 3：健康检查

```bash
curl -f http://<ecs-ip>:8000/health || echo "部署失败，触发回滚"
```

### Step 4：回滚（如需要）

```bash
ssh ecs "docker-compose -f docker-compose.prod.yml up -d --rollback"
```
