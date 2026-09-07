"""Phase 6 — Feedback & Evaluation Contract Tests (v2.1)."""
from __future__ import annotations

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neurocortex.event import (
    CortexEvent,
    PerceptionData,
    InternalState,
    PredictionData,
    OutcomeData,
    FeedbackData,
)
from neurocortex.prediction import BasicPrediction
from neurocortex.feedback import BasicFeedback
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState,
    MockMemory, MockPrediction, MockDecision, MockAction,
    MockOutcomeProvider, MockFeedback, MockLearning,
)
from neurocortex.cortex import NeuroCortex


# ── Helpers ───────────────────────────────────────────────────────


def make_event_with_prediction(
    raw_input: str,
    intent: str = "fix",
    risk: float = 0.2,
    uncertainty: float = 0.2,
    perf_conf: float = 0.5,
    predicted_outcome: str | None = None,
    success_prob: float | None = None,
    pred_confidence: float | None = None,
) -> CortexEvent:
    """Build an event through PREDICTION stage with optional overrides."""
    e = CortexEvent(raw_input)
    e.perceive(PerceptionData(
        raw_input=raw_input,
        intent=intent,
        risk=risk,
        confidence=perf_conf,
    ))
    e.update_state(InternalState(uncertainty=uncertainty))
    pred_module = BasicPrediction()
    e = pred_module.process(e)

    if predicted_outcome is not None:
        e.prediction.predicted_outcome = predicted_outcome
    if success_prob is not None:
        e.prediction.success_probability = success_prob
    if pred_confidence is not None:
        e.prediction.prediction_confidence = pred_confidence
    return e


def compute_feedback_direct(
    event: CortexEvent,
    outcome_success: bool,
    outcome_text: str = "done",
    error_message: str = "",
) -> CortexEvent:
    """Apply outcome and run Phase 6 feedback computation."""
    event.record_outcome(OutcomeData(
        actual_outcome=outcome_text,
        success=outcome_success,
        error_message=error_message,
    ))
    fb = BasicFeedback()
    return fb.process(event)


def full_pipeline(
    raw_input: str,
    feedback_module=None,
    outcome_success: bool = True,
    outcome_text: str = "action completed",
    error_message: str = "",
) -> CortexEvent:
    """Run full NeuroCortex pipeline with optional feedback module."""
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
        feedback=feedback_module or MockFeedback(),
        learning=MockLearning(),
    )
    e = c.process(raw_input)
    # Override outcome for controlled testing
    if e.stage == "LEARNING":
        e.outcome = OutcomeData(
            actual_outcome=outcome_text,
            success=outcome_success,
            error_message=error_message,
        )
        # Re-run feedback with new outcome
        if feedback_module is not None:
            feedback_module.process(e)
    return e


# ═══════════════════════════════════════════════════════════════════
# TEST SUITE — 28 Cases
# ═══════════════════════════════════════════════════════════════════


# ── T01: p=0.0, success=True → miss ─────────────────────────────
class TestT01:
    def test_p_zero_success_true(self):
        e = make_event_with_prediction("fix bug", success_prob=0.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(1.0)


# ── T02: p=0.5, success=False → miss ────────────────────────────
class TestT02:
    def test_p_point_five_failure(self):
        e = make_event_with_prediction("fix bug", success_prob=0.5, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.5)


# ── T03: p=1.0, success=True, c=0.8 → perfect_high_confidence ───
class TestT03:
    def test_p_one_c_high(self):
        e = make_event_with_prediction("fix bug", success_prob=1.0, pred_confidence=0.8)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "perfect_high_confidence"
        assert e.feedback.prediction_error == 0.0


# ── T04: p=1.0, success=True, c=0.5 → perfect ───────────────────
class TestT04:
    def test_p_one_c_low(self):
        e = make_event_with_prediction("fix bug", success_prob=1.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "perfect"
        assert e.feedback.prediction_error == 0.0


# ── T05: confidence=0 → no_prediction ───────────────────────────
class TestT05:
    def test_confidence_zero(self):
        e = make_event_with_prediction("fix bug", pred_confidence=0.0)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "no_prediction"
        assert e.feedback.prediction_error == 0.0


# ── T06: confidence=0.1, p=0.9, success=True → correct ──────────
class TestT06:
    def test_confidence_point_one(self):
        e = make_event_with_prediction("fix bug", success_prob=0.9, pred_confidence=0.1)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "correct"
        assert e.feedback.prediction_error == pytest.approx(0.1)


# ── T07: confidence=0.8, p=0.9, success=True → correct ──────────
class TestT07:
    def test_high_conf_correct(self):
        e = make_event_with_prediction("fix bug", success_prob=0.9, pred_confidence=0.8)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "correct"
        assert e.feedback.prediction_error == pytest.approx(0.1)


# ── T08: unknown intent, p=0.5, success=True → miss ─────────────
class TestT08:
    def test_unknown_intent(self):
        e = make_event_with_prediction(
            "hello", intent="unknown", success_prob=0.5, pred_confidence=0.2
        )
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.5)


# ── T09: high risk, p=0.3, success=False → miss ─────────────────
class TestT09:
    def test_high_risk_failure(self):
        e = make_event_with_prediction(
            "deploy to prod", intent="deploy", risk=0.8,
            uncertainty=0.2, perf_conf=0.7,
            success_prob=0.3, pred_confidence=0.49,
        )
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.3)


