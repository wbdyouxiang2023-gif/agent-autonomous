"""Semantic evidence transfer — novel situation borrows similar history.

This is DERIVED evidence, strictly separated from exact/actual evidence.

BorrowedEvidence fields:
  - source_situation   (intent + raw_input of the known situation)
  - source_action      (action_key)
  - similarity         (0-1 from similarity.similarity)
  - original_support   (success+failure in source statistics)
  - transferred_support/weight  (derived, <= original support)
  - match_level="semantic"
  - borrowed_from      ([situation_key])

Safety rules:
  - NEVER writes to StatisticsStore (immutable original evidence).
  - NEVER creates actual success/failure (estimated only).
  - NEVER looks like exact evidence (match_level="semantic").
  - Unrelated (sim < LOW) → no transfer, ranking untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .similarity import similarity

# Default thresholds (configurable by caller, never hardcoded in engine)
DEFAULT_HIGH_THRESHOLD = 0.70
DEFAULT_LOW_THRESHOLD = 0.60


@dataclass(frozen=True)
class BorrowedEvidence:
    source_situation: str
    source_action: str
    similarity: float
    original_support: int
    original_success: int
    transferred_weight: float
    match_level: str = "semantic"
    borrowed_from: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_situation": self.source_situation,
            "source_action": self.source_action,
            "similarity": round(self.similarity, 4),
            "original_support": self.original_support,
            "original_success": self.original_success,
            "transferred_weight": round(self.transferred_weight, 4),
            "match_level": self.match_level,
            "borrowed_from": list(self.borrowed_from),
        }


def transfer_gate(sim: float, *, high: float = DEFAULT_HIGH_THRESHOLD, low: float = DEFAULT_LOW_THRESHOLD) -> str:
    """Classify a similarity score into a transfer decision.

    Returns one of: "transfer" | "no_transfer" | "discounted".
    """
    if sim >= high:
        return "transfer"
    if sim < low:
        return "no_transfer"
    return "discounted"


def compute_transfer_weight(sim: float, gate: str, *, high: float = DEFAULT_HIGH_THRESHOLD,
                            low: float = DEFAULT_LOW_THRESHOLD) -> float:
    """Derived weight for transferred evidence.

    - transfer:     weight = sim (>= HIGH)
    - discounted:   weight = sim scaled into [0.25, HIGH) range
    - no_transfer:  weight = 0.0
    """
    if gate == "no_transfer":
        return 0.0
    if gate == "transfer":
        return sim
    # discounted: sim in [LOW, HIGH) → scale to [0.25, 0.70)
    span = max(high - low, 1e-6)
    return round(0.25 + (sim - low) / span * (high - 0.25), 4)


def build_borrowed_evidence(
    novel_raw: str,
    source_situation_key: str,
    source_raw: str,
    source_action: str,
    source_success: int,
    source_failure: int,
    *,
    high: float = DEFAULT_HIGH_THRESHOLD,
    low: float = DEFAULT_LOW_THRESHOLD,
) -> tuple[BorrowedEvidence | None, str, SimilarityResultLike]:
    """Create borrowed evidence from one known situation.

    Returns (evidence | None, gate, similarity_result).
    None when gate == no_transfer.
    """
    sim_result = similarity(novel_raw, source_raw)
    sim = sim_result.score
    gate = transfer_gate(sim, high=high, low=low)
    if gate == "no_transfer":
        return None, gate, sim_result

    support = source_success + source_failure
    if support == 0:
        return None, gate, sim_result  # no real evidence to borrow

    weight = compute_transfer_weight(sim, gate, high=high, low=low)
    ev = BorrowedEvidence(
        source_situation=source_situation_key,
        source_action=source_action,
        similarity=sim,
        original_support=support,
        original_success=source_success,
        transferred_weight=weight,
        match_level="semantic",
        borrowed_from=[source_situation_key],
    )
    return ev, gate, sim_result


# Small typing alias to avoid circular import noise
SimilarityResultLike = Any
