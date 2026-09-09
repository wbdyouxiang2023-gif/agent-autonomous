"""Decision module — deterministic decision based on perception + prediction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..event import CortexEvent, DecisionData
from ..interfaces import DecisionModule

if TYPE_CHECKING:
    from ..event import PerceptionData, PredictionData

# Intent → action mapping (frozen for v1)
INTENT_ACTION_MAP: dict[str, str] = {
    "create": "code_edit",
    "fix": "code_review",
    "learn": "respond",
    "optimize": "tool_call",
    "deploy": "tool_call",
}


class BasicDecision(DecisionModule):
    """
    Phase 7 v1 DecisionModule.

    Deterministic, rule-based decision making.

    Input contract:
      READ:   perception.intent, perception.risk, perception.confidence,
              prediction.predicted_outcome, prediction.success_probability,
              prediction.predicted_risk, prediction.prediction_confidence
      READ-ONLY:  internal state (uncertainty, confidence) — for context only
      FORBIDDEN: feedback, memory, representation, state mutation, action execution

    Rules (first match wins):
      Rule 0: empty input → noop
      Rule 1: no valid prediction → noop
      Rule 2: high risk abstention (risk >= 0.8 AND pred_conf > 0.5) → noop
      Rule 3: low confidence + low probability → noop
      Rule 4: known intent with acceptable risk → map intent to action
      Rule 5: unknown intent → respond
      Rule 6: default fallback → noop
    """

    def process(self, event: CortexEvent) -> CortexEvent:
        intent = event.perception.intent
        risk = event.perception.risk
        perf_conf = event.perception.confidence
        pred = event.prediction

        decision = self._decide(intent, risk, perf_conf, pred, event.raw_input)
        event.decide(decision)
        return event

    def _decide(
        self,
        intent: str,
        risk: float,
        perf_conf: float,
        pred: "PredictionData",
        raw_input: str,
    ) -> DecisionData:
        """Apply deterministic decision rules."""
        # Rule 0: Empty input
        if not raw_input.strip():
            return DecisionData(
                selected_action="noop",
                decision_score=0.0,
                decision_reason="empty input",
                candidates=[{"id": "noop", "score": 0.0}],
            )

        # Rule 1: No valid prediction
        if pred.predicted_outcome == "" or pred.prediction_confidence <= 0:
            return DecisionData(
                selected_action="noop",
                decision_score=0.0,
                decision_reason="no valid prediction",
                candidates=[{"id": "noop", "score": 0.0}],
            )

        p = pred.success_probability
        pred_risk = pred.predicted_risk
        pred_conf = pred.prediction_confidence

        # Rule 2: High risk abstention
        if pred_risk >= 0.8 and pred_conf > 0.5:
            return DecisionData(
                selected_action="noop",
                decision_score=0.3,
                decision_reason=f"high risk abstention (risk={pred_risk:.2f}, conf={pred_conf:.2f})",
                candidates=[
                    {"id": "noop", "score": 0.3},
                    {"id": "respond", "score": 0.2},
                ],
            )

        # Rule 3: Low confidence + low probability
        if pred_conf < 0.3 and p < 0.5:
            return DecisionData(
                selected_action="noop",
                decision_score=pred_conf,
                decision_reason="low confidence and low probability",
                candidates=[
                    {"id": "noop", "score": pred_conf},
                    {"id": "respond", "score": 0.3},
                ],
            )

        # Rule 4: Known intent with acceptable risk
        if intent and intent != "unknown" and pred_risk < 0.8:
            action_type = INTENT_ACTION_MAP.get(intent, "respond")
            score = self._clamp(pred_conf * 0.9 + (1.0 - pred_risk) * 0.1, 0.3, 0.9)
            return DecisionData(
                selected_action=action_type,
                decision_score=score,
                decision_reason=(
                    f"intent={intent}, risk={pred_risk:.2f}, p={p:.2f}"
                ),
                candidates=[
                    {"id": action_type, "score": score},
                    {"id": "noop", "score": 0.2},
                ],
            )

        # Rule 5: Unknown intent
        if intent == "unknown" or intent == "":
            return DecisionData(
                selected_action="respond",
                decision_score=0.5,
                decision_reason="unknown intent",
                candidates=[
                    {"id": "respond", "score": 0.5},
                    {"id": "noop", "score": 0.3},
                ],
            )

        # Rule 6: Default fallback
        return DecisionData(
            selected_action="noop",
            decision_score=0.0,
            decision_reason="default fallback",
            candidates=[{"id": "noop", "score": 0.0}],
        )

    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        """Deterministic clamp to [lo, hi]."""
        return max(lo, min(hi, v))
