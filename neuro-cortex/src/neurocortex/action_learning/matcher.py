"""Situation matching — hierarchical, level-weighted evidence attribution.

Levels (most precise first):
    L1  exact situation + action      weight 1.00
    L2  intent + task_type + action   weight 0.80
    L3  intent + action               weight 0.60
    L4  global + action               weight 0.40

Legacy experiences (no situation) can only reach L3/L4.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schema import ActionLearningSituation

LEVEL_WEIGHTS: dict[int, float] = {
    1: 1.00,
    2: 0.80,
    3: 0.60,
    4: 0.40,
}


@dataclass(frozen=True)
class MatchResult:
    level: int
    weight: float
    legacy: bool = False


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _exact_situation_eq(query: "ActionLearningSituation", exp_situation: "ActionLearningSituation") -> bool:
    """Strict equality of ALL available situation fields (never fabricated)."""
    if _norm(query.intent) != _norm(exp_situation.intent):
        return False
    if query.task_type is None or exp_situation.task_type is None:
        return False
    if _norm(query.task_type) != _norm(exp_situation.task_type):
        return False
    if query.error_type is None or exp_situation.error_type is None:
        return False
    if _norm(query.error_type) != _norm(exp_situation.error_type):
        return False
    return True


def _intent_task_type_eq(query: "ActionLearningSituation", exp_situation: "ActionLearningSituation") -> bool:
    if not _norm(query.intent) or not _norm(exp_situation.intent):
        return False
    if _norm(query.intent) != _norm(exp_situation.intent):
        return False
    if query.task_type is None or exp_situation.task_type is None:
        return False
    return _norm(query.task_type) == _norm(exp_situation.task_type)


def _intent_eq(query: "ActionLearningSituation", exp_situation: "ActionLearningSituation") -> bool:
    if not _norm(query.intent) or not _norm(exp_situation.intent):
        return False
    return _norm(query.intent) == _norm(exp_situation.intent)


def match_situation(
    query: "ActionLearningSituation",
    exp_situation: "ActionLearningSituation",
    legacy: bool = False,
    enabled_levels: tuple[int, ...] = (1, 2, 3, 4),
) -> MatchResult | None:
    """Match a query situation against one experience situation (best level)."""
    best: MatchResult | None = None

    if 1 in enabled_levels and not legacy:
        if _exact_situation_eq(query, exp_situation):
            best = MatchResult(level=1, weight=LEVEL_WEIGHTS[1], legacy=False)

    if 2 in enabled_levels and not legacy:
        if best is None and _intent_task_type_eq(query, exp_situation):
            best = MatchResult(level=2, weight=LEVEL_WEIGHTS[2], legacy=False)

    if 3 in enabled_levels:
        if best is None and _intent_eq(query, exp_situation):
            best = MatchResult(level=3, weight=LEVEL_WEIGHTS[3], legacy=legacy)

    if 4 in enabled_levels:
        if best is None:
            if _norm(query.intent) or _norm(query.raw_input):
                best = MatchResult(level=4, weight=LEVEL_WEIGHTS[4], legacy=legacy)

    return best


def degrade_for_legacy(query: "ActionLearningSituation", exp_situation: "ActionLearningSituation") -> tuple[int, float]:
    if _norm(query.intent) and _norm(exp_situation.intent) and _norm(query.intent) == _norm(exp_situation.intent):
        return 3, LEVEL_WEIGHTS[3]
    return 4, LEVEL_WEIGHTS[4]
