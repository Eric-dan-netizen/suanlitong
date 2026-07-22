"""算力通 · GPU 实例管理路由。

POST   /api/v1/instances       → 创建实例
GET    /api/v1/instances       → 实例列表
DELETE /api/v1/instances/{id}  → 释放实例
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..models.schemas import InstanceCreate, InstanceResponse

router = APIRouter(prefix="/api/v1/instances", tags=["instances"])


def _get_conn():
    """数据库连接依赖注入（测试时可覆写）。"""
    with get_db() as conn:
        yield conn


# ── 硬编码演示用户 ID（MVP 阶段） ──────────────────
# TODO: 对接用户认证后，从 JWT / session 中提取真实 user_id
DEMO_USER_ID = 1


def _ensure_demo_user(conn: sqlite3.Connection) -> None:
    """确保演示用户存在。"""
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, balance) VALUES (?, ?, ?)",
        (DEMO_USER_ID, "demo@suanlitong.com", 1000.0),
    )


@router.post("", response_model=InstanceResponse, status_code=201)
def create_instance(body: InstanceCreate, conn: sqlite3.Connection = Depends(_get_conn)):
    """创建 GPU 实例。

    请求体:
        { "provider": "阿里云", "gpu_type": "A100", "image": "ubuntu-22.04-gpu" }

    返回:
        201 + 实例详情（status 初始为 "pending"）

    TODO: 对接云厂商适配器，真正调用云 API 创建实例。
    """
    _ensure_demo_user(conn)

    cursor = conn.execute(
        """
        INSERT INTO gpu_instances (user_id, provider, gpu_type, status)
        VALUES (?, ?, ?, 'pending')
        """,
        (DEMO_USER_ID, body.provider, body.gpu_type),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM gpu_instances WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()

    return dict(row)


@router.get("", response_model=list[InstanceResponse])
def list_instances(conn: sqlite3.Connection = Depends(_get_conn)):
    """获取当前用户的 GPU 实例列表。

    返回所有未释放的实例（status != 'terminated'）。

    TODO: 对接用户认证后按 user_id 过滤。
    """
    rows = conn.execute(
        """
        SELECT * FROM gpu_instances
        WHERE user_id = ? AND status != 'terminated'
        ORDER BY created_at DESC
        """,
        (DEMO_USER_ID,),
    ).fetchall()

    return [dict(row) for row in rows]


@router.delete("/{instance_id}", response_model=InstanceResponse)
def terminate_instance(instance_id: int, conn: sqlite3.Connection = Depends(_get_conn)):
    """释放（终止）GPU 实例。

    将实例状态更新为 "terminated"，并记录终止时间。

    TODO: 对接云厂商适配器，真正调用云 API 释放实例。
    """
    row = conn.execute(
        "SELECT * FROM gpu_instances WHERE id = ? AND user_id = ?",
        (instance_id, DEMO_USER_ID),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="实例不存在或不属于当前用户")

    if row["status"] == "terminated":
        raise HTTPException(status_code=400, detail="实例已释放")

    conn.execute(
        """
        UPDATE gpu_instances
        SET status = 'terminated', terminated_at = datetime('now')
        WHERE id = ?
        """,
        (instance_id,),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM gpu_instances WHERE id = ?",
        (instance_id,),
    ).fetchone()

    return dict(row)
