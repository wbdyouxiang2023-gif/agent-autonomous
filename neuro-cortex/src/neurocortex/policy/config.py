"""Policy configuration.

Flags
-----
NEUROCORTEX_POLICY_ENABLED  (default "false")
    Master switch. When false, PolicyEngine.choose_action returns
    UNDECIDED / fallback (never changes any decision).

NEUROCORTEX_POLICY_SHADOW_ONLY  (default "true")
    When POLICY_ENABLED=true and SHADOW_ONLY=true, the policy computes a
    decision and records it (shadow log) but never affects real behavior.

Policy decision rules
---------------------
POLICY_MIN_EVIDENCE  (default 2)
    Minimum support_count on the top candidate for the policy to make a
    confident (non-fallback) decision. Below it → "insufficient_evidence".

POLICY_CONFIDENCE_THRESHOLD (default 0.0)
    Minimum score gap between top-1 and top-2 for a decision; 0.0 means
    "any evidence gap counts" (top-1 is chosen whenever it has evidence).

POLICY_LOG_PATH (default ~/.neurocortex_policy_log.jsonl)
    Append-only shadow policy log.
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


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _default_log_path() -> Path:
    return Path(os.environ.get("NEUROCORTEX_POLICY_LOG_PATH", str(Path.home() / ".neurocortex_policy_log.jsonl"))).expanduser()


@dataclass(frozen=True)
class PolicyConfig:
    enabled: bool = field(default_factory=lambda: _env_bool("NEUROCORTEX_POLICY_ENABLED", False))
    shadow_only: bool = field(default_factory=lambda: _env_bool("NEUROCORTEX_POLICY_SHADOW_ONLY", True))
    min_evidence: int = field(default_factory=lambda: _env_int("POLICY_MIN_EVIDENCE", 2))
    confidence_threshold: float = field(default_factory=lambda: _env_float("POLICY_CONFIDENCE_THRESHOLD", 0.0))
    log_path: Path = field(default_factory=_default_log_path)
