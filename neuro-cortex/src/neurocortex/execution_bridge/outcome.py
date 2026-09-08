"""Outcome production for the real execution bridge.

RealExecutionOutcomeProvider is the PRODUCTION outcome source. It consumes
only ExecutionResult (never predicted_prob / confidence / synthetic heuristics)
and produces OutcomeData for the Cortex pipeline, plus a minimal evidence
record appended to the execution log.

The legacy PersistentOutcome remains in server.py as the Mock/Synthetic
provider for test/dev only — it is NOT wired into this provider.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ExecutionBridgeConfig
from .schema import ExecutionEvidence, ExecutionResult


class ExecutionLog:
    """Append-only JSONL log of real executions (atomic append per entry)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path).expanduser() if path else None

    def append(self, evidence: ExecutionEvidence) -> bool:
        if self._path is None:
            return False
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(evidence.to_dict(), ensure_ascii=False) + "\n")
        return True

    @property
    def path(self) -> Path | None:
        return self._path


class RealExecutionOutcomeProvider:
    """PRODUCTION outcome source: ExecutionResult → OutcomeData.

    Rules:
      - ExecutionResult.success=True  → OutcomeData(success=True)
      - ExecutionResult.success=False → OutcomeData(success=False)
      - ExecutionResult.success=None  → OutcomeData(success=None) [UNKNOWN]
      - UNKNOWN never enters Action Learning statistics (gate upstream).
    """

    def __init__(self, config: ExecutionBridgeConfig | None = None, log: ExecutionLog | None = None) -> None:
        self._config = config or ExecutionBridgeConfig()
        self._log = log or ExecutionLog(self._config.log_path)

    def to_outcome_data(self, result: ExecutionResult):
        """Convert a real ExecutionResult into OutcomeData for the pipeline."""
        from ..event import OutcomeData

        # Evidence record first (minimal, no Experience schema change)
        self._log.append(ExecutionEvidence(
            execution_id=result.execution_id,
            action_type=result.action_type,
            execution_status=result.status,
            success=result.success,
        ))

        if result.is_known:
            return OutcomeData(
                actual_outcome=result.output or ("done" if result.success else "failed"),
                success=bool(result.success),
            )
        return OutcomeData(actual_outcome="unknown", success=None)

    @property
    def config(self) -> ExecutionBridgeConfig:
        return self._config

    @property
    def log(self) -> ExecutionLog:
        return self._log
