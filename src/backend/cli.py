"""
算力通 · 多云比价 CLI 工具

用法：
    python src/backend/cli.py price A100
    python src/backend/cli.py price H100
    python src/backend/cli.py price 4090

认证：通过环境变量读取各云厂商 AccessKey
    ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET
    HUAWEI_ACCESS_KEY_ID / HUAWEI_ACCESS_KEY_SECRET
    TENCENT_SECRET_ID / TENCENT_SECRET_KEY
"""

import abc
import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

# ── Data Models ──────────────────────────────────────


@dataclass
class GPUPrice:
    """单个云厂商的 GPU 价格信息。"""

    provider: str
    gpu_type: str
    on_demand_price: float  # 按量付费（元/小时）
    spot_price: float  # 抢占式实例（元/小时）
    region: str

    def as_tuple(self):
        return (
            self.provider,
            self.gpu_type,
            self.on_demand_price,
            self.spot_price,
            self.region,
        )


# ── Mock Data ────────────────────────────────────────
# 当前阶段使用 mock 数据，因为真实的云厂商 AccessKey 尚未配置。
# 当真实 API Key 就绪后，删除 MOCK_DATA 字典，启用各 PriceFetcher 的
# `_call_api` 方法（见下方类实现中的 _REAL_API_ENABLED 标记）。

MOCK_DATA: dict[str, list[GPUPrice]] = {
    # 价格来源：阿里云/华为云/腾讯云 2026 Q2 官网 GPU 实例按量付费定价
    # 与商业计划书 V3 中引用的数据一致
    "A100": [
        GPUPrice("阿里云", "A100", 28.50, 12.80, "cn-beijing"),
        GPUPrice("华为云", "A100", 30.20, 14.10, "cn-north-4"),
        GPUPrice("腾讯云", "A100", 29.80, 13.50, "ap-beijing"),
    ],
    # H100 为 NVIDIA 最新代次，极度紧缺
    # 来源：商业计划书 V3 引用价格区间 35-48 元/小时
    "H100": [
        GPUPrice("阿里云", "H100", 45.00, 22.00, "cn-beijing"),
        GPUPrice("华为云", "H100", 48.00, 24.00, "cn-north-4"),
        GPUPrice("腾讯云", "H100", 46.00, 23.00, "ap-beijing"),
    ],
    # RTX 4090 为消费级 GPU，价格区间 1.3-2.6 元/小时
    "4090": [
        GPUPrice("阿里云", "4090", 2.50, 1.20, "cn-beijing"),
        GPUPrice("华为云", "4090", 2.60, 1.30, "cn-north-4"),
        GPUPrice("腾讯云", "4090", 2.40, 1.10, "ap-beijing"),
    ],
}


# ── Abstract Base ───────────────────────────────────


class BasePriceFetcher(abc.ABC):
    """云厂商 GPU 价格查询器基类。

    子类必须实现:
        _provider_name     → str  云厂商名称
        _real_fetch_prices → list[GPUPrice]  真实 API 调用
    """

    TIMEOUT_SEC = 30
    MAX_RETRIES = 3
    RETRY_DELAY_SEC = 1.0

    @property
    @abc.abstractmethod
    def _provider_name(self) -> str: ...

    @abc.abstractmethod
    def _real_fetch_prices(self, gpu_type: str) -> list[GPUPrice]:
        """
        真实 API 调用逻辑。

        MOCK 阶段: 不执行此方法。启用条件:
            os.getenv("ALIYUN_ACCESS_KEY_ID") is not None  # 示例
        """
        ...

    def fetch_prices(self, gpu_type: str) -> list[GPUPrice]:
        """带超时和重试的公开入口。当前阶段返回 mock 数据。"""
        # ── MOCK 分支 ────────────────────────────────
        # TODO: 当环境变量检测到真实 AccessKey 时，切换到真实 API
        if gpu_type in MOCK_DATA:
            return [p for p in MOCK_DATA[gpu_type] if p.provider == self._provider_name]
        return []

        # ── 真实 API 分支 ────────────────────────────
        # 删除上方 MOCK 分支，启用下方代码:
        #
        # last_exc: Optional[Exception] = None
        # for attempt in range(1, self.MAX_RETRIES + 1):
        #     try:
        #         return self._real_fetch_prices(gpu_type)
        #     except Exception as exc:
        #         last_exc = exc
        #         if attempt < self.MAX_RETRIES:
        #             time.sleep(self.RETRY_DELAY_SEC * attempt)
        # raise RuntimeError(
        #     f"[{self._provider_name}] 查询失败 (重试 {self.MAX_RETRIES} 次): {last_exc}"
        # )


