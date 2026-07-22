# 算力通 Phase 0 — Codex 提示词

> 生成日期：2026-07-22
> 使用方法：直接复制粘贴到 Codex，按顺序执行

---

## 执行顺序

```
第 1 轮（今天，没有依赖关系）：
  ├─ 提示词 1：@api-developer → CLI 比价工具
  ├─ 提示词 2：@agent-developer → 设备 Agent 原型
  └─ 提示词 4：@devops-engineer → Docker + CI/CD

第 2 轮（等提示词 1 完成后）：
  └─ 提示词 3：@api-developer → FastAPI 骨架

第 3 轮（等提示词 3 完成后）：
  └─ 提示词 5：@frontend-developer → React 控制台
```

---

## 提示词 1：多云比价 CLI

```
@api-developer

实现算力通多云比价 CLI 工具。文件：src/backend/cli.py

## 功能规格
命令行输入 GPU 型号，输出三家云厂商实时比价表格。

## 使用方式
python src/backend/cli.py price A100
python src/backend/cli.py price H100
python src/backend/cli.py price 4090

## 输出格式（终端表格）
┌──────────┬──────────┬──────────────┬───────────┬──────────────┐
│ 云厂商   │ GPU 型号 │ 按量付费     │ Spot 价格 │ 可用区域     │
│          │          │ （元/小时）  │（元/小时） │              │
├──────────┼──────────┼──────────────┼───────────┼──────────────┤
│ 阿里云   │ A100     │ 28.50        │ 12.80     │ cn-beijing   │
│ 华为云   │ A100     │ 30.20        │ 14.10     │ cn-north-4   │
│ 腾讯云   │ A100     │ 29.80        │ 13.50     │ ap-beijing   │
└──────────┴──────────┴──────────────┴───────────┴──────────────┘

## 技术约束
1. 认证：通过环境变量读取 AccessKey（ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET，华为云、腾讯云同理）
2. 先用 WebFetch 读阿里云 ECS DescribeInstanceTypes API 文档，确认参数名再写代码，禁止凭空编造 API 方法名
3. 每家云厂商写一个独立的 PriceFetcher 类，不要混在一个类里
4. 价格数据目前用 mock 数据占位（真实 API Key 还没配置），但类结构和 API 调用逻辑要完整，注释标明哪些行是 mock
5. 超时 30 秒，重试 3 次
6. 依赖写入 requirements.txt（取消注释对应的云 SDK 行）

## 验收方式
cd /Users/apple/算力通 && python src/backend/cli.py price A100
```

---

## 提示词 2：设备 Agent 原型

```
@agent-developer

写算力通设备 Agent 最小原型。这玩意跑在用户电脑上——必须轻量、不干扰用户、不碰隐私。

## 文件清单
src/agent/
├── daemon.py        # 主进程入口
├── monitor.py       # 系统资源采集
├── heartbeat.py     # UDP 心跳发送
├── executor.py      # Docker 容器执行器
├── config.py        # 配置管理
└── tests/
    ├── test_monitor.py
    └── test_heartbeat.py

## 核心模块规格

### monitor.py
- 用 psutil 采集 CPU/RAM 使用率
- GPU 采集写两套：NVIDIA GPU 用 nvidia-smi 解析（GPUtil 备选），Apple Silicon / AMD 返回 0 不崩
- is_user_active 字段：macOS 用 Quartz 检测空闲时间，Linux 用 xprintidle，Windows 用 GetLastInputInfo，最近 30 秒有操作 → True
- 返回固定格式 dict：{cpu_percent, gpu_percent, ram_percent, is_user_active}

### heartbeat.py
- UDP socket，目标端口 9999
- 每 500ms 发一次，payload 是 JSON < 1KB
- 服务器地址从环境变量 HEARTBEAT_HOST 读，默认 127.0.0.1
- 包含 device_id（自动生成 UUID，首次运行存本地文件）

### executor.py
- 用 docker-py 启动容器跑任务
- 资源限制：CPU 不超过主机 50%，内存不超过主机 50%
- 检测到 is_user_active=True → 暂停容器 → 通知服务端

### daemon.py
- 主循环：每 5 秒采集资源 → 每 500ms 发一次心跳 → 收到任务时启动 executor
- 信号处理：SIGTERM 优雅关闭所有容器

### config.py
- 所有配置从环境变量 + .env 文件读

## 约束（不可违反）
- 进程内存 < 150MB
- 工作目录限定在 ~/.suanlitong/
- 不读取用户个人文件
- 不用摄像头/麦克风
- 所有 Docker 调用要有 try/except，容器操作失败不影响 Agent 主进程存活

## 验收方式
cd /Users/apple/算力通 && python src/agent/daemon.py
# 应该看到：Agent 启动 → 采集资源 → 发送心跳 → 等待任务（日志输出到 stdout）
```

