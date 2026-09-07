"""Experience Prediction Module — adjusts prediction using retrieved experiences and patterns."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..event import CortexEvent, PredictionData
from ..interfaces import PredictionModule
from ..memory.experience_retriever import ExperienceRetriever

if TYPE_CHECKING:
    from ..pattern.retriever import PatternRetriever


class ExperiencePredictionModule(PredictionModule):
    """
    Adjusts prediction based on retrieved past experiences and patterns.

    The adjustment is limited and deterministic:
    - Base prediction from BasicPrediction
    - Then blend with experience signal (30% weight) if relevant experiences found
    - Then blend with pattern signal (15% weight) if relevant patterns found
    - Never override base prediction completely
    - Pattern signal is subservient to experience signal
    """

    def __init__(self, retriever: ExperienceRetriever, base_prediction=None):
        self._retriever = retriever
        self._base_prediction = base_prediction
        # Weight for experience influence (0.0 = no influence, 1.0 = full influence)
        self._experience_weight = 0.3
        # Weight for pattern influence (bounded below experience weight)
        self._pattern_weight = 0.15
        # Optional pattern retriever (set for Phase 12+)
        self._pattern_retriever: PatternRetriever | None = None

    def process(self, event: CortexEvent) -> CortexEvent:
        """Predict with experience + pattern adjustment."""
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

        # Apply experience adjustment if relevant experiences found
        if experiences:
            adjusted = self._adjust_with_experience(adjusted, experiences)

        # Apply pattern adjustment if pattern retriever is configured
        if self._pattern_retriever:
            pattern_results = self._pattern_retriever.retrieve(
                intent=event.perception.intent,
                action_type=event.decision.selected_action if hasattr(event, 'decision') and event.decision.selected_action else "",
            )
            if pattern_results:
                adjusted = self._adjust_with_pattern(adjusted, pattern_results)

        event.predict(adjusted)
        return event

    def _adjust_with_experience(
        self,
        base: PredictionData,
        experiences: list[tuple],
    ) -> PredictionData:
        """Adjust prediction using experience signal."""
        if not experiences:
            return base

        # Analyze experiences
        success_count = 0
        failure_count = 0

        for exp, score in experiences:
            if exp.success:
                success_count += 1
            else:
                failure_count += 1

        total = success_count + failure_count
        if total == 0:
            return base

        # Experience-based probability
        experience_prob = success_count / total if total > 0 else 0.5

        # Blend: (1 - exp_weight - pat_weight) base + exp_weight experience
        adjusted_prob = (1 - self._experience_weight - self._pattern_weight) * base.success_probability + \
                       self._experience_weight * experience_prob

        # Clamp to valid range
        adjusted_prob = max(0.0, min(1.0, adjusted_prob))

        return PredictionData(
            predicted_outcome=base.predicted_outcome,
            success_probability=adjusted_prob,
            predicted_risk=base.predicted_risk,
            prediction_confidence=base.prediction_confidence,
        )

    def _adjust_with_pattern(
        self,
        base: PredictionData,
        patterns: list[tuple],
    ) -> PredictionData:
        """Adjust prediction using pattern signal (bounded, subservient to experience)."""
        if not patterns:
            return base

        # Weighted average of pattern success rates (weighted by confidence)
        total_weight = 0.0
        weighted_prob = 0.0

        for pat, score in patterns:
            if not pat.is_active():
                continue
            weight = pat.confidence
            weighted_prob += pat.success_rate * weight
            total_weight += weight

        if total_weight == 0:
            return base

        pattern_prob = weighted_prob / total_weight

        # Blend with current adjusted probability
        # Pattern weight is bounded: never more than half the experience weight
        effective_pattern_weight = min(self._pattern_weight, self._experience_weight / 2)
        adjusted_prob = (1 - effective_pattern_weight) * base.success_probability + \
                       effective_pattern_weight * pattern_prob

        adjusted_prob = max(0.0, min(1.0, adjusted_prob))

        return PredictionData(
            predicted_outcome=base.predicted_outcome,
            success_probability=adjusted_prob,
            predicted_risk=base.predicted_risk,
            prediction_confidence=base.prediction_confidence,
        )

    @property
    def retriever(self) -> ExperienceRetriever:
        return self._retriever

    @property
    def experience_weight(self) -> float:
        return self._experience_weight

    @experience_weight.setter
    def experience_weight(self, weight: float) -> None:
        self._experience_weight = max(0.0, min(1.0, weight))

    @property
    def pattern_weight(self) -> float:
        return self._pattern_weight

    @pattern_weight.setter
    def pattern_weight(self, weight: float) -> None:
        self._pattern_weight = max(0.0, min(1.0, weight))

    def set_pattern_retriever(self, retriever: PatternRetriever) -> None:
        """Inject a PatternRetriever for Phase 12+ pattern-aware prediction."""
        self._pattern_retriever = retriever