# ── Aliyun ───────────────────────────────────────────


class AliyunPriceFetcher(BasePriceFetcher):
    """阿里云 ECS GPU 实例价格查询。

    真实 API:
        POST / 参数 Action=DescribeInstanceTypes
        → 筛选 GPU 规格 (InstanceTypeFamily 如 ecs.gn7i, ecs.gn8is)
        → POST / 参数 Action=DescribePrice → 按量 / Spot 价格
    """

    @property
    def _provider_name(self) -> str:
        return "阿里云"

    def _real_fetch_prices(self, gpu_type: str) -> list[GPUPrice]:
        """
        真实 API 调用骨架 (当前为占位)。

        实现步骤:
            1. 调用 DescribeInstanceTypes 获取该 GPU 对应的实例规格列表
               请求参数:
                   RegionId            = "cn-beijing"
                   InstanceTypeFamily  根据 GPU 型号选择:
                      A100 → "ecs.gn7i-c16g1.4xlarge" 等
                      H100 → "ecs.gn8is-..." 等
                      4090 → "ecs.gn7i-c32g1.8xlarge" 等

            2. 取第一个实例规格，调用 DescribePrice:
                   InstanceType = <上一步结果>
                   PriceUnit    = "Hour"
                   SpotStrategy = "SpotAsPriceGo"  (Spot 价格)

            3. 解析返回 JSON:
                   on_demand_price = Data.PriceInfo.Price.OriginalPrice
                   spot_price      = Data.PriceInfo.Price.TradePrice

        认证方式:
            使用 alibabacloud_ecs20140526 SDK:
                from alibabacloud_ecs20140526.client import Client
                client = Client(config)  # config 含 AccessKey

        已知问题: 阿里云 DescribePrice 返回的价格是折扣前的"原价"，
        实际代理商价格可能低 10-15%。
        """
        # MOCK 占位 — 真实 API Key 就绪后实现
        return MOCK_DATA.get(gpu_type, [])


# ── Huawei ───────────────────────────────────────────


class HuaweiPriceFetcher(BasePriceFetcher):
    """华为云 ECS GPU 实例价格查询。

    真实 API:
        GET  /v1/{project_id}/cloudservers/flavors?spec=GPU
        → 筛选 GPU 规格
        GET  /v1/{project_id}/cloudservers/flavors/{flavor_id}/os-version
        → 查询按需/Spot 价格
    """

    @property
    def _provider_name(self) -> str:
        return "华为云"

    def _real_fetch_prices(self, gpu_type: str) -> list[GPUPrice]:
        """
        真实 API 调用骨架 (当前为占位)。

        实现步骤:
            1. 调用 GET /v1/{project_id}/cloudservers/flavors
               通过 cond:operation_status="az:normal" 筛选可售规格
               通过 spec 参数筛选 GPU 型规格

            2. 查询价格:
               使用 BSS(商务智能) API 的询价接口

            3. 认证:
               通过 AK/SK 获取 IAM Token，再调用各服务 API

        注意: 华为云 GPU 实例的区域代码格式为 cn-north-4、cn-east-3 等。
        """
        return MOCK_DATA.get(gpu_type, [])


# ── Tencent ──────────────────────────────────────────


