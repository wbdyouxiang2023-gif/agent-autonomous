"""Action Learning Bridge — the ONLY production entry point.

Placed at the DECISION → ACTION boundary:

    BasicDecision
        ↓
    candidates
        ↓
    ActionLearningBridge
        ↓
    ranked candidates
        ↓
    BasicAction

Guarantees
----------
  - NEUROCORTEX_ACTION_LEARNING=false (default) → candidates returned
    unchanged, record_outcome() is a no-op, zero behavior change.
  - ACTION_LEARNING_SHADOW_ONLY=true → ranking computed and recorded but
    candidate ORDER is untouched (Shadow Runtime support).
  - Any engine exception → candidates returned unchanged (fail-safe).
  - Bridge NEVER modifies the Experience schema / JSONL and NEVER reads
    predicted_prob as a learning signal.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .config import ActionLearningConfig
from .engine import ActionLearningEngine
from .schema import (
    ActionLearningOutcome,
    situation_from_event,
)
from .outcome_adapter import OutcomeAdapter, outcome_from_event_real

if TYPE_CHECKING:
    from ..event import CortexEvent

logger = logging.getLogger(__name__)

_SKIP = object()


def _coerce(c: Any) -> Any:
    """Coerce a candidate (str / dict / ActionLearningCandidate)."""
    from .schema import ActionLearningCandidate

    if isinstance(c, str):
        return ActionLearningCandidate(action_type=c, strategy=c)
    if isinstance(c, ActionLearningCandidate):
        return c
    if isinstance(c, dict):
        at = c.get("action_type") or c.get("id") or c.get("action_key") or ""
        if not at:
            return _SKIP
        strategy = c.get("strategy") or at
        return ActionLearningCandidate(action_type=at, strategy=strategy, action_key=at)
    return _SKIP


class ActionLearningBridge:
    """Thin, fail-safe bridge between the decision stage and the executor."""

    def __init__(
        self,
        config: ActionLearningConfig | None = None,
        engine: ActionLearningEngine | None = None,
    ) -> None:
        self._config = config or ActionLearningConfig()
        self._engine = engine or ActionLearningEngine(self._config)
        self._shadow_only = self._config.shadow_only
        self._adapter = OutcomeAdapter(require_real=True)

    @property
    def config(self) -> ActionLearningConfig:
        return self._config

    @property
    def engine(self) -> ActionLearningEngine:
        return self._engine

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def rank_candidates(
        self,
        candidates: list[Any],
        situation: ActionLearningSituation | None = None,
        raw_input: str = "",
        intent: str = "",
        experiences: list[Any] | None = None,
    ) -> list[Any]:
        """Rank candidate actions. Returns candidates in their original order
        when the feature is disabled or the engine fails (fail-safe).
        """
        if not self.enabled:
            return candidates

        try:
            from .schema import ActionLearningSituation

            if situation is None:
                situation = ActionLearningSituation(
                    intent=intent or "",
                    raw_input=raw_input or "",
                    situation_completeness="partial",
                )
            coerced = [_coerce(c) for c in candidates]
            ranked = self._engine.rank_actions(situation, [c for c in coerced if c is not _SKIP], experiences)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("ActionLearningBridge.rank_candidates failed, falling back: %s", exc)
            return candidates

        if self._shadow_only:
            try:
                logger.info("ActionLearning shadow ranking:\n%s", self._engine.explain(ranked))
            except Exception:  # pragma: no cover
                pass
            return candidates

        order = {r["action_key"]: idx for idx, r in enumerate(ranked)}
        try:
            return sorted(candidates, key=lambda c: order.get(_coerce(c).action_key, len(order)))
        except Exception:  # pragma: no cover - defensive
            return candidates

    def record_event_outcome(self, event: "CortexEvent") -> bool:
        """Record a REAL outcome from a completed event into action statistics.

        No-op when disabled, when the event has no usable outcome, or when
        the outcome is UNKNOWN (success=None).
        """
        if not self.enabled:
            return False
        try:
            real = outcome_from_event_real(event)
            if real is None:
                return False
            situation = situation_from_event(event)
            action_type = getattr(getattr(event, "action", None), "action_type", "") or ""
            from .schema import ActionLearningCandidate
            action = ActionLearningCandidate(action_type=action_type, strategy=action_type)
            if not action.action_key:
                return False
            outcome = ActionLearningOutcome(
                success=real.success,
                actual_outcome=real.actual_outcome or "",
            )
            return self._engine.record_outcome(situation, action, outcome)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("ActionLearningBridge.record_event_outcome failed: %s", exc)
            return False
