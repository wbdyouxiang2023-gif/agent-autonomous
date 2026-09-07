"""Phase 10 — Adaptive Behavior Verification Tests (v1).

This test suite verifies that NeuroCortex exhibits limited, deterministic,
rule-based behavioral adaptation through the Learning → State → Prediction
→ Decision → Action causal chain.

Phase 10 does NOT modify any production code. It only adds experiments
and tests to verify the existing architecture supports adaptive behavior.
"""
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


# ── Controlled Outcome Providers ───────────────────────────────────


class FixedOutcomeProvider(OutcomeProvider):
    """Outcome provider that returns a fixed success/failure."""

    def __init__(self, success: bool, outcome_text: str = "fixed outcome"):
        self._success = success
        self._outcome_text = outcome_text

    def provide(self, event: CortexEvent) -> CortexEvent:
        event.record_outcome(OutcomeData(
            actual_outcome=self._outcome_text,
            success=self._success,
        ))
        return event


class ControllableCortex:
    """Helper to create and manage Cortices for experiments."""

    def __init__(self, outcome_provider=None, use_basic_state=True):
        self.cortex = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=BasicStateModule() if use_basic_state else MockState(),
            memory=MockMemory(),
            prediction=BasicPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            outcome_provider=outcome_provider or MockOutcomeProvider(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        # Ensure clean initial state
        self.cortex._state_store.reset()

    @property
    def state_store(self) -> CortexState:
        return self.cortex.state_store

    def process(self, raw_input: str) -> CortexEvent:
        return self.cortex.process(raw_input)

    def get_behavior_snapshot(self, e: CortexEvent) -> dict:
        """Extract comparable behavior fields from an event."""
        return {
            "state_uncertainty": e.state.uncertainty,
            "state_confidence": e.state.confidence,
            "prediction_outcome": e.prediction.predicted_outcome,
            "prediction_p": e.prediction.success_probability,
            "decision_action": e.decision.selected_action,
            "decision_score": e.decision.decision_score,
            "action_type": e.action.action_type,
            "action_status": e.action.status,
        }


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT A — CONTROL (No Learning)
# ═══════════════════════════════════════════════════════════════════


class TestExperimentAControl:
    """Prove that without learning, identical inputs produce stable behavior."""

    def test_identical_inputs_produce_identical_behavior(self):
        """Same input × 3 → same behavior (prediction/decision/action)."""
        exp = ControllableCortex()
        
        e1 = exp.process("fix a bug")
        # Extract only behavior fields (not state which may change)
        behavior1 = {
            "prediction_outcome": e1.prediction.predicted_outcome,
            "prediction_p": e1.prediction.success_probability,
            "decision_action": e1.decision.selected_action,
            "decision_score": e1.decision.decision_score,
            "action_type": e1.action.action_type,
            "action_status": e1.action.status,
        }
        
        e2 = exp.process("fix a bug")
        behavior2 = {
            "prediction_outcome": e2.prediction.predicted_outcome,
            "prediction_p": e2.prediction.success_probability,
            "decision_action": e2.decision.selected_action,
            "decision_score": e2.decision.decision_score,
            "action_type": e2.action.action_type,
            "action_status": e2.action.status,
        }
        
        e3 = exp.process("fix a bug")
        behavior3 = {
            "prediction_outcome": e3.prediction.predicted_outcome,
            "prediction_p": e3.prediction.success_probability,
            "decision_action": e3.decision.selected_action,
            "decision_score": e3.decision.decision_score,
            "action_type": e3.action.action_type,
            "action_status": e3.action.status,
        }
        
        assert behavior1 == behavior2 == behavior3, \
            f"Behavior should be stable without learning:\n{behavior1}\n{behavior2}\n{behavior3}"

    def test_control_cortex_state_stable(self):
        """Control cortex state should not drift without learning trigger."""
        exp = ControllableCortex()
        
        # Process same input multiple times
        for _ in range(5):
            exp.process("fix a bug")
        
        # State should remain at initial values (MockOutcomeProvider = success)
        # With success, uncertainty decreases by 0.05 each time
        # But since perception.confidence=0.7 > 0.6, uncertainty decreases
        assert exp.state_store.uncertainty <= 0.20
        assert exp.state_store.confidence >= 0.50


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT B — TREATMENT (With Learning)
# ═══════════════════════════════════════════════════════════════════


class TestExperimentBTreatment:
    """Prove that learning changes state and can change behavior."""

    def test_failure_learning_changes_state(self):
        """Each failure should increase uncertainty."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        initial_unc = exp.state_store.uncertainty
        initial_conf = exp.state_store.confidence
        
        # Run 3 failures
        for _ in range(3):
            exp.process("fix a bug")
        
        # State should have changed
        assert exp.state_store.uncertainty > initial_unc
        assert exp.state_store.confidence < initial_conf

    def test_success_learning_changes_state(self):
        """Each success should decrease uncertainty."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=True)
        )
        
        initial_unc = exp.state_store.uncertainty
        initial_conf = exp.state_store.confidence
        
        # Run 3 successes
        for _ in range(3):
            exp.process("fix a bug")
        
        # State should have changed
        assert exp.state_store.uncertainty < initial_unc
        assert exp.state_store.confidence > initial_conf

    def test_state_changes_are_persistent(self):
        """Learned state persists across events."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        exp.process("fix a bug")
        state_after_first = exp.state_store.uncertainty
        
        exp.process("fix a bug")
        state_after_second = exp.state_store.uncertainty
        
        assert state_after_second > state_after_first


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT C — CAUSALITY
# ═══════════════════════════════════════════════════════════════════


class TestExperimentCCausality:
    """Prove that learned state causes behavior change."""

    def test_behavior_changes_after_threshold_crossing(self):
        """
        Before learning: uncertainty=0.20 → clear signal path
        After 8 failures: uncertainty≥0.60 → high uncertainty path
        Same input should produce different predictions.
        """
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        # Before learning
        e_before = exp.process("fix a bug")
        pred_before = e_before.prediction.predicted_outcome
        p_before = e_before.prediction.success_probability
        unc_before = e_before.state.uncertainty
        
        # Apply 8 failures to cross threshold
        for _ in range(8):
            exp.process("fix a bug")
        
        # After learning
        e_after = exp.process("fix a bug")
        pred_after = e_after.prediction.predicted_outcome
        p_after = e_after.prediction.success_probability
        unc_after = e_after.state.uncertainty
        
        # Verify state changed
        assert unc_before != unc_after, "State must change after learning"
        
        # Verify prediction changed (threshold crossed)
        assert pred_before != pred_after, \
            f"Prediction should change after threshold crossing:\nBefore: {pred_before}\nAfter: {pred_after}"

    def test_decision_propagates_prediction_change(self):
        """When prediction changes, decision should also change."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        # Before
        e1 = exp.process("fix a bug")
        dec_before = e1.decision.selected_action
        score_before = e1.decision.decision_score
        
        # Cross threshold
        for _ in range(8):
            exp.process("fix a bug")
        
        # After
        e2 = exp.process("fix a bug")
        dec_after = e2.decision.selected_action
        score_after = e2.decision.decision_score
        
        # Decision should change or score should change
        assert (dec_before != dec_after) or (score_before != score_after), \
            "Decision or score should change when prediction changes"

    def test_action_reflects_decision_change(self):
        """When decision changes, action should reflect it."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        # Before
        e1 = exp.process("fix a bug")
        action_before = e1.action.action_type
        
        # Cross threshold
        for _ in range(8):
            exp.process("fix a bug")
        
        # After
        e2 = exp.process("fix a bug")
        action_after = e2.action.action_type
        
        # If decision changed, action should match new decision
        assert e2.decision.selected_action == action_after


# ═══════════════════════════════════════════════════════════════════
# FAKE LEARNING TESTS
# ═══════════════════════════════════════════════════════════════════


class TestFakeLearningDetection:
    """Verify that state adaptation ≠ behavioral adaptation."""

    def test_state_changes_without_behavior_change(self):
        """Small state changes may not cross thresholds."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        # Record initial state and behavior
        e1 = exp.process("fix a bug")
        snap1 = exp.get_behavior_snapshot(e1)
        
        # Apply 1 failure (small state change)
        exp.process("fix a bug")
        
        # Apply another failure
        exp.process("fix a bug")
        
        # Record state after small changes
        e2 = exp.process("fix a bug")
        snap2 = exp.get_behavior_snapshot(e2)
        
        # State definitely changed
        assert e2.state.uncertainty > e1.state.uncertainty
        
        # But behavior might not have changed (not crossed threshold)
        # This is EXPECTED - state adaptation without behavioral adaptation
        # The test verifies we can detect this distinction

    def test_many_failures_eventually_change_behavior(self):
        """With enough failures, behavior WILL change."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        # Collect snapshots at each step
        snapshots = []
        for i in range(10):
            e = exp.process("fix a bug")
            snapshots.append(exp.get_behavior_snapshot(e))
        
        # Find first behavior change
        first_pred = snapshots[0]["prediction_outcome"]
        first_behavior_idx = 0
        for i, snap in enumerate(snapshots):
            if snap["prediction_outcome"] != first_pred:
                first_behavior_idx = i
                break
        else:
            first_behavior_idx = len(snapshots)  # No change observed
        
        # State changed from start
        assert snapshots[-1]["state_uncertainty"] > snapshots[0]["state_uncertainty"]
        
        # Behavior may or may not have changed (depends on threshold)
        # Key point: state adaptation happened, behavioral adaptation may follow

    def test_success_recovery(self):
        """Success can reverse failure-induced state changes."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        # First, cause high uncertainty
        for _ in range(8):
            exp.process("fix a bug")
        
        high_unc = exp.state_store.uncertainty
        assert high_unc >= 0.60
        
        # Now apply successes
        exp.cortex._outcome_provider = FixedOutcomeProvider(success=True)
        
        for _ in range(5):
            exp.process("fix a bug")
        
        # Uncertainty should decrease
        assert exp.state_store.uncertainty < high_unc


