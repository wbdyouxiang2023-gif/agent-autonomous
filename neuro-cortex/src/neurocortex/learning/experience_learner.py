"""Experience Learning Module — captures experiences from completed events."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..event import CortexEvent, Experience, LearningData
from ..interfaces import LearningModule
from ..memory.experience_store import ExperienceStore

if TYPE_CHECKING:
    pass


class ExperienceLearningModule(LearningModule):
    """
    Captures structured experiences from completed CortexEvents.

    Only captures events that have reached LEARNING stage with valid
    prediction, outcome, and feedback data.
    """

    def __init__(self, store: ExperienceStore):
        self._store = store

    def process(self, event: CortexEvent) -> CortexEvent:
        """Capture experience from completed event if valid."""
        # Capture experience from event at FEEDBACK stage
        if event.stage == "FEEDBACK" and self._is_valid_for_experience(event):
            experience = Experience.from_event(event)
            self._store.save(experience)

        # Record learning signal and advance to LEARNING
        signal = "positive" if event.feedback.reward > 0 else "negative"
        event.learn(LearningData(
            learning_signal=signal,
            memory_updates=[],
            state_updates={},
            policy_updates=[],
            prediction_updates={},
        ))

        return event

    def _is_valid_for_experience(self, event: CortexEvent) -> bool:
        """Check if event has enough data to create a meaningful experience."""
        # Must have prediction
        if not event.prediction.predicted_outcome:
            return False

        # Must have outcome (even if failure)
        if not event.outcome.actual_outcome and not event.outcome.success:
            # Empty outcome is not useful
            if not event.outcome.error_message:
                return False

        # Must have feedback (to know prediction error)
        # Note: feedback may be empty string for invalid states
        # We still capture even if evaluation is empty

        return True

    @property
    def store(self) -> ExperienceStore:
        return self._store