---

## 提示词 3：FastAPI 骨架

```
@api-developer

搭建算力通 FastAPI 后端骨架。

## 文件清单
src/backend/app/
├── __init__.py
├── main.py          # FastAPI 应用入口，包含 /health 端点
├── config.py        # 环境变量配置管理
├── db.py            # SQLite 数据库连接 + 表创建
├── routers/
│   ├── __init__.py
│   ├── prices.py    # GET /api/v1/prices?gpu_type=A100
│   └── instances.py # CRUD /api/v1/instances
├── services/
│   ├── __init__.py
│   ├── cloud/
│   │   ├── __init__.py
│   │   ├── base.py       # CloudGPUAdapter 抽象基类
│   │   ├── aliyun.py     # 阿里云适配器（骨架）
│   │   ├── huawei.py     # 华为云适配器（骨架）
│   │   └── tencent.py    # 腾讯云适配器（骨架）
│   └── billing.py        # 计费服务（骨架）
├── models/
│   ├── __init__.py
│   └── schemas.py         # Pydantic 模型
└── tests/
    └── test_health.py

## 各文件规格

### main.py
- FastAPI app 创建 + CORS 中间件
- /health 返回 {"status": "ok", "version": "0.1.0"}
- 注册 routers/prices.py 和 routers/instances.py

### config.py
- 用 pydantic-settings 或 os.environ 读取配置
- 必须项：DATABASE_URL（默认 sqlite:///./suanlitong.db）

### db.py
- SQLite 连接管理
- 创建表：users(id, email, balance, created_at)、gpu_instances(id, user_id, provider, gpu_type, status, created_at, terminated_at)、price_snapshots(id, provider, gpu_type, price_per_hour, spot_price, region, fetched_at)
- 用原始 SQL（不用 SQLAlchemy ORM，MVP 阶段保持简单）

### routers/instances.py
- POST /api/v1/instances → 创建实例（body: {provider, gpu_type, image}）
- GET /api/v1/instances → 列表
- DELETE /api/v1/instances/{id} → 释放

### routers/prices.py
- GET /api/v1/prices?gpu_type=A100 → 从 price_snapshots 表读最新价格

### services/cloud/base.py
- CloudGPUAdapter 抽象基类：list_gpu_prices / create_instance / terminate_instance（用 @abstractmethod）

### services/cloud/aliyun.py, huawei.py, tencent.py
- 继承 CloudGPUAdapter
- 三个方法写骨架 + 占位 raise NotImplementedError
- 每个类留 TODO 注释说明需要对接的 API 名称

## 约束
- 所有云 API 调用必须有超时（30s）+ 重试（3 次）
- 所有接口以 /api/v1/ 为前缀
- requirements.txt 取消 fastapi、uvicorn、pydantic 的注释

## 验收方式
cd /Users/apple/算力通 && uvicorn src.backend.app.main:app --reload
# 访问 http://localhost:8000/health → {"status": "ok", "version": "0.1.0"}
# 访问 http://localhost:8000/api/v1/prices?gpu_type=A100 → []
```

---

## 提示词 4：Docker + CI/CD 基础设施

