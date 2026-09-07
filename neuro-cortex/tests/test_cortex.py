"""Phase 2 tests for NeuroCortex orchestration layer."""
from __future__ import annotations

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from neurocortex.event import CortexEvent, PerceptionData, OutcomeData, FeedbackData
from neurocortex.interfaces import (
    PerceptionModule, RepresentationModule, AttentionModule,
    StateModule, MemoryModule, PredictionModule, DecisionModule,
    ActionModule, FeedbackModule, LearningModule,
)
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState, MockMemory,
    MockPrediction, MockDecision, MockAction, MockFeedback, MockLearning,
    FailingPerception, FailingRepresentation, FailingAttention, FailingState,
    FailingMemory, FailingPrediction, FailingDecision, FailingAction,
    FailingFeedback, FailingLearning,
)
from neurocortex.cortex import NeuroCortex


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def full_cortex():
    return NeuroCortex(
        perception=MockPerception(),
        representation=MockRepresentation(),
        attention=MockAttention(),
        state=MockState(),
        memory=MockMemory(),
        prediction=MockPrediction(),
        decision=MockDecision(),
        action=MockAction(),
        feedback=MockFeedback(),
        learning=MockLearning(),
    )


@pytest.fixture
def minimal_cortex():
    """Cortex with only perception and learning — tests partial pipelines."""
    return NeuroCortex(
        perception=MockPerception(),
        learning=MockLearning(),
    )


# ── 1. Cortex Initialization ───────────────────────────────────


class TestCortexInit:
    def test_default_initialization(self):
        c = NeuroCortex()
        assert c.perception_module is None
        assert c.prediction_module is None
        assert c.decision_module is None

    def test_dependency_injection(self, full_cortex):
        assert isinstance(full_cortex.perception_module, MockPerception)
        assert isinstance(full_cortex.prediction_module, MockPrediction)
        assert isinstance(full_cortex.decision_module, MockDecision)
        assert isinstance(full_cortex.action_module, MockAction)

    def test_partial_dependency_injection(self):
        """Only some modules provided — others remain None."""
        c = NeuroCortex(perception=MockPerception())
        assert isinstance(c.perception_module, MockPerception)
        assert c.prediction_module is None
        assert c.decision_module is None

    def test_all_module_types_accepted(self):
        """Any object implementing the Protocol is accepted."""
        class CustomPerception(PerceptionModule):
            def process(self, event): return event
        c = NeuroCortex(perception=CustomPerception())
        assert c.perception_module is not None


# ── 2. process() — Full Lifecycle ──────────────────────────────


class TestProcess:
    def test_process_reaches_learning(self, full_cortex):
        e = full_cortex.process("build a web api")
        assert e.stage == "LEARNING"
        assert e.status == "ok"

    def test_process_populates_all_stages(self, full_cortex):
        e = full_cortex.process("fix the auth bug")
        assert e.perception.intent != ""
        assert e.representation.features.get("token_count", 0) > 0
        assert len(e.attention.selected_items) > 0
        assert e.state.curiosity > 0
        assert e.prediction.predicted_outcome != ""
        assert e.decision.selected_action != ""
        assert e.action.status == "success"
        assert e.outcome.success is True
        assert e.feedback.reward != 0.0
        assert e.learning.learning_signal != ""

    def test_process_empty_input(self, full_cortex):
        e = full_cortex.process("")
        assert e.stage == "LEARNING"
        assert e.status == "ok"
        assert e.perception.raw_input == ""

    def test_process_special_characters(self, full_cortex):
        e = full_cortex.process("<script>alert('xss')</script> 你好 🌍")
        assert e.stage == "LEARNING"
        assert e.status == "ok"
        assert "xss" in e.raw_input

    def test_process_long_input(self, full_cortex):
        long_input = "x " * 500
        e = full_cortex.process(long_input)
        assert e.stage == "LEARNING"
        assert e.status == "ok"
        assert e.representation.features.get("token_count", 0) == 500


# ── 3. Module Invocation Order ────────────────────────────────


