"""Execution Bridge schemas — ActionRequest / ExecutionResult / Evidence.

Level 4.0: the bridge converts a NeuroCortex Decision into a real Hermes
tool call, and converts the real execution outcome back into OutcomeData.

Rules
-----
- action_key = action_type. tool_name is ONLY set when a real mapping
  exists; otherwise the bridge returns UNSUPPORTED / UNKNOWN (never fakes).
- success is tri-state: True (real success) / False (real failure) / None
  (UNKNOWN — never enters Action Learning).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..event import CortexEvent


@dataclass(frozen=True)
class ActionRequest:
    """A decision to execute a real action through the bridge."""

    request_id: str
    action_type: str
    situation: dict[str, Any]
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    """The REAL result of one tool execution.

    success tri-state:
      True   = definitive real success
      False  = definitive real failure
      None   = UNKNOWN (no reliable result) — never learned
    """

    execution_id: str
    request_id: str
    action_type: str
    tool_name: str
    status: str  # "success" | "failure" | "unknown" | "unsupported" | "error"
    success: bool | None
    output: str = ""
    error: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_known(self) -> bool:
        return self.success is True or self.success is False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionEvidence:
    """Minimal evidence record per real outcome (no Experience schema change)."""

    execution_id: str
    action_type: str
    execution_status: str
    success: bool | None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def request_from_event(event: "CortexEvent") -> ActionRequest | None:
    """Build an ActionRequest from a completed CortexEvent.

    tool_name is only set when the action maps to a real Hermes tool;
    otherwise None → the bridge returns UNSUPPORTED.
    """
    import uuid

    action = getattr(event, "action", None)
    action_type = getattr(action, "action_type", "") if action else ""
    if not action_type:
        return None
    perception = getattr(event, "perception", None)
    intent = getattr(perception, "intent", "") if perception else ""
    return ActionRequest(
        request_id=uuid.uuid4().hex[:12],
        action_type=action_type,
        situation={"intent": intent, "raw_input": getattr(event, "raw_input", "")},
    )