class TencentPriceFetcher(BasePriceFetcher):
    """腾讯云 CVM GPU 实例价格查询。

    真实 API:
        DescribeInstanceTypeConfigs → 筛选 GPU 实例族 (GN10Xp, GN7, PTX1)
        InquiryPriceRunInstances  → 按量/Spot 价格
    """

    @property
    def _provider_name(self) -> str:
        return "腾讯云"

    def _real_fetch_prices(self, gpu_type: str) -> list[GPUPrice]:
        """
        真实 API 调用骨架 (当前为占位)。

        实现步骤:
            1. 调用 DescribeInstanceTypeConfigs
               通过 Filters 筛选 GPU 实例族:
                   GN10Xp → A100
                   GN7    → 消费级 (4090 等)
                   PTX1   → H100

            2. 调用 InquiryPriceRunInstances:
                   InstanceType      = <筛选结果>
                   InstanceChargeType = "POSTPAID_BY_HOUR"  (按量)
                   或 SPOTPAID (竞价)

            3. 认证:
               使用 tencentcloud-sdk-python:
                   from tencentcloud.cvm.v20170312 import cvm_client
                   cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        """
        return MOCK_DATA.get(gpu_type, [])


# ── CLI Table Rendering ──────────────────────────────


def render_table(results: list[GPUPrice]) -> str:
    """将 GPUPrice 列表渲染为终端对齐表格，标记最低价格行。"""
    if not results:
        return "未找到匹配的 GPU 价格数据。"

    hdr = ["云厂商", "GPU 型号", "按量付费\n（元/小时）", "Spot 价格\n（元/小时）", "可用区域"]
    rows = [r.as_tuple() for r in results]

    col_widths = [
        max(len(h.split("\n")[0]), *(len(str(row[i])) for row in rows)) + 2
        for i, h in enumerate(hdr)
    ]

    def fmt_row(cells, widths):
        return "│" + "│".join(f"{{:<{w}}}".format(str(c)) for c, w in zip(cells, widths)) + "│"

    def border(connectors):
        return connectors[0] + connectors[1].join("─" * w for w in col_widths) + connectors[2]

    out = []
    out.append(border("┌┬┐"))
    out.append(fmt_row([h.split("\n")[0] for h in hdr], col_widths))
    out.append(fmt_row([h.split("\n")[1] if "\n" in h else "" for h in hdr], col_widths))
    out.append(border("├┼┤"))

    min_price = min(r.on_demand_price for r in results)
    for r in results:
        row_str = f"{' ' * 6}"  # indent for readability
        cells = [str(c) for c in r.as_tuple()]
        line = fmt_row(cells, col_widths)
        if r.on_demand_price == min_price:
            line += "  ← 最低"
        out.append(line)

    out.append(border("└┴┘"))
    return "\n".join(out)

def cmd_price(args: argparse.Namespace) -> None:
    """处理 `price` 子命令。"""
    gpu_type = args.gpu.upper()
    fetchers: list[BasePriceFetcher] = [
        AliyunPriceFetcher(),
        HuaweiPriceFetcher(),
        TencentPriceFetcher(),
    ]

    all_results: list[GPUPrice] = []
    for fetcher in fetchers:
        try:
            prices = fetcher.fetch_prices(gpu_type)
            all_results.extend(prices)
        except Exception as exc:
            print(f"[WARN] {fetcher._provider_name} 查询失败: {exc}", file=sys.stderr)

    if not all_results:
        print(f"❌ 未找到 GPU 型号 '{gpu_type}' 的价格数据。", file=sys.stderr)
        print(f"   支持的型号: {', '.join(sorted(MOCK_DATA.keys()))}", file=sys.stderr)
        sys.exit(1)

    print(render_table(all_results))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="suanlitong",
        description="算力通 · 多云 GPU 比价 CLI",
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("price", help="查询 GPU 实时比价")
    p.add_argument(
        "gpu",
        help="GPU 型号 (A100 / H100 / 4090)",
    )
    p.set_defaults(func=cmd_price)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
