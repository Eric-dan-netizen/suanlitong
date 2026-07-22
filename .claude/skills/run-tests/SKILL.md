---
name: run-tests
description: 运行算力通项目的完整测试套件。当提交 PR 前、合并到 main 前、或手动触发 /run-tests 时使用。
---

# 测试 Skill

## 测试命令速查

```bash
# 全部测试 + 覆盖率
pytest --cov=src --cov-report=term --cov-report=html

# 仅后端
pytest src/backend/tests/ -v

# 仅 Agent
pytest src/agent/tests/ -v

# 代码风格
black --check src/
isort --check src/
mypy src/

# 一键全量
make test
```

## 工作流程

### Step 1：代码风格检查
```bash
black --check . && isort --check . && echo "✅ Lint passed" || echo "❌ Lint failed"
```

### Step 2：类型检查
```bash
mypy src/ --ignore-missing-imports
```

### Step 3：单元测试 + 覆盖率
```bash
pytest --cov=src --cov-report=term --cov-fail-under=80
```

### Step 4：输出报告
```
测试报告
────────
总计：XX 个测试
通过：XX
失败：XX
覆盖率：XX%

结论：✅ 允许提交 / ❌ 需要修复（附失败详情）
```
