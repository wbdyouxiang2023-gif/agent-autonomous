#!/usr/bin/env python3
"""NeuroCortex MCP Server — 通过 stdio 与 OpenClaw 交互"""
import sys, os, json, hashlib
from datetime import datetime, timezone
import signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from neurocortex.cortex import NeuroCortex
from neurocortex.modules import MockPerception, MockRepresentation, MockAttention, MockState, MockMemory, MockDecision, MockAction, MockFeedback
from neurocortex.state import BasicStateModule
from neurocortex.prediction import BasicPrediction
from neurocortex.learning.experience_learner import ExperienceLearningModule
from neurocortex.memory.experience_store import ExperienceStore
from neurocortex.memory.experience_retriever import ExperienceRetriever
from neurocortex.prediction.experience_prediction import ExperiencePredictionModule
from neurocortex.interfaces import OutcomeProvider
from neurocortex.event import OutcomeData
from neurocortex.perception.intent_router import detect_coarse_intent

STORE_PATH = os.environ.get("NEUROSTORE", os.path.expanduser("~/.neurocortex_memory.jsonl"))

# ── Perception ─────────────────────────────────────────────────

class BilingualPerception(MockPerception):
    def _detect_intent(self, text):
        return detect_coarse_intent(text)


class PersistentOutcome(OutcomeProvider):
    def __init__(self, store):
        self._store = store
    def provide(self, event):
        intent = event.perception.intent
        recent = [e for e in self._store.list_all() if e.intent == intent]
        if intent == "explain":
            success = True
        elif intent == "fix" and recent and not recent[-1].success:
            success = True
        elif intent == "review":
            success = True
        elif len(recent) >= 3:
            h = int(hashlib.md5(event.raw_input.encode()).hexdigest(), 16)
            success = h % 4 != 0
        else:
            h = int(hashlib.md5(event.raw_input.encode()).hexdigest(), 16)
            success = h % 5 != 0
        event.record_outcome(OutcomeData(actual_outcome="done", success=success))
        return event


# ── 初始化 ─────────────────────────────────────────────────────

store = ExperienceStore(STORE_PATH)
learner = ExperienceLearningModule(store)
retriever = ExperienceRetriever(store, top_k=3)
exp_pred = ExperiencePredictionModule(retriever, base_prediction=BasicPrediction())

cortex = NeuroCortex(
    perception=BilingualPerception(),
    representation=MockRepresentation(),
    attention=MockAttention(),
    state=BasicStateModule(),
    memory=MockMemory(),
    prediction=exp_pred,
    decision=MockDecision(),
    action=MockAction(),
    outcome_provider=PersistentOutcome(store),
    feedback=MockFeedback(),
    learning=learner,
)
print(f"NeuroCortex ready. {store.count()} experiences loaded.", file=sys.stderr, flush=True)


def build_response(event, retrieved):
    n = len(retrieved)
    p = event.prediction.success_probability
    labels = {"explain":"解释","create":"创建","fix":"修复","review":"审查",
              "deploy":"部署","optimize":"优化","test":"测试","general":"处理"}
    label = labels.get(event.perception.intent, "处理")
    if n == 0:
        return f"收到，我来{label}。"
    elif p >= 0.85:
        top = retrieved[0][0]
        if top.success:
            return f"这类{label}任务处理过多次，没问题。"
        else:
            return f"之前同类{label}有过困难，这次会格外小心。"
    elif p < 0.5:
        return f"这个{label}任务有风险，我需要更多信息。"
    else:
        return f"好的，开始{label}。"


def get_stats():
    exps = store.list_all()
    if not exps:
        return {"total": 0, "strong": [], "weak": []}
    by_intent = {}
    for e in exps:
        by_intent.setdefault(e.intent, []).append(e.to_dict())
    strong, weak = [], []
    for intent, items in sorted(by_intent.items()):
        rate = sum(1 for e in items if e["success"]) / len(items)
        fails = sum(1 for e in items if not e["success"])
        if rate >= 0.8:
            strong.append(f"{intent}({rate:.0%})")
        if fails > 0:
            weak.append(f"{intent}({fails}次)")
    return {"total": len(exps), "strong": strong, "weak": weak, "by_intent": by_intent}


# ── MCP JSON-RPC over stdio ───────────────────────────────────

_MESSAGE_ID = 1

def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def handle_initialized():
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})

