"""Feedback module — Phase 6 evaluation contract (v2.1)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..event import CortexEvent, FeedbackData
from ..interfaces import FeedbackModule

if TYPE_CHECKING:
    from ..event import OutcomeData, PredictionData


class BasicFeedback(FeedbackModule):
    """
    Phase 6 v2.1 FeedbackModule.

    Evaluation priority (first match wins):
      Rule 0: no_prediction          — invalid prediction
      Rule 1: invalid_outcome        — invalid outcome
      Rule 2: execution_error + Q    — execution error with quality diagnostic
      Rule 3: perfect_high_confidence — err==0 AND confidence>0.7
      Rule 4: perfect                — err==0
      Rule 5: correct                — 0 < err < 0.3
      Rule 6: catastrophically_wrong — err>0.8 AND confidence>0.7
      Rule 7: miss                   — default catch-all

    prediction_error is always a finite float in [0.0, 1.0].
    Invalid states use 0.0 as placeholder; semantics carried by evaluation.
    """

    def process(self, event: CortexEvent) -> CortexEvent:
        pred = event.prediction
        out = event.outcome
        existing_reward = event.feedback.reward

        try:
            evaluation, prediction_error = self._evaluate(pred, out)
        except Exception:
            # Safety net: never let feedback computation crash the pipeline
            evaluation = "miss"
            prediction_error = 0.0

        event.compute_feedback(FeedbackData(
            reward=existing_reward,
            prediction_error=prediction_error,
            evaluation=evaluation,
        ))
        return event

    # ── Core evaluation logic ─────────────────────────────────────

    def _evaluate(
        self, pred: "PredictionData", out: "OutcomeData"
    ) -> tuple[str, float]:
        """Return (evaluation, prediction_error)."""
        # Rule 0
        if not self._is_valid_prediction(pred):
            return "no_prediction", 0.0

        # Rule 1
        if not self._is_valid_outcome(out):
            return "invalid_outcome", 0.0

        # Compute target and error
        target = 1.0 if out.success else 0.0
        err = abs(pred.success_probability - target)
        conf = pred.prediction_confidence
        has_exec_error = out.error_message != ""

        # Rule 2: execution_error + quality
        if has_exec_error:
            quality = self._classify_quality(err, conf)
            return f"execution_error + {quality}", err

        # Rules 3-7
        return self._classify_quality(err, conf), err

    # ── Validation ────────────────────────────────────────────────

    @staticmethod
    def _is_valid_prediction(pred: "PredictionData") -> bool:
        if pred.predicted_outcome == "":
            return False
        if pred.prediction_confidence <= 0:
            return False
        p = pred.success_probability
        c = pred.prediction_confidence
        if not (0.0 <= p <= 1.0):
            return False
        if not math.isfinite(p):
            return False
        if not math.isfinite(c):
            return False
        return True

    @staticmethod
    def _is_valid_outcome(out: "OutcomeData") -> bool:
        return out.actual_outcome != "" and out.success is not None

    # ── Quality classification (Rules 3-7) ────────────────────────

    @staticmethod
    def _classify_quality(err: float, confidence: float) -> str:
        if err == 0.0 and confidence > 0.7:
            return "perfect_high_confidence"
        if err == 0.0:
            return "perfect"
        if 0.0 < err < 0.3:
            return "correct"
        if err > 0.8 and confidence > 0.7:
            return "catastrophically_wrong"
        return "miss"

    @staticmethod
    def _safe_abs(a: float, b: float) -> float:
        """abs with NaN/Inf guard."""
        try:
            val = abs(a - b)
            if math.isnan(val) or math.isinf(val):
                return 0.0
            return val
        except (TypeError, ValueError):
            return 0.0
