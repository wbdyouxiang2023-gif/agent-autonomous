"""Action Learning schemas — independent of the legacy Experience schema.

These dataclasses are derived FROM real CortexEvents via adapters
(`from_event`). The legacy Experience schema in ``event.py`` is NOT modified.

Design rules (Level 3.5-C/D):
  - Never fabricate fields that do not exist in the event.
  - strategy defaults to action_type.
  - action_key = action_type (raw arguments are NEVER part of the key).
  - Outcome must come from REAL OUTCOME. predicted_prob / confidence /
    uncertainty / prediction_error are FORBIDDEN as learning signals.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..event import CortexEvent, Experience


@dataclass(frozen=True)
class ActionLearningSituation:
    """Structured view of the situation that led to a decision."""

    intent: str = ""
    task_type: str | None = None
    error_type: str | None = None
    context_features: dict[str, Any] = field(default_factory=dict)
    raw_input: str = ""
    situation_completeness: str = "partial"  # "full" | "partial"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionLearningCandidate:
    """A candidate action to evaluate/rank."""

    action_type: str = ""
    strategy: str | None = None
    action_key: str = ""

    def __post_init__(self) -> None:
        if not self.strategy:
            object.__setattr__(self, "strategy", self.action_type)
        if not self.action_key:
            object.__setattr__(self, "action_key", self.action_type)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionLearningOutcome:
    """REAL outcome observation with optional task completion tracking.
    
    Design rules (Level 4.0):
    - success: execution_success (did the action execute without error?)
    - task_completion: did the task actually complete? (None = unknown)
    - MUST NOT fabricate task_completion from action_type heuristics
    """

    success: bool
    task_completion: bool | None = None  # NEW: task completion status
    actual_outcome: str = ""
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_complete(self) -> bool:
        """Task completion is known and True."""
        return self.task_completion is True

    @property
    def is_incomplete(self) -> bool:
        """Task completion is known and False."""
        return self.task_completion is False

    @property
    def task_completion_unknown(self) -> bool:
        """Task completion is not known."""
        return self.task_completion is None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Adapters (Event → Action Learning schema) ─────────────────────────


def situation_from_event(event: "CortexEvent") -> ActionLearningSituation:
    perception = getattr(event, "perception", None)
    intent = getattr(perception, "intent", "") if perception is not None else ""
    raw_input = getattr(event, "raw_input", "")
    return ActionLearningSituation(
        intent=intent,
        task_type=None,
        error_type=None,
        context_features={},
        raw_input=raw_input,
        situation_completeness="partial",
    )


def candidate_from_action_type(action_type: str) -> ActionLearningCandidate:
    return ActionLearningCandidate(action_type=action_type, strategy=action_type)


def outcome_from_event(event: "CortexEvent") -> ActionLearningOutcome | None:
    """Derive a REAL outcome from a completed event (None when unknown).
    
    Task completion is extracted from event.outcome.task_completed if available.
    If not present, task_completion is set to None (unknown).
    
    NEVER fabricates task_completion from action_type.
    """
    outcome = getattr(event, "outcome", None)
    if outcome is None:
        return None
    success = getattr(outcome, "success", None)
    if success is None:
        return None
    actual_outcome = getattr(outcome, "actual_outcome", "")
    
    # Extract task_completion if available (NEW in Level 4.0)
    # Do NOT use action_type heuristics
    task_completed = getattr(outcome, "task_completed", None)
    task_completion = bool(task_completed) if task_completed is not None else None
    
    return ActionLearningOutcome(
        success=bool(success),
        task_completion=task_completion,
        actual_outcome=actual_outcome or "",
    )


def candidate_from_legacy_experience(exp: "Experience") -> ActionLearningCandidate | None:
    action_type = getattr(exp, "action_type", "") or ""
    if not action_type:
        return None
    return candidate_from_action_type(action_type)


def situation_from_legacy_experience(exp: "Experience") -> ActionLearningSituation:
    intent = getattr(exp, "intent", "") or ""
    raw_input = getattr(exp, "raw_input", "") or ""
    return ActionLearningSituation(
        intent=intent,
        task_type=None,
        error_type=None,
        context_features={},
        raw_input=raw_input,
        situation_completeness="partial",
    )
