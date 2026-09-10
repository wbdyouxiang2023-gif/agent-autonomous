"""NeuroCortex — orchestration layer for the cognitive lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from .event import CortexEvent
from .state.cortex_state import CortexState

if TYPE_CHECKING:
    from .interfaces import (
        PerceptionModule, RepresentationModule, AttentionModule,
        StateModule, MemoryModule, PredictionModule, DecisionModule,
        ActionModule, OutcomeProvider, FeedbackModule, LearningModule,
    )

T = TypeVar("T", bound="CortexEvent")


class NeuroCortex:
    """
    Orchestration layer that connects modules into a complete cognitive lifecycle.

    Each stage is implemented by an injectable module. The core only manages:
    - Module invocation order
    - Error handling and diagnosis
    - Event lifecycle progression

    Modules communicate exclusively through CortexEvent — no direct cross-module calls.
    """

    # Ordered list of (stage_name, method_name) for _run_stages.
    # ACTION module handles ACT only — does NOT produce outcome.
    # OUTCOME is provided by a separate injected OutcomeProvider.
    # FEEDBACK module handles compute_feedback separately.
    _STAGES = (
        ("PERCEPTION",   "perceive"),
        ("REPRESENTATION", "represent"),
        ("ATTENTION",    "attend"),
        ("STATE",        "update_state"),
        ("MEMORY",       "retrieve_memory"),
        ("PREDICTION",   "predict"),
        ("DECISION",     "decide"),
        ("ACTION",       "act"),
        ("OUTCOME",      "obtain_outcome"),
        ("FEEDBACK",     "compute_feedback"),
        ("LEARNING",     "learn"),
    )

    def __init__(
        self,
        perception: PerceptionModule | None = None,
        representation: RepresentationModule | None = None,
        attention: AttentionModule | None = None,
        state: StateModule | None = None,
        memory: MemoryModule | None = None,
        prediction: PredictionModule | None = None,
        decision: DecisionModule | None = None,
        action: ActionModule | None = None,
        outcome_provider: OutcomeProvider | None = None,
        feedback: FeedbackModule | None = None,
        learning: LearningModule | None = None,
        state_store: CortexState | None = None,
    ) -> None:
        self._perception = perception
        self._representation = representation
        self._attention = attention
        self._state = state
        self._memory = memory
        self._prediction = prediction
        self._decision = decision
        self._action = action
        self._outcome_provider = outcome_provider
        self._feedback = feedback
        self._learning = learning
        self._state_store = (
            state_store
            if state_store is not None
            else CortexState()
        )

    # ── Public API ───────────────────────────────────────────────

    def process(self, raw_input: str) -> CortexEvent:
        """
        Run the full cognitive lifecycle on raw_input.

        Returns the completed CortexEvent (stage=LEARNING or stage=error_stage on failure).
        """
        event = CortexEvent(raw_input=raw_input)

        # ONE-WAY SNAPSHOT: CortexState → event.state
        event.state = self._state_store.to_internal_state()

        try:
            event = self._run_stages(event)

            # AUTHORIZED TRANSITION (single commit point)
            if event.stage == "LEARNING":
                self._state_store.update_from_event(event)

        except Exception as exc:
            event.status = "error"
            event.error = str(exc)
            # error_stage is set inside _run_stages per-module
        return event

    def perceive(self, event: CortexEvent) -> CortexEvent:
        """Delegate perception to the registered module."""
        return self._perception.process(event) if self._perception else event

    def represent(self, event: CortexEvent) -> CortexEvent:
        """Delegate representation to the registered module."""
        return self._representation.process(event) if self._representation else event

    def attend(self, event: CortexEvent) -> CortexEvent:
        """Delegate attention to the registered module."""
        return self._attention.process(event) if self._attention else event

    def update_state(self, event: CortexEvent) -> CortexEvent:
        """Delegate state update to the registered module."""
        return self._state.process(event) if self._state else event

    def retrieve_memory(self, event: CortexEvent) -> CortexEvent:
        """Delegate memory retrieval to the registered module."""
        return self._memory.process(event) if self._memory else event

    def predict(self, event: CortexEvent) -> CortexEvent:
        """Delegate prediction to the registered module."""
        return self._prediction.process(event) if self._prediction else event

    def decide(self, event: CortexEvent) -> CortexEvent:
        """Delegate decision to the registered module."""
        return self._decision.process(event) if self._decision else event

    def act(self, event: CortexEvent) -> CortexEvent:
        """Delegate action execution to the registered module."""
        return self._action.process(event) if self._action else event

    def obtain_outcome(self, event: CortexEvent) -> CortexEvent:
        """Obtain outcome from the injected OutcomeProvider."""
        if self._outcome_provider:
            return self._outcome_provider.provide(event)
        # No provider: leave outcome empty, stage stays at ACTION
        return event

    def compute_feedback(self, event: CortexEvent) -> CortexEvent:
        """Delegate feedback computation to the registered module."""
        return self._feedback.process(event) if self._feedback else event

    def learn(self, event: CortexEvent) -> CortexEvent:
        """Delegate learning to the registered module."""
        return self._learning.process(event) if self._learning else event

    # ── Internal orchestration ───────────────────────────────────

    def _run_stages(self, event: CortexEvent) -> CortexEvent:
        """Execute all stages in order, stopping on first failure."""
        pipeline = [
            ("PERCEPTION",   self._perception,   "perceive"),
            ("REPRESENTATION", self._representation, "represent"),
            ("ATTENTION",    self._attention,    "attend"),
            ("STATE",        self._state,        "update_state"),
            ("MEMORY",       self._memory,       "retrieve_memory"),
            ("PREDICTION",   self._prediction,   "predict"),
            ("DECISION",     self._decision,     "decide"),
            ("ACTION",       self._action,       "act"),
            ("OUTCOME",      self._outcome_provider, "obtain_outcome"),
            ("FEEDBACK",     self._feedback,     "compute_feedback"),
            ("LEARNING",     self._learning,     "learn"),
        ]
        for stage_name, module, method_name in pipeline:
            if module is None:
                continue
            try:
                event = getattr(self, method_name)(event)
            except Exception as exc:
                event.status = "error"
                event.error = str(exc)
                event.error_stage = stage_name
                break
        return event

    # ── Module accessors (for testing and introspection) ────────

    @property
    def perception_module(self):
        return self._perception

    @property
    def prediction_module(self):
        return self._prediction

    @property
    def decision_module(self):
        return self._decision

    @property
    def action_module(self):
        return self._action

    @property
    def outcome_provider(self):
        return self._outcome_provider

    @property
    def state_store(self) -> CortexState:
        """Access the persistent session state."""
        return self._state_store
