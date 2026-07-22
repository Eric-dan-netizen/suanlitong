---
name: billing-engine
description: 搭建或修改算力通计费系统。当需要实现按秒计费、余额管理、欠费处理、或对接支付网关时触发。
---

# 计费引擎 Skill

## 核心模型

### 计费公式

```
费用 = GPU 单价 × 使用秒数 / 3600

其中：
- GPU 单价来自实时价格缓存（Redis）
- 使用秒数 = 实例终止时间 - 实例创建时间 - 暂停时间
- 计量精度：秒
```

### 数据库表

```sql
CREATE TABLE billing_records (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    gpu_type TEXT NOT NULL,
    price_per_hour REAL NOT NULL,
    used_seconds INTEGER NOT NULL,
    cost REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_balances (
    user_id TEXT PRIMARY KEY,
    balance REAL DEFAULT 0.0,
    frozen_balance REAL DEFAULT 0.0,
    updated_at TIMESTAMP
);
```

## 工作流程

### Step 1：计量逻辑

- 实例创建时：记录 `start_time` 到 Redis
- 每 60 秒：计算增量时长，预估费用，冻结对应余额
- 实例终止时：计算最终费用，从余额扣除

### Step 2：余额管理

- 余额不足时：先发提醒 → 欠费 5 分钟后自动停服
- 冻结余额：正在运行中的实例预估费用，不可用于新实例

### Step 3：支付集成

- 支付宝：调用支付宝开放平台 API
- 微信支付：JSAPI 支付
- 充值成功后：更新 `user_balances` → 发送通知

### Step 4：对账

```python
# 每日对账脚本
def daily_reconciliation(date):
    """
    对比：平台计费记录 vs 云厂商账单
    差异 > 1% → 告警
    """
```
