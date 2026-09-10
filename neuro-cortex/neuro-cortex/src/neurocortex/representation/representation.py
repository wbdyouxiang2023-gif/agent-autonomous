"""Representation module — converts PerceptionData into machine-processable representation."""

from __future__ import annotations

from typing import Any
import math

from ..event import CortexEvent, RepresentationData
from ..interfaces import RepresentationModule


class EmbeddingProvider:
    """
    Protocol-like base class for embedding providers.

    Subclasses must implement `embed(text: str) -> list[float]`.
    This is NOT an ABC — it provides a default fallback so concrete
    implementations can be mixed in without strict interface enforcement.
    """

    def embed(self, text: str) -> list[float]:
        """
        Convert text to a numeric vector.

        Default: deterministic hash-based embedding (stable, no model).
        For production: replace with a real embedding provider.
        """
        return self._hash_embedding(text, dim=16)

    @staticmethod
    def _hash_embedding(text: str, dim: int = 16) -> list[float]:
        """
        Deterministic hash-based embedding.
        Same input always produces same output.
        Values are in [-1, 1] range, normalized to [0, 1].
        """
        if not text:
            return [0.5] * dim
        # Use multiple hash functions for better distribution
        vectors: list[list[float]] = []
        for seed in range(3):
            h = hash((text, seed)) & 0xFFFFFFFF
            component = []
            for i in range(dim):
                h = ((h ^ (h >> 16)) * 0x45d9f3b) & 0xFFFFFFFF
                component.append((h & 0xFF) / 255.0)
            vectors.append(component)
        # Average across hash functions
        result = []
        for i in range(dim):
            avg = sum(v[i] for v in vectors) / len(vectors)
            result.append(round(avg, 4))
        return result


class BasicRepresentation(RepresentationModule):
    """
    Deterministic representation module.

    Converts PerceptionData into:
    - structured_features: named numeric features
    - embedding: fixed-dimension vector
    - raw_text: preserved original text
    """

    def __init__(self, embedding_dim: int = 16, embedding_provider: EmbeddingProvider | None = None) -> None:
        self._dim = embedding_dim
        self._provider = embedding_provider or EmbeddingProvider()

    def process(self, event: CortexEvent) -> CortexEvent:
        perf = event.perception
        features = self._extract_features(perf, event.raw_input)
        embedding = self._provider.embed(event.raw_input)
        # Ensure embedding dimension matches expected
        if len(embedding) != self._dim:
            embedding = self._pad_or_truncate(embedding, self._dim)

        event.represent(RepresentationData(
            raw_text=event.raw_input,
            features=features,
            embedding=embedding,
        ))
        return event

    def _extract_features(self, perf: "PerceptionData", text: str) -> dict[str, float]:
        """Extract deterministic numeric features from perception data and raw text."""
        tokens = text.split() if text else []
        chars = list(text) if text else []

        features: dict[str, float] = {
            # Length features
            "token_count": len(tokens),
            "char_count": len(chars),
            "word_length_avg": sum(len(t) for t in tokens) / max(len(tokens), 1),
            "max_word_length": max((len(t) for t in tokens), default=0),

            # Perception-derived features
            "intent_confidence": perf.confidence,
            "risk_score": perf.risk,
            "entity_count": float(len(perf.entities)),

            # Statistical features
            "uppercase_ratio": sum(1 for c in chars if c.isupper()) / max(len(chars), 1),
            "digit_ratio": sum(1 for c in chars if c.isdigit()) / max(len(chars), 1),
            "punctuation_ratio": sum(1 for c in chars if c in "!?,.;:()[]{}\"'") / max(len(chars), 1),
            "space_ratio": chars.count(" ") / max(len(chars), 1),
            "question_mark_ratio": chars.count("?") / max(len(chars), 1),
        }

        # N-gram features (character-level, deterministic)
        for n in (2, 3):
            ngrams = [text[i:i+n] for i in range(len(text) - n + 1)] if len(text) >= n else []
            features[f"char_bigram_{n}gram_count"] = len(ngrams)
            # First n-gram hash as a signature feature
            if ngrams:
                h = hash(ngrams[0]) & 0xFFFF
                features[f"char_{n}gram_signature"] = h / 65535.0

        # Word n-gram features
        if len(tokens) >= 2:
            bigrams = [" ".join(tokens[i:i+2]) for i in range(len(tokens) - 1)]
            features["word_bigram_count"] = len(bigrams)
        else:
            features["word_bigram_count"] = 0

        return features

    @staticmethod
    def _pad_or_truncate(vec: list[float], dim: int) -> list[float]:
        if len(vec) == dim:
            return vec
        if len(vec) < dim:
            return vec + [0.5] * (dim - len(vec))
        return vec[:dim]


class DummyEmbeddingProvider(EmbeddingProvider):
    """Embedding provider that returns zeros — useful for testing dimension stability."""

    def __init__(self, dim: int = 16) -> None:
        self._dim = dim

    def embed(self, text: str) -> list[float]:
        return [0.0] * self._dim