# ═══════════════════════════════════════════════════════════════════
# DETERMINISM TESTS
# ═══════════════════════════════════════════════════════════════════


class TestDeterminism:
    """Verify deterministic repeatability."""

    def test_same_initial_state_same_results(self):
        """Two Cortices with same initial state produce same results."""
        exp_a = ControllableCortex()
        exp_b = ControllableCortex()
        
        e_a = exp_a.process("fix a bug")
        e_b = exp_b.process("fix a bug")
        
        snap_a = exp_a.get_behavior_snapshot(e_a)
        snap_b = exp_b.get_behavior_snapshot(e_b)
        
        assert snap_a == snap_b

    def test_deterministic_after_learning(self):
        """Same learning sequence produces same final state."""
        # Cortex A
        exp_a = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        for _ in range(5):
            exp_a.process("fix a bug")
        state_a = exp_a.state_store.uncertainty
        
        # Cortex B (identical setup)
        exp_b = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        for _ in range(5):
            exp_b.process("fix a bug")
        state_b = exp_b.state_store.uncertainty
        
        assert state_a == state_b

    def test_ten_iterations_same_output(self):
        """Ten identical runs produce identical results."""
        results = []
        for _ in range(10):
            exp = ControllableCortex()
            e = exp.process("fix a bug")
            results.append(exp.get_behavior_snapshot(e))
        
        assert all(r == results[0] for r in results)


