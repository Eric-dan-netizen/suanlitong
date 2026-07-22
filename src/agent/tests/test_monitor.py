"""monitor.py 单元测试。

测试系统资源采集和用户活跃检测的各平台路径。
"""

from __future__ import annotations

import platform
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.agent.monitor import (
    _check_user_activity,
    _get_cpu_percent,
    _get_gpu_percent,
    _get_ram_percent,
    _gpu_via_gputil,
    _gpu_via_nvidia_smi,
    get_system_usage,
)

IS_WINDOWS = platform.system() == "Windows"


# ── get_system_usage 集成测试 ────────────────────────


class TestGetSystemUsage:
    """get_system_usage() 返回格式验证。"""

    @patch("src.agent.monitor._get_cpu_percent", return_value=42.0)
    @patch("src.agent.monitor._get_gpu_percent", return_value=75.5)
    @patch("src.agent.monitor._get_ram_percent", return_value=60.0)
    @patch("src.agent.monitor._check_user_activity", return_value=True)
    def test_returns_correct_format(self, *_mocks):
        result = get_system_usage(idle_threshold=30)
        assert isinstance(result, dict)
        assert result == {
            "cpu_percent": 42.0,
            "gpu_percent": 75.5,
            "ram_percent": 60.0,
            "is_user_active": True,
        }

    @patch("src.agent.monitor._get_cpu_percent", return_value=0.0)
    @patch("src.agent.monitor._get_gpu_percent", return_value=0.0)
    @patch("src.agent.monitor._get_ram_percent", return_value=0.0)
    @patch("src.agent.monitor._check_user_activity", return_value=False)
    def test_all_zero_when_failures(self, *_mocks):
        result = get_system_usage()
        assert result == {
            "cpu_percent": 0.0,
            "gpu_percent": 0.0,
            "ram_percent": 0.0,
            "is_user_active": False,
        }

    def test_idle_threshold_passed_through(self):
        with (
            patch("src.agent.monitor._get_cpu_percent", return_value=10.0),
            patch("src.agent.monitor._get_gpu_percent", return_value=0.0),
            patch("src.agent.monitor._get_ram_percent", return_value=10.0),
            patch("src.agent.monitor._check_user_activity") as mock_check,
        ):
            get_system_usage(idle_threshold=60)
            mock_check.assert_called_once_with(60)


# ── CPU 采集 ────────────────────────────────────────


class TestGetCpuPercent:
    def test_normal(self):
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 45.7
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = _get_cpu_percent()
            assert result == 45.7

    def test_import_error_fallback(self):
        with patch.dict("sys.modules"):
            sys.modules.pop("psutil", None)
            result = _get_cpu_percent()
            assert result == 0.0

    def test_runtime_error_fallback(self):
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.side_effect = RuntimeError("boom")
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = _get_cpu_percent()
            assert result == 0.0


# ── RAM 采集 ────────────────────────────────────────


class TestGetRamPercent:
    def test_normal(self):
        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.return_value.percent = 67.8
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = _get_ram_percent()
            assert result == 67.8

    def test_fallback_on_error(self):
        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.side_effect = OSError("boom")
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = _get_ram_percent()
            assert result == 0.0

    def test_import_error_fallback(self):
        with patch.dict("sys.modules"):
            sys.modules.pop("psutil", None)
            result = _get_ram_percent()
            assert result == 0.0


# ── GPU 采集 ────────────────────────────────────────


class TestGetGpuPercent:
    @patch("src.agent.monitor._gpu_via_nvidia_smi", return_value=88.5)
    @patch("src.agent.monitor._gpu_via_gputil")
    def test_nvidia_smi_first(self, mock_gputil, _mock_smi):
        result = _get_gpu_percent()
        assert result == 88.5
        mock_gputil.assert_not_called()

    @patch("src.agent.monitor._gpu_via_nvidia_smi", return_value=-1.0)
    @patch("src.agent.monitor._gpu_via_gputil", return_value=55.0)
    def test_fallback_to_gputil(self, _mock_gputil, _mock_smi):
        result = _get_gpu_percent()
        assert result == 55.0

    @patch("src.agent.monitor._gpu_via_nvidia_smi", return_value=-1.0)
    @patch("src.agent.monitor._gpu_via_gputil", return_value=-1.0)
    def test_all_fail_returns_zero(self, _mock_gputil, _mock_smi):
        result = _get_gpu_percent()
        assert result == 0.0


