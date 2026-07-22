"""算力通 Agent · 系统资源采集。

采集 CPU / GPU / RAM 使用率，以及用户活跃状态。
GPU 检测兼容 NVIDIA（nvidia-smi / GPUtil）、Apple Silicon、AMD 等所有平台。
"""

from __future__ import annotations

import logging
import platform
import subprocess
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── 公开接口 ─────────────────────────────────────────


def get_system_usage(idle_threshold: int = 30) -> Dict[str, Any]:
    """采集当前系统资源使用情况。

    Args:
        idle_threshold: 用户空闲判定阈值（秒），默认 30 秒。
            最近 idle_threshold 秒内有键盘/鼠标事件 → is_user_active = True。

    Returns:
        {
            cpu_percent: float,       # 0-100
            gpu_percent: float,       # 0-100，NVIDIA 有效，其余返回 0
            ram_percent: float,       # 0-100
            is_user_active: bool,     # 是否有近期用户操作
        }
    """
    return {
        "cpu_percent": _get_cpu_percent(),
        "gpu_percent": _get_gpu_percent(),
        "ram_percent": _get_ram_percent(),
        "is_user_active": _check_user_activity(idle_threshold),
    }


# ── CPU ──────────────────────────────────────────────


def _get_cpu_percent() -> float:
    """获取整机 CPU 使用率（0-100），非阻塞快照。

    首次调用返回 0.0 属于 psutil 正常行为；
    daemon.py 在启动时已调用一次用于"预热"。
    """
    try:
        import psutil

        return round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        logger.debug("psutil cpu_percent failed", exc_info=True)
        return 0.0


# ── RAM ──────────────────────────────────────────────


def _get_ram_percent() -> float:
    """获取内存使用率（0-100）。"""
    try:
        import psutil

        return round(psutil.virtual_memory().percent, 1)
    except Exception:
        logger.debug("psutil virtual_memory failed", exc_info=True)
        return 0.0


# ── GPU ──────────────────────────────────────────────


def _get_gpu_percent() -> float:
    """获取 GPU 使用率（0-100）。

    策略（按优先级）：
        1. nvidia-smi 解析 —— Linux / Windows NVIDIA
        2. GPUtil 库 —— 跨平台 NVIDIA
        3. 返回 0 —— Apple Silicon / AMD / 无 GPU
    """
    # ── 策略 1: nvidia-smi ──────────────────────────
    gpu = _gpu_via_nvidia_smi()
    if gpu >= 0:
        return gpu

    # ── 策略 2: GPUtil ──────────────────────────────
    gpu = _gpu_via_gputil()
    if gpu >= 0:
        return gpu

    # ── 策略 3: 无 NVIDIA GPU ───────────────────────
    return 0.0


def _gpu_via_nvidia_smi() -> float:
    """通过 nvidia-smi CLI 采集 GPU 利用率。

    Returns:
        GPU 使用率 (0-100)，失败返回 -1.0。
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return -1.0
        values = [
            float(v.strip())
            for v in result.stdout.strip().split("\n")
            if v.strip()
        ]
        if not values:
            return -1.0
        return round(max(values), 1)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        return -1.0


def _gpu_via_gputil() -> float:
    """通过 GPUtil 库采集 GPU 利用率。

    Returns:
        GPU 使用率 (0-100)，失败或不可用返回 -1.0。
    """
    try:
        import GPUtil  # type: ignore[import-untyped]

        gpus = GPUtil.getGPUs()
        if not gpus:
            return -1.0
        return round(max(g.load * 100 for g in gpus), 1)
    except Exception:
        return -1.0


# ── 用户活跃检测 ─────────────────────────────────────


def _check_user_activity(timeout_seconds: int = 30) -> bool:
    """检测用户是否在最近 timeout_seconds 秒内有操作。

    多平台实现：
        - macOS:    ioreg 读取 HIDIdleTime（Quartz 等效）
        - Linux:    xprintidle（X11）
        - Windows:  GetLastInputInfo (kernel32)

    Returns:
        True  表示用户最近活跃
        False 表示用户空闲超过阈值，或检测失败（容错默认）
    """
    system = platform.system()

    if system == "Darwin":
        return _macos_idle_check(timeout_seconds)
    elif system == "Linux":
        return _linux_idle_check(timeout_seconds)
    elif system == "Windows":
        return _windows_idle_check(timeout_seconds)
    else:
        return False


def _macos_idle_check(timeout_seconds: int) -> bool:
    """macOS: 通过 IORegistry 读取 HIDIdleTime（纳秒），换算为秒。"""
    try:
        result = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        for line in result.stdout.split("\n"):
            if "HIDIdleTime" in line:
                # 形如:   "HIDIdleTime" = 123456789
                raw = line.split("=")[-1].strip()
                idle_ns = int(raw)
                idle_seconds = idle_ns / 1_000_000_000
                return idle_seconds < timeout_seconds
    except Exception:
        logger.debug("macOS idle check failed", exc_info=True)
    return False


def _linux_idle_check(timeout_seconds: int) -> bool:
    """Linux: 调用 xprintidle 获取空闲毫秒数。"""
    try:
        result = subprocess.run(
            ["xprintidle"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        idle_ms = int(result.stdout.strip())
        return (idle_ms / 1000) < timeout_seconds
    except Exception:
        logger.debug("Linux idle check failed", exc_info=True)
    return False


def _windows_idle_check(timeout_seconds: int) -> bool:
    """Windows: 通过 GetLastInputInfo 获取空闲毫秒数。"""
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("dwTime", wintypes.DWORD),
            ]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        if not user32.GetLastInputInfo(ctypes.byref(lii)):
            return False

        idle_ms = kernel32.GetTickCount() - lii.dwTime
        return (idle_ms / 1000) < timeout_seconds
    except Exception:
        logger.debug("Windows idle check failed", exc_info=True)
    return False
