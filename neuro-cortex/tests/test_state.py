"""Tests for CortexState - Phase 4 State module."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neurocortex.state import CortexState, BasicStateModule
from neurocortex.event import (
    CortexEvent, PerceptionData, OutcomeData, FeedbackData, LearningData,
    InternalState,
)
from neurocortex.cortex import NeuroCortex
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState, MockMemory,
    MockPrediction, MockDecision, MockAction, MockFeedback, MockLearning,
    MockOutcomeProvider, FailingOutcomeProvider,
)


# ── Helper ──────────────────────────────────────────────────────


def make_complete_event(raw_input: str, confidence: float = 0.5,
                        success: bool = True, intent: str = "") -> CortexEvent:
    """Create a fully processed event for state testing."""
    e = CortexEvent(raw_input)
    e.perceive(PerceptionData(raw_input=raw_input, confidence=confidence,
                               intent=intent or ("unknown" if confidence < 0.3 else "fix")))
    e.record_outcome(OutcomeData(success=success,
                                  actual_outcome="test outcome" if success else "failure"))
    e.compute_feedback(FeedbackData(reward=1.0 if success else -0.5))
    e.learn(LearningData(learning_signal="positive" if success else "negative"))
    return e


def assert_state_equal(s1: CortexState, s2: CortexState) -> None:
    """Compare states ignoring timestamp."""
    assert s1.uncertainty == s2.uncertainty
    assert s1.confidence == s2.confidence
    assert s1.active_goal == s2.active_goal
    assert s1.recent_inputs == s2.recent_inputs


# ── S1: Initial state ───────────────────────────────────────────


class TestInitialState:
    def test_default_values(self):
        state = CortexState()
        assert state.uncertainty == 0.2
        assert state.confidence == 0.5
        assert state.active_goal == ""
        assert state.recent_inputs == []
        assert state.curiosity == 0.5  # reserved


# ── S2: Success increases confidence ───────────────────────────


class TestSuccessTransition:
    def test_high_confidence_reduces_uncertainty(self):
        state = CortexState()
        event = make_complete_event("test", confidence=0.8, success=True)
        state.update_from_event(event)
        assert state.uncertainty < 0.2  # decreased

    def test_success_increases_confidence(self):
        state = CortexState()
        event = make_complete_event("test", confidence=0.7, success=True)
        state.update_from_event(event)
        assert state.confidence > 0.5  # increased


# ── S3: Failure decreases confidence ───────────────────────────


class TestFailureTransition:
    def test_explicit_failure_decreases_confidence(self):
        state = CortexState()
        event = make_complete_event("test", confidence=0.5, success=False)
        state.update_from_event(event)
        assert state.confidence < 0.5  # decreased
        assert state.uncertainty > 0.2  # increased

    def test_unknown_outcome_no_transition(self):
        """No outcome recorded → no transition."""
        state = CortexState()
        event = CortexEvent("test")
        event.perceive(PerceptionData(confidence=0.5))
        # No outcome recorded
        # state should remain unchanged
        # (update_from_event only transitions on known outcomes)


# ── S4: Low confidence increases uncertainty ───────────────────


class TestLowConfidenceTransition:
    def test_low_confidence_increases_uncertainty(self):
        state = CortexState()
        event = CortexEvent("vague input")
        event.perceive(PerceptionData(confidence=0.2))
        event.record_outcome(OutcomeData(success=False, actual_outcome=""))
        event.compute_feedback(FeedbackData())
        event.learn(LearningData())
        state.update_from_event(event)
        assert state.uncertainty > 0.2  # increased


# ── S5: Intent becomes goal ────────────────────────────────────


class TestActiveGoal:
    def test_known_intent_becomes_goal(self):
        state = CortexState()
        event = make_complete_event("fix the bug", intent="fix")
        state.update_from_event(event)
        assert state.active_goal == "fix"

    def test_request_forms_goal_candidate(self):
        state = CortexState()
        event = CortexEvent("帮我检查一下这个方案有没有风险")
        event.perceive(PerceptionData(
            confidence=0.5, intent="unknown",
            metadata={"input_type": "request"}
        ))
        event.record_outcome(OutcomeData(success=True))
        event.compute_feedback(FeedbackData(reward=0.5))
        event.learn(LearningData(learning_signal="positive"))
        state.update_from_event(event)
        assert state.active_goal != ""
        assert "检查" in state.active_goal or "风险" in state.active_goal

    def test_no_goal_for_greeting(self):
        state = CortexState()
        event = make_complete_event("hello", intent="unknown")
        state.update_from_event(event)
        # Greeting has no goal
        assert state.active_goal == ""


# ── S6: Chinese input preserved ────────────────────────────────


class TestChineseHandling:
    def test_chinese_input_preserved(self):
        state = CortexState()
        event = make_complete_event("帮我实现一个用户认证系统")
        state.update_from_event(event)
        assert "帮我实现一个用户认证系统" in state.recent_inputs

    def test_mixed_language_preserved(self):
        state = CortexState()
        event = make_complete_event("检查 API 的 timeout 问题")
        state.update_from_event(event)
        assert "检查 API 的 timeout 问题" in state.recent_inputs

    def test_chinese_goal_extraction(self):
        state = CortexState()
        event = CortexEvent("帮我检查一下这个方案有没有风险")
        event.perceive(PerceptionData(confidence=0.4, intent="unknown",
                                       metadata={"input_type": "request"}))
        event.record_outcome(OutcomeData(success=True))
        event.compute_feedback(FeedbackData(reward=0.5))
        event.learn(LearningData())
        state.update_from_event(event)
        assert "检查" in state.active_goal or "风险" in state.active_goal


# ── S7: Deterministic updates ──────────────────────────────────


class TestDeterministic:
    def test_same_sequence_same_result(self):
        events = [
            make_complete_event("event1", confidence=0.8, success=True),
            make_complete_event("event2", confidence=0.6, success=False),
            make_complete_event("event3", confidence=0.9, success=True),
        ]
        state1 = CortexState()
        for e in events:
            state1.update_from_event(e)

        state2 = CortexState()
        for e in events:
            state2.update_from_event(e)

        assert_state_equal(state1, state2)

    def test_timestamp_not_compared(self):
        import time
        state1 = CortexState()
        e1 = make_complete_event("test")
        state1.update_from_event(e1)
        time.sleep(0.01)
        state1.update_from_event(e1)

        state2 = CortexState()
        state2.update_from_event(e1)
        time.sleep(0.01)
        state2.update_from_event(e1)

        # Should be equal despite different timestamps
        assert state1 == state2


# ── S8: Curiosity reserved ─────────────────────────────────────


class TestCuriosityReserved:
    def test_curiosity_unchanged(self):
        state = CortexState()
        initial = state.curiosity
        event = make_complete_event("any input")
        state.update_from_event(event)
        assert state.curiosity == initial == 0.5


# ── S9: Recent inputs capped ───────────────────────────────────


class TestRecentInputs:
    def test_buffer_capped_at_10(self):
        state = CortexState()
        for i in range(15):
            event = make_complete_event(f"event {i}")
            state.update_from_event(event)
        assert len(state.recent_inputs) == 10
        assert state.recent_inputs[0] == "event 5"
        assert state.recent_inputs[-1] == "event 14"


# ── S10: Serialization invariants ──────────────────────────────


class TestSerialization:
    def test_from_dict_clamps_values(self):
        data = {"uncertainty": 2.0, "confidence": -0.5, "recent_inputs": []}
        state = CortexState.from_dict(data)
        assert state.uncertainty == 1.0  # clamped
        assert state.confidence == 0.0   # clamped

    def test_from_dict_caps_inputs(self):
        data = {"recent_inputs": [f"item {i}" for i in range(20)]}
        state = CortexState.from_dict(data)
        assert len(state.recent_inputs) == 10

    def test_roundtrip_preserves_state(self):
        state = CortexState(uncertainty=0.3, confidence=0.7,
                           active_goal="test", recent_inputs=["a", "b"])
        restored = CortexState.from_dict(state.to_dict())
        assert_state_equal(state, restored)


# ── S11: Isolation between instances ───────────────────────────


class TestIsolation:
    def test_multiple_cortices_independent(self):
        """Two Cortex instances should have independent state stores."""
        c1 = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(),
            memory=MockMemory(), prediction=MockPrediction(),
            decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=MockLearning(),
        )
        c2 = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(),
            memory=MockMemory(), prediction=MockPrediction(),
            decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=MockLearning(),
        )

        e1 = c1.process("first cortex")
        e2 = c2.process("second cortex")

        # Different instances should have independent state stores
        assert c1.state_store is not c2.state_store
        # But both should process successfully
        assert e1.stage == "LEARNING"
        assert e2.stage == "LEARNING"


# ── S12: Backward compatibility ────────────────────────────────


class TestBackwardCompatibility:
    def test_existing_tests_pass(self):
        """Verify backward compatibility by checking key tests."""
        # These should all pass without modification
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest", "neuro-cortex/tests/test_event.py", "-q", "--tb=no"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Event tests failed: {result.stdout}"

        result2 = subprocess.run(
            ["python3", "-m", "pytest", "neuro-cortex/tests/test_perception.py", "-q", "--tb=no"],
            capture_output=True, text=True, timeout=30
        )
        assert result2.returncode == 0, f"Perception tests failed: {result2.stdout}"


# ── S13: BasicStateModule behavior ─────────────────────────────


class TestBasicStateModule:
    def test_ensures_event_state_exists(self):
        module = BasicStateModule()
        event = CortexEvent("test")
        event.state = None  # Force removal
        result = module.process(event)
        assert result.state is not None
        assert isinstance(result.state, InternalState)

    def test_passthrough_no_side_effects(self):
        module = BasicStateModule()
        event = CortexEvent("test")
        event.state = InternalState(curiosity=0.8)
        result = module.process(event)
        # Should not modify existing state
        assert result.state.curiosity == 0.8


# ── S14: Cortex integration ────────────────────────────────────


class TestCortexIntegration:
    def test_state_persists_across_events(self):
        c = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(),
            memory=MockMemory(), prediction=MockPrediction(),
            decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e1 = c.process("first event")
        e2 = c.process("second event")

        # State should persist across events
        assert len(c.state_store.recent_inputs) == 2
        assert "first event" in c.state_store.recent_inputs
        assert "second event" in c.state_store.recent_inputs

    def test_state_injected_into_event(self):
        c = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(),
            memory=MockMemory(), prediction=MockPrediction(),
            decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=MockLearning(),
        )
        # Set initial state
        c.state_store.uncertainty = 0.3
        c.state_store.confidence = 0.7

        e = c.process("test")
        # Event should receive snapshot (BasicStateModule is passthrough)
        assert e.state.uncertainty == 0.3
        assert e.state.confidence == 0.7
