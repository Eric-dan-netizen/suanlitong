"""算力通 Agent · 配置管理。

所有配置从环境变量读取，可选 .env 文件提供默认值。
环境变量始终优先于 .env 文件。
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

# ── 工作目录 / 文件路径 ──────────────────────────────

_raw_home = os.getenv("SUANLITONG_HOME", "")
if _raw_home:
    AGENT_HOME = Path(_raw_home)
else:
    try:
        AGENT_HOME = Path.home() / ".suanlitong"
        AGENT_HOME.parent.mkdir(mode=0o700, exist_ok=True)
    except PermissionError:
        import tempfile
        AGENT_HOME = Path(tempfile.mkdtemp(prefix="suanlitong-"))
ENV_FILE = AGENT_HOME / ".env"
DEVICE_ID_FILE = AGENT_HOME / "device_id"


def _ensure_agent_home() -> None:
    """确保 ~/.suanlitong/ 目录存在。无权限时降级到临时目录。"""
    global AGENT_HOME
    try:
        AGENT_HOME.mkdir(mode=0o700, exist_ok=True)
    except PermissionError:
        import tempfile
        AGENT_HOME = Path(tempfile.mkdtemp(prefix="suanlitong-"))
        AGENT_HOME.mkdir(mode=0o700, exist_ok=True)


def _load_dotenv() -> None:
    """从 ~/.suanlitong/.env 加载环境变量（如果存在）。"""
    env_file = ENV_FILE
    if not env_file.exists():
        return
    try:
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass  # .env 读取失败不阻塞 Agent 启动


def _get_or_create_device_id() -> str:
    """读取或创建持久化设备 ID。

    首次运行生成 UUID4 并写入 ~/.suanlitong/device_id，
    此后读取该文件。确保设备标识在重启后不变。
    """
    _ensure_agent_home()
    try:
        if DEVICE_ID_FILE.exists():
            device_id = DEVICE_ID_FILE.read_text(encoding="utf-8").strip()
            if device_id:
                return device_id
    except OSError:
        pass

    device_id = uuid.uuid4().hex
    try:
        DEVICE_ID_FILE.write_text(device_id, encoding="utf-8")
    except OSError:
        pass  # 写入失败也返回内存中的 ID，保证 Agent 不崩
    return device_id


# ── 启动时加载 ───────────────────────────────────────

_load_dotenv()


# ── Config 数据类 ────────────────────────────────────


class Config:
    """Agent 全局配置（只读语义）。"""

    def __init__(self) -> None:
        _ensure_agent_home()

        # ── 心跳 ──────────────────────────────────────
        self.heartbeat_host: str = os.getenv("HEARTBEAT_HOST", "127.0.0.1")
        self.heartbeat_port: int = int(os.getenv("HEARTBEAT_PORT", "9999"))
        self.heartbeat_interval: float = float(os.getenv("HEARTBEAT_INTERVAL", "0.5"))

        # ── 监控 ──────────────────────────────────────
        self.monitor_interval: float = float(os.getenv("MONITOR_INTERVAL", "5.0"))
        self.idle_threshold: int = int(os.getenv("IDLE_THRESHOLD", "30"))

        # ── 任务执行 ──────────────────────────────────
        self.cpu_limit_percent: float = float(os.getenv("CPU_LIMIT_PERCENT", "50"))
        self.mem_limit_percent: float = float(os.getenv("MEM_LIMIT_PERCENT", "50"))
        self.task_poll_interval: float = float(os.getenv("TASK_POLL_INTERVAL", "2.0"))

        # ── 身份 ──────────────────────────────────────
        self.device_id: str = _get_or_create_device_id()
        self.agent_home: Path = AGENT_HOME

        # ── 可选：任务服务器地址 ─────────────────────
        self.api_server: str | None = os.getenv("API_SERVER") or None

    def __repr__(self) -> str:
        return (
            f"Config(device_id={self.device_id[:8]}..., "
            f"heartbeat={self.heartbeat_host}:{self.heartbeat_port}, "
            f"limits=cpu≤{self.cpu_limit_percent}% ram≤{self.mem_limit_percent}%)"
        )
