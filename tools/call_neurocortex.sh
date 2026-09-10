#!/bin/bash
# NeuroCortex 自动调用脚本 - Hermes版本
set -u
MSG="${1-}"
SESSION="${2:-hermes}"

if [ -z "$MSG" ]; then
    echo "Usage: call_neurocortex.sh <message> [session]" >&2
    exit 1
fi

PAYLOAD=$(python3 -c 'import json,sys; print(json.dumps({"msg": sys.argv[1], "session": sys.argv[2]}))' "$MSG" "$SESSION")

RESULT=$(curl -sS -X POST http://localhost:9100/chat \
  -H "Content-Type: application/json" \
  --data-binary "$PAYLOAD")

INTENT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('intent','general'))" 2>/dev/null || echo "general")
PROB=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('probability',0.5))" 2>/dev/null || echo "0.5")

case "$INTENT" in
  explain|review|read)
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

SAVE_PAYLOAD=$(python3 -c 'import json,sys; print(json.dumps({"msg": sys.argv[1], "intent": sys.argv[2], "prob": float(sys.argv[3])}))' "$MSG" "$INTENT" "$PROB")

SAVE_HTTP=$(curl -sS -o /tmp/nc_save_body.json -w "%{http_code}" -X POST http://localhost:9100/save \
  -H "Content-Type: application/json" \
  --data-binary "$SAVE_PAYLOAD")

if [ "$SAVE_HTTP" != "200" ]; then
    echo "SAVE_FAIL:http=$SAVE_HTTP" >&2
    exit 2
fi
python3 -c 'import json,sys; d=json.load(open("/tmp/nc_save_body.json")); assert d.get("ok") is True, d; print("SAVE_OK:count=%s" % d.get("experience_count"))'
