"""Phase 1 tests for CortexEvent."""
import json
import pytest
from src.neurocortex.event import (
    CortexEvent,
    PerceptionData,
    RepresentationData,
    AttentionData,
    InternalState,
    MemoryData,
    PredictionData,
    DecisionData,
    ActionData,
    OutcomeData,
    FeedbackData,
    LearningData,
    Source,
    ActionStatus,
    ActionType,
)


# ── Initialization ─────────────────────────────────────────────


class TestEventInit:
    def test_default_init(self):
        e = CortexEvent()
        assert e.raw_input == ""
        assert e.stage == "INPUT"
        assert e.perception.raw_input == ""
        assert e.state.curiosity == 0.5
        assert len(e.id) == 12  # hex truncated uuid4

    def test_init_with_input(self):
        e = CortexEvent(raw_input="hello world", source=Source.HUMAN)
        assert e.raw_input == "hello world"
        assert e.perception.raw_input == "hello world"
        assert e.representation.raw_text == "hello world"

    def test_init_with_session_id(self):
        e = CortexEvent(session_id="abc123")
        assert e.session_id == "abc123"

    def test_init_generates_unique_ids(self):
        e1 = CortexEvent()
        e2 = CortexEvent()
        assert e1.id != e2.id
        assert e1.session_id != e2.session_id

    def test_init_with_string_source(self):
        e = CortexEvent(source="human")
        assert e.stage == "INPUT"  # source is accepted but not stored directly


# ── Stage transitions ──────────────────────────────────────────


