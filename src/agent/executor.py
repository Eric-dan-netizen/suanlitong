"""算力通 Agent · Docker 容器执行器。

在隔离的 Docker 容器中执行算力任务，提供资源限制和用户活跃感知的暂停/恢复机制。
所有 Docker 操作均包裹 try/except，容器故障不影响 Agent 主进程存活。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────

DEFAULT_CPU_SHARES = 512           # 默认 CPU 份额（1024 = 1 核）
GRACEFUL_STOP_TIMEOUT = 10         # 优雅关闭超时（秒）
CONTAINER_LABEL_PREFIX = "com.suanlitong"  # 容器标签前缀


# ── 异常 ─────────────────────────────────────────────


class ExecutorError(Exception):
    """执行器异常基类。"""


class DockerUnavailableError(ExecutorError):
    """Docker daemon 不可用。"""


class TaskConfigError(ExecutorError):
    """任务配置无效。"""


# ── 执行器 ───────────────────────────────────────────


class Executor:
    """Docker 容器任务执行器。

    职责：
        - 启动容器执行任务（资源受限）
        - 用户活跃时暂停所有容器
        - 用户空闲时恢复容器
        - SIGTERM 时优雅关闭所有容器
    """

    def __init__(self, cpu_limit_percent: float = 50, mem_limit_percent: float = 50) -> None:
        self._cpu_limit_pct = cpu_limit_percent
        self._mem_limit_pct = mem_limit_percent
        self._client: Any = None          # docker.DockerClient
        self._containers: dict[str, str] = {}  # task_id → container_id
        self._paused: bool = False

    # ── 初始化 ───────────────────────────────────────

    def _ensure_client(self) -> Any:
        """获取 Docker 客户端（惰性初始化）。"""
        if self._client is not None:
            return self._client
        try:
            import docker

            self._client = docker.from_env()
            self._client.ping()
            logger.info("Docker client initialized")
            return self._client
        except ImportError:
            raise DockerUnavailableError(
                "docker-py not installed. Run: pip install docker"
            )
        except Exception as exc:
            raise DockerUnavailableError(
                f"Docker daemon unreachable: {exc}"
            )

    # ── 资源计算 ─────────────────────────────────────

    def _compute_resources(self) -> dict[str, Any]:
        """根据主机资源和配置限制计算容器资源配额。

        Returns:
            {"mem_limit": str, "nano_cpus": int}
        """
        try:
            import psutil

            total_mem_mb = psutil.virtual_memory().total / (1024 * 1024)
            cpu_count = psutil.cpu_count(logical=True) or 1
        except Exception:
            # 保守默认值
            total_mem_mb = 4096
            cpu_count = 2

        mem_limit_mb = int(total_mem_mb * (self._mem_limit_pct / 100))
        nano_cpus = int(cpu_count * (self._cpu_limit_pct / 100) * 1e9)

        logger.debug(
            "Resource limits: mem=%dMB (%.0f%% of %dMB), cpus=%.1f (%.0f%% of %d)",
            mem_limit_mb,
            self._mem_limit_pct,
            int(total_mem_mb),
            nano_cpus / 1e9,
            self._cpu_limit_pct,
            cpu_count,
        )
        return {"mem_limit": f"{mem_limit_mb}m", "nano_cpus": nano_cpus}

    # ── 任务执行 ─────────────────────────────────────

    def run_task(self, task_id: str, image: str, command: str | None = None,
                 env: dict[str, str] | None = None,
                 volumes: dict[str, dict[str, str]] | None = None) -> str:
        """启动一个任务容器。

        Args:
            task_id:   任务 ID（用作容器名）
            image:     Docker 镜像
            command:   容器启动命令（可选）
            env:       环境变量（可选）
            volumes:   卷挂载（可选）

        Returns:
            container_id

        Raises:
            DockerUnavailableError
            TaskConfigError
        """
        try:
            client = self._ensure_client()
            resources = self._compute_resources()
        except ExecutorError:
            raise
        except Exception as exc:
            raise ExecutorError(f"Failed to prepare task environment: {exc}")

        container_name = f"slt-{task_id}"
        labels = {
            f"{CONTAINER_LABEL_PREFIX}.task-id": task_id,
        }

        try:
            container = client.containers.run(
                image=image,
                command=command,
                name=container_name,
                detach=True,
                mem_limit=resources["mem_limit"],
                nano_cpus=resources["nano_cpus"],
                cpu_shares=DEFAULT_CPU_SHARES,
                environment=env or {},
                volumes=volumes or {},
                labels=labels,
                # 安全约束
                read_only=False,          # 任务需要写临时文件
                network_mode="bridge",    # 隔离网络
                cap_drop=["ALL"],         # 丢弃所有 capabilities
                security_opt=["no-new-privileges:true"],
            )
            self._containers[task_id] = container.id
            logger.info(
                "Task %s started: container=%s image=%s mem=%s cpus=%.1f",
                task_id,
                container.short_id,
                image,
                resources["mem_limit"],
                resources["nano_cpus"] / 1e9,
            )
            return container.id

        except Exception as exc:
            raise ExecutorError(f"Failed to start container for task {task_id}: {exc}")

    # ── 暂停 / 恢复 ──────────────────────────────────

    def pause_all(self) -> list[str]:
        """暂停所有正在运行的任务容器。

        当 is_user_active=True 时由 daemon 调用。

        Returns:
            被暂停的 task_id 列表。
        """
        if self._paused:
            return []

        paused_tasks: list[str] = []
        client = self._client
        if client is None:
            return paused_tasks

        for task_id, container_id in list(self._containers.items()):
            try:
                container = client.containers.get(container_id)
                if container.status == "running":
                    container.pause()
                    paused_tasks.append(task_id)
                    logger.info("Container paused: task=%s container=%s",
                                task_id, container.short_id)
            except Exception:
                logger.debug(
                    "Failed to pause container for task %s", task_id, exc_info=True
                )

        if paused_tasks:
            self._paused = True
            logger.info("Paused %d container(s), agent entering passive mode", len(paused_tasks))

        return paused_tasks

    def resume_all(self) -> list[str]:
        """恢复所有被暂停的任务容器。

        Returns:
            被恢复的 task_id 列表。
        """
        if not self._paused:
            return []

        resumed_tasks: list[str] = []
        client = self._client
        if client is None:
            return resumed_tasks

        for task_id, container_id in list(self._containers.items()):
            try:
                container = client.containers.get(container_id)
                if container.status == "paused":
                    container.unpause()
                    resumed_tasks.append(task_id)
                    logger.info("Container resumed: task=%s container=%s",
                                task_id, container.short_id)
            except Exception:
                logger.debug(
                    "Failed to resume container for task %s", task_id, exc_info=True
                )

        if resumed_tasks:
            self._paused = False
            logger.info("Resumed %d container(s), agent back to active mode", len(resumed_tasks))

        return resumed_tasks

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def active_tasks(self) -> list[str]:
        return list(self._containers.keys())

    # ── 关闭 ─────────────────────────────────────────

    def shutdown(self) -> None:
        """优雅关闭所有容器。

        先 SIGTERM → 等待 GRACEFUL_STOP_TIMEOUT 秒 → SIGKILL。
        """
        client = self._client
        if client is None:
            self._containers.clear()
            return

        for task_id, container_id in list(self._containers.items()):
            try:
                container = client.containers.get(container_id)
                if container.status == "paused":
                    try:
                        container.unpause()
                    except Exception:
                        pass

                logger.info("Stopping container: task=%s container=%s",
                            task_id, container.short_id)
                container.stop(timeout=GRACEFUL_STOP_TIMEOUT)
                try:
                    container.remove()
                except Exception:
                    pass
            except Exception:
                logger.debug(
                    "Failed to stop container for task %s", task_id, exc_info=True
                )

        self._containers.clear()
        self._paused = False
        logger.info("All containers stopped, executor shut down")