```
@devops-engineer

写算力通的 Docker + CI/CD + 部署基础配置。

## 文件清单
├── Dockerfile.backend        # 后端 FastAPI 服务镜像
├── Dockerfile.agent          # 设备 Agent 镜像（预装 PyTorch + Jupyter）
├── docker-compose.yml        # 本地开发环境一键启动
├── scripts/
│   └── seed_db.py            # 数据库初始化（建表 + 插入 mock 价格数据）
├── .github/workflows/
│   └── test.yml              # PR 触发 lint + test
└── .env.example              # 环境变量模板

## 各文件规格

### Dockerfile.backend
- 基础镜像：python:3.11-slim
- 复制 requirements.txt → pip install
- 复制 src/backend/ → WORKDIR /app
- CMD: uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000

### Dockerfile.agent
- 基础镜像：nvidia/cuda:12.4-runtime-ubuntu22.04
- 预装：PyTorch 2.x + Jupyter + vLLM（注释写明后续再启用）
- 复制 src/agent/ → WORKDIR /agent
- CMD: python daemon.py

### docker-compose.yml
- 服务：backend（端口 8000）、frontend（端口 3000）、redis（6379）
- 暂不挂 PostgreSQL（MVP 用 SQLite）
- 所有服务放在 suanlitong 网络下

### .github/workflows/test.yml
- 触发条件：push 到任意分支、PR 到 main
- Python 3.11 setup → pip install -r requirements-dev.txt → black --check → pytest --cov=src --cov-report=term

### scripts/seed_db.py
- 创建 SQLite 数据库 + 三张表（users, gpu_instances, price_snapshots）
- 插入阿里云/华为云/腾讯云 A100/H100/4090 的 mock 价格数据

### .env.example
- 列出所有必需环境变量（ALIYUN_ACCESS_KEY_ID 等），值填 "your-xxx-here"

## 约束
- 不在任何文件中硬编码密钥
- 不挂 root、不跑 privileged 容器
- .env 不提交
- Docker 镜像尽量小（slim 基础镜像、清理 apt 缓存）

## 验收方式
docker compose up
# 后端健康检查：curl localhost:8000/health
# 数据库初始化：python scripts/seed_db.py
```

---

## 提示词 5：React 控制台骨架

```
@frontend-developer

搭建算力通 React 控制台骨架。

## 技术栈
React 18 + TypeScript + Tailwind CSS + React Router v6 + Axios + Vite

## 文件清单
src/frontend/
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── vite.config.ts
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── pages/
│   │   ├── PriceComparison.tsx    # 首页：GPU 比价
│   │   ├── Instances.tsx          # 实例列表
│   │   └── Billing.tsx            # 余额展示
│   ├── components/
│   │   ├── Layout.tsx             # 全局布局（侧边栏 + 顶栏）
│   │   ├── GPUCard.tsx            # GPU 价格卡片
│   │   └── PriceTable.tsx         # 比价表格
│   ├── hooks/
│   │   └── useApi.ts              # Axios 封装
│   ├── types/
│   │   └── index.ts
│   └── utils/
│       └── format.ts              # 价格格式化
└── public/

## 页面规格

### PriceComparison.tsx（首页 /）
- 顶部：GPU 型号下拉框（A100 / H100 / 4090），默认 A100
- 下方：三列卡片，每列一个云厂商
- 每张卡片显示：云厂商名、GPU 型号、按量付费价格、Spot 价格、可用区域、[创建实例] 按钮
- 最低价格那一列用绿色边框高亮
- 数据从 GET /api/v1/prices 获取（先写 mock 数据在前端，API 就绪后切换）

### Instances.tsx（/instances）
- 表格列：实例 ID、GPU 型号、云厂商、状态（彩色徽标）、已用时长、费用、操作
- 操作列：[释放] 按钮

### Billing.tsx（/billing）
- 账户余额展示（大字体）
- 消费记录列表

### 设计约束
- 深色主题（bg-slate-900 / text-white 为主色调）
- 价格数字右对齐，青色系（cyan）作为强调色
- 响应式：移动端隐藏侧边栏，卡片换行堆叠
- 所有 API 调用写在一个 useApi hook 里，不要散落在各组件

### Layout.tsx
- 左侧边栏：算力通 Logo + 导航（比价 / 实例 / 计费）
- 右侧内容区

## 约束
- npm create vite@latest 用 React + TypeScript 模板
- Tailwind CSS 用 v3 的 PostCSS 插件方式配置
- 数据先写 mock JSON，后端 API 就绪后改一行 baseURL 即可切换

## 验收方式
cd /Users/apple/算力通/src/frontend && npm install && npm run dev
# 访问 http://localhost:5173
# 看到比价页面，三列 GPU 卡片，深色主题，最低价高亮
```

---

## 交付标准（阶段 0 完成标志）

- [ ] 在终端执行 `suanlitong price A100`，输出三家云厂商实时比价表
- [ ] 访问 `localhost:5173`，能看到 GPU 比价页面，深色主题
- [ ] 访问 `localhost:8000/health`，返回 `{"status": "ok"}`
- [ ] `docker compose up` 一键启动所有服务
