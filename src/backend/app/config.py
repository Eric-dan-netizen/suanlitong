"""算力通 · 配置管理（环境变量）。

用法：
    from src.backend.app.config import settings
    db_url = settings.database_url
"""

import os

# ── 数据库 ───────────────────────────────────────────
DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:////tmp/suanlitong_test.db")

# ── 应用 ───────────────────────────────────────────
APP_VERSION: str = "0.1.0"
APP_HOST: str = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.environ.get("APP_PORT", "8000"))

# ── 云厂商认证 ──────────────────────────────────────
ALIYUN_ACCESS_KEY_ID: str = os.environ.get("ALIYUN_ACCESS_KEY_ID", "")
ALIYUN_ACCESS_KEY_SECRET: str = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")
HUAWEI_ACCESS_KEY_ID: str = os.environ.get("HUAWEI_ACCESS_KEY_ID", "")
HUAWEI_ACCESS_KEY_SECRET: str = os.environ.get("HUAWEI_ACCESS_KEY_SECRET", "")
TENCENT_SECRET_ID: str = os.environ.get("TENCENT_SECRET_ID", "")
TENCENT_SECRET_KEY: str = os.environ.get("TENCENT_SECRET_KEY", "")

# ── 超时 & 重试 ────────────────────────────────────
CLOUD_API_TIMEOUT_SEC: int = 30
CLOUD_API_MAX_RETRIES: int = 3
PRICE_CACHE_TTL_SEC: int = 300  # 价格缓存 5 分钟


def _db_path_from_url(url: str) -> str:
    """从 sqlite:////tmp/suanlitong_test.db 提取文件路径。"""
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return url