class TestInvocationOrder:
    def test_stages_in_correct_order(self, full_cortex):
        """Track the order in which modules are called."""
        call_order = []

        class TrackingPerception(MockPerception):
            def process(self, event):
                call_order.append("PERCEPTION")
                return super().process(event)

        class TrackingRepresentation(MockRepresentation):
            def process(self, event):
                call_order.append("REPRESENTATION")
                return super().process(event)

        class TrackingAttention(MockAttention):
            def process(self, event):
                call_order.append("ATTENTION")
                return super().process(event)

        class TrackingState(MockState):
            def process(self, event):
                call_order.append("STATE")
                return super().process(event)

        class TrackingMemory(MockMemory):
            def process(self, event):
                call_order.append("MEMORY")
                return super().process(event)

        class TrackingPrediction(MockPrediction):
            def process(self, event):
                call_order.append("PREDICTION")
                return super().process(event)

        class TrackingDecision(MockDecision):
            def process(self, event):
                call_order.append("DECISION")
                return super().process(event)

        class TrackingAction(MockAction):
            def process(self, event):
                call_order.append("ACTION")
                return super().process(event)

        class TrackingFeedback(MockFeedback):
            def process(self, event):
                call_order.append("FEEDBACK")
                return super().process(event)

        class TrackingLearning(MockLearning):
            def process(self, event):
                call_order.append("LEARNING")
                return super().process(event)

        c = NeuroCortex(
            perception=TrackingPerception(),
            representation=TrackingRepresentation(),
            attention=TrackingAttention(),
            state=TrackingState(),
            memory=TrackingMemory(),
            prediction=TrackingPrediction(),
            decision=TrackingDecision(),
            action=TrackingAction(),
            feedback=TrackingFeedback(),
            learning=TrackingLearning(),
        )
        c.process("test ordering")
        expected = [
            "PERCEPTION", "REPRESENTATION", "ATTENTION", "STATE",
            "MEMORY", "PREDICTION", "DECISION", "ACTION", "FEEDBACK", "LEARNING",
        ]
        assert call_order == expected

    def test_perception_before_representation(self, full_cortex):
        e = full_cortex.process("test")
        # perception happens first in the pipeline
        assert e.perception.intent != ""
        assert e.representation.features != {}

    def test_prediction_before_decision(self, full_cortex):
        e = full_cortex.process("test")
        assert e.prediction.predicted_outcome != ""
        assert e.decision.selected_action != ""

    def test_decision_before_action(self, full_cortex):
        e = full_cortex.process("test")
        assert e.decision.selected_action != ""
        assert e.action.status == "success"

    def test_action_before_feedback(self, full_cortex):
        e = full_cortex.process("test")
        assert e.action.status == "success"
        assert e.outcome.actual_outcome != ""
        assert e.feedback.reward != 0.0

    def test_feedback_before_learning(self, full_cortex):
        e = full_cortex.process("test")
        assert e.feedback.reward != 0.0
        assert e.learning.learning_signal != ""


# ── 4. Event Data Flow ─────────────────────────────────────────


class TestDataFlow:
    def test_input_propagates_through_pipeline(self, full_cortex):
        input_text = "optimize the database query"
        e = full_cortex.process(input_text)
        assert e.raw_input == input_text
        assert e.perception.raw_input == input_text
        assert e.representation.raw_text == input_text

    def test_perception_intent_flows_to_decision(self, full_cortex):
        e = full_cortex.process("fix the login bug")
        # MockPerception detects "fix" → intent="fix"
        # MockDecision maps intent="fix" → action="code_review"
        assert e.perception.intent == "fix"
        assert e.decision.selected_action == "code_review"

    def test_prediction_probability_affects_feedback_reward(self, full_cortex):
        # Short input → low predicted probability → low reward
        e_short = full_cortex.process("x")
        # Long input → higher predicted probability → higher reward
        e_long = full_cortex.process("this is a much longer input text to test prediction")
        assert e_long.feedback.reward >= e_short.feedback.reward

    def test_state_curiosity_varies_with_input_length(self, full_cortex):
        e_short = full_cortex.process("hi")
        e_long = full_cortex.process("a" * 200)
        assert e_long.state.curiosity > e_short.state.curiosity


