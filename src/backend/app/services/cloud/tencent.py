"""算力通 · 腾讯云 GPU 适配器（骨架）。

TODO: 对接腾讯云 CVM API
  - 查询 GPU 实例规格：DescribeInstanceTypeConfigs（筛选 GPU 族 GN10Xp, GN7, PTX1）
  - 查询价格：InquiryPriceRunInstances（按量 + Spot）
  - 创建实例：RunInstances
  - 释放实例：TerminateInstances
  - SDK: tencentcloud-sdk-python (tencentcloud.cvm.v20170312)
  - 认证：SecretId + SecretKey
"""

from .base import CloudGPUAdapter


class TencentGPUAdapter(CloudGPUAdapter):
    """腾讯云 CVM GPU 实例适配器。"""

    @property
    def provider_name(self) -> str:
        return "腾讯云"

    async def _list_gpu_prices_impl(self, gpu_type: str) -> list[dict]:
        """TODO: 调用腾讯云 InquiryPriceRunInstances API 查询 GPU 实例价格。

        实现步骤:
            1. 调用 DescribeInstanceTypeConfigs
               通过 Filters 筛选 GPU 实例族:
               - GN10Xp → A100
               - GN7    → 消费级 (4090 等)
               - PTX1   → H100
            2. 调用 InquiryPriceRunInstances:
               - InstanceType      = <筛选结果>
               - InstanceChargeType = "POSTPAID_BY_HOUR"（按量）或 "SPOTPAID"（竞价）
               - Placement.Zone    = "ap-beijing-1" 等
            3. 解析返回的 UnitPrice 得到每小时价格
        """
        raise NotImplementedError(
            "腾讯云 GPU 价格查询尚未实现。"
            " 需对接 tencentcloud-sdk-python 的 InquiryPriceRunInstances API。"
        )

    async def _create_instance_impl(self, gpu_type: str, image: str) -> dict:
        """TODO: 调用腾讯云 RunInstances API 创建 GPU 实例。

        实现步骤:
            1. 构建 RunInstances 请求:
               - InstanceType = <GPU 规格>
               - ImageId = image
               - InstanceChargeType = "POSTPAID_BY_HOUR"
               - InternetAccessible.InternetMaxBandwidthOut = 10
            2. 调用 API，解析返回的 InstanceIdSet
            3. 调用 DescribeInstances 轮询状态至 RUNNING
            4. 返回 {instance_id, status, ip, ssh_port}
        """
        raise NotImplementedError(
            "腾讯云 GPU 实例创建尚未实现。"
            " 需对接 tencentcloud-sdk-python 的 RunInstances API。"
        )

    async def _terminate_instance_impl(self, instance_id: str) -> bool:
        """TODO: 调用腾讯云 TerminateInstances API 释放 GPU 实例。

        实现步骤:
            1. 调用 TerminateInstances(InstanceIds=[instance_id])
            2. 返回 True 表示释放成功
        """
        raise NotImplementedError(
            "腾讯云 GPU 实例释放尚未实现。"
            " 需对接 tencentcloud-sdk-python 的 TerminateInstances API。"
        )
