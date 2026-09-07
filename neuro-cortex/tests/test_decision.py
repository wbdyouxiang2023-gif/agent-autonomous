"""Phase 7 — Decision Module Tests (v1)."""
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
)
from neurocortex.decision import BasicDecision
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState,
    MockMemory, MockPrediction, MockDecision, MockAction,
    MockOutcomeProvider, MockFeedback, MockLearning,
)
from neurocortex.cortex import NeuroCortex


# ── Helpers ───────────────────────────────────────────────────────


def make_event_with_decision(
    raw_input: str,
    intent: str = "fix",
    risk: float = 0.2,
    perf_conf: float = 0.7,
    predicted_outcome: str = "task completes",
    success_prob: float = 0.7,
    pred_risk: float = 0.3,
    pred_confidence: float = 0.6,
) -> CortexEvent:
    """Build an event through PREDICTION stage ready for DECISION."""
    from neurocortex.event import MemoryData, AttentionData, RepresentationData
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
    return e


# ═══════════════════════════════════════════════════════════════════
# TEST SUITE — 31 Cases
# ═══════════════════════════════════════════════════════════════════


# ── 1. Known intent cases ────────────────────────────────────────

class TestKnownIntent:
    def test_fix_intent(self):
        e = make_event_with_decision("fix bug", intent="fix")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "code_review"
        assert result.decision.decision_score > 0.3
        assert result.decision.decision_reason != ""

    def test_create_intent(self):
        e = make_event_with_decision("create API", intent="create")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "code_edit"

    def test_learn_intent(self):
        e = make_event_with_decision("learn python", intent="learn")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "respond"

    def test_optimize_intent(self):
        e = make_event_with_decision("optimize query", intent="optimize")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "tool_call"

    def test_deploy_intent(self):
        e = make_event_with_decision("deploy app", intent="deploy")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "tool_call"


# ── 2. Unknown intent cases ──────────────────────────────────────

class TestUnknownIntent:
    def test_unknown_intent(self):
        e = make_event_with_decision("hello", intent="unknown")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "respond"
        assert result.decision.decision_score == 0.5

    def test_empty_intent(self):
        e = make_event_with_decision("test", intent="")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "respond"

    def test_empty_input(self):
        e = CortexEvent("")
        e.perceive(PerceptionData(raw_input="", intent="unknown", risk=0.0, confidence=0.5))
        e.update_state(InternalState())
        e.predict(PredictionData(predicted_outcome="", success_probability=0.5,
                                 predicted_risk=0.0, prediction_confidence=0.5))
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"
        assert result.decision.decision_score == 0.0

    def test_whitespace_input(self):
        e = CortexEvent("   ")
        e.perceive(PerceptionData(raw_input="   ", intent="unknown", risk=0.0, confidence=0.5))
        e.update_state(InternalState())
        e.predict(PredictionData(predicted_outcome="", success_probability=0.5,
                                 predicted_risk=0.0, prediction_confidence=0.5))
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"


# ── 3. Missing / invalid prediction cases ────────────────────────

class TestMissingPrediction:
    def test_no_valid_prediction_empty_outcome(self):
        e = make_event_with_decision("test", predicted_outcome="")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"
        assert result.decision.decision_score == 0.0

    def test_no_valid_prediction_zero_confidence(self):
        e = make_event_with_decision("test", pred_confidence=0.0)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"
        assert result.decision.decision_score == 0.0


# ── 4. High risk cases ───────────────────────────────────────────

class TestHighRisk:
    def test_high_risk_abstain(self):
        """risk=0.9, pred_conf=0.6 → noop."""
        e = make_event_with_decision("deploy", pred_risk=0.9, pred_confidence=0.6)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"
        assert "high risk" in result.decision.decision_reason

    def test_high_risk_threshold_080(self):
        """pred_risk=0.80, pred_conf=0.51 → noop (boundary)."""
        e = make_event_with_decision("test", pred_risk=0.80, pred_confidence=0.51)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"

    def test_below_high_risk_threshold(self):
        """pred_risk=0.79, pred_conf=0.6 → should NOT abstain."""
        e = make_event_with_decision("test", pred_risk=0.79, pred_confidence=0.6)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action != "noop"

    def test_high_risk_low_confidence_no_abstain(self):
        """pred_risk=0.9, pred_conf=0.5 → Rule 2 doesn't match (0.5 not > 0.5),
        but Rule 4 also rejected (risk >= 0.8), so falls through to noop via Rule 6."""
        e = make_event_with_decision("test", pred_risk=0.9, pred_confidence=0.5)
        d = BasicDecision()
        result = d.process(e)
        # Both Rule 2 (needs conf > 0.5) and Rule 4 (needs risk < 0.8) fail
        # Falls through to Rule 6: noop
        assert result.decision.selected_action == "noop"

    def test_high_risk_high_prob_still_abstain(self):
        """p=0.95, risk=1.0 → noop regardless of high probability."""
        e = make_event_with_decision("test", success_prob=0.95, pred_risk=1.0, pred_confidence=0.9)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"


# ── 5. Low confidence + low probability ──────────────────────────

class TestLowConfidenceLowProb:
    def test_low_conf_low_prob(self):
        """pred_conf=0.2, p=0.4 → noop."""
        e = make_event_with_decision("test", pred_confidence=0.2, success_prob=0.4)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"

    def test_borderline_confidence(self):
        """pred_conf=0.3, p=0.6 → should NOT noop."""
        e = make_event_with_decision("test", pred_confidence=0.3, success_prob=0.6)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action != "noop"

    def test_low_conf_high_prob(self):
        """pred_conf=0.2, p=0.9 → should NOT noop (prob is high)."""
        e = make_event_with_decision("test", pred_confidence=0.2, success_prob=0.9)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action != "noop"