# ── T10: error=0.3 boundary → miss (NOT correct) ────────────────
class TestT10:
    def test_error_zero_point_three_is_miss(self):
        e = make_event_with_prediction("fix", success_prob=0.3, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.3)


# ── T11: empty predicted_outcome → no_prediction ────────────────
class TestT11:
    def test_empty_predicted_outcome(self):
        e = make_event_with_prediction(
            "fix bug", predicted_outcome="", success_prob=0.5, pred_confidence=0.5
        )
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "no_prediction"
        assert e.feedback.prediction_error == 0.0


# ── T12: error=0.3 with success=True → miss ─────────────────────
class TestT12:
    def test_error_point_three_success(self):
        e = make_event_with_prediction("fix", success_prob=0.7, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.3)


# ── T13: error=0.8 boundary → miss (NOT catastrophically_wrong) ─
class TestT13:
    def test_error_zero_point_eight_is_miss(self):
        e = make_event_with_prediction("fix", success_prob=0.8, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.8)


# ── T14: error=0.81, c=0.9 → catastrophically_wrong ─────────────
class TestT14:
    def test_catastrophic(self):
        e = make_event_with_prediction("fix", success_prob=0.81, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "catastrophically_wrong"
        assert e.feedback.prediction_error == pytest.approx(0.81)


# ── T15: error=1.0, c=0.5 → miss (NOT catastrophically_wrong) ──
class TestT15:
    def test_error_one_low_confidence(self):
        e = make_event_with_prediction("fix", success_prob=0.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(1.0)


# ── T16: error=1.0, c=0.9 → catastrophically_wrong ──────────────
class TestT16:
    def test_error_one_high_confidence(self):
        e = make_event_with_prediction("fix", success_prob=0.0, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "catastrophically_wrong"
        assert e.feedback.prediction_error == pytest.approx(1.0)


# ── T17: prediction=None (empty PredictionData) → no_prediction ─
class TestT17:
    def test_none_prediction(self):
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e.update_state(InternalState())
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "no_prediction"
        assert e.feedback.prediction_error == 0.0


# ── T18: outcome=None (empty OutcomeData) → invalid_outcome ─────
class TestT18:
    def test_none_outcome(self):
        e = make_event_with_prediction("fix bug", success_prob=0.8, pred_confidence=0.7)
        e.record_outcome(OutcomeData(actual_outcome="", success=False))
        fb = BasicFeedback()
        e = fb.process(e)
        assert e.feedback.evaluation == "invalid_outcome"
        assert e.feedback.prediction_error == 0.0


# ── T19: ambiguous outcome (success=None) → invalid_outcome ─────
class TestT19:
    def test_ambiguous_outcome(self):
        e = make_event_with_prediction("fix bug", success_prob=0.8, pred_confidence=0.7)
        e.record_outcome(OutcomeData(actual_outcome="something happened", success=None))
        fb = BasicFeedback()
        e = fb.process(e)
        assert e.feedback.evaluation == "invalid_outcome"
        assert e.feedback.prediction_error == 0.0


# ── T20a: execution_error + catastrophically_wrong ──────────────
class TestT20a:
    def test_execution_error_catastrophic(self):
        e = make_event_with_prediction("deploy", success_prob=0.9, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=False, error_message="timeout")
        assert e.feedback.evaluation == "execution_error + catastrophically_wrong"
        assert e.feedback.prediction_error == pytest.approx(0.9)


# ── T20b: execution_error + miss ────────────────────────────────
class TestT20b:
    def test_execution_error_miss(self):
        e = make_event_with_prediction("deploy", success_prob=0.8, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False, error_message="timeout")
        assert e.feedback.evaluation == "execution_error + miss"
        assert e.feedback.prediction_error == pytest.approx(0.8)


# ── T20c: execution_error + perfect_high_confidence ─────────────
class TestT20c:
    def test_execution_error_perfect_high_conf(self):
        e = make_event_with_prediction("deploy", success_prob=1.0, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=True, error_message="minor warning")
        assert e.feedback.evaluation == "execution_error + perfect_high_confidence"
        assert e.feedback.prediction_error == 0.0


# ── T21a: no prediction, no outcome → no_prediction ─────────────
class TestT21a:
    def test_no_prediction_no_outcome(self):
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e.update_state(InternalState())
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "no_prediction"


# ── T21b: valid prediction, no outcome → invalid_outcome ────────
class TestT21b:
    def test_prediction_no_outcome(self):
        e = make_event_with_prediction("fix bug", success_prob=0.8, pred_confidence=0.7)
        e.record_outcome(OutcomeData(actual_outcome="", success=None))
        fb = BasicFeedback()
        e = fb.process(e)
        assert e.feedback.evaluation == "invalid_outcome"


# ── T22: state immutability ─────────────────────────────────────
class TestT22:
    def test_feedback_does_not_modify_state(self):
        e = make_event_with_prediction("fix bug", success_prob=0.8, pred_confidence=0.7)
        original_curiosity = e.state.curiosity
        original_confidence = e.state.confidence
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.state.curiosity == original_curiosity
        assert e.state.confidence == original_confidence


# ── T23: deterministic output ───────────────────────────────────
class TestT23:
    def test_deterministic(self):
        results = []
        for _ in range(5):
            e = make_event_with_prediction("fix", success_prob=0.85, pred_confidence=0.75)
            e = compute_feedback_direct(e, outcome_success=False)
            results.append((e.feedback.evaluation, e.feedback.prediction_error))
        assert all(r == results[0] for r in results)


# ── T24: full Cortex integration with FeedbackModule ────────────
class TestT24:
    def test_full_pipeline_with_feedback(self):
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
        assert e.feedback.evaluation != ""
        assert isinstance(e.feedback.prediction_error, float)


# ── T25: prediction_error is always float, never None ───────────
class TestT25:
    def test_error_always_float(self):
        cases = [
            ("no_prediction", dict(success_prob=0.5, pred_confidence=0.0), True),
            ("invalid_outcome", dict(success_prob=0.8, pred_confidence=0.7), False),
            ("perfect", dict(success_prob=1.0, pred_confidence=0.5), True),
            ("correct", dict(success_prob=0.8, pred_confidence=0.5), True),
            ("miss", dict(success_prob=0.2, pred_confidence=0.5), False),
            ("catastrophic", dict(success_prob=0.0, pred_confidence=0.9), True),
        ]
        for name, kwargs, success in cases:
            e = make_event_with_prediction("test", **kwargs)
            if kwargs.get("pred_confidence") == 0.0:
                e = compute_feedback_direct(e, outcome_success=success)
            elif name == "invalid_outcome":
                e.record_outcome(OutcomeData(actual_outcome="", success=None))
                e = BasicFeedback().process(e)
            else:
                e = compute_feedback_direct(e, outcome_success=success)
            assert isinstance(e.feedback.prediction_error, float)
            assert not math.isnan(e.feedback.prediction_error)
            assert not math.isinf(e.feedback.prediction_error)


# ── T26: p=0.0, success=False → perfect ─────────────────────────
class TestT26:
    def test_p_zero_failure_perfect(self):
        e = make_event_with_prediction("avoid danger", success_prob=0.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "perfect"
        assert e.feedback.prediction_error == 0.0


# ── T27: p=1.0, success=False, c=0.5 → miss ─────────────────────
class TestT27:
    def test_p_one_failure_low_conf(self):
        e = make_event_with_prediction("fix", success_prob=1.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(1.0)


# ── T28: regression — 222 existing tests still pass ─────────────
class TestT28:
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
             "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"Regression failed:\n{result.stdout}\n{result.stderr}"


# ── T29: reward immutability ────────────────────────────────────
class TestT29:
    """Reward must never be modified by BasicFeedback."""

    def test_reward_unchanged_on_success(self):
        e = make_event_with_prediction("fix bug", success_prob=0.9, pred_confidence=0.8)
        e.feedback.reward = 3.14
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.reward == 3.14
        assert e.feedback.evaluation == "correct"

    def test_reward_unchanged_on_failure(self):
        e = make_event_with_prediction("fix bug", success_prob=0.9, pred_confidence=0.8)
        e.feedback.reward = -7.0
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.reward == -7.0
        assert e.feedback.evaluation == "catastrophically_wrong"

    def test_reward_unchanged_on_invalid_prediction(self):
        e = make_event_with_prediction("fix bug", pred_confidence=0.0)
        e.feedback.reward = 5.0
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.reward == 5.0
        assert e.feedback.evaluation == "no_prediction"

    def test_reward_unchanged_on_invalid_outcome(self):
        e = make_event_with_prediction("fix bug", success_prob=0.9, pred_confidence=0.8)
        e.feedback.reward = 2.5
        e.record_outcome(OutcomeData(actual_outcome="", success=None))
        e = BasicFeedback().process(e)
        assert e.feedback.reward == 2.5
        assert e.feedback.evaluation == "invalid_outcome"

    def test_reward_unchanged_on_execution_error(self):
        e = make_event_with_prediction("deploy", success_prob=0.9, pred_confidence=0.9)
        e.feedback.reward = 9.9
        e = compute_feedback_direct(e, outcome_success=False, error_message="timeout")
        assert e.feedback.reward == 9.9
        assert e.feedback.evaluation == "execution_error + catastrophically_wrong"

    def test_reward_unchanged_on_perfect(self):
        e = make_event_with_prediction("fix bug", success_prob=1.0, pred_confidence=0.9)
        e.feedback.reward = 0.0
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.reward == 0.0
        assert e.feedback.evaluation == "perfect_high_confidence"

    def test_reward_unchanged_default_is_zero(self):
        e = make_event_with_prediction("fix bug", success_prob=1.0, pred_confidence=0.9)
        # Default reward is 0.0
        assert e.feedback.reward == 0.0
        e = compute_feedback_direct(e, outcome_success=True)
        # Must still be 0.0 after feedback
        assert e.feedback.reward == 0.0
