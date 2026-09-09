"""Experience Prediction Module — adjusts prediction using retrieved experiences."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..event import CortexEvent, PredictionData
from ..interfaces import PredictionModule
from ..memory.experience_retriever import ExperienceRetriever

if TYPE_CHECKING:
    pass


class ExperiencePredictionModule(PredictionModule):
    """
    Adjusts prediction based on retrieved past experiences.

    The adjustment is limited and deterministic:
    - Base prediction from BasicPrediction
    - Then blend with experience signal if relevant experiences found
    - Never override base prediction completely
    """

    def __init__(self, retriever: ExperienceRetriever, base_prediction=None):
        self._retriever = retriever
        self._base_prediction = base_prediction
        # Weight for experience influence (0.0 = no influence, 1.0 = full influence)
        self._experience_weight = 0.3

    def process(self, event: CortexEvent) -> CortexEvent:
        """Predict with experience adjustment."""
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

        if not experiences:
            # No relevant experiences, return base prediction
            return event

        # Calculate experience-influenced prediction
        adjusted = self._adjust_prediction(event.prediction, experiences)
        event.predict(adjusted)
        return event

    def _adjust_prediction(
        self,
        base: PredictionData,
        experiences: list[tuple],
    ) -> PredictionData:
        """
        Adjust prediction based on experience signal.

        Rules:
        1. Count successes vs failures in relevant experiences
        2. Blend with base probability using _experience_weight
        3. Clamp to valid range
        4. Keep same predicted_outcome pattern but adjust confidence
        """
        if not experiences:
            return base

        # Analyze experiences
        success_count = 0
        failure_count = 0
        total_weight = 0.0

        for exp, score in experiences:
            if exp.success:
                success_count += 1
            else:
                failure_count += 1
            total_weight += score

        total = success_count + failure_count
        if total == 0:
            return base

        # Experience-based probability
        experience_prob = success_count / total if total > 0 else 0.5

        # Blend: 70% base, 30% experience
        adjusted_prob = (1 - self._experience_weight) * base.success_probability + \
                       self._experience_weight * experience_prob

        # Clamp to valid range
        adjusted_prob = max(0.0, min(1.0, adjusted_prob))

        # Create adjusted prediction
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
