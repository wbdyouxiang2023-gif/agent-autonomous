"""Experience Retriever — deterministic keyword-based retrieval."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..event import Experience

if TYPE_CHECKING:
    from .experience_store import ExperienceStore


class ExperienceRetriever:
    """
    Retrieves relevant experiences using deterministic keyword matching.

    Ranking criteria:
    1. Tag overlap (intent, action, outcome tags)
    2. Keyword overlap in raw_input
    3. Confidence weighting
    4. Recency (newer experiences weighted slightly higher)
    """

    def __init__(self, store: "ExperienceStore", top_k: int = 3):
        self._store = store
        self._top_k = top_k

    def retrieve(
        self,
        raw_input: str,
        intent: str = "",
        action_type: str = "",
        success: bool | None = None,
    ) -> list[tuple[Experience, float]]:
        """
        Retrieve relevant experiences sorted by relevance score.

        Returns list of (experience, score) tuples.
        Score is between 0.0 and 1.0.
        """
        experiences = self._store.list_all()
        if not experiences:
            return []

        # Extract query keywords
        query_tags = set()
        if intent:
            query_tags.add(f"intent:{intent}")
        if action_type:
            query_tags.add(f"action:{action_type}")
        if success is not None:
            tag = "outcome:success" if success else "outcome:failure"
            query_tags.add(tag)

        query_keywords = set(raw_input.lower().split()) if raw_input.strip() else set()

        scored = []
        for exp in experiences:
            score = self._calculate_score(exp, query_tags, query_keywords)
            if score > 0:
                scored.append((exp, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:self._top_k]

    def _calculate_score(
        self,
        exp: Experience,
        query_tags: set[str],
        query_keywords: set[str],
    ) -> float:
        """Calculate relevance score for an experience."""
        score = 0.0

        # Tag matching (highest weight)
        exp_tags = set(exp.context_tags)
        tag_overlap = len(query_tags & exp_tags)
        if tag_overlap > 0:
            score += tag_overlap * 0.4

        # Keyword overlap
        exp_keywords = set(exp.raw_input.lower().split()) if exp.raw_input.strip() else set()
        keyword_overlap = len(query_keywords & exp_keywords)
        if keyword_overlap > 0:
            score += min(keyword_overlap * 0.1, 0.3)

        # Confidence weighting
        if exp.confidence > 0:
            score += exp.confidence * 0.1

        return min(score, 1.0)

    def set_top_k(self, k: int) -> None:
        """Change top-k retrieval limit."""
        self._top_k = k
