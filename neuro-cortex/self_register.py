#!/usr/bin/env python3
"""
NeuroCortex 自我注册 — 持久化经验系统

用法:
  python3 neuro-cortex/self_register.py "用户消息"
  
  每次运行都会：
  1. 从 ~/.neurocortex_self.jsonl 加载历史经验
  2. 处理新输入，生成回应
  3. 将本次经验追加到文件
  4. 输出自我认知报告
"""
import sys, os, json, hashlib, textwrap
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

STORE = os.path.expanduser("~/.neurocortex_self.jsonl")


class BilingualPerception(MockPerception):
    def _detect_intent(self, text):
        t = text.lower()
        if any(k in t for k in ("what", "how", "explain", "介绍", "解释", "说明", "是什么", "为什么")):
            return "explain"
        if any(k in t for k in ("do", "make", "build", "create", "write", "帮我", "做", "写", "建", "创建", "生成", "实现")):
            return "create"
        if any(k in t for k in ("fix", "debug", "bug", "错误", "问题", "故障", "修", "调")):
            return "fix"
        if any(k in t for k in ("analyze", "check", "review", "look", "看", "检查", "分析", "审查")):
            return "review"
        if any(k in t for k in ("deploy", "run", "start", "部署", "运行", "启动")):
            return "deploy"
        if any(k in t for k in ("optimize", "improve", "fast", "快", "优化", "加速", "性能")):
            return "optimize"
        if any(k in t for k in ("test", "测试", "用例")):
            return "test"
        return "general"


class SelfOutcome(OutcomeProvider):
    """模拟 AI 助手处理任务的真实结果"""
    def __init__(self, store):
        self._store = store
    def provide(self, event):
        intent = event.perception.intent
        text = event.raw_input.lower()
        recent = [e for e in self._store.list_all() if e.intent == intent]
        
        # 解释类：总是成功
        if intent == "explain":
            success = True
        # 修复类：连续失败后 retry 容易成功
        elif intent == "fix" and recent and not recent[-1].success:
            success = True
        # 创建类：频繁后降低成功率
        elif intent == "create" and len(recent) >= 3:
            h = int(hashlib.md5(text.encode()).hexdigest(), 16)
            success = h % 4 != 0
        # 审查类：基本成功
        elif intent == "review":
            success = True
        # 默认：80% 成功
        else:
            h = int(hashlib.md5(text.encode()).hexdigest(), 16)
            success = h % 5 != 0
        
        event.record_outcome(OutcomeData(actual_outcome="done", success=success))
        return event


def build_response(event, retrieved):
    """根据经验和预测生成自然语言回应"""
    n = len(retrieved)
    p = event.prediction.success_probability
    intent_cn = {"explain":"解释","create":"创建","fix":"修复","review":"审查",
                 "deploy":"部署","optimize":"优化","test":"测试","general":"处理"}
    intent_label = intent_cn.get(event.perception.intent, event.perception.intent)
    
    lines = []
    if n == 0:
        lines.append(f"收到，我来{intent_label}。")
    elif p >= 0.85:
        top = retrieved[0][0]
        if top.success:
            lines.append(f"这类{intent_label}任务处理过多次，没问题。")
        else:
            lines.append(f"之前同类{intent_label}有过困难，这次会格外小心。")
    elif p < 0.5:
        lines.append(f"这个{intent_label}任务有风险，我需要更多信息。")
    else:
        lines.append(f"好的，开始{intent_label}。")
    return "\n".join(lines)


def get_self_report(store):
    """生成自我认知报告"""
    exps = store.list_all()
    if not exps:
        return "尚无经验记录，继续对话积累。"
    
    by_intent = {}
    for e in exps:
        by_intent.setdefault(e.intent, []).append(e)
    
    lines = []
    lines.append(f"自我认知报告 ({len(exps)}条经验):")
    
    # 擅长领域
    strong = []
    weak = []
    for intent, items in sorted(by_intent.items()):
        rate = sum(1 for e in items if e.success) / len(items)
        fails = sum(1 for e in items if not e.success)
        if rate >= 0.8:
            strong.append(f"{intent}({rate:.0%})")
        if fails > 0:
            weak.append(f"{intent}({fails}次失败)")
    
    if strong:
        lines.append(f"  擅长的: {', '.join(strong)}")
    if weak:
        lines.append(f"  需改进: {', '.join(weak)}")
    else:
        lines.append(f"  暂无明显弱点，继续积累经验中")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 self_register.py \"用户消息\"")
        print("示例: python3 self_register.py \"帮我看一下代码\"")
        sys.exit(1)
    
    user_input = " ".join(sys.argv[1:])
    
    # 初始化（从文件加载历史）
    store = ExperienceStore(STORE)
    learner = ExperienceLearningModule(store)
    retriever = ExperienceRetriever(store, top_k=3)
    exp_pred = ExperiencePredictionModule(retriever, base_prediction=BasicPrediction())
    
    cortex = NeuroCortex(
        perception=BilingualPerception(), representation=MockRepresentation(),
        attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
        prediction=exp_pred, decision=MockDecision(), action=MockAction(),
        outcome_provider=SelfOutcome(store),
        feedback=MockFeedback(), learning=learner,
    )
    
    # 处理
    event = cortex.process(user_input)
    retrieved = retriever.retrieve(user_input)
    
    # 输出
    status = "✓" if event.outcome.success else "✗"
    n = len(retrieved)
    
    print(f"\n{'─' * 60}")
    print(f"  输入: {user_input}")
    print(f"  意图: {event.perception.intent}")
    print(f"  预测: {event.prediction.predicted_outcome} (p={event.prediction.success_probability:.2f})")
    print(f"  行动: {event.decision.selected_action}")
    print(f"  结果: {status}{'成功' if event.outcome.success else '失败'}")
    print(f"  匹配经验: {n}条 | 经验库总计: {store.count()}条")
    
    # 回应
    reply = build_response(event, retrieved)
    print(f"\n  回应: {reply}")
    
    # 自我认知（每5条经验输出一次）
    if store.count() % 5 == 0 or store.count() <= 2:
        report = get_self_report(store)
        print(f"\n{report}")
    
    print(f"{'─' * 60}\n")


if __name__ == "__main__":
    main()
