"""Execution Bridge — NeuroCortex ↔ Hermes Real Execution (Level 4.0).

Maps NeuroCortex Decisions to real, safe, read-only Hermes tool calls and
converts the real execution outcome back into the Cortex pipeline.

OFF by default (REAL_EXECUTION_BRIDGE_ENABLED=false): zero side effects.
"""
from .config import ExecutionBridgeConfig
from .schema import ActionRequest, ExecutionResult, ExecutionEvidence, request_from_event
from .adapter import HermesExecutionAdapter
from .outcome import ExecutionLog, RealExecutionOutcomeProvider
from .bridge import ExecutionBridge

__all__ = [
    "ExecutionBridgeConfig",
    "ActionRequest",
    "ExecutionResult",
    "ExecutionEvidence",
    "request_from_event",
    "HermesExecutionAdapter",
    "ExecutionLog",
    "RealExecutionOutcomeProvider",
    "ExecutionBridge",
]
