"""Module interfaces (Protocols) for NeuroCortex stages."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event import CortexEvent


class PerceptionModule(ABC):
    """Transform raw input into structured perception data."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class RepresentationModule(ABC):
    """Convert perception into machine-processable representation."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class AttentionModule(ABC):
    """Select which aspects of the representation deserve focus."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class StateModule(ABC):
    """Update dynamic internal state based on current event."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class MemoryModule(ABC):
    """Retrieve relevant past experiences for the current context."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class PredictionModule(ABC):
    """Predict likely outcomes given current state and memories."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class DecisionModule(ABC):
    """Select an action from available candidates."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class ActionModule(ABC):
    """Execute the selected action. Records action data but NOT the outcome."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class OutcomeProvider(ABC):
    """Provide the real/simulated outcome after an action has executed.

    Outcome is a factual observation of what the world produced — distinct from
    the Action's execution status. An action can succeed while the outcome fails
    (e.g. code edits applied but tests still fail).
    """

    @abstractmethod
    def provide(self, event: CortexEvent) -> CortexEvent:
        ...


class FeedbackModule(ABC):
    """Compute evaluation signal by comparing prediction vs outcome."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...


class LearningModule(ABC):
    """Adapt system parameters based on feedback signal."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...