class TestStageTransitions:
    def test_perceive_advances_stage(self):
        e = CortexEvent(raw_input="test")
        assert e.stage == "INPUT"
        e.perceive()
        assert e.stage == "PERCEPTION"

    def test_perceive_with_data(self):
        e = CortexEvent(raw_input="buy shoes")
        e.perceive(PerceptionData(intent="purchase", confidence=0.9))
        assert e.perception.intent == "purchase"
        assert e.perception.confidence == 0.9
        assert e.stage == "PERCEPTION"

    def test_perceive_with_dict(self):
        e = CortexEvent(raw_input="fix bug")
        e.perceive({"intent": "debug", "risk": 0.3})
        assert e.perception.intent == "debug"
        assert e.perception.risk == 0.3

    def test_represent_advances_stage(self):
        e = CortexEvent(raw_input="code").perceive()
        e.represent(RepresentationData(features={"len": 4}, embedding=[0.1, 0.2]))
        assert e.stage == "REPRESENTATION"
        assert e.representation.features == {"len": 4}

    def test_represent_with_dict(self):
        e = CortexEvent(raw_input="x").perceive()
        e.represent({"features": {"a": 1.0}, "raw_text": "x"})
        assert e.representation.features["a"] == 1.0

    def test_attend_advances_stage(self):
        e = CortexEvent("x").perceive().represent()
        e.attend(AttentionData(selected_items=["key"], attention_scores={"key": 0.8}))
        assert e.stage == "ATTENTION"
        assert e.attention.selected_items == ["key"]

    def test_update_state_clamps_values(self):
        e = CortexEvent("x").perceive().represent().attend()
        e.update_state(InternalState(curiosity=1.5, caution=-0.3, uncertainty=2.0))
        assert e.state.curiosity == 1.0
        assert e.state.caution == 0.0
        assert e.state.uncertainty == 1.0
        assert e.stage == "STATE"

    def test_update_state_with_dict(self):
        e = CortexEvent("x").perceive().represent().attend()
        e.update_state({"curiosity": 0.9, "motivation": 0.7})
        assert e.state.curiosity == 0.9
        assert e.state.motivation == 0.7

    def test_retrieve_memory_advances_stage(self):
        e = CortexEvent("x").perceive().represent().attend().update_state()
        e.retrieve_memory(MemoryData(retrieved_memories=[{"id": "m1"}]))
        assert e.stage == "MEMORY"
        assert e.memory.retrieved_memories[0]["id"] == "m1"

    def test_predict_advances_stage(self):
        e = CortexEvent("x").perceive().represent().attend().update_state().retrieve_memory()
        e.predict(PredictionData(success_probability=0.85, predicted_risk=0.1))
        assert e.stage == "PREDICTION"
        assert e.prediction.success_probability == 0.85

    def test_decide_advances_stage(self):
        e = CortexEvent("x").perceive().represent().attend().update_state()\
           .retrieve_memory().predict()
        e.decide(DecisionData(selected_action="edit_file", decision_score=0.7))
        assert e.stage == "DECISION"
        assert e.decision.selected_action == "edit_file"

    def test_act_advances_stage(self):
        e = CortexEvent("x").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide()
        e.act(ActionData(action_type="code_edit", status="executing"))
        assert e.stage == "ACTION"
        assert e.action.status == "executing"

    def test_evaluate_advances_stage(self):
        e = CortexEvent("x").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide().act()
        e.evaluate(
            OutcomeData(actual_outcome="file edited", success=True),
            FeedbackData(reward=1.0, prediction_error=0.15)
        )
        assert e.stage == "FEEDBACK"
        assert e.outcome.success is True
        assert e.feedback.reward == 1.0

    def test_record_outcome_advances_stage(self):
        e = CortexEvent("x").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide().act()
        e.record_outcome(OutcomeData(actual_outcome="file saved", success=True))
        assert e.stage == "OUTCOME"
        assert e.outcome.actual_outcome == "file saved"

    def test_compute_feedback_advances_stage(self):
        e = CortexEvent("x").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide().act()\
           .record_outcome(OutcomeData(success=True))
        e.compute_feedback(FeedbackData(reward=1.0, prediction_error=0.1))
        assert e.stage == "FEEDBACK"
        assert e.feedback.reward == 1.0

    def test_outcome_and_feedback_are_separate(self):
        """Outcome and Feedback occupy distinct stages with independent data."""
        e = CortexEvent("x").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide().act()
        e.record_outcome(OutcomeData(actual_outcome="crash", success=False))
        assert e.stage == "OUTCOME"
        assert e.outcome.success is False
        assert e.feedback.reward == 0.0  # not yet computed
        e.compute_feedback(FeedbackData(reward=-1.0))
        assert e.stage == "FEEDBACK"
        assert e.feedback.reward == -1.0

    def test_learn_advances_stage(self):
        e = CortexEvent("x").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide().act()\
           .record_outcome(OutcomeData(actual_outcome="done", success=True))\
           .compute_feedback(FeedbackData(reward=1.0))
        e.learn(LearningData(learning_signal="positive", state_updates={"confidence": 0.7}))
        assert e.stage == "LEARNING"
        assert e.learning.learning_signal == "positive"
        assert e.learning.state_updates["confidence"] == 0.7

    def test_full_pipeline(self):
        e = (CortexEvent("optimize the algorithm")
             .perceive(PerceptionData(intent="optimize", confidence=0.85))
             .represent(RepresentationData(features={"complexity": 3}))
             .attend(AttentionData(selected_items=["algorithm"], attention_reason="high priority")))
        assert e.stage == "ATTENTION"
        assert e.perception.intent == "optimize"
        assert e.attention.selected_items == ["algorithm"]

    def test_cannot_go_backward(self):
        e = CortexEvent("x").perceive()
        # Already at PERCEPTION, calling perceive() again is a no-op
        e.perceive()
        assert e.stage == "PERCEPTION"

    def test_cannot_jump_ahead_without_sequence(self):
        e = CortexEvent("x")
        # Must call perceive() before represent(), etc.
        with pytest.raises(ValueError, match="one stage"):
            e.advance_to("REPRESENTATION")  # skips PERCEPTION

    def test_unknown_stage_raises(self):
        e = CortexEvent("x")
        with pytest.raises(ValueError, match="Unknown stage"):
            e.advance_to("UNKNOWN")


# ── Type / boundary validation ────────────────────────────────


