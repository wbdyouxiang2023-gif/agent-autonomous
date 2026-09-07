"""Prediction module — deterministic prediction based on perception and state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..event import CortexEvent, PredictionData
from ..interfaces import PredictionModule

if TYPE_CHECKING:
    from ..state.cortex_state import CortexState


class BasicPrediction(PredictionModule):
    """
    Deterministic prediction module.

    Prediction v1 = Perception + InternalState

    Does NOT use Representation (hash-based embedding has no semantic value).
    Does NOT compute prediction_error (Phase 6 Feedback).
    Does NOT modify event.state or CortexState.

    Rule priority: risk > uncertainty > intent
    """

    def __init__(self, state_store: "CortexState | None" = None) -> None:
        self._state_store = state_store

    def process(self, event: CortexEvent) -> CortexEvent:
        """Predict outcome based on perception and state."""
        intent = event.perception.intent
        risk = event.perception.risk
        unc = event.state.uncertainty
        perf_conf = event.perception.confidence

        prediction = self._predict(intent, risk, unc, perf_conf, event.raw_input)
        event.predict(prediction)
        return event

    def _predict(
        self,
        intent: str,
        risk: float,
        unc: float,
        perf_conf: float,
        raw_input: str,
    ) -> PredictionData:
        """Apply deterministic prediction rules."""
        # Rule 0: Empty input
        if not raw_input.strip():
            return PredictionData(
                predicted_outcome="",
                success_probability=0.5,
                predicted_risk=0.0,
                prediction_confidence=0.0,
            )

        # Rule 1: High Risk (priority: risk > uncertainty > intent)
        if risk >= 0.6:
            return self._high_risk_prediction(intent, risk, perf_conf)

        # Rule 2: High Uncertainty (only if risk < 0.6)
        if unc >= 0.6:
            return self._high_uncertainty_prediction(intent, risk, perf_conf)

        # Rule 3: Clear Signal (known intent, low risk, low uncertainty)
        if intent and intent != "unknown" and risk < 0.4 and unc < 0.4:
            return self._clear_signal_prediction(intent, risk, perf_conf)

        # Rule 4: Unknown (unknown intent, low risk, low uncertainty)
        return self._unknown_prediction(intent, risk, perf_conf)

    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        """Deterministic clamp to [lo, hi]."""
        return max(lo, min(hi, v))

    def _high_risk_prediction(
        self, intent: str, risk: float, perf_conf: float
    ) -> PredictionData:
        """
        High risk dominates.
        Priority: risk > uncertainty > intent
        
        Known intent with high risk must preserve intent information.
        Unknown intent with high risk gets generic high-risk outcome.
        """
        if intent and intent != "unknown":
            # Known intent with high risk - preserve intent
            return PredictionData(
                predicted_outcome=f"{intent}可能存在风险",
                success_probability=self._clamp(0.4 + (1.0 - risk) * 0.2, 0.4, 0.6),
                predicted_risk=self._clamp(risk, 0.0, 1.0),
                prediction_confidence=self._clamp(perf_conf * 0.7, 0.0, 1.0),
            )
        else:
            # Unknown intent with high risk
            return PredictionData(
                predicted_outcome="高风险未知任务",
                success_probability=0.3,
                predicted_risk=self._clamp(risk, 0.0, 1.0),
                prediction_confidence=0.2,
            )

    def _high_uncertainty_prediction(
        self, intent: str, risk: float, perf_conf: float
    ) -> PredictionData:
        """High uncertainty, but risk < 0.6."""
        if intent and intent != "unknown":
            return PredictionData(
                predicted_outcome="不确定性高",
                success_probability=0.5,
                predicted_risk=self._clamp(risk, 0.0, 1.0),
                prediction_confidence=self._clamp(perf_conf * 0.5, 0.0, 0.4),
            )
        else:
            return PredictionData(
                predicted_outcome="信息不足",
                success_probability=0.3,
                predicted_risk=self._clamp(risk, 0.0, 1.0),
                prediction_confidence=0.2,
            )

    def _clear_signal_prediction(
        self, intent: str, risk: float, perf_conf: float
    ) -> PredictionData:
        """Clear signal: known intent, low risk, low uncertainty."""
        return PredictionData(
            predicted_outcome=f"{intent}完成",
            success_probability=self._clamp(perf_conf + 0.1, 0.0, 0.9),
            predicted_risk=self._clamp(risk, 0.0, 1.0),
            prediction_confidence=self._clamp(perf_conf * 0.8, 0.0, 1.0),
        )

    def _unknown_prediction(
        self, intent: str, risk: float, perf_conf: float
    ) -> PredictionData:
        """Unknown intent, low risk, low uncertainty."""
        return PredictionData(
            predicted_outcome="无法判断任务",
            success_probability=0.5,
            predicted_risk=self._clamp(risk, 0.0, 1.0),
            prediction_confidence=0.2,
        )
