"""Mock module implementations for Phase 2 testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..interfaces import (
    PerceptionModule, RepresentationModule, AttentionModule,
    StateModule, MemoryModule, PredictionModule, DecisionModule,
    ActionModule, OutcomeProvider, FeedbackModule, LearningModule,
)
from ..event import (
    PerceptionData, RepresentationData, AttentionData, InternalState,
    MemoryData, PredictionData, DecisionData, ActionData,
    OutcomeData, FeedbackData, LearningData,
)
from ..feedback import BasicFeedback

if TYPE_CHECKING:
    from ..event import CortexEvent


class MockPerception(PerceptionModule):
    """Basic perception: extract intent keyword from raw input."""

    def process(self, event: CortexEvent) -> CortexEvent:
        intent = self._detect_intent(event.raw_input)
        event.perceive(PerceptionData(
            raw_input=event.raw_input,
            intent=intent,
            confidence=0.7,
            entities=[],
        ))
        return event

    @staticmethod
    def _detect_intent(text: str) -> str:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ("create", "build", "make", "write")):
            return "create"
        if any(kw in text_lower for kw in ("fix", "debug", "repair", "solve")):
            return "fix"
        if any(kw in text_lower for kw in ("learn", "understand", "explain")):
            return "learn"
        if any(kw in text_lower for kw in ("optimize", "improve", "refactor")):
            return "optimize"
        if any(kw in text_lower for kw in ("deploy", "run", "start")):
            return "deploy"
        return "general"


class MockRepresentation(RepresentationModule):
    """Basic representation: tokenize and compute simple features."""

    def process(self, event: CortexEvent) -> CortexEvent:
        tokens = event.raw_input.split()
        event.represent(RepresentationData(
            raw_text=event.raw_input,
            features={"token_count": len(tokens), "char_count": len(event.raw_input)},
            embedding=[float(len(tokens)) / 10.0],
        ))
        return event


class MockAttention(AttentionModule):
    """Basic attention: select first token as focus if short input."""

    def process(self, event: CortexEvent) -> CortexEvent:
        tokens = event.raw_input.split()
        selected = tokens[:2] if tokens else []
        scores = {t: 1.0 / (i + 1) for i, t in enumerate(selected)}
        event.attend(AttentionData(
            selected_items=selected,
            attention_scores=scores,
            attention_reason=f"first {len(selected)} tokens of input",
        ))
        return event


class MockState(StateModule):
    """Basic state: set curiosity based on input novelty heuristic."""

    def process(self, event: CortexEvent) -> CortexEvent:
        novelty = min(len(event.raw_input) / 100.0, 1.0)
        event.update_state(InternalState(
            curiosity=0.5 + novelty * 0.3,
            motivation=0.6,
            confidence=0.5,
            uncertainty=1.0 - novelty,
        ))
        return event


class MockMemory(MemoryModule):
    """Basic memory: return empty retrieval (no persistent store in Phase 2)."""

    def process(self, event: CortexEvent) -> CortexEvent:
        event.retrieve_memory(MemoryData(
            retrieved_memories=[],
            memory_scores={},
        ))
        return event


class MockPrediction(PredictionModule):
    """Basic prediction: estimate success based on input length heuristic."""

    def process(self, event: CortexEvent) -> CortexEvent:
        prob = min(max(len(event.raw_input) / 50.0, 0.2), 0.9)
        event.predict(PredictionData(
            predicted_outcome="task completes",
            success_probability=prob,
            predicted_risk=1.0 - prob,
            prediction_confidence=0.5,
        ))
        return event


class MockDecision(DecisionModule):
    """Basic decision: choose action based on perceived intent."""

    def process(self, event: CortexEvent) -> CortexEvent:
        intent = event.perception.intent
        action_map = {
            "create": "code_edit",
            "fix": "code_review",
            "learn": "respond",
            "optimize": "tool_call",
            "deploy": "tool_call",
        }
        action_type = action_map.get(intent, "respond")
        event.decide(DecisionData(
            candidates=[
                {"id": action_type, "score": 0.8},
                {"id": "noop", "score": 0.2},
            ],
            selected_action=action_type,
            decision_score=0.8,
            decision_reason=f"intent={intent} → action={action_type}",
        ))
        return event


class MockAction(ActionModule):
    """Basic action: execute and record action data only. Does NOT produce outcome."""

    def process(self, event: CortexEvent) -> CortexEvent:
        action_type = event.decision.selected_action
        payload = {"text": event.raw_input}
        event.act(ActionData(
            action_type=action_type,
            action_payload=payload,
            status="success",
            planned=True,
            actual=True,
        ))
        return event


class MockOutcomeProvider(OutcomeProvider):
    """Default outcome provider: always reports success."""

    def provide(self, event: CortexEvent) -> CortexEvent:
        event.record_outcome(OutcomeData(
            actual_outcome=f"action '{event.action.action_type}' completed",
            success=True,
        ))
        return event


class FailingOutcomeProvider(OutcomeProvider):
    """Outcome provider that always reports failure."""

    def provide(self, event: CortexEvent) -> CortexEvent:
        event.record_outcome(OutcomeData(
            actual_outcome="outcome failed",
            success=False,
            error_message="simulated failure",
        ))
        return event


class MockFeedback(FeedbackModule):
    """Phase 6 v2.1 feedback: evaluation via BasicFeedback contract.

    Note: reward computation is preserved for backward compatibility
    with existing regression tests. BasicFeedback itself does not modify reward.
    """

    def __init__(self) -> None:
        self._feedback = BasicFeedback()

    def process(self, event: CortexEvent) -> CortexEvent:
        # Run Phase 6 evaluation (does not modify reward)
        event = self._feedback.process(event)
        # Preserve legacy reward computation for backward compatibility
        predicted = event.prediction.success_probability
        actual_success = event.outcome.success
        reward = 1.0 if actual_success else -0.5
        event.feedback = FeedbackData(
            reward=reward,
            prediction_error=event.feedback.prediction_error,
            evaluation=event.feedback.evaluation,
        )
        return event


class MockLearning(LearningModule):
    """Basic learning: record learning signal without modifying parameters."""

    def process(self, event: CortexEvent) -> CortexEvent:
        signal = "positive" if event.feedback.reward > 0 else "negative"
        event.learn(LearningData(
            learning_signal=signal,
            memory_updates=[],
            state_updates={},
            policy_updates=[],
            prediction_updates={},
        ))
        return event


# ---------------------------------------------------------------------------
# Failure modules — each raises a specific exception for error handling tests
# ---------------------------------------------------------------------------


class FailingPerception(MockPerception):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("perception module failed")


class FailingRepresentation(MockRepresentation):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("representation module failed")


class FailingAttention(MockAttention):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("attention module failed")


class FailingState(MockState):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("state module failed")


class FailingMemory(MockMemory):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("memory module failed")


class FailingPrediction(MockPrediction):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("prediction module failed")


class FailingDecision(MockDecision):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("decision module failed")


class FailingAction(MockAction):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("action module failed")


class FailingFeedback(MockFeedback):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("feedback module failed")


class FailingLearning(MockLearning):
    def process(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("learning module failed")


class FailingOutcomeProvider(OutcomeProvider):
    def provide(self, event: CortexEvent) -> CortexEvent:
        raise RuntimeError("outcome provider failed")