class TestTypeAndBoundary:
    def test_empty_event_serializes_cleanly(self):
        e = CortexEvent()
        d = e.to_dict()
        assert d["stage"] == "INPUT"
        assert d["raw_input"] == ""
        assert d["perception"]["raw_input"] == ""
        assert d["state"]["curiosity"] == 0.5

    def test_null_data_does_not_override(self):
        e = CortexEvent(raw_input="hello").perceive(PerceptionData(intent="buy"))
        # Second perceive with None is a no-op (stage already PERCEPTION)
        e.perceive(None)
        assert e.perception.intent == "buy"

    def test_representation_embedding_is_list(self):
        e = CortexEvent().represent(RepresentationData(embedding=[0.1, 0.2, 0.3]))
        assert e.representation.embedding == [0.1, 0.2, 0.3]

    def test_action_data_defaults(self):
        e = CortexEvent().act()
        assert e.action.action_type == "noop"
        assert e.action.status == "planned"
        assert e.action.planned is True
        assert e.action.actual is False


# ── Serialization ─────────────────────────────────────────────


class TestSerialization:
    def test_to_dict_contains_all_stages(self):
        e = CortexEvent("test input").perceive().represent().attend().update_state()
        d = e.to_dict()
        assert "perception" in d
        assert "representation" in d
        assert "attention" in d
        assert "state" in d
        assert "memory" in d
        assert "prediction" in d
        assert "decision" in d
        assert "action" in d
        assert "outcome" in d
        assert "feedback" in d
        assert "learning" in d

    def test_to_json_roundtrip(self):
        e = CortexEvent("hello").perceive(PerceptionData(intent="greet"))
        json_str = e.to_json()
        restored = CortexEvent.from_json(json_str)
        assert restored.raw_input == "hello"
        assert restored.perception.intent == "greet"
        assert restored.id == e.id
        assert restored.session_id == e.session_id

    def test_to_dict_is_json_serializable(self):
        e = CortexEvent("test").perceive(PerceptionData(intent="x", confidence=0.9))
        d = e.to_dict()
        json.dumps(d)  # should not raise

    def test_serialization_preserves_enum_values(self):
        e = CortexEvent()
        d = e.to_dict()
        assert isinstance(d["stage"], str)
        assert d["state"]["curiosity"] == 0.5


# ── Deserialization ───────────────────────────────────────────


class TestDeserialization:
    def test_from_dict_restores_all_fields(self):
        e = CortexEvent("original").perceive(
            PerceptionData(intent="search", confidence=0.95, risk=0.2)
        ).represent(RepresentationData(features={"tokens": 5}, embedding=[0.5]))
        restored = CortexEvent.from_dict(e.to_dict())
        assert restored.raw_input == "original"
        assert restored.perception.intent == "search"
        assert restored.perception.confidence == 0.95
        assert restored.representation.features["tokens"] == 5
        assert restored.representation.embedding == [0.5]

    def test_from_dict_handles_partial_data(self):
        partial = {"raw_input": "hi", "stage": "INPUT"}
        e = CortexEvent.from_dict(partial)
        assert e.raw_input == "hi"
        assert e.stage == "INPUT"
        assert e.perception.raw_input == "hi"

    def test_from_dict_preserves_id_and_timestamp(self):
        e = CortexEvent("x")
        original_id = e.id
        restored = CortexEvent.from_dict(e.to_dict())
        assert restored.id == original_id
        assert restored.timestamp == e.timestamp


# ── Round-trip ────────────────────────────────────────────────


