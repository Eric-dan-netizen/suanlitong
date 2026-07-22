"""算力通 · 云厂商 GPU 适配器抽象基类。

所有云厂商适配器必须继承 CloudGPUAdapter，实现三个核心方法。
每个方法均内置超时（30s）和重试（3 次）语义——子类只需实现 _xxx_impl。
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional  # noqa: UP045

logger = logging.getLogger(__name__)


class CloudGPUAdapter(ABC):
    """云厂商 GPU 实例管理抽象基类。"""

    timeout_sec: int = 30
    max_retries: int = 3
    retry_delay_sec: float = 1.0

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    async def _list_gpu_prices_impl(self, gpu_type: str) -> list[dict]:
        ...

    @abstractmethod
    async def _create_instance_impl(self, gpu_type: str, image: str) -> dict:
        ...

    @abstractmethod
    async def _terminate_instance_impl(self, instance_id: str) -> bool:
        ...

    async def list_gpu_prices(self, gpu_type: str) -> list[dict]:
        return await self._retry(
            self._list_gpu_prices_impl, gpu_type,
            ctx=f"list_gpu_prices({gpu_type})",
        )

    async def create_instance(self, gpu_type: str, image: str) -> dict:
        return await self._retry(
            self._create_instance_impl, gpu_type, image,
            ctx=f"create_instance({gpu_type}, {image})",
        )

    async def terminate_instance(self, instance_id: str) -> bool:
        return await self._retry(
            self._terminate_instance_impl, instance_id,
            ctx=f"terminate_instance({instance_id})",
        )

    async def _retry(self, fn: Any, *args: Any, ctx: str = "") -> Any:
        last_exc: Optional[Exception] = None  # noqa: UP045
        for attempt in range(1, self.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    fn(*args), timeout=self.timeout_sec,
                )
            except TimeoutError:
                last_exc = TimeoutError(
                    f"[{self.provider_name}] {ctx} 超时 ({self.timeout_sec}s)"
                )
            except Exception as exc:
                last_exc = exc

            logger.warning("Attempt %d/%d: %s", attempt, self.max_retries, last_exc)
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay_sec * attempt)

        raise RuntimeError(
            f"[{self.provider_name}] {ctx} 失败 "
            f"(重试 {self.max_retries} 次): {last_exc}"
        )


_registry: dict[str, CloudGPUAdapter] = {}


def register_adapter(adapter: CloudGPUAdapter) -> None:
    _registry[adapter.provider_name] = adapter


def get_adapter(provider: str) -> Optional[CloudGPUAdapter]:  # noqa: UP045
    return _registry.get(provider)