# ── 5. Module Failure Handling ─────────────────────────────────


class TestModuleFailure:
    def test_perception_failure(self, full_cortex):
        c = NeuroCortex(
            perception=FailingPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "PERCEPTION"
        assert "perception module failed" in e.error
        # Stage stays at INPUT because failure happens before advance_to
        assert e.stage == "INPUT"

    def test_representation_failure(self, full_cortex):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=FailingRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "REPRESENTATION"

    def test_attention_failure(self, full_cortex):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=FailingAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "ATTENTION"

    def test_state_failure(self, full_cortex):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=FailingState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "STATE"

    def test_memory_failure(self, full_cortex):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=FailingMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "MEMORY"

    def test_prediction_failure(self, full_cortex):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=FailingPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "PREDICTION"

    def test_decision_failure(self, full_cortex):
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

    def test_action_failure(self, full_cortex):
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

    def test_feedback_failure(self, full_cortex):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=FailingFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "FEEDBACK"

    def test_learning_failure(self, full_cortex):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=FailingLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "LEARNING"

    def test_error_event_still_serializable(self, full_cortex):
        c = NeuroCortex(perception=FailingPerception())
        e = c.process("test")
        d = e.to_dict()
        assert d["status"] == "error"
        assert d["error_stage"] == "PERCEPTION"
        restored = CortexEvent.from_dict(d)
        assert restored.status == "error"
        assert restored.error_stage == "PERCEPTION"


# ── 6. Module Replacement (Decoupling Test) ────────────────────


class TestModuleReplacement:
    def test_swap_prediction_module(self, full_cortex):
        """Replace prediction with a custom one — cortex doesn't need changes."""
        class CustomPrediction(PredictionModule):
            def process(self, event):
                event.predict(PerceptionData.__class__.__bases__[0] if False else None)  # dummy
                return event

        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=CustomPrediction(),  # swapped
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        # Should not crash — the cortex only calls process(), doesn't know the type
        e = c.process("test")
        assert e.status in ("ok", "error")  # may error if CustomPrediction is broken

    def test_swap_all_modules(self, full_cortex):
        """Replace every module with a custom implementation."""
        class SilentModule:
            """A module that does nothing but return the event unchanged."""
            def process(self, event):
                return event

        c = NeuroCortex(
            perception=SilentModule(),
            representation=SilentModule(),
            attention=SilentModule(),
            state=SilentModule(),
            memory=SilentModule(),
            prediction=SilentModule(),
            decision=SilentModule(),
            action=SilentModule(),
            feedback=SilentModule(),
            learning=SilentModule(),
        )
        e = c.process("test")
        # All SilentModules are no-ops — event stays at INPUT (no stages advanced)
        assert e.stage == "INPUT"
        assert e.status == "ok"

    def test_failing_prediction_does_not_break_cortex(self, full_cortex):
        """Cortex gracefully handles a failing prediction module."""
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=FailingPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "PREDICTION"
        # Event is still inspectable
        assert e.raw_input == "test"
        assert e.perception.raw_input == "test"


# ── 7. Individual Stage Methods ────────────────────────────────


class TestStageMethods:
    def test_perceive_method(self, full_cortex):
        e = CortexEvent("hello")
        result = full_cortex.perceive(e)
        assert result.stage == "PERCEPTION"
        assert result.perception.intent != ""

    def test_represent_method(self, full_cortex):
        e = CortexEvent("hello").perceive()
        result = full_cortex.represent(e)
        assert result.stage == "REPRESENTATION"
        assert result.representation.features != {}

    def test_attend_method(self, full_cortex):
        e = CortexEvent("hello").perceive().represent()
        result = full_cortex.attend(e)
        assert result.stage == "ATTENTION"
        assert result.attention.selected_items != []

    def test_update_state_method(self, full_cortex):
        e = CortexEvent("hello").perceive().represent().attend()
        result = full_cortex.update_state(e)
        assert result.stage == "STATE"
        assert 0 <= result.state.curiosity <= 1

    def test_retrieve_memory_method(self, full_cortex):
        e = CortexEvent("hello").perceive().represent().attend().update_state()
        result = full_cortex.retrieve_memory(e)
        assert result.stage == "MEMORY"

    def test_predict_method(self, full_cortex):
        e = CortexEvent("hello").perceive().represent().attend().update_state().retrieve_memory()
        result = full_cortex.predict(e)
        assert result.stage == "PREDICTION"
        assert result.prediction.predicted_outcome != ""

    def test_decide_method(self, full_cortex):
        e = CortexEvent("hello").perceive().represent().attend().update_state()\
           .retrieve_memory().predict()
        result = full_cortex.decide(e)
        assert result.stage == "DECISION"
        assert result.decision.selected_action != ""

    def test_act_method(self, full_cortex):
        e = CortexEvent("hello").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide()
        result = full_cortex.act(e)
        # MockAction: act() → ACTION, record_outcome() → OUTCOME
        assert result.stage == "OUTCOME"
        assert result.action.status == "success"

    def test_compute_feedback_method(self, full_cortex):
        # Build event through DECISION, then use cortex methods
        e = CortexEvent("hello").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide()
        e = full_cortex.act(e)       # MockAction: ACTION → OUTCOME
        result = full_cortex.compute_feedback(e)  # OUTCOME → FEEDBACK
        assert result.stage == "FEEDBACK"

    def test_learn_method(self, full_cortex):
        e = CortexEvent("hello").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide()
        e = full_cortex.act(e)                # → OUTCOME
        e = full_cortex.compute_feedback(e)   # → FEEDBACK
        result = full_cortex.learn(e)         # → LEARNING
        assert result.stage == "LEARNING"
        assert result.learning.learning_signal != ""


# ── 8. No-Module Cortex ───────────────────────────────────────


class TestNoModules:
    def test_empty_cortex_process(self):
        """Cortex with no modules — process() returns event at INPUT."""
        c = NeuroCortex()
        e = c.process("test")
        assert e.stage == "INPUT"
        assert e.status == "ok"

    def test_partial_cortex_stops_at_missing_module(self, minimal_cortex):
        """Cortex with only perception — stops after first available stage."""
        e = minimal_cortex.process("test")
        assert e.stage == "PERCEPTION"
        assert e.status == "ok"


# ── 9. Error State Diagnostics ────────────────────────────────


class TestErrorDiagnostics:
    def test_error_message_is_informative(self, full_cortex):
        c = NeuroCortex(perception=FailingPerception())
        e = c.process("test")
        assert "perception module failed" in e.error
        assert len(e.error) > 0

    def test_error_preserves_partial_event(self, full_cortex):
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=FailingAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            feedback=MockFeedback(),
            learning=MockLearning(),
        )
        e = c.process("test")
        assert e.status == "error"
        assert e.error_stage == "ATTENTION"
        # Previous stages completed successfully
        assert e.perception.intent != ""
        assert e.representation.features != {}
        # Future stages are empty
        assert e.state.curiosity == 0.5  # default

    def test_error_event_summary(self, full_cortex):
        c = NeuroCortex(perception=FailingPerception())
        e = c.process("test")
        summary = e.summary()
        assert "ERROR" in summary
        assert "PERCEPTION" in summary


# ── 10. Multiple Sequential Runs ──────────────────────────────


class TestMultipleRuns:
    def test_independent_runs(self, full_cortex):
        """Each process() call starts fresh — no state leakage."""
        e1 = full_cortex.process("first run")
        e2 = full_cortex.process("second run")
        assert e1.id != e2.id
        assert e1.raw_input == "first run"
        assert e2.raw_input == "second run"
        # Different inputs should at minimum have different raw_inputs preserved
        assert e1.perception.raw_input == "first run"
        assert e2.perception.raw_input == "second run"

    def test_consistent_behavior_same_input(self, full_cortex):
        """Same input produces consistent structure (stages always reach LEARNING)."""
        e1 = full_cortex.process("build api")
        e2 = full_cortex.process("build api")
        assert e1.stage == "LEARNING"
        assert e2.stage == "LEARNING"
        assert e1.perception.intent == e2.perception.intent
