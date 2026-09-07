"""Tests for BasicRepresentation module."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neurocortex.event import CortexEvent, PerceptionData, RepresentationData
from neurocortex.representation import BasicRepresentation, EmbeddingProvider, DummyEmbeddingProvider


# ── Normal operation ───────────────────────────────────────────


class TestBasicRepresentation:
    def test_basic_transformation(self):
        rep = BasicRepresentation()
        e = CortexEvent("build the API")
        e.perceive(PerceptionData(raw_input="build the API", intent="create", confidence=0.7))
        e = rep.process(e)
        assert e.representation.raw_text == "build the API"
        assert len(e.representation.embedding) == 16  # default dim
        assert isinstance(e.representation.features, dict)

    def test_features_are_numeric(self):
        rep = BasicRepresentation()
        e = CortexEvent("hello world test")
        e.perceive(PerceptionData(raw_input="hello world test"))
        e = rep.process(e)
        for k, v in e.representation.features.items():
            assert isinstance(v, (int, float)), f"Feature {k} is {type(v)}"

    def test_embedding_is_list_of_floats(self):
        rep = BasicRepresentation()
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e = rep.process(e)
        assert isinstance(e.representation.embedding, list)
        assert all(isinstance(x, float) for x in e.representation.embedding)

    def test_embedding_dimension_stable(self):
        """Embedding dimension must be consistent across calls."""
        rep = BasicRepresentation(embedding_dim=32)
        e = CortexEvent("stable test")
        e.perceive(PerceptionData(raw_input="stable test"))
        e = rep.process(e)
        assert len(e.representation.embedding) == 32

    def test_features_contains_length_features(self):
        rep = BasicRepresentation()
        e = CortexEvent("a b c d e")
        e.perceive(PerceptionData(raw_input="a b c d e"))
        e = rep.process(e)
        feats = e.representation.features
        assert feats["token_count"] == 5
        assert feats["char_count"] == 9  # "a b c d e"
        assert feats["word_length_avg"] > 0


# ── Deterministic stability ────────────────────────────────────


class TestDeterministic:
    def test_same_input_same_embedding_10_times(self):
        """Same text must produce identical embedding 10 times."""
        rep = BasicRepresentation()
        results = []
        for _ in range(10):
            e = CortexEvent("deterministic test string")
            e.perceive(PerceptionData(raw_input="deterministic test string"))
            e = rep.process(e)
            results.append(tuple(e.representation.embedding))
        assert all(r == results[0] for r in results), "Embedding is not deterministic"

    def test_same_input_same_features_10_times(self):
        rep = BasicRepresentation()
        results = []
        for _ in range(10):
            e = CortexEvent("deterministic test string")
            e.perceive(PerceptionData(raw_input="deterministic test string"))
            e = rep.process(e)
            results.append(tuple(sorted(e.representation.features.items())))
        assert all(r == results[0] for r in results), "Features are not deterministic"

    def test_different_inputs_different_embeddings(self):
        rep = BasicRepresentation()
        e1 = CortexEvent("hello world")
        e1.perceive(PerceptionData(raw_input="hello world"))
        e1 = rep.process(e1)
        e2 = CortexEvent("goodbye world")
        e2.perceive(PerceptionData(raw_input="goodbye world"))
        e2 = rep.process(e2)
        # Different inputs should produce different embeddings
        assert e1.representation.embedding != e2.representation.embedding


# ── Edge cases ─────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_text(self):
        rep = BasicRepresentation()
        e = CortexEvent("")
        e.perceive(PerceptionData(raw_input=""))
        e = rep.process(e)
        assert e.representation.raw_text == ""
        assert e.representation.embedding == [0.5] * 16
        assert e.representation.features["token_count"] == 0

    def test_very_long_text(self):
        rep = BasicRepresentation()
        long_text = "word " * 1000
        e = CortexEvent(long_text)
        e.perceive(PerceptionData(raw_input=long_text))
        e = rep.process(e)
        assert e.representation.features["token_count"] == 1000
        assert len(e.representation.embedding) == 16

    def test_special_characters(self):
        rep = BasicRepresentation()
        e = CortexEvent("<script>alert('xss')</script> 你好 🌍")
        e.perceive(PerceptionData(raw_input="<script>alert('xss')</script> 你好 🌍"))
        e = rep.process(e)
        assert e.representation.raw_text == "<script>alert('xss')</script> 你好 🌍"
        assert len(e.representation.embedding) == 16

    def test_unicode_text(self):
        rep = BasicRepresentation()
        e = CortexEvent("中文测试 日本語テスト")
        e.perceive(PerceptionData(raw_input="中文测试 日本語テスト"))
        e = rep.process(e)
        assert e.representation.raw_text == "中文测试 日本語テスト"
        assert len(e.representation.embedding) == 16


# ── Missing perception data ────────────────────────────────────


class TestMissingPerception:
    def test_with_empty_perception(self):
        """Representation should work even if perception data is minimal."""
        rep = BasicRepresentation()
        e = CortexEvent("hello")
        # No perception set — use defaults
        e = rep.process(e)
        assert e.representation.raw_text == "hello"
        assert len(e.representation.embedding) == 16

    def test_perception_missing_entities(self):
        rep = BasicRepresentation()
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test", entities=[]))
        e = rep.process(e)
        assert e.representation.features["entity_count"] == 0.0


# ── Embedding provider replacement ────────────────────────────


class TestEmbeddingProvider:
    def test_default_provider(self):
        rep = BasicRepresentation()
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e = rep.process(e)
        assert len(e.representation.embedding) == 16
        # Default provider is EmbeddingProvider
        assert isinstance(rep._provider, EmbeddingProvider)

    def test_custom_embedding_provider(self):
        class MyProvider(EmbeddingProvider):
            def embed(self, text: str) -> list[float]:
                return [1.0, 2.0, 3.0] + [0.0] * 13

        rep = BasicRepresentation(embedding_dim=16, embedding_provider=MyProvider())
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e = rep.process(e)
        assert e.representation.embedding == [1.0, 2.0, 3.0] + [0.0] * 13

    def test_dummy_provider_for_testing(self):
        rep = BasicRepresentation(embedding_dim=8, embedding_provider=DummyEmbeddingProvider(8))
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e = rep.process(e)
        assert e.representation.embedding == [0.0] * 8
        # Deterministic — same every time
        e2 = rep.process(CortexEvent("test"))
        e2.perceive(PerceptionData(raw_input="test"))
        assert e2.representation.embedding == [0.0] * 8


# ── Feature structure ──────────────────────────────────────────


class TestFeatureStructure:
    def test_required_features_present(self):
        rep = BasicRepresentation()
        e = CortexEvent("hello world")
        e.perceive(PerceptionData(raw_input="hello world"))
        e = rep.process(e)
        required = ["token_count", "char_count", "word_length_avg", "max_word_length",
                     "intent_confidence", "risk_score", "entity_count",
                     "uppercase_ratio", "digit_ratio", "punctuation_ratio"]
        for f in required:
            assert f in e.representation.features, f"Missing feature: {f}"

    def test_ngram_features_present(self):
        rep = BasicRepresentation()
        e = CortexEvent("hello world test")
        e.perceive(PerceptionData(raw_input="hello world test"))
        e = rep.process(e)
        feats = e.representation.features
        assert "char_bigram_2gram_count" in feats
        assert "char_bigram_3gram_count" in feats
        assert "word_bigram_count" in feats


# ── Cortex pipeline integration ────────────────────────────────


class TestPipelineIntegration:
    def test_representation_receives_perception_data(self):
        """Representation should be able to read from the event's perception field."""
        from neurocortex.perception import BasicPerception
        rep = BasicRepresentation()
        perc = BasicPerception()

        e = CortexEvent("fix the auth bug")
        e = perc.process(e)           # fills perception
        e = rep.process(e)            # reads perception, produces representation
        assert e.representation.raw_text == "fix the auth bug"
        assert e.representation.features["token_count"] == 4
        assert len(e.representation.embedding) == 16
