#!/bin/bash
# NeuroCortex 自动调用 wrapper
MESSAGE="${1:-$(cat)}"
if [ -z "$MESSAGE" ]; then
    echo "Usage: nc-wrapper.sh <message>"
    exit 1
fi
RESULT=$(python3 /root/.openclaw/workspace/tools/neurocortex.py analyze "$MESSAGE" 2>/dev/null)
INTENT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('intent','?'))" 2>/dev/null)
PROB=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('probability',0))" 2>/dev/null)
RESPONSE=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)
echo "=== NeuroCortex ==="
echo "Intent: $INTENT | Prob: $PROB | $RESPONSE"
echo "==================="
