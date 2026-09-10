"""Phase 8 — Action Module Tests (v1)."""
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
    MemoryData,
    AttentionData,
    RepresentationData,
)
from neurocortex.action import BasicAction
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState,
    MockMemory, MockPrediction, MockDecision, MockAction,
    MockOutcomeProvider, MockFeedback, MockLearning,
)
from neurocortex.cortex import NeuroCortex


# ── Helpers ───────────────────────────────────────────────────────


def make_event_with_decision(
    raw_input: str = "test",
    intent: str = "fix",
    risk: float = 0.2,
    perf_conf: float = 0.7,
    predicted_outcome: str = "task completes",
    success_prob: float = 0.7,
    pred_risk: float = 0.3,
    pred_confidence: float = 0.6,
    selected_action: str = "code_review",
    decision_score: float = 0.8,
) -> CortexEvent:
    """Build an event through DECISION stage ready for ACTION."""
    e = CortexEvent(raw_input)
    e.perceive(PerceptionData(
        raw_input=raw_input,
        intent=intent,
        risk=risk,
        confidence=perf_conf,
    ))
    e.represent(RepresentationData())
    e.attend(AttentionData())
    e.update_state(InternalState())
    e.retrieve_memory(MemoryData())
    e.predict(PredictionData(
        predicted_outcome=predicted_outcome,
        success_probability=success_prob,
        predicted_risk=pred_risk,
        prediction_confidence=pred_confidence,
    ))
    e.decide(DecisionData(
        selected_action=selected_action,
        decision_score=decision_score,
        decision_reason=f"test decision for {selected_action}",
        candidates=[{"id": selected_action, "score": decision_score}],
    ))
    return e


def make_event_minimal(raw_input: str = "test") -> CortexEvent:
    """Build minimal event through DECISION with defaults."""
    return make_event_with_decision(raw_input=raw_input)


# ═══════════════════════════════════════════════════════════════════
# TEST SUITE — 35+ Cases
# ═══════════════════════════════════════════════════════════════════


# ── A. Decision Integration (5 tests) ────────────────────────────

class TestDecisionIntegration:
    def test_valid_decision_code_edit(self):
        e = make_event_with_decision(selected_action="code_edit", decision_score=0.8)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"
        assert result.action.action_type == "code_edit"
        assert result.action.planned is True
        assert result.action.actual is True

    def test_valid_decision_respond(self):
        e = make_event_with_decision(selected_action="respond", decision_score=0.7)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"
        assert result.action.action_type == "respond"

    def test_valid_decision_code_review(self):
        e = make_event_with_decision(selected_action="code_review", decision_score=0.9)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"
        assert result.action.action_type == "code_review"

    def test_valid_decision_tool_call(self):
        e = make_event_with_decision(selected_action="tool_call", decision_score=0.6)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"
        assert result.action.action_type == "tool_call"

    def test_valid_decision_noop(self):
        e = make_event_with_decision(selected_action="noop", decision_score=0.5)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"
        assert result.action.action_type == "noop"
        assert result.action.actual is True


# ── B. Missing Decision / Empty Action (3 tests) ─────────────────

class TestMissingDecision:
    def test_empty_selected_action(self):
        e = make_event_with_decision(selected_action="", decision_score=0.5)
        a = BasicAction()
        result = a.process(e)
        # Empty action → backward compat: success with noop type
        assert result.action.status == "success"
        assert result.action.action_type == "noop"

    def test_no_decision_data(self):
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e.represent(RepresentationData())
        e.attend(AttentionData())
        e.update_state(InternalState())
        e.retrieve_memory(MemoryData())
        e.predict(PredictionData())
        # No decide() call → selected_action stays ""
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"

    def test_empty_decision_reason_ignored(self):
        """decision_reason is READ-ONLY, should not affect execution."""
        e = make_event_with_decision()
        e.decision.decision_reason = ""
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"


# ── C. Noop Handling (2 tests) ───────────────────────────────────

class TestNoop:
    def test_noop_always_succeeds(self):
        e = make_event_with_decision(selected_action="noop", decision_score=0.0)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"
        assert result.action.actual is True

    def test_noop_bypasses_score_gate(self):
        """noop should succeed even with decision_score=0."""
        e = make_event_with_decision(selected_action="noop", decision_score=0.0)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"


# ── D. Unknown Action (2 tests) ──────────────────────────────────

class TestUnknownAction:
    def test_unknown_action_raises(self):
        e = make_event_with_decision(selected_action="shell_exec", decision_score=0.8)
        a = BasicAction()
        with pytest.raises(ValueError, match="Unknown action type"):
            a.process(e)

    def test_unknown_action_records_failure(self):
        e = make_event_with_decision(selected_action="file_write", decision_score=0.8)
        a = BasicAction()
        with pytest.raises(ValueError):
            a.process(e)
        # After exception, action should record failure
        assert e.action.status == "failure"
        assert e.action.actual is False


# ── E. Score Boundary (6 tests) ──────────────────────────────────

