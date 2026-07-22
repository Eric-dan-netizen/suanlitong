"""算力通 · FastAPI 应用入口。

启动:
    uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APP_VERSION
from .db import init_db
from .routers import instances, prices


# ── 生命周期 ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理。"""
    # 启动：初始化数据库
    init_db()
    yield
    # 关闭：暂无清理逻辑


# ── FastAPI 应用 ────────────────────────────────────

app = FastAPI(
    title="算力通 API",
    description="多云 GPU 算力聚合平台 · 后端 API",
    version=APP_VERSION,
    lifespan=lifespan,
)

# ── CORS 中间件 ─────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP 阶段允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ────────────────────────────────────────

app.include_router(prices.router)
app.include_router(instances.router)


# ── 健康检查 ────────────────────────────────────────

@app.get("/health", tags=["system"])
def health_check():
    """健康检查端点。

    返回:
        {"status": "ok", "version": "0.1.0"}
    """
    return {"status": "ok", "version": APP_VERSION}
