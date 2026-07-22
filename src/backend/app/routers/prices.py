"""算力通 · 价格查询路由。

GET /api/v1/prices?gpu_type=A100 → 返回最新价格快照。
"""

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..db import get_db
from ..models.schemas import PriceSnapshotResponse

router = APIRouter(prefix="/api/v1/prices", tags=["prices"])


def _get_conn():
    """数据库连接依赖注入（测试时可覆写）。"""
    with get_db() as conn:
        yield conn


@router.get("", response_model=list[PriceSnapshotResponse])
def list_prices(
    gpu_type: Optional[str] = Query(None, description="GPU 型号筛选（如 A100）"),
    conn: sqlite3.Connection = Depends(_get_conn),  # noqa: UP045
):
    """查询 GPU 实时比价。

    返回各云厂商的最新价格快照。
    若指定 gpu_type，则仅返回该型号的价格。

    取每个 (provider, gpu_type) 组合中 id 最大（最新）的一条记录。
    """
    if gpu_type:
        rows = conn.execute(
            """
            SELECT p.provider, p.gpu_type, p.price_per_hour, p.spot_price,
                   p.region, p.fetched_at
            FROM price_snapshots p
            INNER JOIN (
                SELECT provider, gpu_type, MAX(id) AS max_id
                FROM price_snapshots
                WHERE gpu_type = ?
                GROUP BY provider, gpu_type
            ) latest ON p.id = latest.max_id
            ORDER BY p.price_per_hour ASC
            """,
            (gpu_type,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT p.provider, p.gpu_type, p.price_per_hour, p.spot_price,
                   p.region, p.fetched_at
            FROM price_snapshots p
            INNER JOIN (
                SELECT provider, gpu_type, MAX(id) AS max_id
                FROM price_snapshots
                GROUP BY provider, gpu_type
            ) latest ON p.id = latest.max_id
            ORDER BY p.gpu_type, p.price_per_hour ASC
            """,
        ).fetchall()

    return [dict(row) for row in rows]
