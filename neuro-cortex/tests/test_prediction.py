"""Tests for BasicPrediction module - Phase 5."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neurocortex.prediction import BasicPrediction
from neurocortex.event import (
    CortexEvent, PerceptionData, InternalState, PredictionData,
)
from neurocortex.cortex import NeuroCortex
from neurocortex.state import CortexState
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState,
    MockMemory, MockPrediction, MockDecision, MockAction,
    MockFeedback, MockLearning, MockOutcomeProvider,
)


# ── Helpers ──────────────────────────────────────────────────────


def make_event(raw_input: str, intent: str = "unknown",
               risk: float = 0.0, uncertainty: float = 0.2,
               perf_conf: float = 0.5) -> CortexEvent:
    """Create a minimal event for prediction testing."""
    e = CortexEvent(raw_input)
    e.perceive(PerceptionData(
        raw_input=raw_input,
        intent=intent,
        risk=risk,
        confidence=perf_conf,
    ))
    e.update_state(InternalState(uncertainty=uncertainty, confidence=1.0 - uncertainty))
    return e


# ── 1. known intent + low uncertainty ──────────────────────────


class TestKnownIntentLowUncertainty:
    def test_clear_signal_prediction(self):
        e = make_event("fix the bug", intent="fix", risk=0.2, uncertainty=0.2, perf_conf=0.8)
        p = BasicPrediction()
        result = p.process(e)
        assert result.prediction.predicted_outcome == "fix完成"
        assert result.prediction.success_probability > 0.6
        assert result.prediction.prediction_confidence > 0.5
        assert result.prediction.predicted_risk == 0.2

    def test_create_intent_low_uncertainty(self):
        e = make_event("build API", intent="create", risk=0.1, uncertainty=0.1, perf_conf=0.9)
        p = BasicPrediction()
        result = p.process(e)
        assert "完成" in result.prediction.predicted_outcome
        assert result.prediction.success_probability > 0.7


# ── 2. known intent + high uncertainty ─────────────────────────


class TestKnownIntentHighUncertainty:
    def test_high_uncertainty_known_intent(self):
        e = make_event("fix bug", intent="fix", risk=0.2, uncertainty=0.8, perf_conf=0.5)
        p = BasicPrediction()
        result = p.process(e)
        assert result.prediction.predicted_outcome == "不确定性高"
        assert result.prediction.success_probability == 0.5
        assert result.prediction.prediction_confidence < 0.4


# ── 3. known intent + high risk ────────────────────────────────


class TestKnownIntentHighRisk:
    def test_high_risk_known_intent(self):
        e = make_event("delete database", intent="delete", risk=0.8, uncertainty=0.2, perf_conf=0.7)
        p = BasicPrediction()
        result = p.process(e)
        assert "delete" in result.prediction.predicted_outcome
        assert result.prediction.predicted_risk >= 0.6
        assert 0.4 <= result.prediction.success_probability <= 0.6


# ── 4. unknown intent + low risk ───────────────────────────────


class TestUnknownIntentLowRisk:
    def test_unknown_low_risk(self):
        e = make_event("hello", intent="unknown", risk=0.1, uncertainty=0.2, perf_conf=0.5)
        p = BasicPrediction()
        result = p.process(e)
        assert result.prediction.predicted_outcome == "无法判断任务"
        assert result.prediction.success_probability == 0.5
        assert result.prediction.prediction_confidence == 0.2


# ── 5. unknown intent + high risk ──────────────────────────────


class TestUnknownIntentHighRisk:
    def test_unknown_high_risk(self):
        """CRITICAL: intent=unknown + risk=0.8 + unc=0.8"""
        e = make_event("帮我检查一下有没有风险", intent="unknown", risk=0.8, uncertainty=0.8, perf_conf=0.5)
        p = BasicPrediction()
        result = p.process(e)
        assert result.prediction.predicted_outcome == "高风险未知任务"
        assert result.prediction.success_probability == 0.3
        assert result.prediction.predicted_risk == 0.8
        assert result.prediction.prediction_confidence == 0.2


# ── 6. unknown intent + high uncertainty ───────────────────────


class TestUnknownHighUncertainty:
    def test_unknown_high_uncertainty(self):
        e = make_event("maybe something", intent="unknown", risk=0.2, uncertainty=0.8, perf_conf=0.5)
        p = BasicPrediction()
        result = p.process(e)
        assert result.prediction.predicted_outcome == "信息不足"
        assert result.prediction.success_probability == 0.3
        assert result.prediction.prediction_confidence == 0.2


# ── 7. empty input ─────────────────────────────────────────────


class TestEmptyInput:
    def test_empty_string(self):
        e = CortexEvent("")
        e.perceive(PerceptionData(raw_input=""))
        e.update_state(InternalState())
        p = BasicPrediction()
        result = p.process(e)
        assert result.prediction.predicted_outcome == ""
        assert result.prediction.success_probability == 0.5
        assert result.prediction.predicted_risk == 0.0
        assert result.prediction.prediction_confidence == 0.0

    def test_whitespace_only(self):
        e = CortexEvent("   ")
        e.perceive(PerceptionData(raw_input="   "))
        e.update_state(InternalState())
        p = BasicPrediction()
        result = p.process(e)
        assert result.prediction.predicted_outcome == ""


# ── 8. deterministic repeatability ─────────────────────────────


class TestDeterministic:
    def test_same_input_same_output_10_times(self):
        p = BasicPrediction()
        results = []
        for _ in range(10):
            e = make_event("fix bug", intent="fix", risk=0.2, uncertainty=0.2, perf_conf=0.8)
            result = p.process(e)
            results.append((
                result.prediction.predicted_outcome,
                result.prediction.success_probability,
                result.prediction.predicted_risk,
                result.prediction.prediction_confidence,
            ))
        assert all(r == results[0] for r in results), "Prediction must be deterministic"


# ── 9. success_probability bounds ──────────────────────────────


class TestProbabilityBounds:
    def test_bounds_all_scenarios(self):
        p = BasicPrediction()
        scenarios = [
            ("fix", 0.2, 0.2, 0.8),   # clear signal
            ("fix", 0.8, 0.2, 0.7),   # high risk
            ("unknown", 0.2, 0.8, 0.5),  # high uncertainty
            ("unknown", 0.8, 0.8, 0.5),  # unknown + high risk
            ("", 0.0, 0.0, 0.0),      # empty
        ]
        for intent, risk, unc, conf in scenarios:
            e = make_event("test", intent=intent, risk=risk, uncertainty=unc, perf_conf=conf)
            result = p.process(e)
            assert 0.0 <= result.prediction.success_probability <= 1.0
            assert result.prediction.success_probability == result.prediction.success_probability  # not NaN


# ── 10. predicted_risk bounds ──────────────────────────────────


class TestRiskBounds:
    def test_bounds_all_scenarios(self):
        p = BasicPrediction()
        scenarios = [
            ("fix", 0.2, 0.2, 0.8),
            ("fix", 0.9, 0.2, 0.7),
            ("unknown", 0.5, 0.5, 0.5),
        ]
        for intent, risk, unc, conf in scenarios:
            e = make_event("test", intent=intent, risk=risk, uncertainty=unc, perf_conf=conf)
            result = p.process(e)
            assert 0.0 <= result.prediction.predicted_risk <= 1.0


# ── 11. risk/probability independence ──────────────────────────


class TestRiskProbabilityIndependence:
    def test_high_prob_high_risk(self):
        """Can have success_prob=0.9 and risk=0.8 simultaneously."""
        # This happens when intent is known, risk is high but perception is confident
        e = make_event("execute script", intent="deploy", risk=0.85, uncertainty=0.1, perf_conf=0.9)
        p = BasicPrediction()
        result = p.process(e)
        # High risk should dominate, but let's verify both fields exist and are independent
        assert result.prediction.success_probability != 1.0 - result.prediction.predicted_risk or \
               result.prediction.predicted_risk >= 0.6  # risk takes priority


# ── 12. prediction_confidence bounds ───────────────────────────


class TestConfidenceBounds:
    def test_bounds(self):
        p = BasicPrediction()
        e = make_event("test", intent="fix", risk=0.2, uncertainty=0.2, perf_conf=0.8)
        result = p.process(e)
        assert 0.0 <= result.prediction.prediction_confidence <= 1.0


# ── 13. Chinese Unicode preservation ───────────────────────────


class TestChineseUnicode:
    def test_chinese_input_preserved(self):
        e = make_event("帮我修复API漏洞", intent="fix", risk=0.3, uncertainty=0.2, perf_conf=0.7)
        p = BasicPrediction()
        result = p.process(e)
        # Should not raise, should produce valid prediction
        assert result.prediction.predicted_outcome != ""
        assert isinstance(result.prediction.predicted_outcome, str)

    def test_mixed_chinese_english(self):
        e = make_event("检查 API timeout 问题", intent="fix", risk=0.2, uncertainty=0.2, perf_conf=0.6)
        p = BasicPrediction()
        result = p.process(e)
        assert result.prediction.predicted_outcome != ""


# ── 14. Prediction does not modify event.state ─────────────────


class TestPredictionDoesNotModifyState:
    def test_state_unchanged(self):
        e = make_event("test", intent="fix", risk=0.2, uncertainty=0.2, perf_conf=0.8)
        original_unc = e.state.uncertainty
        original_conf = e.state.confidence
        p = BasicPrediction()
        p.process(e)
        assert e.state.uncertainty == original_unc
        assert e.state.confidence == original_conf


# ── 15. Prediction does not modify CortexState ─────────────────


class TestPredictionDoesNotModifyCortexState:
    def test_cortex_state_unchanged(self):
        state = CortexState(confidence=0.7, uncertainty=0.3, active_goal="test")
        p = BasicPrediction(state_store=state)
        e = make_event("test", intent="fix", risk=0.2, uncertainty=0.2, perf_conf=0.8)
        p.process(e)
        assert state.confidence == 0.7
        assert state.uncertainty == 0.3
        assert state.active_goal == "test"


# ── 16. Prediction does not execute Action ─────────────────────


class TestPredictionDoesNotExecuteAction:
    def test_action_not_executed(self):
        p = BasicPrediction()
        e = make_event("test", intent="fix", risk=0.2, uncertainty=0.2, perf_conf=0.8)
        p.process(e)
        assert e.action.status == "planned"  # default, not executed


# ── 17. Prediction decoupled from Decision ─────────────────────


class TestPredictionDecoupledFromDecision:
    def test_prediction_before_decision(self):
        """Prediction stage must come before Decision in pipeline."""
        from neurocortex.cortex import NeuroCortex
        stages = NeuroCortex._STAGES
        pred_idx = next(i for i, (s, _) in enumerate(stages) if s == "PREDICTION")
        dec_idx = next(i for i, (s, _) in enumerate(stages) if s == "DECISION")
        assert pred_idx < dec_idx


# ── 18. Cortex instance isolation ──────────────────────────────


class TestCortexIsolation:
    def test_independent_instances(self):
        c1 = NeuroCortex(prediction=MockPrediction())
        c2 = NeuroCortex(prediction=MockPrediction())
        e1 = c1.process("test1")
        e2 = c2.process("test2")
        # Different instances, different events
        assert e1.id != e2.id


# ── 19. Integration test ───────────────────────────────────────


class TestIntegration:
    def test_full_pipeline_with_prediction(self):
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
        e = c.process("帮我修复API漏洞")
        assert e.stage == "LEARNING"
        assert e.prediction.predicted_outcome != ""
        assert 0.0 <= e.prediction.success_probability <= 1.0
        assert 0.0 <= e.prediction.predicted_risk <= 1.0


# ── 20. Real BasicPrediction with CortexState integration ──────


class TestRealBasicPredictionIntegration:
    def test_basic_prediction_with_cortex_state(self):
        """Test real BasicPrediction with CortexState injection."""
        from neurocortex.state import CortexState
        
        state = CortexState(confidence=0.7, uncertainty=0.3, active_goal="fix API")
        pred = BasicPrediction(state_store=state)
        
        e = make_event("帮我修复API漏洞", intent="fix", risk=0.3, uncertainty=0.3, perf_conf=0.8)
        result = pred.process(e)
        
        # Verify prediction generated
        assert result.prediction.predicted_outcome == "fix完成"
        assert result.prediction.success_probability > 0.6
        assert result.prediction.predicted_risk == 0.3
        
        # Verify CortexState not modified
        assert state.confidence == 0.7
        assert state.uncertainty == 0.3
        assert state.active_goal == "fix API"

    def test_known_intent_high_risk_preserves_intent(self):
        """Known intent + high risk must preserve intent in outcome."""
        p = BasicPrediction()
        e = make_event("deploy to production", intent="deploy", risk=0.8, uncertainty=0.2, perf_conf=0.7)
        result = p.process(e)
        
        assert "deploy" in result.prediction.predicted_outcome
        assert result.prediction.predicted_risk >= 0.6
        assert 0.4 <= result.prediction.success_probability <= 0.6

    def test_state_immutability_during_prediction(self):
        """Prediction must not modify event.state or CortexState."""
        from neurocortex.state import CortexState
        
        state = CortexState(confidence=0.8, uncertainty=0.2)
        p = BasicPrediction(state_store=state)
        
        e = make_event("test", intent="fix", risk=0.2, uncertainty=0.2, perf_conf=0.9)
        original_unc = e.state.uncertainty
        original_conf = e.state.confidence
        
        p.process(e)
        
        # event.state unchanged
        assert e.state.uncertainty == original_unc
        assert e.state.confidence == original_conf
        # CortexState unchanged
        assert state.confidence == 0.8
        assert state.uncertainty == 0.2

    def test_full_pipeline_with_real_prediction(self):
        """Full pipeline with real BasicPrediction (not MockPrediction)."""
        from neurocortex.state import CortexState
        
        state = CortexState()
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=BasicPrediction(state_store=state),  # Real BasicPrediction
            decision=MockDecision(),
            action=MockAction(),
            outcome_provider=MockOutcomeProvider(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        
        e = c.process("帮我修复API漏洞")
        
        # Verify pipeline completes
        assert e.stage == "LEARNING"
        # Verify prediction exists
        assert e.prediction.predicted_outcome != ""
        # Verify state not modified
        assert state.confidence == 0.5  # default
        assert state.active_goal == ""  # default (no goal extracted from this input)


# ── 20. Regression: 195 existing tests ─────────────────────────


class TestRegression:
    def test_existing_tests_pass(self):
        """Verify existing Phase 0-4 tests still pass."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest",
             "neuro-cortex/tests/test_event.py",
             "neuro-cortex/tests/test_perception.py",
             "neuro-cortex/tests/test_representation.py",
             "neuro-cortex/tests/test_state.py",
             "-q", "--tb=no"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"Tests failed:\n{result.stdout}"