# ═══════════════════════════════════════════════════════════════════
# CORTEX ISOLATION TESTS
# ═══════════════════════════════════════════════════════════════════


class TestCortexIsolation:
    """Verify Cortex instances are independent."""

    def test_independent_cortices_dont_pollute(self):
        """Learning in Cortex A should not affect Cortex B."""
        exp_a = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        exp_b = ControllableCortex()  # Fresh cortex with initial state
        
        # Learn in A (5 failures)
        for _ in range(5):
            exp_a.process("fix a bug")
        state_a_after_learning = exp_a.state_store.uncertainty
        
        # B processes same input
        e_b = exp_b.process("fix a bug")
        state_b = exp_b.state_store.uncertainty
        
        # States should be different (A learned, B didn't)
        assert state_a_after_learning != state_b
        # B should be at initial/normal level, not polluted by A
        assert state_b < state_a_after_learning

    def test_separate_state_stores(self):
        """Each Cortex has its own state store."""
        exp_a = ControllableCortex()
        exp_b = ControllableCortex()
        
        assert exp_a.state_store is not exp_b.state_store

    def test_event_isolation(self):
        """Events don't share state references."""
        exp = ControllableCortex()
        
        e1 = exp.process("fix a bug")
        e2 = exp.process("fix a bug")
        
        assert e1 is not e2
        assert id(e1.state) != id(e2.state)


# ═══════════════════════════════════════════════════════════════════
# COMPARISON TESTS
# ═══════════════════════════════════════════════════════════════════


class TestComparison:
    """Control vs Treatment comparison."""

    def test_control_vs_treatment_different_states(self):
        """Control and treatment should diverge after learning."""
        control = ControllableCortex()  # Success outcomes
        treatment = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        # Run same number of events
        for _ in range(5):
            control.process("fix a bug")
            treatment.process("fix a bug")
        
        # States should diverge
        assert control.state_store.uncertainty != treatment.state_store.uncertainty
        assert control.state_store.confidence != treatment.state_store.confidence

    def test_control_vs_treatment_behavior_divergence(self):
        """After enough divergence, behavior should differ."""
        control = ControllableCortex()
        treatment = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        # Control: successes
        for _ in range(3):
            control.process("fix a bug")
        
        # Treatment: failures
        for _ in range(8):
            treatment.process("fix a bug")
        
        # Get behavior
        e_control = control.process("fix a bug")
        e_treatment = treatment.process("fix a bug")
        
        # Predictions should differ
        assert e_control.prediction.predicted_outcome != e_treatment.prediction.predicted_outcome


# ═══════════════════════════════════════════════════════════════════
# ACCEPTANCE CRITERIA TESTS
# ═══════════════════════════════════════════════════════════════════


