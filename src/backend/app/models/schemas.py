"""算力通 · Pydantic 数据模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── 实例 ─────────────────────────────────────────────

class InstanceCreate(BaseModel):
    """创建 GPU 实例的请求体。"""
    provider: str = Field(..., description="云厂商：阿里云 / 华为云 / 腾讯云")
    gpu_type: str = Field(..., description="GPU 型号：A100 / H100 / 4090 等")
    image: str = Field(..., description="镜像 ID 或名称")


class InstanceResponse(BaseModel):
    """GPU 实例的响应体。"""
    id: int
    user_id: int
    provider: str
    gpu_type: str
    status: str
    created_at: str
    terminated_at: Optional[str] = None


# ── 价格 ─────────────────────────────────────────────

class PriceSnapshotResponse(BaseModel):
    """价格快照的响应体。"""
    provider: str
    gpu_type: str
    price_per_hour: float
    spot_price: Optional[float] = None
    region: str
    fetched_at: str


# ── 通用 ─────────────────────────────────────────────

class HealthResponse(BaseModel):
    """健康检查响应。"""
    status: str
    version: str


class ErrorResponse(BaseModel):
    """通用错误响应。"""
    detail: str
