"""test_heartbeat.py — UDP 心跳发送单元测试。

使用 mock socket 避免真实网络 I/O，mock Config 避免文件系统依赖。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.agent.config import Config
from src.agent.heartbeat import MAX_PAYLOAD_BYTES, HeartbeatClient


# ── Fixtures ─────────────────────────────────────────


@pytest.fixture
def mock_config() -> Config:
    """构造一个纯 mock 的 Config，不触碰文件系统。"""
    config = MagicMock(spec=Config)
    config.heartbeat_host = "127.0.0.1"
    config.heartbeat_port = 9999
    config.device_id = "deadbeefcafebabec0ffee1234567890"
    return config


@pytest.fixture
def sample_usage() -> dict:
    return {
        "cpu_percent": 42.0,
        "gpu_percent": 75.5,
        "ram_percent": 60.0,
        "is_user_active": False,
    }


# ── HeartbeatClient ──────────────────────────────────


class TestHeartbeatClient:
    """心跳客户端基本功能测试。"""

    def test_device_id(self, mock_config):
        client = HeartbeatClient(mock_config)
        assert client.device_id == mock_config.device_id
        client.close()

    def test_send_normal(self, mock_config, sample_usage):
        """正常发送 → 返回 True，验证 payload 结构。"""
        client = HeartbeatClient(mock_config)
        mock_sock = MagicMock()
        client._sock = mock_sock

        result = client.send(sample_usage, current_task="task-001")

        assert result is True
        mock_sock.sendto.assert_called_once()

        call_args = mock_sock.sendto.call_args
        data, addr = call_args[0]
        payload = json.loads(data.decode("utf-8"))

        assert payload["device_id"] == mock_config.device_id
        assert payload["usage"] == sample_usage
        assert payload["current_task"] == "task-001"
        assert isinstance(payload["timestamp"], int)
        assert addr == ("127.0.0.1", 9999)
        assert len(data) <= MAX_PAYLOAD_BYTES

    def test_send_no_task(self, mock_config, sample_usage):
        """无当前任务时 current_task 为 None。"""
        client = HeartbeatClient(mock_config)
        mock_sock = MagicMock()
        client._sock = mock_sock

        result = client.send(sample_usage)
        assert result is True

        data = mock_sock.sendto.call_args[0][0]
        payload = json.loads(data)
        assert payload["current_task"] is None

    def test_send_socket_error(self, mock_config, sample_usage):
        """发送时 socket 异常 → 返回 False，不抛异常。"""
        client = HeartbeatClient(mock_config)
        mock_sock = MagicMock()
        mock_sock.sendto.side_effect = OSError("Network unreachable")
        client._sock = mock_sock

        result = client.send(sample_usage)
        assert result is False

    def test_payload_size_limit(self, mock_config):
        """超大 usage 数据 → 触发降级，payload 仍 < 1KB。"""
        client = HeartbeatClient(mock_config)
        mock_sock = MagicMock()
        client._sock = mock_sock

        huge_usage = {
            "cpu_percent": 50.0,
            "gpu_percent": 80.0,
            "ram_percent": 70.0,
            "is_user_active": False,
            "padding": "x" * MAX_PAYLOAD_BYTES,
        }

        result = client.send(huge_usage, current_task="task-big")
        assert result is True

        data = mock_sock.sendto.call_args[0][0]
        assert len(data) <= MAX_PAYLOAD_BYTES

    def test_close(self, mock_config):
        """close() 正常关闭 socket。"""
        client = HeartbeatClient(mock_config)
        mock_sock = MagicMock()
        client._sock = mock_sock
        client.close()
        mock_sock.close.assert_called_once()

    def test_close_on_already_closed(self, mock_config):
        """close() 在 socket 已关闭时不抛异常。"""
        client = HeartbeatClient(mock_config)
        mock_sock = MagicMock()
        mock_sock.close.side_effect = OSError("Already closed")
        client._sock = mock_sock
        client.close()  # 不应抛异常


class TestHeartbeatInterval:
    """验证心跳配置参数正确传递。"""

    def test_interval_from_config(self):
        config = MagicMock(spec=Config)
        config.heartbeat_host = "10.0.0.1"
        config.heartbeat_port = 7777
        config.device_id = "test-device-id"

        client = HeartbeatClient(config)
        assert client._host == "10.0.0.1"
        assert client._port == 7777
        client.close()
