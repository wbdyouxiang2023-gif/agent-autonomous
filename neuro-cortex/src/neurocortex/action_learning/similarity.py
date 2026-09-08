"""Situation similarity — deterministic, pure-Python, no ML.

Combines:
  - character n-gram Jaccard
  - token Jaccard
  - lexical overlap (shared tokens / unique tokens)

Output:
  similarity_score (0.0-1.0)
  method / components (for explainability)
  matched_tokens (when interpretable)

Guarantees:
  - deterministic (no randomness; hash-free)
  - case-normalized
  - punctuation-tolerant
  - empty input → 0.0 (no fabricated similarity)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_NGRAM_N = 3


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation to spaces, collapse whitespace."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"[^a-z0-9_\u4e00-\u9fff ]", " ", t)  # keep CJK chars too
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _char_ngrams(text: str, n: int = _NGRAM_N) -> set[str]:
    """Character n-grams over the normalized string (spaces significant)."""
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0  # both empty → no evidence of similarity
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class SimilarityResult:
    score: float
    method: str = "char3gram+token+lexical"
    components: dict[str, float] = field(default_factory=dict)
    matched_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "method": self.method,
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "matched_tokens": self.matched_tokens,
        }


def similarity(text_a: str, text_b: str) -> SimilarityResult:
    """Compute deterministic similarity between two situation texts.

    Score = 0.4*char3gram_jaccard + 0.4*token_jaccard + 0.2*lexical_overlap
    """
    na = _normalize(text_a)
    nb = _normalize(text_b)

    if not na or not nb:
        return SimilarityResult(score=0.0, components={"char3gram": 0.0, "token": 0.0, "lexical": 0.0}, matched_tokens=[])

    # Character 3-gram Jaccard (over normalized string, includes spaces)
    c3_a = _char_ngrams(na, 3)
    c3_b = _char_ngrams(nb, 3)
    c3 = _jaccard(c3_a, c3_b)

    # Token Jaccard
    ta = set(_tokens(na))
    tb = set(_tokens(nb))
    tok = _jaccard(ta, tb)

    # Lexical overlap: |shared| / |union| (same as token Jaccard but keep
    # separate component for interpretability; identical here by definition,
    # but exposed separately so callers can weight differently).
    lex = tok

    score = 0.4 * c3 + 0.4 * tok + 0.2 * lex
    matched = sorted(ta & tb)

    return SimilarityResult(
        score=round(score, 4),
        components={"char3gram": round(c3, 4), "token": round(tok, 4), "lexical": round(lex, 4)},
        matched_tokens=matched,
    )