def handle_tools_list():
    tools = [
        {
            "name": "neurocortex_chat",
            "description": "向 NeuroCortex 发送消息，触发认知循环（感知→决策→行动→学习），积累经验",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "msg": {"type": "string", "description": "要处理的输入消息"},
                    "session": {"type": "string", "description": "会话标识，默认 default"}
                },
                "required": ["msg"]
            }
        },
        {
            "name": "neurocortex_stats",
            "description": "查看 NeuroCortex 经验统计：擅长/困难领域、按意图分布",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "neurocortex_experiences",
            "description": "列出所有已积累的经验记录",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "neurocortex_clear",
            "description": "清空经验库（不可恢复）",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "neurocortex_health",
            "description": "检查 NeuroCortex 服务状态和经验库大小",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
    ]
    send({"jsonrpc": "2.0", "id": None, "method": "notifications/tools/list", "result": {"tools": tools}})
    # Actually, for MCP we need a proper response
    # Let me handle this differently


def handle_request(msg):
    global _MESSAGE_ID
    method = msg.get("method", "")
    params = msg.get("params", {})
    req_id = msg.get("id")

    if method == "initialize":
        send({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "neurocortex", "version": "1.0.0"}
            }
        })
        handle_initialized()

    elif method == "tools/list":
        tools = [
            {
                "name": "neurocortex_chat",
                "description": "向 NeuroCortex 发送消息，触发认知循环（感知→决策→行动→学习），积累经验",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "msg": {"type": "string", "description": "要处理的输入消息"},
                        "session": {"type": "string", "description": "会话标识，默认 default"}
                    },
                    "required": ["msg"]
                }
            },
            {
                "name": "neurocortex_stats",
                "description": "查看 NeuroCortex 经验统计：擅长/困难领域、按意图分布",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "neurocortex_experiences",
                "description": "列出所有已积累的经验记录",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "neurocortex_clear",
                "description": "清空经验库",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "neurocortex_health",
                "description": "检查 NeuroCortex 服务状态",
                "inputSchema": {"type": "object", "properties": {}}
            },
        ]
        send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}})

    elif method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {})

        if name == "neurocortex_chat":
            msg_text = args.get("msg", "")
            session = args.get("session", "default")
            if not msg_text:
                send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "msg is required"}})
                return
            event = cortex.process(msg_text)
            retrieved = retriever.retrieve(msg_text)
            stats = get_stats()
            resp = build_response(event, retrieved)
            content = [{"type": "text", "text": resp}]
            send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": content,
                    "isError": False,
                    "_meta": {
                        "intent": event.perception.intent,
                        "probability": round(event.prediction.success_probability, 2),
                        "action": event.decision.selected_action,
                        "success": event.outcome.success,
                        "experience_count": store.count(),
                        "event_summary": event.summary(),
                    }
                }
            })

        elif name == "neurocortex_stats":
            s = get_stats()
            lines = [f"总经验: {s['total']} 条\n"]
            if s.get('strong'):
                lines.append(f"擅长: {', '.join(s['strong'])}\n")
            if s.get('weak'):
                lines.append(f"困难: {', '.join(s['weak'])}\n")
            if not s.get('strong') and not s.get('weak') and s['total'] > 0:
                lines.append("暂无足够数据\n")
            by_intent = s.get('by_intent', {})
            if by_intent:
                lines.append("\n按类型分布:\n")
                for intent, items in sorted(by_intent.items()):
                    succ = sum(1 for e in items if e['success'])
                    tot = len(items)
                    lines.append(f"  {intent}: {tot}次 (成功{succ})\n")
            send({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "".join(lines)}], "isError": False}})

        elif name == "neurocortex_experiences":
            exps = store.list_all()
            if not exps:
                send({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "暂无经验"}], "isError": False}})
                return
            lines = [f"\n共 {len(exps)} 条经验:\n\n"]
            for i, e in enumerate(exps, 1):
                status = "✓" if e['success'] else "✗"
                lines.append(f"  {i}. [{status}] '{e['raw_input'][:40]}' intent={e['intent']} p={e['predicted_prob']:.2f}\n")
            send({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "".join(lines)}], "isError": False}})

        elif name == "neurocortex_clear":
            if os.path.exists(STORE_PATH):
                os.remove(STORE_PATH)
                send({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "经验库已清空"}], "isError": False}})
            else:
                send({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "经验库已为空"}], "isError": False}})

        elif name == "neurocortex_health":
            send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"NeuroCortex 运行中 | 经验库: {store.count()} 条 | 存储: {STORE_PATH}"}],
                    "isError": False
                }
            })

        else:
            send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {name}"}})

    else:
        send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}})


def main():
    # Read JSON-RPC messages from stdin (one per line)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            handle_request(msg)
        except json.JSONDecodeError as e:
            send({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}})


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    main()