class TestGpuViaNvidiaSmi:
    def test_single_gpu(self):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = "85\n"
        with patch("subprocess.run", return_value=proc):
            assert _gpu_via_nvidia_smi() == 85.0

    def test_multi_gpu_returns_max(self):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = "45\n78\n92\n"
        with patch("subprocess.run", return_value=proc):
            assert _gpu_via_nvidia_smi() == 92.0

    def test_empty_output(self):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = "\n"
        with patch("subprocess.run", return_value=proc):
            assert _gpu_via_nvidia_smi() == -1.0

    def test_command_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert _gpu_via_nvidia_smi() == -1.0

    def test_nonzero_exit(self):
        proc = MagicMock()
        proc.returncode = 1
        with patch("subprocess.run", return_value=proc):
            assert _gpu_via_nvidia_smi() == -1.0

    def test_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            assert _gpu_via_nvidia_smi() == -1.0


class TestGpuViaGputil:
    def test_normal(self):
        mock_gpu = MagicMock()
        mock_gpu.load = 0.65
        mock_gputil_mod = MagicMock()
        mock_gputil_mod.getGPUs.return_value = [mock_gpu]
        with patch.dict("sys.modules", {"GPUtil": mock_gputil_mod}):
            assert _gpu_via_gputil() == 65.0

    def test_multi_gpu(self):
        g1 = MagicMock()
        g1.load = 0.3
        g2 = MagicMock()
        g2.load = 0.9
        mock_gputil_mod = MagicMock()
        mock_gputil_mod.getGPUs.return_value = [g1, g2]
        with patch.dict("sys.modules", {"GPUtil": mock_gputil_mod}):
            assert _gpu_via_gputil() == 90.0

    def test_no_gpus(self):
        mock_gputil_mod = MagicMock()
        mock_gputil_mod.getGPUs.return_value = []
        with patch.dict("sys.modules", {"GPUtil": mock_gputil_mod}):
            assert _gpu_via_gputil() == -1.0

    def test_import_error(self):
        with patch.dict("sys.modules"):
            sys.modules.pop("GPUtil", None)
            assert _gpu_via_gputil() == -1.0

    def test_getgpus_raises(self):
        mock_gputil_mod = MagicMock()
        mock_gputil_mod.getGPUs.side_effect = RuntimeError("GPU error")
        with patch.dict("sys.modules", {"GPUtil": mock_gputil_mod}):
            assert _gpu_via_gputil() == -1.0


# ── 用户活跃检测 ────────────────────────────────────


class TestCheckUserActivity:
    def test_darwin_active(self):
        proc = MagicMock()
        proc.stdout = '"HIDIdleTime" = 5000000000\n'
        with (
            patch("platform.system", return_value="Darwin"),
            patch("subprocess.run", return_value=proc),
        ):
            assert _check_user_activity(30) is True

    def test_darwin_idle(self):
        proc = MagicMock()
        proc.stdout = '"HIDIdleTime" = 60000000000\n'
        with (
            patch("platform.system", return_value="Darwin"),
            patch("subprocess.run", return_value=proc),
        ):
            assert _check_user_activity(30) is False

    def test_darwin_subprocess_error(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("subprocess.run", side_effect=OSError("boom")),
        ):
            assert _check_user_activity(30) is False

    def test_linux_active(self):
        proc = MagicMock()
        proc.stdout = "10000\n"
        with (
            patch("platform.system", return_value="Linux"),
            patch("subprocess.run", return_value=proc),
        ):
            assert _check_user_activity(30) is True

    def test_linux_idle(self):
        proc = MagicMock()
        proc.stdout = "60000\n"
        with (
            patch("platform.system", return_value="Linux"),
            patch("subprocess.run", return_value=proc),
        ):
            assert _check_user_activity(30) is False

    def test_linux_no_xprintidle(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            assert _check_user_activity(30) is False

    @pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
    def test_windows_active(self):
        with (
            patch("platform.system", return_value="Windows"),
            patch("ctypes.windll.user32.GetLastInputInfo", return_value=1),
            patch("ctypes.windll.kernel32.GetTickCount", return_value=15000),
        ):
            assert _check_user_activity(30) is True

    @pytest.mark.skipif(not IS_WINDOWS, reason="Windows-only test")
    def test_windows_idle(self):
        with (
            patch("platform.system", return_value="Windows"),
            patch("ctypes.windll.user32.GetLastInputInfo", return_value=1),
            patch("ctypes.windll.kernel32.GetTickCount", return_value=100000),
        ):
            assert _check_user_activity(30) is False

    @patch("platform.system", return_value="UnknownOS")
    def test_unknown_platform(self, _mock_system):
        assert _check_user_activity(30) is False
