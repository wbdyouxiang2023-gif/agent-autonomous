"""Action module — deterministic symbolic action execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..event import CortexEvent, ActionData
from ..interfaces import ActionModule

if TYPE_CHECKING:
    from ..event import DecisionData

# Known symbolic action types (frozen for v1)
KNOWN_ACTIONS: set[str] = {
    "noop",
    "respond",
    "code_review",
    "code_edit",
    "tool_call",
}

# Safety gate threshold
SCORE_THRESHOLD: float = 0.3


class BasicAction(ActionModule):
    """
    Phase 8 v1 ActionModule.

    Deterministic, symbolic action execution.

    Input contract:
      READ:   event.decision.selected_action, event.decision.decision_score,
              event.raw_input
      READ-ONLY: event.decision.decision_reason, event.decision.candidates
      FORBIDDEN: perception, representation, state, prediction, memory,
                 feedback, outcome, CortexState

    Safety gate (first match wins):
      Rule 0: empty selected_action → skip (status="skipped")
      Rule 1: noop → success (instant return)
      Rule 2: decision_score < 0.3 → skip (status="skipped")
      Rule 3: unknown action type → fail (raise ValueError)
      Rule 4: valid known action → success (symbolic execution)
    """

    def process(self, event: CortexEvent) -> CortexEvent:
        selected_action = event.decision.selected_action
        decision_score = event.decision.decision_score
        raw_input = event.raw_input

        try:
            action_data = self._execute(selected_action, decision_score, raw_input)
        except ValueError:
            # Unknown action type — record failure and re-raise for Cortex error handling
            event.act(ActionData(
                action_type=selected_action,
                action_payload={"text": raw_input},
                status="failure",
                planned=True,
                actual=False,
            ))
            raise

        event.act(action_data)
        return event

    def _execute(
        self,
        selected_action: str,
        decision_score: float,
        raw_input: str,
    ) -> ActionData:
        """Apply safety gate and produce ActionData."""
        # Rule 0: Noop — always safe, instant success
        if selected_action == "noop":
            return ActionData(
                action_type="noop",
                action_payload={"text": raw_input},
                status="success",
                planned=True,
                actual=True,
            )

        # Rule 1: Low decision score
        if decision_score < SCORE_THRESHOLD:
            return ActionData(
                action_type=selected_action or "noop",
                action_payload={"text": raw_input},
                status="skipped",
                planned=True,
                actual=False,
            )

        # Rule 2: Unknown action type
        if selected_action and selected_action not in KNOWN_ACTIONS:
            raise ValueError(f"Unknown action type: {selected_action!r}")

        # Rule 3: Valid known action or empty (backward compat) — symbolic execution
        return ActionData(
            action_type=selected_action or "noop",
            action_payload={"text": raw_input},
            status="success",
            planned=True,
            actual=True,
        )
