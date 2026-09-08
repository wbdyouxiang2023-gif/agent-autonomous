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
    """REAL outcome observation. Only success=True/False is usable."""

    success: bool
    actual_outcome: str = ""
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

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
    """Derive a REAL outcome from a completed event (None when unknown)."""
    outcome = getattr(event, "outcome", None)
    if outcome is None:
        return None
    success = getattr(outcome, "success", None)
    if success is None:
        return None
    actual_outcome = getattr(outcome, "actual_outcome", "")
    return ActionLearningOutcome(success=bool(success), actual_outcome=actual_outcome or "")


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
