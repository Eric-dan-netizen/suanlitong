---
name: cloud-gpu-integration
description: 对接新的云厂商 GPU API。当需要适配阿里云/华为云/腾讯云 GPU 实例 API、实现多云比价、或新增云厂商支持时触发。
---

# 多云 GPU 集成 Skill

## 工作流程

### Step 1：阅读云厂商 API 文档

使用 WebFetch 获取云厂商 GPU 实例相关 API 文档：

- 阿里云：ECS DescribeInstanceTypes（GPU 规格）+ CreateInstance
- 华为云：ECS 创建云服务器（GPU 型）
- 腾讯云：CVM 创建实例（GPU 实例）

提取以下信息：
- GPU 型号列表及规格（vCPU、内存、GPU 显存）
- 计费方式：按量付费 / 包年包月 / Spot（抢占式）
- 各区域可用区和价格
- API 认证方式（AccessKey / 临时令牌）

### Step 2：实现适配器

继承 `CloudGPUAdapter` 基类，实现三个方法：

```python
class AliyunGPUAdapter(CloudGPUAdapter):
    async def list_gpu_prices(self, gpu_type: str) -> list[dict]
    async def create_instance(self, gpu_type, image, hours) -> dict
    async def terminate_instance(self, instance_id) -> bool
```

### Step 3：价格数据缓存

将价格数据写入 Redis，TTL 5 分钟。Key 格式：`price:aliyun:A100:cn-beijing`

### Step 4：集成测试

```bash
pytest tests/test_aliyun_adapter.py -v
```

验证：
- 价格列表非空
- 实例创建返回有效 instance_id
- 实例释放成功
