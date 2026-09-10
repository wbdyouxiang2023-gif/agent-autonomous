"""Hermes Execution Adapter — maps ActionRequest → real Hermes tool call.

Level 4.0: the ONLY supported real tool in phase 1 is a SAFE READ-ONLY
operation. We deliberately do NOT wire terminal (shell) or file writes —
they have side effects. The chosen tool:

    tools.file_tools.read_file_tool(path, offset, limit, task_id)

It reads a file and returns text or a tool_error. It is read-only and
side-effect-free, so it is the safest possible real executor to validate
the bridge with.

We import the REAL Hermes implementation (adapter, not copy): if the import
fails, the adapter degrades to UNSUPPORTED — never a fake execution.

Mapping (phase 1):
    action_type == "read_file"  → tool_name="read_file_tool", args={"path": ...}
    anything else               → UNSUPPORTED (never pretend to execute)

Result semantics:
    tool returns text                        → success=True
    tool returns tool_error (dict w/ error)  → success=False
    tool raises / timeout / import missing   → success=None (UNKNOWN)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from .config import ExecutionBridgeConfig
from .schema import ActionRequest, ExecutionResult

# Read-only, side-effect-free real tool — the safest executor for validation.
# Import lazily so a missing tools package never breaks NeuroCortex.
_READ_TOOL_NAME = "read_file_tool"


def _resolve_real_executor():
    """Import the REAL Hermes file read tool (adapter, not copy)."""
    try:
        from tools.file_tools import read_file_tool
        return read_file_tool
    except ImportError:
        return None


class HermesExecutionAdapter:
    """Converts ActionRequest → real Hermes tool call → ExecutionResult."""

    def __init__(self, config: ExecutionBridgeConfig | None = None) -> None:
        self._config = config or ExecutionBridgeConfig()
        self._executor = _resolve_real_executor()

    @property
    def config(self) -> ExecutionBridgeConfig:
        return self._config

    @property
    def executor_available(self) -> bool:
        return self._executor is not None

    def execute(self, request: ActionRequest) -> ExecutionResult:
        """Execute a real read-only tool call and return ExecutionResult.

        When the bridge is disabled, the tool is unsupported, or the real
        executor is unavailable → UNSUPPORTED / UNKNOWN, never a fake run.
        """
        started = datetime.now(timezone.utc).isoformat()
        execution_id = f"exec-{request.request_id}"

        # Safety: disabled → zero side effects
        if not self._config.enabled:
            return ExecutionResult(
                execution_id=execution_id, request_id=request.request_id,
                action_type=request.action_type, tool_name=request.tool_name or "",
                status="unsupported", success=None,
                error="REAL_EXECUTION_BRIDGE_ENABLED=false (disabled)",
                started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
            )

        # Only read_file maps to a real tool in phase 1
        if request.action_type != "read_file":
            return ExecutionResult(
                execution_id=execution_id, request_id=request.request_id,
                action_type=request.action_type, tool_name=request.tool_name or "",
                status="unsupported", success=None,
                error=f"unsupported action_type={request.action_type!r} (phase 1 supports read_file only)",
                started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
            )

        if self._executor is None:
            return ExecutionResult(
                execution_id=execution_id, request_id=request.request_id,
                action_type=request.action_type, tool_name=_READ_TOOL_NAME,
                status="unknown", success=None,
                error="real Hermes executor unavailable (tools.file_tools not importable)",
                started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
            )

        path = request.arguments.get("path", "")
        try:
            output = self._executor(path=path, task_id="default")
            finished = datetime.now(timezone.utc).isoformat()
            # read_file_tool returns a JSON STRING (not a dict) carrying an
            # "error" field on failure, e.g.
            #   '{"content": "", "total_lines": 0, ..., "error": "File not found: ..."}'
            # Parse it and treat any non-empty error as a REAL failure.
            parsed = output
            if isinstance(output, str):
                try:
                    import json as _json
                    candidate = _json.loads(output)
                    if isinstance(candidate, dict):
                        parsed = candidate
                except (ValueError, TypeError):
                    pass  # plain text output → success

            if isinstance(parsed, dict):
                err = parsed.get("error")
                if err:
                    return ExecutionResult(
                        execution_id=execution_id, request_id=request.request_id,
                        action_type=request.action_type, tool_name=_READ_TOOL_NAME,
                        status="failure", success=False,
                        error=str(err),
                        started_at=started, finished_at=finished,
                    )
                content = parsed.get("content", "") if "content" in parsed else str(parsed)
                return ExecutionResult(
                    execution_id=execution_id, request_id=request.request_id,
                    action_type=request.action_type, tool_name=_READ_TOOL_NAME,
                    status="success", success=True,
                    output=str(content)[:2000],
                    started_at=started, finished_at=finished,
                )
            return ExecutionResult(
                execution_id=execution_id, request_id=request.request_id,
                action_type=request.action_type, tool_name=_READ_TOOL_NAME,
                status="success", success=True,
                output=str(output)[:2000],
                started_at=started, finished_at=finished,
            )
        except Exception as exc:
            return ExecutionResult(
                execution_id=execution_id, request_id=request.request_id,
                action_type=request.action_type, tool_name=_READ_TOOL_NAME,
                status="unknown", success=None,
                error=f"execution raised: {exc}",
                started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
            )
