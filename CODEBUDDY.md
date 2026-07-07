# CODEBUDDY.md — 算力通项目上下文

## 项目概述

**算力通（SuanLiTong）** 是一个面向 AI 创业者和独立开发者的多云 GPU 算力聚合平台。
核心价值主张：**让算力像自来水一样，扭开即用。**

- **赛道：** AI 算力服务 / GPU 云计算
- **阶段：** 种子轮（融资 200 万，出让 10%-15%）
- **创始人：** Eric（律师 + 全栈工程师）
- **当前状态：** 融资筹备期，MVP 未开工

## 目录结构

```
算力通/
├── src/                    # MVP 源码（待开发）
│   ├── backend/            # Python/FastAPI 后端
│   └── frontend/           # Vue/React 前端
├── docs/
│   ├── pitch/              # 商业计划书 + Pitch Deck
│   ├── research/           # 行业研究报告
│   └── legal/              # 合规文档（ICP/EDI 等）
├── scripts/                # 工具脚本（PPT 生成等）
├── assets/                 # 设计资源
├── ROADMAP.md              # 项目路线图 & 任务看板
├── CODEBUDDY.md            # 本文件
├── Makefile                # 常用命令入口
├── pyproject.toml          # Python 项目配置
└── requirements.txt        # Python 依赖
```

## 技术栈（规划）

| 层级 | 技术选型 | 理由 |
|------|----------|------|
| 后端 | Python + FastAPI | 快速开发，异步支持好，云 SDK 生态完善 |
| 前端 | React / Vue 3 | 社区成熟，招聘容易 |
| 数据库 | PostgreSQL + Redis | 关系型 + 缓存层 |
| 基础设施 | Kubernetes + Terraform | GPU 实例 IaC 管理 |
| 云 SDK | 阿里云/华为云/腾讯云 Python SDK | 多云比价核心 |

## 商业模式（三阶段）

1. **0-12月 纯代理：** 云厂商返佣 8%-18% + 平台差价 10%-20%，毛利率 10%-25%
2. **12-36月 混合云：** 代理 + 自有 GPU，毛利率 25%-45%
3. **36月+ 资产运营：** 算力期货 + 调度 SaaS，毛利率 40%-55%

## 竞品格局

| 竞品 | 定位 | 差异化 |
|------|------|--------|
| AutoDL | 消费级 GPU（4090 为主） | 算力通主攻企业级 A100/H100 |
| 阿里云 PAI | 企业级 AI 平台 | 算力通更轻量、更快上手 |
| 恒源云/矩池云 | GPU 租赁 | 算力通多云聚合 + 比价 |

## 关键约束

- **不买卡起步：** 种子轮资金用于 MVP 开发 + 冷启动，不用于购买 GPU
- **许可证前置：** ICP + EDI 许可证是上线前提，申请周期 60-90 天
- **先验证 PMF：** 代理模式验证产品-市场匹配后，再考虑自有资产

## 工作约定

- **分支策略：** `main`（稳定） + `dev`（开发） + `feat/*`（功能分支）
- **Commit 规范：** Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`)
- **代码审查：** PR 必须至少 1 人 review
- **文档语言：** 中文（代码注释可用英文）
- **每周复盘：** 更新 ROADMAP.md 任务状态

## 常用命令

```bash
make help        # 查看所有命令
make setup       # 初始化开发环境
make ppt         # 生成 Pitch Deck PPTX
make lint        # 代码检查
make test        # 运行测试
```
