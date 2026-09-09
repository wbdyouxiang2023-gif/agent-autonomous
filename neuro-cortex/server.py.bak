#!/usr/bin/env python3
"""NeuroCortex — 持续学习的对话服务

启动后自动监听，每次对话都会积累和更新经验。
经验持久化到 ~/.neurocortex_memory.jsonl

用法:
  python3 neuro-cortex/server.py
  # 然后在另一个终端:
  echo '{"msg": "帮我看一下代码"}' | nc localhost 9100
  # 或:
  curl -X POST http://localhost:9100/chat -d '{"msg":"hello"}'
"""
import sys, os, json, hashlib
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
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

# ── Action Learning (Level 3.5-C) — OFF by default ────────────────────
# NEUROCORTEX_ACTION_LEARNING=false → bridge is a no-op passthrough.
from neurocortex.action_learning import ActionLearningBridge
ACTION_LEARNING_ENABLED = os.environ.get("NEUROCORTEX_ACTION_LEARNING", "false").strip().lower() in ("1", "true", "yes", "on")
ACTION_LEARNING_SHADOW = os.environ.get("ACTION_LEARNING_SHADOW_ONLY", "true").strip().lower() in ("1", "true", "yes", "on")
action_bridge = ActionLearningBridge()

PORT = 9100
STORE_PATH = os.path.expanduser("~/.neurocortex_memory.jsonl")


class BilingualPerception(MockPerception):
    def _detect_intent(self, text):
        t = text.lower()
        if any(k in t for k in ("what", "how", "explain", "介绍", "解释", "说明", "是什么", "为什么", "了解", "知道")):
            return "explain"
        if any(k in t for k in ("do", "make", "build", "create", "write", "帮我", "做", "写", "建", "创建", "生成", "实现", "开发")):
            return "create"
        if any(k in t for k in ("fix", "debug", "bug", "错误", "问题", "故障", "修", "调", "解决", "修复")):
            return "fix"
        if any(k in t for k in ("analyze", "check", "review", "look", "看", "检查", "分析", "审查", "看看")):
            return "review"
        if any(k in t for k in ("deploy", "run", "start", "部署", "运行", "启动", "上线", "发布")):
            return "deploy"
        if any(k in t for k in ("optimize", "improve", "fast", "快", "优化", "加速", "性能", "提升")):
            return "optimize"
        if any(k in t for k in ("test", "测试", "用例", "验证")):
            return "test"
        return "general"


class PersistentOutcome(OutcomeProvider):
    """根据历史模式自适应决定结果"""
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


def get_stats(store):
    exps = store.list_all()
    if not exps:
        return {"total": 0, "strong": [], "weak": []}
    by_intent = {}
    for e in exps:
        by_intent.setdefault(e.intent, []).append(e.to_dict())
    strong = []
    weak = []
    for intent, items in sorted(by_intent.items()):
        rate = sum(1 for e in items if e["success"]) / len(items)
        fails = sum(1 for e in items if not e["success"])
        if rate >= 0.8:
            strong.append(f"{intent}({rate:.0%})")
        if fails > 0:
            weak.append(f"{intent}({fails}次)")
    return {"total": len(exps), "strong": strong, "weak": weak, "by_intent": by_intent}


# 初始化
print(f"Loading NeuroCortex, experience store: {STORE_PATH}")
store = ExperienceStore(STORE_PATH)
learner = ExperienceLearningModule(store)
retriever = ExperienceRetriever(store, top_k=3)
exp_pred = ExperiencePredictionModule(retriever, base_prediction=BasicPrediction())
cortex = NeuroCortex(
    perception=BilingualPerception(), representation=MockRepresentation(),
    attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
    prediction=exp_pred, decision=MockDecision(), action=MockAction(),
    outcome_provider=PersistentOutcome(store),
    feedback=MockFeedback(), learning=learner,
)

# ── Action Learning hook (Level 3.5-C) — no-op unless enabled ─────────
_original_process = cortex.process

def _process_with_action_learning(raw_input):
    event = _original_process(raw_input)
    if ACTION_LEARNING_ENABLED:
        action_bridge.record_event_outcome(event)
    return event

cortex.process = _process_with_action_learning

print(f"Action Learning: {'ENABLED' if ACTION_LEARNING_ENABLED else 'OFF'} (shadow={ACTION_LEARNING_SHADOW})")
print(f"Loaded {store.count()} experiences. Ready on port {PORT}.")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence logs

    def do_GET(self):
        if self.path == "/stats":
            stats = get_stats(store)
            self._json(stats)
        elif self.path == "/experiences":
            exps = store.list_all()
            self._json([e.to_dict() for e in exps])
        elif self.path == "/health":
            self._json({"status": "ok", "experiences": store.count()})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/chat":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            msg = body.get("msg", "").strip()
            if not msg:
                self._json({"error": "empty message"}, 400)
                return
            event = cortex.process(msg)
            retrieved = retriever.retrieve(msg)
            stats = get_stats(store)
            resp = {
                "input": msg,
                "intent": event.perception.intent,
                "prediction": event.prediction.predicted_outcome,
                "probability": event.prediction.success_probability,
                "action": event.decision.selected_action,
                "success": event.outcome.success,
                "evaluation": event.feedback.evaluation,
                "response": build_response(event, retrieved),
                "experience_count": store.count(),
                "retrieved": len(retrieved),
                "stats": stats,
            }
            self._json(resp)
        else:
            self._json({"error": "not found"}, 404)

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"NeuroCortex running on http://localhost:{PORT}")
    print(f"  POST /chat   - 发送消息")
    print(f"  GET  /stats  - 查看统计")
    print(f"  GET  /health - 健康检查")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutdown.")
        server.shutdown()
