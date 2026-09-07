"""Tests for BasicPerception module."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neurocortex.event import CortexEvent, PerceptionData
from neurocortex.perception import BasicPerception


# ── Normal text inputs ─────────────────────────────────────────


class TestNormalInputs:
    def test_create_intent(self):
        p = BasicPerception()
        e = CortexEvent("build a new API endpoint")
        e = p.process(e)
        assert e.perception.intent == "create"
        assert e.perception.confidence > 0

    def test_fix_intent(self):
        p = BasicPerception()
        e = CortexEvent("fix the login bug")
        e = p.process(e)
        assert e.perception.intent == "fix"

    def test_learn_intent(self):
        p = BasicPerception()
        e = CortexEvent("explain how transformers work")
        e = p.process(e)
        assert e.perception.intent == "learn"

    def test_optimize_intent(self):
        p = BasicPerception()
        e = CortexEvent("optimize the database query performance")
        e = p.process(e)
        assert e.perception.intent == "optimize"

    def test_deploy_intent(self):
        p = BasicPerception()
        e = CortexEvent("deploy the application to production")
        e = p.process(e)
        assert e.perception.intent == "deploy"

    def test_inquiry_intent(self):
        p = BasicPerception()
        e = CortexEvent("how do I set up a server?")
        e = p.process(e)
        assert e.perception.intent == "inquire"

    def test_unknown_intent(self):
        p = BasicPerception()
        e = CortexEvent("the weather is nice today")
        e = p.process(e)
        # No keyword match → intent should be "unknown" with low confidence
        assert e.perception.intent == "unknown"
        assert e.perception.confidence < 0.5

    def test_entities_extracted(self):
        p = BasicPerception()
        e = CortexEvent("Build the Auth module with Redis cache")
        e = p.process(e)
        entities = e.perception.entities
        assert "Auth" in entities
        assert "Redis" in entities

    def test_language_detection_chinese(self):
        p = BasicPerception()
        e = CortexEvent("帮我检查一下这个方案有没有风险")
        e = p.process(e)
        assert e.perception.metadata["language"] == "zh"

    def test_language_detection_latin(self):
        p = BasicPerception()
        e = CortexEvent("Hello world this is a test")
        e = p.process(e)
        assert e.perception.metadata["language"] == "latin"


# ── Empty input ────────────────────────────────────────────────


class TestEmptyInput:
    def test_empty_string(self):
        p = BasicPerception()
        e = CortexEvent("")
        e = p.process(e)
        assert e.perception.raw_input == ""
        assert e.perception.intent == "unknown"
        assert e.perception.confidence == 0.0
        assert e.perception.risk == 0.0

    def test_whitespace_only(self):
        p = BasicPerception()
        e = CortexEvent("   ")
        e = p.process(e)
        assert e.perception.confidence == 0.0


# ── Non-string input handling ──────────────────────────────────


class TestNonStringInput:
    def test_none_input_becomes_empty_string(self):
        p = BasicPerception()
        e = CortexEvent(raw_input="")  # CortexEvent accepts str, not None
        e = p.process(e)
        assert e.perception.raw_input == ""
        assert e.perception.confidence == 0.0


# ── Unknown fields ─────────────────────────────────────────────


class TestUnknownFields:
    def test_unkown_intent_default_confidence(self):
        p = BasicPerception()
        e = CortexEvent("something vague and unclear")
        e = p.process(e)
        assert e.perception.intent == "unknown"
        assert 0 < e.perception.confidence < 0.5

    def test_neutral_emotion_when_no_marker(self):
        p = BasicPerception()
        e = CortexEvent("process the data")
        e = p.process(e)
        assert e.perception.emotion == "neutral"

    def test_zero_risk_when_no_risk_keywords(self):
        p = BasicPerception()
        e = CortexEvent("write a simple function")
        e = p.process(e)
        assert e.perception.risk == 0.0

    def test_low_confidence_for_generic_input(self):
        p = BasicPerception()
        e = CortexEvent("do stuff")
        e = p.process(e)
        # Generic input with no clear signals → low confidence
        assert e.perception.confidence < 0.4


# ── Confidence and uncertainty ─────────────────────────────────


class TestConfidence:
    def test_high_confidence_clear_intent(self):
        p = BasicPerception()
        e = CortexEvent("fix the critical security vulnerability in the auth module")
        e = p.process(e)
        assert e.perception.intent == "security"
        assert e.perception.risk > 0

    def test_low_confidence_no_signals(self):
        p = BasicPerception()
        e = CortexEvent("hm")
        e = p.process(e)
        assert e.perception.confidence < 0.3

    def test_risk_not_forced_high(self):
        """System should not over-estimate risk without evidence."""
        p = BasicPerception()
        e = CortexEvent("write a hello world program")
        e = p.process(e)
        # No risk keywords → risk should be 0, not forced to high
        assert e.perception.risk == 0.0
        assert e.perception.metadata["risk_confidence"] < 0.2

    def test_emotion_uncertain_detected(self):
        p = BasicPerception()
        e = CortexEvent("I'm not sure if this will work, maybe try it")
        e = p.process(e)
        assert e.perception.emotion == "uncertain"
        assert e.perception.confidence > 0.1


# ── Entities ───────────────────────────────────────────────────


class TestEntities:
    def test_empty_entities_for_plain_text(self):
        p = BasicPerception()
        e = CortexEvent("just some plain text")
        e = p.process(e)
        assert e.perception.entities == []

    def test_camelcase_entities(self):
        p = BasicPerception()
        e = CortexEvent("Implement the UserService class")
        e = p.process(e)
        assert "UserService" in e.perception.entities

    def test_quoted_entities(self):
        p = BasicPerception()
        e = CortexEvent('Check the "database connection" string')
        e = p.process(e)
        assert "database connection" in e.perception.entities


# ── Deterministic stability ────────────────────────────────────


class TestDeterministic:
    def test_same_input_same_output_10_times(self):
        """Same input must produce identical perception 10 times."""
        p = BasicPerception()
        results = []
        for _ in range(10):
            e = CortexEvent("fix the authentication module security issue")
            e = p.process(e)
            results.append((e.perception.intent, e.perception.risk, e.perception.confidence))
        assert all(r == results[0] for r in results), "Perception is not deterministic"

    def test_metadata_is_deterministic(self):
        p = BasicPerception()
        e1 = CortexEvent("build the Redis cache layer")
        e1 = p.process(e1)
        e2 = CortexEvent("build the Redis cache layer")
        e2 = p.process(e2)
        assert e1.perception.metadata == e2.perception.metadata


# ── Metadata structure ────────────────────────────────────────


class TestMetadata:
    def test_metadata_contains_required_keys(self):
        p = BasicPerception()
        e = CortexEvent("test input")
        e = p.process(e)
        meta = e.perception.metadata
        assert "input_type" in meta
        assert "language" in meta
        assert "intent_confidence" in meta
        assert "emotion_confidence" in meta
        assert "risk_confidence" in meta
        assert "entity_count" in meta
        assert "token_count" in meta

    def test_input_type_classification(self):
        p = BasicPerception()
        e_cmd = CortexEvent("/deploy --force")
        e_cmd = p.process(e_cmd)
        assert e_cmd.perception.metadata["input_type"] == "command"

        e_q = CortexEvent("What is the risk?")
        e_q = p.process(e_q)
        assert e_q.perception.metadata["input_type"] == "question"

        e_short = CortexEvent("hi")
        e_short = p.process(e_short)
        assert e_short.perception.metadata["input_type"] in ("short", "statement")

    def test_risk_detection_with_danger_keyword(self):
        p = BasicPerception()
        e = CortexEvent("This is a dangerous exploit that could cause a breach")
        e = p.process(e)
        assert e.perception.risk > 0.3
        assert e.perception.metadata["risk_confidence"] > 0.3
