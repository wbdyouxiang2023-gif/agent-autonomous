"""Pattern Retriever — deterministic pattern retrieval by condition."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .pattern import Pattern

if TYPE_CHECKING:
    from .store import PatternStore


class PatternRetriever:
    """
    Retrieves relevant patterns using deterministic condition matching.

    Matching criteria:
    1. Exact intent match (highest priority)
    2. Exact action_type match
    3. Pattern confidence ranking
    4. Only active patterns are returned

    Unlike ExperienceRetriever, PatternRetriever does NOT do keyword matching.
    Patterns are matched by their structural condition (intent + action_type).
    """

    def __init__(self, store: "PatternStore", top_k: int = 3):
        self._store = store
        self._top_k = top_k

    def retrieve(
        self,
        intent: str = "",
        action_type: str = "",
    ) -> list[tuple[Pattern, float]]:
        """
        Retrieve patterns matching the given condition.

        Args:
            intent: Target intent to match
            action_type: Target action type to match

        Returns:
            List of (pattern, relevance_score) tuples sorted by confidence.
            Only active patterns are returned.
        """
        patterns = self._store.list_active()
        if not patterns:
            return []

        scored = []
        for pat in patterns:
            score = self._calculate_score(pat, intent, action_type)
            if score > 0:
                scored.append((pat, score))

        scored.sort(key=lambda x: (x[1], x[0].confidence), reverse=True)
        return scored[:self._top_k]

    def _calculate_score(
        self,
        pat: Pattern,
        query_intent: str,
        query_action_type: str,
    ) -> float:
        """
        Calculate relevance score for a pattern.

        Scoring:
          - Intent match: +0.5
          - Action type match: +0.3
          - Confidence weight: × pat.confidence
        """
        if not query_intent and not query_action_type:
            # No query condition — return all active patterns with base confidence
            return pat.confidence * 0.5

        score = 0.0

        if query_intent and pat.condition_intent == query_intent:
            score += 0.5

        if query_action_type and pat.condition_action_type == query_action_type:
            score += 0.3

        # Scale by confidence (active patterns already have confidence > 0)
        score *= max(pat.confidence, 0.1)

        return score

    def retrieve_by_intent(self, intent: str) -> list[tuple[Pattern, float]]:
        """Convenience: retrieve all patterns matching an intent."""
        return self.retrieve(intent=intent)

    def retrieve_by_condition(self, intent: str, action_type: str) -> list[tuple[Pattern, float]]:
        """Convenience: retrieve patterns matching both intent and action_type."""
        return self.retrieve(intent=intent, action_type=action_type)

    def set_top_k(self, k: int) -> None:
        """Change top-k retrieval limit."""
        self._top_k = k
