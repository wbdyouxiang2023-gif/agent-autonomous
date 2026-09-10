"""Experience Prediction Module — adjusts prediction using retrieved experiences.

Pattern.support_score is used as a QUALITY WEIGHT for experience evidence,
NOT as an independent prediction signal. This eliminates double counting
where the same experiences contributed to both experience_prob and pattern_prob.

Evidence flow (Scheme B — Bounded Adjustment):
  empirical_rate(E) × clamp(support_score, 0.5, 1.0) → adjusted_evidence
  prediction = (1-w) × base + w × adjusted_evidence
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..event import CortexEvent, PredictionData
from ..interfaces import PredictionModule
from ..memory.experience_retriever import ExperienceRetriever

if TYPE_CHECKING:
    from ..pattern.retriever import PatternRetriever


class ExperiencePredictionModule(PredictionModule):
    """
    Adjusts prediction based on retrieved past experiences.

    Pattern.support_score acts as a QUALITY WEIGHT for experience evidence,
    NOT as an independent prediction signal. This eliminates double counting.

    Evidence flow (Scheme B — Bounded Adjustment):
      adjusted_evidence = empirical_rate(E) × clamp(support_score, 0.5, 1.0)
      prediction = (1-w) × base + w × adjusted_evidence

    Where:
      w = _evidence_weight (default 0.30, same as Phase 11)
      empirical_rate(E) = success_count(retrieved) / count(retrieved)
      support_score ∈ [0.0, 0.9] from Pattern dataclass

    Key invariants:
      - No Pattern → identity transform (Phase 11 behavior preserved)
      - Pattern can only DAMPEN evidence, never amplify it
      - Safety floor at 0.5 prevents evidence collapse
      - Retired/Weakening patterns have zero influence
    """

    def __init__(self, retriever: ExperienceRetriever, base_prediction=None):
        self._retriever = retriever
        self._base_prediction = base_prediction
        # Total evidence weight (0.0 = no influence, 1.0 = full influence)
        self._evidence_weight = 0.3
        # Safety floor for quality factor (prevents evidence collapse)
        self._quality_floor = 0.5
        # Optional pattern retriever (set for Phase 12+)
        self._pattern_retriever: PatternRetriever | None = None

    def process(self, event: CortexEvent) -> CortexEvent:
        """Predict with experience evidence adjusted by pattern quality."""
        # First get base prediction
        if self._base_prediction:
            event = self._base_prediction.process(event)
        else:
            # Fallback: use default prediction
            from ..prediction import BasicPrediction
            base = BasicPrediction()
            event = base.process(event)

        # Try to retrieve relevant experiences
        experiences = self._retriever.retrieve(
            raw_input=event.raw_input,
            intent=event.perception.intent,
            action_type=event.decision.selected_action if hasattr(event, 'decision') and event.decision.selected_action else "",
        )

        # Start with base prediction
        adjusted = event.prediction

        # Apply evidence adjustment if relevant experiences found
        if experiences:
            adjusted = self._adjust_evidence(adjusted, experiences)

        event.predict(adjusted)
        return event

    def _adjust_evidence(
        self,
        base: PredictionData,
        experiences: list[tuple],
    ) -> PredictionData:
        """
        Adjust evidence using experience signal, modulated by pattern quality.

        Formula:
          empirical_rate = success_count / total
          quality_factor = clamp(avg_support_score, floor, 1.0)
          adjusted = empirical_rate × quality_factor
          prediction = (1-w) × base + w × adjusted
        """
        if not experiences:
            return base

        # Compute empirical rate from retrieved experiences
        success_count = sum(1 for exp, _ in experiences if exp.success)
        total = len(experiences)
        if total == 0:
            return base

        empirical_rate = success_count / total

        # Compute quality factor from patterns (if available)
        quality_factor = self._compute_quality_factor()

        # Apply bounded adjustment
        adjusted_evidence = empirical_rate * quality_factor
        adjusted_prob = (1 - self._evidence_weight) * base.success_probability + \
                       self._evidence_weight * adjusted_evidence

        # Clamp to valid range
        adjusted_prob = max(0.0, min(1.0, adjusted_prob))

        return PredictionData(
            predicted_outcome=base.predicted_outcome,
            success_probability=adjusted_prob,
            predicted_risk=base.predicted_risk,
            prediction_confidence=base.prediction_confidence,
        )

    def _compute_quality_factor(self) -> float:
        """
        Compute evidence quality factor from patterns.

        Returns:
          1.0 if no patterns available (identity — Phase 11 behavior)
          clamp(avg_support_score, floor, 1.0) otherwise
        """
        if not self._pattern_retriever:
            return 1.0

        # Retrieve active patterns
        patterns = self._pattern_retriever.retrieve(
            intent="",  # We'll get all active patterns and filter
        )
        if not patterns:
            return 1.0

        # Average support score across matching patterns
        total_support = sum(pat.support_score for pat, _ in patterns)
        avg_support = total_support / len(patterns)

        # Clamp to [floor, 1.0]
        return max(self._quality_floor, min(1.0, avg_support))

    @property
    def retriever(self) -> ExperienceRetriever:
        return self._retriever

    @property
    def evidence_weight(self) -> float:
        return self._evidence_weight

    @evidence_weight.setter
    def evidence_weight(self, weight: float) -> None:
        self._evidence_weight = max(0.0, min(1.0, weight))

    @property
    def quality_floor(self) -> float:
        return self._quality_floor

    def set_pattern_retriever(self, retriever: PatternRetriever) -> None:
        """Inject a PatternRetriever for pattern-quality-adjusted prediction."""
        self._pattern_retriever = retriever