class TestScoreBoundary:
    def test_score_below_threshold_029(self):
        """score=0.29 < 0.3 → skip."""
        e = make_event_with_decision(selected_action="code_edit", decision_score=0.29)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "skipped"
        assert result.action.actual is False

    def test_score_at_threshold_030(self):
        """score=0.30 == 0.3 → execute (threshold is inclusive for execution)."""
        e = make_event_with_decision(selected_action="code_edit", decision_score=0.30)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"
        assert result.action.actual is True

    def test_score_above_threshold_031(self):
        """score=0.31 > 0.3 → execute."""
        e = make_event_with_decision(selected_action="code_edit", decision_score=0.31)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"
        assert result.action.actual is True

    def test_score_zero(self):
        """score=0.0 → skip."""
        e = make_event_with_decision(selected_action="code_edit", decision_score=0.0)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "skipped"

    def test_score_one(self):
        """score=1.0 → execute."""
        e = make_event_with_decision(selected_action="code_edit", decision_score=1.0)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "success"

    def test_score_negative(self):
        """score=-0.1 → skip."""
        e = make_event_with_decision(selected_action="code_edit", decision_score=-0.1)
        a = BasicAction()
        result = a.process(e)
        assert result.action.status == "skipped"


# ── F. All Known Symbolic Actions (5 tests) ──────────────────────

class TestSymbolicActions:
    def test_all_known_actions_succeed(self):
        """All known action types should produce status='success'."""
        for action in ["noop", "respond", "code_review", "code_edit", "tool_call"]:
            e = make_event_with_decision(selected_action=action, decision_score=0.8)
            a = BasicAction()
            result = a.process(e)
            assert result.action.status == "success", f"Failed for {action}"
            assert result.action.action_type == action

    def test_action_payload_contains_raw_input(self):
        e = make_event_with_decision(raw_input="hello world")
        a = BasicAction()
        result = a.process(e)
        assert result.action.action_payload["text"] == "hello world"

    def test_action_payload_for_noop(self):
        e = make_event_with_decision(selected_action="noop")
        a = BasicAction()
        result = a.process(e)
        assert "text" in result.action.action_payload

    def test_action_type_matches_selected_action(self):
        for action in ["respond", "code_review", "code_edit", "tool_call"]:
            e = make_event_with_decision(selected_action=action)
            a = BasicAction()
            result = a.process(e)
            assert result.action.action_type == action

    def test_planned_and_actual_for_valid_actions(self):
        e = make_event_with_decision(selected_action="tool_call")
        a = BasicAction()
        result = a.process(e)
        assert result.action.planned is True
        assert result.action.actual is True


# ── G. Immutability (5 tests) ────────────────────────────────────

class TestImmutability:
    def test_decision_not_modified(self):
        e = make_event_with_decision()
        original = DecisionData(
            selected_action=e.decision.selected_action,
            decision_score=e.decision.decision_score,
            decision_reason=e.decision.decision_reason,
            candidates=list(e.decision.candidates),
        )
        a = BasicAction()
        a.process(e)
        assert e.decision.selected_action == original.selected_action
        assert e.decision.decision_score == original.decision_score
        assert e.decision.decision_reason == original.decision_reason
        assert e.decision.candidates == original.candidates

    def test_perception_not_modified(self):
        e = make_event_with_decision()
        original_intent = e.perception.intent
        a = BasicAction()
        a.process(e)
        assert e.perception.intent == original_intent

    def test_prediction_not_modified(self):
        e = make_event_with_decision()
        original_prob = e.prediction.success_probability
        a = BasicAction()
        a.process(e)
        assert e.prediction.success_probability == original_prob

    def test_state_not_modified(self):
        e = make_event_with_decision()
        original_unc = e.state.uncertainty
        a = BasicAction()
        a.process(e)
        assert e.state.uncertainty == original_unc

    def test_feedback_not_modified(self):
        e = make_event_with_decision()
        original_reward = e.feedback.reward
        a = BasicAction()
        a.process(e)
        assert e.feedback.reward == original_reward


# ── H. Determinism (2 tests) ─────────────────────────────────────

class TestDeterministic:
    def test_same_input_same_output_10_times(self):
        results = []
        for _ in range(10):
            e = make_event_with_decision(selected_action="code_edit", decision_score=0.8)
            a = BasicAction()
            result = a.process(e)
            results.append((
                result.action.status,
                result.action.action_type,
                result.action.planned,
                result.action.actual,
            ))
        assert all(r == results[0] for r in results)

    def test_different_actions_different_outputs(self):
        e1 = make_event_with_decision(selected_action="code_edit")
        e2 = make_event_with_decision(selected_action="respond")
        a = BasicAction()
        r1 = a.process(e1)
        r2 = a.process(e2)
        assert r1.action.action_type == "code_edit"
        assert r2.action.action_type == "respond"
        assert r1.action.action_type != r2.action.action_type


# ── I. Full Cortex Integration (3 tests) ─────────────────────────

class TestIntegration:
    def test_full_pipeline_with_real_action(self):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            outcome_provider=MockOutcomeProvider(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("fix the bug")
        assert e.stage == "LEARNING"
        assert e.status == "ok"
        assert e.action.status == "success"
        assert e.action.action_type != ""

    def test_action_before_outcome(self):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            outcome_provider=MockOutcomeProvider(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.action.status == "success"
        assert e.outcome.success is True

    def test_action_failure_in_pipeline(self):
        class FailingAction(MockAction):
            def process(self, event):
                raise RuntimeError("action module failed")

        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=FailingAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "ACTION"


# ── J. No External Side Effects (2 tests) ────────────────────────

class TestNoSideEffects:
    def test_no_subprocess_import(self):
        """BasicAction must not import subprocess."""
        import neurocortex.action.action as mod
        assert not hasattr(mod, 'subprocess')

    def test_no_network_import(self):
        """BasicAction must not import network libraries."""
        import neurocortex.action.action as mod
        assert not hasattr(mod, 'requests')
        assert not hasattr(mod, 'urllib')


# ── K. Regression (1 test) ───────────────────────────────────────

class TestRegression:
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
             "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"Regression failed:\n{result.stdout}\n{result.stderr}"
