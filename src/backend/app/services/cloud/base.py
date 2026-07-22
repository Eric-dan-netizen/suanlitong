"""算力通 · 云厂商 GPU 适配器抽象基类。

所有云厂商适配器必须继承 CloudGPUAdapter，实现三个核心方法。
每个方法均内置超时（30s）和重试（3 次）语义——子类只需实现 _xxx_impl。
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class CloudGPUAdapter(ABC):
    """云厂商 GPU 实例管理抽象基类。

    子类需要实现:
        - _list_gpu_prices_impl(gpu_type: str) -> list[dict]
        - _create_instance_impl(gpu_type: str, image: str) -> dict
        - _terminate_instance_impl(instance_id: str) -> bool

    公开方法 list_gpu_prices / create_instance / terminate_instance
    自动附加超时和重试逻辑。
    """

    # ── 默认超时与重试 ──────────────────────────────
    timeout_sec: int = 30
    max_retries: int = 3
    retry_delay_sec: float = 1.0

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """云厂商名称，如 '阿里云'、'华为云'、'腾讯云'。"""
        ...

    # ── 抽象方法（子类实现） ────────────────────────

    @abstractmethod
    async def _list_gpu_prices_impl(self, gpu_type: str) -> list[dict]:
        """子类实现：调用真实云 API 查询 GPU 价格。

        Returns:
            [{provider, gpu_type, price_per_hour, spot_price, region}]
        """
        ...

    @abstractmethod
    async def _create_instance_impl(self, gpu_type: str, image: str) -> dict:
        """子类实现：调用真实云 API 创建 GPU 实例。

        Returns:
            {instance_id, status, ip, ssh_port}
        """
        ...

    @abstractmethod
    async def _terminate_instance_impl(self, instance_id: str) -> bool:
        """子类实现：调用真实云 API 释放 GPU 实例。

        Returns:
            True 表示释放成功。
        """
        ...

    # ── 公开方法（自动重试） ────────────────────────

    async def list_gpu_prices(self, gpu_type: str) -> list[dict]:
        """带超时和重试的价格查询入口。"""
        return await self._retry(
            self._list_gpu_prices_impl,
            gpu_type,
            ctx=f"list_gpu_prices({gpu_type})",
        )

    async def create_instance(self, gpu_type: str, image: str) -> dict:
        """带超时和重试的实例创建入口。"""
        return await self._retry(
            self._create_instance_impl,
            gpu_type,
            image,
            ctx=f"create_instance({gpu_type}, {image})",
        )

    async def terminate_instance(self, instance_id: str) -> bool:
        """带超时和重试的实例释放入口。"""
        return await self._retry(
            self._terminate_instance_impl,
            instance_id,
            ctx=f"terminate_instance({instance_id})",
        )

    # ── 内部重试逻辑 ────────────────────────────────

    async def _retry(self, fn: Any, *args: Any, ctx: str = "") -> Any:
        """执行 fn(*args)，失败时最多重试 max_retries 次。"""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    fn(*args),
                    timeout=self.timeout_sec,
                )
            except asyncio.TimeoutError:
                last_exc = TimeoutError(
                    f"[{self.provider_name}] {ctx} 超时 ({self.timeout_sec}s)"
                )
                logger.warning("Attempt %d/%d: %s", attempt, self.max_retries, last_exc)
            except Exception as exc:
                last_exc = exc
                logger.warning("Attempt %d/%d: %s", attempt, self.max_retries, exc)

            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay_sec * attempt)

        raise RuntimeError(
            f"[{self.provider_name}] {ctx} 失败 "
            f"(重试 {self.max_retries} 次): {last_exc}"
        )


# ── 适配器注册表 ────────────────────────────────────

_registry: dict[str, CloudGPUAdapter] = {}


def register_adapter(adapter: CloudGPUAdapter) -> None:
    """注册一个云厂商适配器。"""
    _registry[adapter.provider_name] = adapter


def get_adapter(provider: str) -> CloudGPUAdapter | None:
    """根据云厂商名称获取已注册的适配器。"""
    return _registry.get(provider)


def get_all_adapters() -> dict[str, CloudGPUAdapter]:
    """获取所有已注册的适配器。"""
    return dict(_registry)
