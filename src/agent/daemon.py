"""算力通 Agent · 主进程入口。

设计原则：
    - 轻量：目标内存 < 150MB，不加载重型框架
    - 不干扰用户：用户活跃时自动暂停算力任务
    - 容错：任何子模块故障不影响主进程存活

运行方式:
    python -m src.agent.daemon

生命周期管理:
    systemd (Linux) / launchd (macOS) 负责进程守护和自动重启。
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from typing import Any

from .config import Config
from .executor import DockerUnavailableError, Executor
from .heartbeat import HeartbeatClient
from .monitor import get_system_usage

# ── 日志 ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("suanlitong.agent")


# ── 主进程 ───────────────────────────────────────────


class AgentDaemon:
    """算力通设备 Agent 主进程。

    核心循环:
        - 心跳线程: 每 500ms 发送一次 UDP 心跳
        - 控制循环: 每 monitor_interval 秒采一次资源，
          检测到用户活跃 → 暂停容器；空闲 → 恢复容器
    """

    def __init__(self) -> None:
        self.config = Config()
        self.running = False

        # 子模块（惰性初始化）
        self._heartbeat: HeartbeatClient | None = None
        self._executor: Executor | None = None
        self._latest_usage: dict[str, Any] = {}
        self._usage_lock = threading.Lock()

        # 信号处理
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("Agent initialized: %s", self.config)

    # ── 信号处理 ─────────────────────────────────────

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        """SIGTERM / SIGINT 处理器：触发优雅关闭。"""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, initiating graceful shutdown...", sig_name)
        self.running = False

    # ── 主循环 ───────────────────────────────────────

    def run(self) -> int:
        """启动 Agent 主循环。

        Returns:
            0 正常退出，1 异常退出。
        """
        if self.running:
            logger.warning("Agent is already running")
            return 1

        self.running = True

        # ── 预热 CPU 采样 ─────────────────────────────
        try:
            import psutil
            psutil.cpu_percent(interval=0.1)  # 首次调用返回非零值
        except Exception:
            pass

        # ── 启动心跳线程 ──────────────────────────────
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="heartbeat"
        )
        heartbeat_thread.start()

        # ── 初始化 executor ───────────────────────────
        try:
            self._executor = Executor(
                cpu_limit_percent=self.config.cpu_limit_percent,
                mem_limit_percent=self.config.mem_limit_percent,
            )
            # 触发 Docker 连通性检查
            self._executor._ensure_client()
            logger.info("Executor ready, Docker daemon reachable")
        except DockerUnavailableError as exc:
            logger.warning("Docker unavailable, running in monitor-only mode: %s", exc)
        except Exception as exc:
            logger.warning("Executor init failed, running in monitor-only mode: %s", exc)

        # ── 控制循环 ─────────────────────────────────
        logger.info(
            "Agent running: monitor_interval=%.1fs heartbeat_interval=%.1fs",
            self.config.monitor_interval,
            self.config.heartbeat_interval,
        )

        exit_code = 0
        try:
            while self.running:
                try:
                    self._control_tick()
                except Exception:
                    logger.exception("Control tick failed, continuing")
                time.sleep(self.config.monitor_interval)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
        finally:
            exit_code = self._shutdown()

        return exit_code

    def _control_tick(self) -> None:
        """单次控制周期。

        1. 采集系统资源
        2. 根据用户活跃状态暂停/恢复容器
        """
        # 1. 采集资源
        usage = get_system_usage(idle_threshold=self.config.idle_threshold)

        with self._usage_lock:
            self._latest_usage = usage

        logger.debug(
            "Usage: cpu=%.1f%% gpu=%.1f%% ram=%.1f%% user_active=%s",
            usage["cpu_percent"],
            usage["gpu_percent"],
            usage["ram_percent"],
            usage["is_user_active"],
        )

        # 2. 用户活跃感知
        executor = self._executor
        if executor is None:
            return

        is_active: bool = usage["is_user_active"]

        if is_active and not executor.is_paused:
            paused = executor.pause_all()
            if paused:
                # 通知服务端（通过心跳中的 current_task 变更）
                logger.info("User active, paused %d task(s)", len(paused))
        elif not is_active and executor.is_paused:
            resumed = executor.resume_all()
            if resumed:
                logger.info("User idle, resumed %d task(s)", len(resumed))

    # ── 心跳循环（独立线程）──────────────────────────

    def _heartbeat_loop(self) -> None:
        """独立线程：按心跳间隔向服务端发送 UDP 心跳。

        使用最新一次资源快照，不阻塞控制循环。
        """
        hb = HeartbeatClient(self.config)
        self._heartbeat = hb

        logger.info(
            "Heartbeat started: target=%s:%d interval=%.1fms",
            self.config.heartbeat_host,
            self.config.heartbeat_port,
            self.config.heartbeat_interval * 1000,
        )

        while self.running:
            try:
                with self._usage_lock:
                    usage = dict(self._latest_usage)

                executor = self._executor
                current_task: str | None = None
                if executor and executor.active_tasks:
                    current_task = executor.active_tasks[0]

                hb.send(usage, current_task=current_task)

            except Exception:
                logger.debug("Heartbeat error", exc_info=True)

            time.sleep(self.config.heartbeat_interval)

        hb.close()
        logger.info("Heartbeat stopped")

    # ── 关机 ─────────────────────────────────────────

    def _shutdown(self) -> int:
        """优雅关闭流程。"""
        logger.info("Agent shutting down...")

        # 关闭心跳
        if self._heartbeat:
            self._heartbeat.close()

        # 关闭所有容器
        if self._executor:
            try:
                self._executor.shutdown()
            except Exception:
                logger.exception("Error during executor shutdown")

        logger.info("Agent stopped")
        return 0


# ── 入口 ─────────────────────────────────────────────


def main() -> None:
    """Agent 命令行入口。"""
    # 确保工作目录存在，且当前目录不跑到 / 等奇怪位置
    os.chdir(os.path.expanduser("~"))
    daemon = AgentDaemon()
    sys.exit(daemon.run())


if __name__ == "__main__":
    main()