class TestRoundTrip:
    def test_full_pipeline_roundtrip(self):
        e = (CortexEvent("build a web API")
             .perceive(PerceptionData(intent="build", confidence=0.9))
             .represent(RepresentationData(features={"type": "api"}))
             .attend(AttentionData(selected_items=["api", "build"]))
             .update_state(InternalState(curiosity=0.8, motivation=0.9))
             .retrieve_memory(MemoryData(retrieved_memories=[{"context": "similar project"}]))
             .predict(PredictionData(success_probability=0.7, predicted_risk=0.3))
             .decide(DecisionData(selected_action="create_project", decision_score=0.75))
             .act(ActionData(action_type="tool_call", status="success"))
             .evaluate(
                 OutcomeData(actual_outcome="project created", success=True),
                 FeedbackData(reward=0.8, prediction_error=0.05)
             )
             .learn(LearningData(
                 learning_signal="success",
                 state_updates={"confidence": 0.85},
                 memory_updates=["created api project"]
             )))

        restored = CortexEvent.from_dict(e.to_dict())

        assert restored.raw_input == e.raw_input
        assert restored.perception.intent == e.perception.intent
        assert restored.representation.features["type"] == "api"
        assert restored.attention.selected_items == ["api", "build"]
        assert restored.state.curiosity == 0.8
        assert restored.memory.retrieved_memories[0]["context"] == "similar project"
        assert restored.prediction.success_probability == 0.7
        assert restored.decision.selected_action == "create_project"
        assert restored.action.status == "success"
        assert restored.outcome.success is True
        assert restored.feedback.reward == 0.8
        assert restored.learning.state_updates["confidence"] == 0.85
        assert restored.learning.memory_updates == ["created api project"]
        assert restored.id == e.id

    def test_copy_creates_independent_event(self):
        e = CortexEvent("test").perceive(PerceptionData(intent="original"))
        copy = e.copy()
        copy.represent(RepresentationData(features={"x": 1}))
        assert e.representation.features == {}
        assert copy.representation.features == {"x": 1}


# ── Summary ───────────────────────────────────────────────────


class TestSummary:
    def test_summary_shows_key_info(self):
        e = CortexEvent("fix auth bug")
        e.perceive(PerceptionData(intent="debug"))
        e.predict(PredictionData(predicted_outcome="patch works", success_probability=0.6))
        e.decide(DecisionData(selected_action="patch_auth"))
        e.act(ActionData(status="success"))
        e.evaluate(OutcomeData(success=True, actual_outcome="bug fixed"))
        s = e.summary()
        assert "[LEARNING]" not in s  # not yet
        assert "fix auth bug" in s
        assert "debug" in s
        assert "patch_auth" in s

    def test_summary_after_learning(self):
        e = CortexEvent("x").perceive().represent().attend().update_state()\
           .retrieve_memory().predict().decide().act()\
           .record_outcome(OutcomeData(success=True))\
           .compute_feedback(FeedbackData(reward=0.5))\
           .learn(LearningData(learning_signal="improved"))
        s = e.summary()
        assert "improved" in s


# ── Edge cases ────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_string_input(self):
        e = CortexEvent(raw_input="")
        assert e.raw_input == ""
        assert e.perception.raw_input == ""
        e.perceive()
        assert e.stage == "PERCEPTION"

    def test_very_long_input(self):
        long_input = "x" * 10000
        e = CortexEvent(raw_input=long_input)
        assert e.raw_input == long_input
        d = e.to_dict()
        assert len(d["raw_input"]) == 10000

    def test_special_characters_in_input(self):
        e = CortexEvent(raw_input="你好 🌍 <script>alert('xss')</script>")
        assert "你好" in e.raw_input
        restored = CortexEvent.from_dict(e.to_dict())
        assert restored.raw_input == e.raw_input

    def test_decision_candidates_preserved(self):
        e = CortexEvent().decide(DecisionData(
            candidates=[{"id": "a", "score": 0.9}, {"id": "b", "score": 0.7}],
            selected_action="a"
        ))
        restored = CortexEvent.from_dict(e.to_dict())
        assert len(restored.decision.candidates) == 2
        assert restored.decision.candidates[0]["id"] == "a"

    def test_action_payload_preserved(self):
        e = CortexEvent().act(ActionData(
            action_type="tool_call",
            action_payload={"command": "git status"},
            status="success"
        ))
        restored = CortexEvent.from_dict(e.to_dict())
        assert restored.action.action_payload["command"] == "git status"
