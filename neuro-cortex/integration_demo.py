#!/usr/bin/env python3
"""
NeuroCortex 对话集成示例

展示如何将 NeuroCortex 接入实际对话/任务系统。

使用方式:
  python3 neuro-cortex/integration_demo.py
"""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from neurocortex.cortex import NeuroCortex
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention,
    MockState, MockMemory, MockDecision, MockAction, MockFeedback
)
from neurocortex.state import BasicStateModule
from neurocortex.prediction import BasicPrediction
from neurocortex.learning.experience_learner import ExperienceLearningModule
from neurocortex.memory.experience_store import ExperienceStore
from neurocortex.memory.experience_retriever import ExperienceRetriever
from neurocortex.prediction.experience_prediction import ExperiencePredictionModule
from neurocortex.interfaces import OutcomeProvider
from neurocortex.event import OutcomeData


# ── 1. 自定义感知模块（支持中英混合意图识别）────────────────────────
class BilingualPerception(MockPerception):
    """扩展 MockPerception，增加中文关键词支持"""
    def _detect_intent(self, text):
        t = text.lower()
        if any(k in t for k in ("bug", "fix", "修复", "查", "debug", "修理", "看下", "看看", "检查")):
            return "fix"
        if any(k in t for k in ("write", "create", "build", "make", "写", "创建", "开发", "实现", "生成")):
            return "create"
        if any(k in t for k in ("deploy", "部署", "上线", "发布", "run", "跑")):
            return "deploy"
        if any(k in t for k in ("optimize", "improve", "refactor", "优化", "重构", "加速", "性能")):
            return "optimize"
        if any(k in t for k in ("test", "测试", "用例")):
            return "test"
        if any(k in t for k in ("review", "check", "校", "审核")):
            return "review"
        return "general"


# ── 2. 自定义结果提供者（模拟真实任务结果）──────────────────────────
class AdaptiveOutcome(OutcomeProvider):
    """
    根据历史经验自适应决定任务结果。
    
    规则:
    - 首次遇到某类任务: 默认成功
    - 连续成功后: 降低成功率（模拟疲劳/复杂情况）
    - 失败后 retry: 提高成功率（积累经验后）
    """
    def __init__(self, store):
        self._store = store

    def provide(self, event):
        intent = event.perception.intent
        exps = self._store.list_all()
        recent = [e for e in exps if e.intent == intent]

        if len(recent) >= 2:
            last = recent[-1]
            if not last.success:
                success = True           # 失败后 retry 成功
            elif last.success_probability > 0.9:
                h = int(hashlib.md5((event.raw_input + "fatigue").encode()).hexdigest(), 16)
                success = h % 5 != 0     # 80% 成功率
            else:
                success = True
        else:
            success = True

        event.record_outcome(OutcomeData(
            actual_outcome=f"{intent}完成",
            success=success,
        ))
        return event


# ── 3. 构建有经验的 Cortex ──────────────────────────────────────────
def build_cortex(store_path=None):
    """
    创建 NeuroCortex 实例。
    
    Args:
        store_path: 经验存储文件路径（None 表示不持久化）
    
    Returns:
        (cortex, store, retriever) 三元组
    """
    store = ExperienceStore(store_path)
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
        outcome_provider=AdaptiveOutcome(store),
        feedback=MockFeedback(),
        learning=learner,
    )
    return cortex, store, retriever


# ── 4. 构建自然语言回应 ──────────────────────────────────────────────
INTENT_LABEL = {
    "fix": "修复", "create": "创建", "deploy": "部署",
    "optimize": "优化", "test": "测试", "review": "审核", "general": "处理",
}


def build_response(event, retrieved, store):
    """根据事件数据和经验库生成自然语言回应"""
    intent_cn = INTENT_LABEL.get(event.perception.intent, event.perception.intent)
    n_match = len(retrieved)

    if n_match == 0:
        return f"收到，我来{intent_cn}。"
    elif event.prediction.success_probability >= 0.85:
        top_exp = retrieved[0][0]
        if top_exp.success:
            return f"这类{intent_cn}任务处理过多次，没问题。"
        else:
            return f"之前同类{intent_cn}有过困难，这次会格外小心。"
    elif event.prediction.success_probability < 0.5:
        return f"这个{intent_cn}任务有风险，我需要更多信息。"
    else:
        return f"好的，开始{intent_cn}。"


# ── 5. 主流程 ────────────────────────────────────────────────────────
def main():
    # 可以选择指定持久化路径
    store_path = os.path.join(os.path.dirname(__file__), "..", ".data", "experiences.jsonl")
    os.makedirs(os.path.dirname(store_path), exist_ok=True)

    cortex, store, retriever = build_cortex(store_path)

    print("=" * 70)
    print("  NeuroCortex 对话集成 Demo")
    print(f"  经验存储: {store_path}")
    print("=" * 70)

    # 模拟对话
    dialogue = [
        ("帮我看一下这段代码有没有 bug",      "fix"),
        ("帮我写一个用户登录 API",             "create"),
        ("把这个部署到生产环境",               "deploy"),
        ("再帮我检查一下另一个文件",           "fix"),
        ("有个 bug 在支付模块，帮我修一下",   "fix"),
        ("帮我写测试用例",                     "test"),
        ("优化一下数据库查询性能",             "optimize"),
    ]

    for text, expected_intent in dialogue:
        event = cortex.process(text)
        retrieved = retriever.retrieve(text)
        reply = build_response(event, retrieved, store)

        status_icon = "✓" if event.outcome.success else "✗"
        print(f"\n  用户: 「{text}」")
        print(f"  AI:   {reply}")
        print(f"        [intent={event.perception.intent} pred={event.prediction.predicted_outcome}(p={event.prediction.success_probability:.2f}) "
              f"action={event.decision.selected_action}] → {status_icon}{'成功' if event.outcome.success else '失败'}")
        print(f"        经验库: {store.count()}条 | 检索匹配: {len(retrieved)}条")

    # 统计
    print(f"\n{'─' * 70}")
    successes = sum(1 for e in store.list_all() if e.success)
    failures = store.count() - successes
    print(f"  对话结束 — 经验库: {store.count()}条 (成功{successes}, 失败{failures})")
    print(f"  下次对话时，系统会自动检索相关经验来调整预测和行为")
    print("=" * 70)


if __name__ == "__main__":
    main()
