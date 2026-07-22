"""算力通 · 数据库初始化 + Mock 价格数据填充。

用法：
    python scripts/seed_db.py                  # 默认路径
    DATABASE_URL=sqlite:///./test.db python scripts/seed_db.py
"""

import os
import sys

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backend.app.db import init_db, get_db

# ═══════════════════════════════════════════════════════
# Mock 价格数据
# 来源：阿里云/华为云/腾讯云 2026 Q2 官网 GPU 实例按量付费定价
# ═══════════════════════════════════════════════════════

MOCK_PRICES = [
    # ── A100 ──────────────────────────────────────────
    ("阿里云", "A100", 28.50, 12.80, "cn-beijing"),
    ("华为云", "A100", 30.20, 14.10, "cn-north-4"),
    ("腾讯云", "A100", 29.80, 13.50, "ap-beijing"),
    # ── H100 ──────────────────────────────────────────
    ("阿里云", "H100", 45.00, 22.00, "cn-beijing"),
    ("华为云", "H100", 48.00, 24.00, "cn-north-4"),
    ("腾讯云", "H100", 46.00, 23.00, "ap-beijing"),
    # ── RTX 4090 ──────────────────────────────────────
    ("阿里云", "4090", 2.50, 1.20, "cn-beijing"),
    ("华为云", "4090", 2.60, 1.30, "cn-north-4"),
    ("腾讯云", "4090", 2.40, 1.10, "ap-beijing"),
]

# ═══════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════

INSERT_PRICE = """
INSERT INTO price_snapshots (provider, gpu_type, price_per_hour, spot_price, region)
VALUES (?, ?, ?, ?, ?)
"""


def seed():
    """建表 + 插入 mock 数据。"""
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./suanlitong.db")
    print(f"📦 数据库: {db_path}")

    # 1. 建表 + 索引（幂等）
    init_db()
    print("✅ 表结构就绪（users / gpu_instances / price_snapshots）")

    # 2. 插入 mock 价格数据（幂等：先清再插）
    with get_db() as conn:
        conn.execute("DELETE FROM price_snapshots")
        conn.executemany(INSERT_PRICE, MOCK_PRICES)
    print(f"✅ 已插入 {len(MOCK_PRICES)} 条价格数据")

    # 3. 验证
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]
        samples = conn.execute(
            "SELECT provider, gpu_type, price_per_hour "
            "FROM price_snapshots ORDER BY gpu_type, provider"
        ).fetchall()
        print(f"📊 总计 {count} 条记录:")
        for row in samples:
            print(f"   {row['provider']:4s} | {row['gpu_type']:4s} | ¥{row['price_per_hour']:.2f}/h")


if __name__ == "__main__":
    seed()
    print("\n🎉 数据库初始化完成")
