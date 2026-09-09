#!/bin/bash
# NeuroCortex 自动调用脚本 - Hermes版本
MSG="$1"
SESSION="${2:-hermes}"

# 调用MCP服务分析意图
RESULT=$(curl -s -X POST http://localhost:9100/chat \
  -H "Content-Type: application/json" \
  -d "{\"msg\": \"$MSG\", \"session\": \"$SESSION\"}" 2>/dev/null)

# 提取意图和概率
INTENT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('intent','general'))" 2>/dev/null || echo "general")
PROB=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('probability',0.5))" 2>/dev/null || echo "0.5")

# 根据历史成功率调整策略
case "$INTENT" in
  explain|review)
    echo "STRONG:$INTENT:$PROB:直接执行"
    ;;
  deploy|general)
    echo "MEDIUM:$INTENT:$PROB:分步确认"
    ;;
  create|fix)
    echo "MEDIUM:$INTENT:$PROB:谨慎处理"
    ;;
  test)
    echo "WEAK:$INTENT:$PROB:保守处理"
    ;;
  *)
    echo "UNKNOWN:$INTENT:$PROB:试探性执行"
    ;;
esac

# 保存经验
curl -s -X POST http://localhost:9100/save \
  -H "Content-Type: application/json" \
  -d "{\"msg\": \"$MSG\", \"intent\": \"$INTENT\", \"prob\": $PROB}" 2>/dev/null
