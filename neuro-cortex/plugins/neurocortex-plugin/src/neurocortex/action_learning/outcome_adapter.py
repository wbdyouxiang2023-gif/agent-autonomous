"""Outcome Adapter — the ONLY bridge between execution results and Action Learning.

Level 3.5-D principle: Action Learning may learn ONLY from REAL execution
results (success=True / success=False). Anything unknown must be recorded
as success=None and must NEVER enter statistics.

Rules
-----
- success=None (UNKNOWN) is NOT failure and NOT success. It is ignored.
- predicted_prob / confidence / uncertainty / prediction_error are NEVER
  used as outcomes.
- Mock / synthetic outcomes are explicitly tagged source="mock" and must
  not pollute production statistics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..event import CortexEvent, OutcomeData


@dataclass(frozen=True)
class ExecutionResult:
    """A REAL execution result produced by an actual executor.

    ``success`` must be a definitive bool. When the executor cannot
    determine success (action never ran, timeout, unknown), pass
    success=None — the adapter treats it as UNKNOWN.
    """
    success: bool | None
    actual_outcome: str = ""
    source: str = "real"  # "real" | "mock"
    metadata: dict[str, Any] = field(default_factory=dict)
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_known(self) -> bool:
        return self.success is True or self.success is False


class OutcomeAdapter:
    """Converts ExecutionResult → OutcomeData, enforcing the UNKNOWN gate.

    Production use:  adapter.to_outcome_data(execution_result)
    Mock isolation:  adapter.to_outcome_data(mock_result) where the mock
                     result declares source="mock". Downstream statistics
                     MUST NOT ingest source="mock" results.
    """

    def __init__(self, require_real: bool = True) -> None:
        self._require_real = require_real

    def to_outcome_data(self, result: ExecutionResult) -> "OutcomeData":
        from ..event import OutcomeData

        if result.source == "mock" and self._require_real:
            return OutcomeData(actual_outcome="unknown", success=None)

        if not result.is_known:
            return OutcomeData(actual_outcome="unknown", success=None)

        return OutcomeData(
            actual_outcome=result.actual_outcome or "done",
            success=bool(result.success),
        )

    def is_learning_eligible(self, outcome_data: "OutcomeData") -> bool:
        return outcome_data.success is True or outcome_data.success is False


def outcome_from_event_real(event: "CortexEvent") -> "OutcomeData | None":
    """Extract REAL outcome from a CortexEvent (None when UNKNOWN)."""
    outcome = getattr(event, "outcome", None)
    if outcome is None:
        return None
    success = getattr(outcome, "success", None)
    if success is None:
        return None
    from ..event import OutcomeData
    return OutcomeData(
        actual_outcome=getattr(outcome, "actual_outcome", "") or "done",
        success=bool(success),
    )
