#!/bin/bash
# 算力通 · 部署后健康检查
set -euo pipefail

API_URL="${1:-https://api.suanlitong.cn}"
FAIL=0

echo "=== 健康检查 ${API_URL} ==="

STATUS=$(curl -sf "${API_URL}/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "FAIL")
if [ "$STATUS" != "ok" ]; then
  echo "❌ /health 失败: status=${STATUS}"
  FAIL=1
else
  echo "✅ /health → ok"
fi

PRICES=$(curl -sf "${API_URL}/api/v1/prices?gpu_type=A100" 2>/dev/null || echo "[]")
COUNT=$(echo "$PRICES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
if [ "$COUNT" -eq 0 ]; then
  echo "⚠️  /api/v1/prices 返回空（数据可能尚未采集）"
else
  echo "✅ /api/v1/prices?gpu_type=A100 → ${COUNT} 条"
fi

CODE=$(curl -so /dev/null -w "%{http_code}" "${API_URL}/api/v1/instances" 2>/dev/null || echo "000")
if [ "$CODE" -eq 200 ]; then
  echo "✅ /api/v1/instances → 200"
else
  echo "❌ /api/v1/instances → ${CODE}"
  FAIL=1
fi

if [ "$FAIL" -eq 1 ]; then
  echo "❌ 健康检查未通过"
  exit 1
fi
echo "=== 健康检查全部通过 ==="