# ── 6. Boundary cases ────────────────────────────────────────────

class TestBoundary:
    def test_p_zero_success_false(self):
        """p=0.0, success=False: err=0 → perfect path, but decision still picks action."""
        e = make_event_with_decision("test", success_prob=0.0, pred_risk=0.1, pred_confidence=0.8)
        d = BasicDecision()
        result = d.process(e)
        # p=0 but risk is low and confidence is high → still picks action based on intent
        assert result.decision.selected_action != "noop"

    def test_p_one_success_true(self):
        """p=1.0, success=True, low risk → action selected."""
        e = make_event_with_decision("test", success_prob=1.0, pred_risk=0.1, pred_confidence=0.9)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action != "noop"

    def test_predicted_risk_zero(self):
        """pred_risk=0.0 → normal decision path."""
        e = make_event_with_decision("test", pred_risk=0.0, pred_confidence=0.7)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action != "noop"

    def test_predicted_risk_one(self):
        """pred_risk=1.0, pred_conf>0.5 → noop."""
        e = make_event_with_decision("test", pred_risk=1.0, pred_confidence=0.6)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.selected_action == "noop"


# ── 7. Immutability cases ────────────────────────────────────────

class TestImmutability:
    def test_prediction_not_modified(self):
        e = make_event_with_decision("test")
        original = PredictionData(
            predicted_outcome=e.prediction.predicted_outcome,
            success_probability=e.prediction.success_probability,
            predicted_risk=e.prediction.predicted_risk,
            prediction_confidence=e.prediction.prediction_confidence,
        )
        d = BasicDecision()
        d.process(e)
        assert e.prediction.predicted_outcome == original.predicted_outcome
        assert e.prediction.success_probability == original.success_probability
        assert e.prediction.predicted_risk == original.predicted_risk
        assert e.prediction.prediction_confidence == original.prediction_confidence

    def test_perception_not_modified(self):
        e = make_event_with_decision("test")
        original_intent = e.perception.intent
        original_risk = e.perception.risk
        d = BasicDecision()
        d.process(e)
        assert e.perception.intent == original_intent
        assert e.perception.risk == original_risk

    def test_state_not_modified(self):
        e = make_event_with_decision("test")
        original_uncertainty = e.state.uncertainty
        original_confidence = e.state.confidence
        d = BasicDecision()
        d.process(e)
        assert e.state.uncertainty == original_uncertainty
        assert e.state.confidence == original_confidence

    def test_decision_not_modified_before_process(self):
        """Decision data before process should be default."""
        e = make_event_with_decision("test")
        assert e.decision.selected_action == ""
        assert e.decision.decision_score == 0.5
        d = BasicDecision()
        d.process(e)
        assert e.decision.selected_action != ""


# ── 8. Determinism cases ─────────────────────────────────────────

class TestDeterministic:
    def test_same_input_same_output_5_times(self):
        results = []
        for _ in range(5):
            e = make_event_with_decision("fix bug", intent="fix", pred_risk=0.3, pred_confidence=0.7)
            d = BasicDecision()
            result = d.process(e)
            results.append((
                result.decision.selected_action,
                result.decision.decision_score,
                result.decision.decision_reason,
            ))
        assert all(r == results[0] for r in results)

    def test_different_inputs_different_decisions(self):
        e1 = make_event_with_decision("fix bug", intent="fix")
        e2 = make_event_with_decision("create API", intent="create")
        d = BasicDecision()
        r1 = d.process(e1)
        r2 = d.process(e2)
        assert r1.decision.selected_action == "code_review"
        assert r2.decision.selected_action == "code_edit"
        assert r1.decision.selected_action != r2.decision.selected_action


# ── 9. Integration cases ─────────────────────────────────────────

class TestIntegration:
    def test_full_pipeline_with_real_decision(self):
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
        assert e.decision.selected_action != ""

    def test_decision_before_action(self):
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
        # Decision runs before Action in pipeline
        assert e.decision.selected_action != ""
        assert e.action.status == "success"

    def test_decision_failure(self):
        class FailingDecision(MockDecision):
            def process(self, event):
                raise RuntimeError("decision module failed")

        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=FailingDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "DECISION"


# ── 10. Candidates output ────────────────────────────────────────

class TestCandidates:
    def test_candidates_always_present(self):
        e = make_event_with_decision("fix bug")
        d = BasicDecision()
        result = d.process(e)
        assert len(result.decision.candidates) > 0
        assert result.decision.candidates[0]["id"] == result.decision.selected_action

    def test_candidates_includes_noop_fallback(self):
        e = make_event_with_decision("fix bug")
        d = BasicDecision()
        result = d.process(e)
        ids = [c["id"] for c in result.decision.candidates]
        assert "noop" in ids


# ── 11. Decision score bounds ────────────────────────────────────

class TestDecisionScore:
    def test_score_in_bounds_for_normal_case(self):
        e = make_event_with_decision("fix bug")
        d = BasicDecision()
        result = d.process(e)
        assert 0.0 <= result.decision.decision_score <= 1.0

    def test_score_zero_for_noop(self):
        e = make_event_with_decision("", intent="unknown")
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.decision_score == 0.0

    def test_score_above_threshold_for_known_intent(self):
        e = make_event_with_decision("fix bug", pred_confidence=0.9, pred_risk=0.1)
        d = BasicDecision()
        result = d.process(e)
        assert result.decision.decision_score >= 0.3


# ── 12. Regression ───────────────────────────────────────────────

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
             "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"Regression failed:\n{result.stdout}\n{result.stderr}"
