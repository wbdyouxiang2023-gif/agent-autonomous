"""Execution Bridge configuration.

Flags
-----
REAL_EXECUTION_BRIDGE_ENABLED  (default "false")
    Master switch. When false, the bridge NEVER executes anything real and
    returns UNSUPPORTED / UNKNOWN (zero side effects).

EXECUTION_TIMEOUT_SECONDS     (default 10)
    Timeout for real tool execution.

EXECUTION_LOG_PATH            (default ~/.neurocortex_execution_log.jsonl)
    Append-only evidence log of real executions.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ExecutionBridgeConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("REAL_EXECUTION_BRIDGE_ENABLED", False))
    timeout_seconds: int = field(default_factory=lambda: _env_int("EXECUTION_TIMEOUT_SECONDS", 10))
    log_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("EXECUTION_LOG_PATH", str(Path.home() / ".neurocortex_execution_log.jsonl"))
        ).expanduser()
    )
