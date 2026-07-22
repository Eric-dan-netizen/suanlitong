"""算力通 · 数据库连接管理 + 表创建（原始 SQL，无 ORM）。"""

import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager

from .config import DATABASE_URL, _db_path_from_url

_db_lock = threading.Lock()


def _get_db_path() -> str:
    """从 DATABASE_URL 提取 SQLite 文件路径。"""
    return _db_path_from_url(DATABASE_URL)


def get_connection() -> sqlite3.Connection:
    """创建并返回一个新的 SQLite 连接。

    每次调用返回独立连接；调用方负责关闭。
    """
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """上下文管理器：自动 commit/close 的数据库连接。

    用法：
        with get_db() as conn:
            conn.execute("SELECT ...")
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 表创建 SQL ──────────────────────────────────────

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE,
    balance     REAL    NOT NULL DEFAULT 0.0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_GPU_INSTANCES_TABLE = """
CREATE TABLE IF NOT EXISTS gpu_instances (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    provider      TEXT    NOT NULL,
    gpu_type      TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    terminated_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

CREATE_PRICE_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS price_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider        TEXT    NOT NULL,
    gpu_type        TEXT    NOT NULL,
    price_per_hour  REAL    NOT NULL,
    spot_price      REAL,
    region          TEXT    NOT NULL,
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_prices_gpu_type ON price_snapshots(gpu_type);",
    "CREATE INDEX IF NOT EXISTS idx_prices_fetched   ON price_snapshots(fetched_at);",
    "CREATE INDEX IF NOT EXISTS idx_instances_user    ON gpu_instances(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_instances_status  ON gpu_instances(status);",
]


def init_db() -> None:
    """初始化数据库：创建表 + 索引（幂等）。"""
    with _db_lock:
        with get_db() as conn:
            conn.execute(CREATE_USERS_TABLE)
            conn.execute(CREATE_GPU_INSTANCES_TABLE)
            conn.execute(CREATE_PRICE_SNAPSHOTS_TABLE)
            for idx_sql in CREATE_INDEXES:
                conn.execute(idx_sql)
