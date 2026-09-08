"""Action Learning configuration — all knobs live here.

Feature flags are read from environment variables so the module can be
enabled/disabled without touching production code paths.

Flags
-----
NEUROCORTEX_ACTION_LEARNING  (default "false")
    Master switch. When "false" the ActionLearningBridge returns candidate
    actions unchanged and record_outcome() is a no-op.

ACTION_LEARNING_SHADOW_ONLY  (default "true")
    When NEUROCORTEX_ACTION_LEARNING=true and this is "true", ranking is
    computed and recorded but candidate ORDER is left untouched (Shadow mode).

ACTION_LEARNING_STATISTICS_PATH (default ~/.neurocortex_action_statistics.json)

REAL_EXECUTION_BRIDGE_ENABLED (default "false")
    Level 4.0: when "false" the real-execution bridge is a pure passthrough
    (no shell / file / web side effects). Only when explicitly "true" can
    real tool execution happen.

Smoothing / scoring knobs
-------------------------
ACTION_SMOOTHING_ALPHA        (default 1)
ACTION_SMOOTHING_BETA         (default 1)
ACTION_CONFIDENCE_K           (default 5)
ACTION_PRIOR_RATE             (default 0.5)
ACTION_HISTORY_WEIGHT         (default 0.6)
ACTION_SEMANTIC_WEIGHT        (default 0.3)
ACTION_RECENCY_WEIGHT         (default 0.1)
ACTION_RECENCY_HALF_LIFE_DAYS (default 14)
ACTION_RETRIEVAL_TOP_K        (default 10)
ACTION_LEARNING_MATCH_LEVELS  (default "1,2,3,4")
ACTION_SITUATION_EVIDENCE_THRESHOLD (default 2)
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


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_string(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _statistics_path() -> Path:
    raw = os.environ.get("ACTION_LEARNING_STATISTICS_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".neurocortex_action_statistics.json"


@dataclass(frozen=True)
class ActionLearningConfig:
    """Immutable configuration snapshot for the Action Learning Engine."""

    # ── Feature flags ──────────────────────────────────────────
    enabled: bool = field(default_factory=lambda: _env_bool("NEUROCORTEX_ACTION_LEARNING", False))
    shadow_only: bool = field(default_factory=lambda: _env_bool("ACTION_LEARNING_SHADOW_ONLY", True))
    statistics_path: Path = field(default_factory=_statistics_path)
    real_bridge_enabled: bool = field(default_factory=lambda: _env_bool("REAL_EXECUTION_BRIDGE_ENABLED", False))

    # ── Smoothing / evidence ───────────────────────────────────
    smoothing_alpha: float = field(default_factory=lambda: _env_float("ACTION_SMOOTHING_ALPHA", 1.0))
    smoothing_beta: float = field(default_factory=lambda: _env_float("ACTION_SMOOTHING_BETA", 1.0))
    confidence_k: float = field(default_factory=lambda: _env_float("ACTION_CONFIDENCE_K", 5.0))
    prior_rate: float = field(default_factory=lambda: _env_float("ACTION_PRIOR_RATE", 0.5))

    # ── Scoring weights ────────────────────────────────────────
    history_weight: float = field(default_factory=lambda: _env_float("ACTION_HISTORY_WEIGHT", 0.6))
    semantic_weight: float = field(default_factory=lambda: _env_float("ACTION_SEMANTIC_WEIGHT", 0.3))
    recency_weight: float = field(default_factory=lambda: _env_float("ACTION_RECENCY_WEIGHT", 0.1))
    recency_half_life_days: float = field(default_factory=lambda: _env_float("ACTION_RECENCY_HALF_LIFE_DAYS", 14.0))

    # ── Retrieval / matching ───────────────────────────────────
    retrieval_top_k: int = field(default_factory=lambda: _env_int("ACTION_RETRIEVAL_TOP_K", 10))
    match_levels: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x) for x in _env_string("ACTION_LEARNING_MATCH_LEVELS", "1,2,3,4").split(",") if x.strip().isdigit()
        ) or (1, 2, 3, 4)
    )
    situation_evidence_threshold: int = field(
        default_factory=lambda: _env_int("ACTION_SITUATION_EVIDENCE_THRESHOLD", 2)
    )

    @property
    def active(self) -> bool:
        return self.enabled
