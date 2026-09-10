"""Execution Bridge — NeuroCortex Decision → real Hermes tool → real outcome.

Sits between DECISION and ACTION (and back into OUTCOME). It is:
  - OFF by default (REAL_EXECUTION_BRIDGE_ENABLED=false) → pure passthrough,
    zero side effects, pipeline unchanged.
  - Fail-safe: any bridge error → original pipeline behavior.
  - Adapter-based: calls the real Hermes executor (tools.file_tools), never
    reimplements it.

Flow:
    Decision
      ↓
    ActionRequest
      ↓
    ExecutionBridge
      ↓
    ExecutionResult
      ↓
    RealExecutionOutcomeProvider → OutcomeData
      ↓
    Feedback / Learning
"""
from __future__ import annotations

import logging
from typing import Any

from .config import ExecutionBridgeConfig
from .adapter import HermesExecutionAdapter
from .outcome import ExecutionLog, RealExecutionOutcomeProvider
from .schema import ActionRequest, ExecutionResult

logger = logging.getLogger(__name__)


class ExecutionBridge:
    """Fail-safe, flag-gated real execution bridge."""

    def __init__(
        self,
        config: ExecutionBridgeConfig | None = None,
        adapter: HermesExecutionAdapter | None = None,
        outcome_provider: RealExecutionOutcomeProvider | None = None,
    ) -> None:
        self._config = config or ExecutionBridgeConfig()
        self._adapter = adapter or HermesExecutionAdapter(self._config)
        self._outcome = outcome_provider or RealExecutionOutcomeProvider(self._config)

    @property
    def config(self) -> ExecutionBridgeConfig:
        return self._config

    @property
    def adapter(self) -> HermesExecutionAdapter:
        return self._adapter

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def execute(self, request: ActionRequest) -> ExecutionResult:
        """Execute one real tool call (no-op/unsupported when disabled).

        The real execution result is recorded into the execution log via
        the outcome provider (minimal evidence), so every REAL run leaves
        an audit trail. When disabled, NO log is written (zero side effects).
        """
        try:
            result = self._adapter.execute(request)
            # Persist evidence ONLY for real execution attempts (enabled).
            # Disabled/unsupported results are never logged (zero side effects).
            if self._config.enabled:
                self._outcome.to_outcome_data(result)
            return result
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("ExecutionBridge.execute failed: %s", exc)
            return ExecutionResult(
                execution_id=f"exec-{request.request_id}-err",
                request_id=request.request_id,
                action_type=request.action_type,
                tool_name=request.tool_name or "",
                status="error",
                success=None,
                error=str(exc),
            )

    def execute_event(self, event: Any) -> Any:
        """Run the bridge over a CortexEvent, returning the (possibly
        modified) event with a real outcome when the bridge is enabled.

        When disabled or unsupported, the event is returned UNCHANGED
        (original pipeline continues with its own outcome provider).
        """
        if not self._config.enabled:
            return event

        try:
            from .schema import request_from_event
            request = request_from_event(event)
            if request is None or request.action_type != "read_file":
                return event  # unsupported → original pipeline

            result = self.execute(request)
            outcome_data = self._outcome.to_outcome_data(result)
            event.record_outcome(outcome_data)
            return event
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("ExecutionBridge.execute_event failed, pipeline unchanged: %s", exc)
            return event
