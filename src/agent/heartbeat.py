"""算力通 Agent · 心跳客户端。

通过 UDP 向服务端周期性发送心跳包，包含设备 ID、资源快照和当前任务。
UDP 无连接，每条消息独立发送，无需重连逻辑。
"""

from __future__ import annotations

import json
import logging
import socket
import time
from typing import Any, Dict, Optional

from .config import Config

logger = logging.getLogger(__name__)

# 心跳包最大字节数（1KB 上限）
MAX_PAYLOAD_BYTES = 1024


class HeartbeatClient:
    """UDP 心跳发送器。

    设计要点：
        - UDP 无状态：每条消息独立，天然支持服务端切换 IP
        - Payload < 1KB：保证不分片
        - 发送失败静默：不影响主进程
    """

    def __init__(self, config: Config) -> None:
        self._host: str = config.heartbeat_host
        self._port: int = config.heartbeat_port
        self._device_id: str = config.device_id
        self._sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # UDP 发送超时（避免阻塞主线程）
        self._sock.settimeout(0.5)

    @property
    def device_id(self) -> str:
        return self._device_id

    def send(
        self,
        usage: Dict[str, Any],
        current_task: Optional[str] = None,
    ) -> bool:
        """发送一次心跳。

        Args:
            usage: 系统资源快照（来自 monitor.get_system_usage()）
            current_task: 当前运行中的任务 ID，无任务时为 None

        Returns:
            True 如果发送成功，False 如果失败。
        """
        payload: Dict[str, Any] = {
            "device_id": self._device_id,
            "usage": usage,
            "current_task": current_task,
            "timestamp": int(time.time()),
        }

        try:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            logger.warning("Failed to serialize heartbeat payload", exc_info=True)
            return False

        if len(data) > MAX_PAYLOAD_BYTES:
            logger.warning(
                "Heartbeat payload too large (%d bytes), truncating", len(data)
            )
            # 降级：去掉 usage 明细，只发身份 + 时间戳
            fallback = {
                "device_id": self._device_id,
                "current_task": current_task,
                "timestamp": payload["timestamp"],
            }
            data = json.dumps(fallback, separators=(",", ":")).encode("utf-8")
            if len(data) > MAX_PAYLOAD_BYTES:
                logger.error("Heartbeat payload still too large after truncation")
                return False

        try:
            self._sock.sendto(data, (self._host, self._port))
            return True
        except OSError:
            logger.debug(
                "Heartbeat send failed to %s:%d", self._host, self._port, exc_info=True
            )
            return False

    def close(self) -> None:
        """关闭 UDP socket。"""
        try:
            self._sock.close()
        except OSError:
            pass
