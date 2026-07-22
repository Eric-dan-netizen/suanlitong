---
name: device-agent
description: 开发或调试算力通设备客户端。当需要实现系统资源监控、心跳协议、Docker 任务执行、或 Checkpoint 机制时触发。
---

# 设备 Agent Skill

## 架构

```
daemon.py（主进程，systemd/launchd 管理）
  ├── monitor.py   → 每 5 秒采集系统资源
  ├── heartbeat.py → 每 500ms 发送 UDP 心跳
  ├── executor.py  → Docker 容器管理
  └── checkpoint.py → 任务状态保存/恢复
```

## 工作流程

### Step 1：实现资源监控

```python
import psutil, GPUtil

def get_system_usage():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    gpus = GPUtil.getGPUs()
    gpu_percent = max(g. load * 100 for g in gpus) if gpus else 0

    # 用户活跃检测：macOS 用 Quartz，Linux 用 xprintidle
    is_active = check_user_activity(timeout_seconds=30)

    return {
        "cpu_percent": cpu,
        "gpu_percent": gpu_percent,
        "ram_percent": ram,
        "is_user_active": is_active
    }
```

### Step 2：实现心跳

- 协议：UDP，目标端口 9999
- Payload：JSON，< 1KB
- 重连逻辑：UDP 无连接，每次发送独立

### Step 3：实现任务执行

- Docker SDK for Python
- 资源限制：`mem_limit='50%'`, `nano_cpus=CPU核心数*0.5`
- 优雅关闭：SIGTERM → 等待 10s → SIGKILL

### Step 4：测试

```bash
# 模拟用户活跃 → 任务暂停
python -m pytest tests/test_executor.py::test_pause_on_user_active

# 模拟断网 → Agent 重连
python -m pytest tests/test_heartbeat.py::test_reconnect
```