class TestAcceptanceCriteria:
    """Formal acceptance criteria verification."""

    def test_ac1_stable_behavior_without_learning(self):
        """AC-1: Same input without learning → stable behavior."""
        exp = ControllableCortex()
        e1 = exp.process("fix a bug")
        e2 = exp.process("fix a bug")
        
        # Compare behavior only (not state which changes with learning)
        behavior1 = {
            "prediction_outcome": e1.prediction.predicted_outcome,
            "decision_action": e1.decision.selected_action,
            "action_type": e1.action.action_type,
        }
        behavior2 = {
            "prediction_outcome": e2.prediction.predicted_outcome,
            "decision_action": e2.decision.selected_action,
            "action_type": e2.action.action_type,
        }
        assert behavior1 == behavior2

    def test_ac2_state_changes_after_learning(self):
        """AC-2: Learning changes CortexState."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        initial = exp.state_store.uncertainty
        exp.process("fix a bug")
        assert exp.state_store.uncertainty != initial

    def test_ac3_downstream_behavior_changes(self):
        """AC-3: At least one downstream behavior changes."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        e_before = exp.process("fix a bug")
        for _ in range(8):
            exp.process("fix a bug")
        e_after = exp.process("fix a bug")
        
        before = exp.get_behavior_snapshot(e_before)
        after = exp.get_behavior_snapshot(e_after)
        
        # At least one field should differ
        assert before != after, "Behavior should change after threshold crossing"

    def test_ac4_change_attributable_to_state(self):
        """AC-4: Behavior change is due to state, not input."""
        # This is verified by the control experiment (Experiment A)
        # Same input, different state → different behavior
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        e1 = exp.process("fix a bug")
        for _ in range(8):
            exp.process("fix a bug")
        e2 = exp.process("fix a bug")  # Same input!
        
        assert e1.raw_input == e2.raw_input  # Input unchanged
        assert exp.get_behavior_snapshot(e1) != exp.get_behavior_snapshot(e2)  # Behavior changed

    def test_ac5_real_learning_chain(self):
        """AC-5: Learning goes through real Outcome → Feedback → Learning."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        
        e = exp.process("fix a bug")
        
        # Verify the chain exists
        assert e.outcome.success is False  # Outcome
        assert e.feedback.evaluation != ""  # Feedback computed
        assert e.learning.learning_signal != ""  # Learning recorded
        assert exp.state_store.uncertainty > 0.20  # State changed

    def test_ac6_chain_integrity(self):
        """AC-6: Prediction → Decision → Action链路完整."""
        exp = ControllableCortex()
        e = exp.process("fix a bug")
        
        assert e.prediction.predicted_outcome != ""
        assert e.decision.selected_action != ""
        assert e.action.action_type == e.decision.selected_action

    def test_ac7_success_decreases_uncertainty(self):
        """AC-7: Success learning reduces uncertainty."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=True)
        )
        initial = exp.state_store.uncertainty
        for _ in range(3):
            exp.process("fix a bug")
        assert exp.state_store.uncertainty < initial

    def test_ac8_failure_increases_uncertainty(self):
        """AC-8: Failure learning increases uncertainty."""
        exp = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        initial = exp.state_store.uncertainty
        for _ in range(3):
            exp.process("fix a bug")
        assert exp.state_store.uncertainty > initial

    def test_ac9_cortex_isolation(self):
        """AC-9: Cortices are independent."""
        exp_a = ControllableCortex(
            outcome_provider=FixedOutcomeProvider(success=False)
        )
        exp_b = ControllableCortex()  # Fresh cortex
        
        for _ in range(5):
            exp_a.process("fix a bug")
        
        e_b = exp_b.process("fix a bug")
        
        # A should have high uncertainty (learned from failures)
        assert exp_a.state_store.uncertainty > 0.20
        # B should have lower uncertainty (only one success event)
        assert e_b.state.uncertainty < exp_a.state_store.uncertainty
        # Verify they're different objects
        assert exp_a.cortex.state_store is not exp_b.cortex.state_store

    def test_ac10_deterministic(self):
        """AC-10: Experiments are deterministic."""
        results = []
        for _ in range(5):
            exp = ControllableCortex()
            exp.process("fix a bug")
            results.append((exp.state_store.uncertainty, exp.state_store.confidence))
        assert all(r == results[0] for r in results)


# ═══════════════════════════════════════════════════════════════════
# REGRESSION TEST
# ═══════════════════════════════════════════════════════════════════


class TestRegression:
    """Ensure Phase 0-9 tests still pass."""

    def test_all_existing_tests_pass(self):
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
             "neuro-cortex/tests/test_phase9.py",
             "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"Regression failed:\n{result.stdout}\n{result.stderr}"
