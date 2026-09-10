"""Phase 9 — Cross-Event Learning Loop Tests (v1)."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neurocortex.event import (
    CortexEvent,
    PerceptionData,
    InternalState,
    PredictionData,
    DecisionData,
    ActionData,
    OutcomeData,
    FeedbackData,
    MemoryData,
    AttentionData,
    RepresentationData,
    LearningData,
)
from neurocortex.cortex import NeuroCortex
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState,
    MockMemory, MockPrediction, MockDecision, MockAction,
    MockOutcomeProvider, MockFeedback, MockLearning,
)
from neurocortex.state import BasicStateModule, CortexState
from neurocortex.prediction import BasicPrediction
from neurocortex.interfaces import OutcomeProvider


# ── Helpers ───────────────────────────────────────────────────────


class FailingOutcomeProviderImpl(OutcomeProvider):
    """Outcome provider that reports failure without raising."""

    def provide(self, event: CortexEvent) -> CortexEvent:
        event.record_outcome(OutcomeData(
            actual_outcome="outcome failed",
            success=False,
            error_message="simulated failure",
        ))
        return event


def make_cortex_with_basic_state(**kwargs) -> NeuroCortex:
    """Create a Cortex with BasicStateModule for integration tests."""
    return NeuroCortex(
        perception=MockPerception(),
        representation=MockRepresentation(),
        attention=MockAttention(),
        state=BasicStateModule(),  # Key: use BasicStateModule, not MockState
        memory=MockMemory(),
        prediction=BasicPrediction(),  # Key: use BasicPrediction to see state
        decision=MockDecision(),
        action=MockAction(),
        outcome_provider=kwargs.get("outcome_provider", MockOutcomeProvider()),
        feedback=MockFeedback(),
        learning=MockLearning(),
    )


def make_cortex_with_mock_state(**kwargs) -> NeuroCortex:
    """Create a Cortex with MockState for regression tests."""
    return NeuroCortex(
        perception=MockPerception(),
        representation=MockRepresentation(),
        attention=MockAttention(),
        state=MockState(),  # Original behavior for regression
        memory=MockMemory(),
        prediction=MockPrediction(),
        decision=MockDecision(),
        action=MockAction(),
        outcome_provider=kwargs.get("outcome_provider", MockOutcomeProvider()),
        feedback=MockFeedback(),
        learning=MockLearning(),
    )


# ═══════════════════════════════════════════════════════════════════
# TEST SUITE — 12 Cases
# ═══════════════════════════════════════════════════════════════════


# ── T01: Initial State ───────────────────────────────────────────
class TestT01InitialState:
    def test_initial_cortex_state(self):
        """Verify initial CortexState values."""
        c = make_cortex_with_basic_state()
        assert c.state_store.uncertainty == 0.20
        assert c.state_store.confidence == 0.50
        assert c.state_store.active_goal == ""
        assert c.state_store.recent_inputs == []


# ── T02: Success Propagation ─────────────────────────────────────
class TestT02SuccessPropagation:
    def test_success_propagates_to_next_event(self):
        """Event 1 success → Event 2 inherits learned state."""
        c = make_cortex_with_basic_state()
        
        # Event 1
        e1 = c.process("fix a bug")
        assert e1.outcome.success is True
        assert c.state_store.confidence == pytest.approx(0.55)
        assert c.state_store.uncertainty == pytest.approx(0.15)
        
        # Event 2 — must inherit Event 1's learning
        e2 = c.process("fix another bug")
        assert e2.state.confidence == pytest.approx(0.55)
        assert e2.state.uncertainty == pytest.approx(0.15)
        assert e2.outcome.success is True
        
        # Event 2 learning should further update CortexState
        assert c.state_store.confidence == pytest.approx(0.60)
        assert c.state_store.uncertainty == pytest.approx(0.10)


# ── T03: Failure Propagation ─────────────────────────────────────
class TestT03FailurePropagation:
    def test_failure_propagates_to_next_event(self):
        """Event 1 failure → Event 2 inherits learned state."""
        c = make_cortex_with_basic_state(
            outcome_provider=FailingOutcomeProviderImpl()
        )
        
        # Event 1: failure + high perception conf → net uncertainty +0.05
        e1 = c.process("fix a bug")
        assert e1.outcome.success is False
        # cortex_state: uncertainty += 0.1 (failure) - 0.05 (high perf_conf) = +0.05
        assert c.state_store.confidence == pytest.approx(0.40)
        assert c.state_store.uncertainty == pytest.approx(0.25)
        
        # Event 2 — must inherit Event 1's learning
        e2 = c.process("fix another bug")
        assert e2.state.confidence == pytest.approx(0.40)
        assert e2.state.uncertainty == pytest.approx(0.25)
        assert e2.outcome.success is False
        
        # Event 2 learning: uncertainty += 0.05 again
        assert c.state_store.confidence == pytest.approx(0.30)
        assert c.state_store.uncertainty == pytest.approx(0.30)


# ── T04: Three Consecutive Successes ─────────────────────────────
class TestT04ThreeSuccesses:
    def test_three_consecutive_successes(self):
        """Track state at each event boundary."""
        c = make_cortex_with_basic_state()
        
        # Event 1
        e1 = c.process("fix a bug")
        assert e1.state.confidence == pytest.approx(0.50)
        assert e1.state.uncertainty == pytest.approx(0.20)
        assert c.state_store.confidence == pytest.approx(0.55)
        assert c.state_store.uncertainty == pytest.approx(0.15)
        
        # Event 2
        e2 = c.process("fix another bug")
        assert e2.state.confidence == pytest.approx(0.55)
        assert e2.state.uncertainty == pytest.approx(0.15)
        assert c.state_store.confidence == pytest.approx(0.60)
        assert c.state_store.uncertainty == pytest.approx(0.10)
        
        # Event 3
        e3 = c.process("fix yet another bug")
        assert e3.state.confidence == pytest.approx(0.60)
        assert e3.state.uncertainty == pytest.approx(0.10)
        assert c.state_store.confidence == pytest.approx(0.65)
        assert c.state_store.uncertainty == pytest.approx(0.05)


# ── T05: Three Consecutive Failures ──────────────────────────────
class TestT05ThreeFailures:
    def test_three_consecutive_failures(self):
        """Track state at each event boundary."""
        c = make_cortex_with_basic_state(
            outcome_provider=FailingOutcomeProviderImpl()
        )
        
        # Event 1: failure + high perception conf → net uncertainty +0.05
        e1 = c.process("fix a bug")
        assert e1.state.confidence == pytest.approx(0.50)
        assert e1.state.uncertainty == pytest.approx(0.20)
        assert c.state_store.confidence == pytest.approx(0.40)
        assert c.state_store.uncertainty == pytest.approx(0.25)
        
        # Event 2: inherits 0.40/0.25, then learns again
        e2 = c.process("fix another bug")
        assert e2.state.confidence == pytest.approx(0.40)
        assert e2.state.uncertainty == pytest.approx(0.25)
        assert c.state_store.confidence == pytest.approx(0.30)
        assert c.state_store.uncertainty == pytest.approx(0.30)
        
        # Event 3: inherits 0.30/0.30, then learns again
        e3 = c.process("fix yet another bug")
        assert e3.state.confidence == pytest.approx(0.30)
        assert e3.state.uncertainty == pytest.approx(0.30)
        assert c.state_store.confidence == pytest.approx(0.20)
        assert c.state_store.uncertainty == pytest.approx(0.35)


# ── T06: New Event Object ────────────────────────────────────────
class TestT06NewEventObject:
    def test_new_event_is_independent_object(self):
        """Event 2 must be a new CortexEvent, not a reference to Event 1."""
        c = make_cortex_with_basic_state()
        e1 = c.process("fix a bug")
        e2 = c.process("fix another bug")
        
        assert e1 is not e2
        assert id(e1) != id(e2)


# ── T07: State Snapshot Isolation ────────────────────────────────
class TestT07StateSnapshotIsolation:
    def test_event_state_snapshot_is_isolated(self):
        """Modifying event1.state must not affect event2 or CortexState."""
        c = make_cortex_with_basic_state()
        e1 = c.process("fix a bug")
        e2 = c.process("fix another bug")
        
        # Modify e1.state
        original_e2_conf = e2.state.confidence
        e1.state.confidence = 0.99
        
        # e2.state must be unchanged
        assert e2.state.confidence == original_e2_conf
        
        # CortexState must be unchanged
        assert c.state_store.confidence != 0.99


# ── T08: Cortex Isolation ───────────────────────────────────────
class TestT08CortexIsolation:
    def test_two_cortex_instances_are_independent(self):
        """Cortex A and B must have independent state."""
        c_a = make_cortex_with_basic_state()
        c_b = make_cortex_with_basic_state()
        
        # A learns
        for _ in range(3):
            c_a.process("fix a bug")
        
        # B doesn't learn from A
        e_b = c_b.process("fix a bug")
        
        assert c_a.state_store.confidence > c_b.state_store.confidence
        assert c_a.state_store is not c_b.state_store
        assert e_b.state.confidence == 0.50  # B starts fresh


# ── T09: Prediction Sees Learned State ───────────────────────────
class TestT09PredictionPropagation:
    def test_prediction_reads_learned_uncertainty(self):
        """BasicPrediction must read event.state.uncertainty, not initial value."""
        c = make_cortex_with_basic_state()
        
        # Event 1: initial uncertainty = 0.20
        e1 = c.process("fix a bug")
        p1 = e1.prediction.success_probability
        
        # Event 2: uncertainty should be 0.15 (learned)
        e2 = c.process("fix another bug")
        p2 = e2.prediction.success_probability
        
        # Verify state was learned correctly
        assert e2.state.uncertainty == pytest.approx(0.15)
        assert e2.state.confidence == pytest.approx(0.55)
        
        # Verify BasicPrediction reads the learned state
        # With uncertainty=0.15 < 0.4, it should take "clear signal" path
        assert e2.prediction.predicted_outcome == "fix完成"


# ── T10: MockState Regression ────────────────────────────────────
class TestT10MockStateRegression:
    def test_mock_state_behavior_unchanged(self):
        """MockState must continue to compute from input length."""
        c = make_cortex_with_mock_state()
        
        e1 = c.process("x")  # short input
        e2 = c.process("a" * 100)  # long input
        
        # MockState computes uncertainty from input length
        # Short input → high uncertainty
        # Long input → low uncertainty
        assert e1.state.uncertainty > e2.state.uncertainty
        
        # MockState ignores CortexState learning
        # So even after learning, next event resets
        assert c.state_store.uncertainty < 0.20  # Learned
        assert e2.state.uncertainty == 1.0 - min(100/100, 1.0)  # MockState ignores learning


# ── T11: Full Lifecycle with BasicStateModule ───────────────────
class TestT11FullLifecycle:
    def test_full_lifecycle_reaches_learning(self):
        """Complete pipeline must reach LEARNING stage."""
        c = make_cortex_with_basic_state()
        e = c.process("fix a bug")
        
        assert e.stage == "LEARNING"
        assert e.status == "ok"
        assert e.outcome.success is True
        assert e.feedback.evaluation != ""
        assert e.learning.learning_signal != ""


# ── T12: Regression — 334 Existing Tests ────────────────────────
class TestT12Regression:
    def test_all_existing_tests_pass(self):
        """Run all Phase 0-8 tests; must not regress."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest",
             "neuro-cortex/tests/test_event.py",
             "neuro-cortex/tests/test_perception.py",
             "neuro-cortex/tests/test_representation.py",
             "neuro-cortex/tests/test_state.py",
             "neuro-cortex/tests/test_cortex.py",
             "neuro-cortex/tests/test_prediction.py",
             "neuro-cortex/tests/test_phase0.py",
             "neuro-cortex/tests/test_feedback.py",
             "neuro-cortex/tests/test_decision.py",
             "neuro-cortex/tests/test_action.py",
             "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"Regression failed:\n{result.stdout}\n{result.stderr}"
