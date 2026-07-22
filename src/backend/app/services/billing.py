"""算力通 · 计费服务（骨架）。

按秒计量、余额管理、欠费处理。
当前阶段为骨架实现，后续需对接:
  - 实例运行时长追踪 (gpu_instances 表的 created_at / terminated_at)
  - 余额扣减定时任务 (APScheduler / Celery)
  - 欠费自动停机逻辑
"""

import logging

from ..db import get_db

logger = logging.getLogger(__name__)

# ── 定价表（元/秒） ────────────────────
# TODO: 后续从 price_snapshots 表动态读取，或从云 API 实时获取

GPU_HOURLY_RATES: dict[str, float] = {
    "A100": 28.50,
    "H100": 45.00,
    "4090": 2.50,
}


def calculate_cost(gpu_type: str, duration_seconds: float) -> float:
    """计算 GPU 实例使用费用。"""
    hourly = GPU_HOURLY_RATES.get(gpu_type.upper(), 0.0)
    return round((hourly / 3600.0) * duration_seconds, 4)


def deduct_balance(user_id: int, amount: float) -> bool:
    """从用户余额中扣费（数据库事务）。

    Returns: True 扣费成功 / False 余额不足。
    TODO: 对接真实用户认证后启用
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT balance FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not row:
            logger.warning("deduct_balance: user %d not found", user_id)
            return False
        if row["balance"] < amount:
            logger.info(
                "deduct_balance: user %d 余额不足 "
                "(balance=%.4f < amount=%.4f)",
                user_id, row["balance"], amount,
            )
            return False

        conn.execute(
            "UPDATE users SET balance = balance - ? WHERE id = ?",
            (amount, user_id),
        )
        logger.info("deduct_balance: user %d 扣费 %.4f 元", user_id, amount)
        return True


# ── 欠费检查（骨架） ───────────────────

def check_arrears(user_id: int) -> bool:
    """检查用户是否欠费（余额 <= 0）。

    TODO: 对接真实用户认证后启用
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT balance FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return False
        return row["balance"] <= 0
