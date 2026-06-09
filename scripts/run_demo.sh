#!/usr/bin/env bash
# ── Demo 录制一键启动脚本 ──
# 用法:
#   TOOL_CACHE_MODE=force_cache LLM_CACHE_TTL_SECONDS=2592000 bash scripts/run_demo.sh
#
# 依赖: 已用 `python scripts/warmup_cache.py --targets 飞书 钉钉` 预灌过缓存

set -euo pipefail

echo "=== Demo 競品分析 ==="
echo "模式: TOOL_CACHE_MODE=${TOOL_CACHE_MODE:-force_cache}"
echo "目标: 飞书 / 钉钉"
echo "模板: demo_competitor_analysis"
echo ""

# 启动 API server（后台）
echo "🚀 启动 API server (port 8000)..."
python -m uvicorn src.api.app:app --port 8000 --log-level warning &
SERVER_PID=$!
sleep 3

# 健康检查
if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ API server 启动失败"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi
echo "✅ API server 已就绪"

# 提交任务
echo "📤 提交竞品分析任务..."
START_TS=$(date +%s)
RESPONSE=$(curl -s -X POST http://localhost:8000/api/tasks \
    -H "Content-Type: application/json" \
    -d '{
        "targets": ["飞书", "钉钉"],
        "industry": "saas",
        "execution_mode": "auto",
        "collection_depth": "demo"
    }')
echo "响应: $RESPONSE"

# 提取 task_id
TASK_ID=$(echo "$RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin)['task_id'])" 2>/dev/null || echo "")
if [ -z "$TASK_ID" ]; then
    echo "❌ 未能获取 task_id"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
fi
echo "📋 task_id: $TASK_ID"

# 轮询等待完成
echo "⏳ 等待任务完成..."
while true; do
    STATUS=$(curl -sf "http://localhost:8000/api/tasks/$TASK_ID" | python -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "running")
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        break
    fi
    sleep 5
done

END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))
echo "⏱️  总耗时: ${DURATION}s"

if [ "$STATUS" = "completed" ]; then
    echo "✅ 任务完成！"
    # 获取报告
    echo ""
    echo "=== 报告摘要 ==="
    curl -s "http://localhost:8000/api/reports/$TASK_ID" \
        | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary','')[:500] if isinstance(d,dict) else d[:500])" 2>/dev/null || echo "(报告获取失败)"
else
    echo "❌ 任务失败"
fi

# 清理
kill $SERVER_PID 2>/dev/null || true
echo ""
echo "=== Demo 结束 ==="