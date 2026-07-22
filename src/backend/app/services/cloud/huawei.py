"""算力通 · 华为云 GPU 适配器（骨架）。

TODO: 对接华为云 ECS API
  - 查询 GPU 规格：GET /v1/{project_id}/cloudservers/flavors（筛选 GPU 型规格）
  - 查询价格：BSS 询价 API
  - 创建实例：POST /v1/{project_id}/cloudservers
  - 释放实例：DELETE /v1/{project_id}/cloudservers/{server_id}
  - SDK: huaweicloudsdkecs
  - 认证：AK/SK → IAM Token → 调用各服务 API
  区域代码格式: cn-north-4, cn-east-3 等。
"""

from .base import CloudGPUAdapter


class HuaweiGPUAdapter(CloudGPUAdapter):
    """华为云 ECS GPU 实例适配器。"""

    @property
    def provider_name(self) -> str:
        return "华为云"

    async def _list_gpu_prices_impl(self, gpu_type: str) -> list[dict]:
        """TODO: 调用华为云 BSS 询价 API 查询 GPU 实例价格。

        实现步骤:
            1. 通过 AK/SK 获取 IAM Token
            2. 调用 GET /v1/{project_id}/cloudservers/flavors
               参数 cond:operation_status="az:normal" 筛选可售规格
            3. 使用 BSS（商务智能）API 的询价接口获取按量/Spot 价格
        """
        raise NotImplementedError(
            "华为云 GPU 价格查询尚未实现。"
            " 需对接 huaweicloudsdkecs SDK 的 BSS 询价 API。"
        )

    async def _create_instance_impl(self, gpu_type: str, image: str) -> dict:
        """TODO: 调用华为云 ECS 创建 API 创建 GPU 实例。

        实现步骤:
            1. 获取 IAM Token
            2. POST /v1/{project_id}/cloudservers
               请求体包含:
               - server.flavorRef = <GPU 规格 ID>
               - server.imageRef = image
               - server.root_volume.volumetype = "SSD"
            3. 解析返回的 server_id，轮询状态至 ACTIVE
            4. 返回 {instance_id, status, ip, ssh_port}
        """
        raise NotImplementedError(
            "华为云 GPU 实例创建尚未实现。"
            " 需对接 huaweicloudsdkecs SDK 的 cloudservers 创建 API。"
        )

    async def _terminate_instance_impl(self, instance_id: str) -> bool:
        """TODO: 调用华为云 ECS 删除 API 释放 GPU 实例。

        实现步骤:
            1. 获取 IAM Token
            2. DELETE /v1/{project_id}/cloudservers/{instance_id}
               参数:
               - servers[0].id = instance_id
               - delete_publicip = true
               - delete_volume = true
            3. 返回 True 表示删除成功
        """
        raise NotImplementedError(
            "华为云 GPU 实例释放尚未实现。"
            " 需对接 huaweicloudsdkecs SDK 的 cloudservers 删除 API。"
        )
