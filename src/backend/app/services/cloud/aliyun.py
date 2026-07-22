"""算力通 · 阿里云 GPU 适配器（骨架）。

TODO: 对接阿里云 ECS API
  - 查询 GPU 实例规格：DescribeInstanceTypes（筛选 GPU 族如 ecs.gn7i, ecs.gn8is）
  - 查询价格：DescribePrice（按量付费 + Spot）
  - 创建实例：RunInstances
  - 释放实例：DeleteInstance
  - SDK: alibabacloud-ecs20140526
"""

from .base import CloudGPUAdapter


class AliyunGPUAdapter(CloudGPUAdapter):
    """阿里云 ECS GPU 实例适配器。"""

    @property
    def provider_name(self) -> str:
        return "阿里云"

    async def _list_gpu_prices_impl(self, gpu_type: str) -> list[dict]:
        """TODO: 调用阿里云 DescribePrice API 查询 GPU 实例价格。

        实现步骤:
            1. 根据 gpu_type 映射到 ECS 实例规格族（如 A100 → ecs.gn7i-c32g1.8xlarge）
            2. 调用 DescribePrice，参数:
               - InstanceType = <规格>
               - PriceUnit = "Hour"
               - InternetChargeType = "PayByTraffic"
            3. 解析返回的按量付费和 Spot 价格
        """
        raise NotImplementedError(
            "阿里云 GPU 价格查询尚未实现。"
            " 需对接 alibabacloud-ecs20140526 SDK 的 DescribePrice API。"
        )

    async def _create_instance_impl(self, gpu_type: str, image: str) -> dict:
        """TODO: 调用阿里云 RunInstances API 创建 GPU 实例。

        实现步骤:
            1. 构建 RunInstances 请求参数:
               - InstanceType = <GPU 规格>
               - ImageId = image
               - InstanceChargeType = "PostPaid"（按量）
               - InternetMaxBandwidthOut = 10
            2. 调用 API，解析返回的 InstanceId
            3. 等待实例进入 Running 状态后返回 {instance_id, status, ip, ssh_port}
        """
        raise NotImplementedError(
            "阿里云 GPU 实例创建尚未实现。"
            " 需对接 alibabacloud-ecs20140526 SDK 的 RunInstances API。"
        )

    async def _terminate_instance_impl(self, instance_id: str) -> bool:
        """TODO: 调用阿里云 DeleteInstance API 释放 GPU 实例。

        实现步骤:
            1. 调用 DeleteInstance(InstanceId=instance_id, Force=True)
            2. 返回 True 表示删除成功
        """
        raise NotImplementedError(
            "阿里云 GPU 实例释放尚未实现。"
            " 需对接 alibabacloud-ecs20140526 SDK 的 DeleteInstance API。"
        )
