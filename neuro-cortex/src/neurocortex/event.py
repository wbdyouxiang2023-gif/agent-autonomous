"""CortexEvent: unified data structure flowing through the cognitive lifecycle."""

from __future__ import annotations

import copy
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ── Enums ──────────────────────────────────────────────────────


class Source(Enum):
    """Where the input originated."""
    HUMAN = "human"
    SYSTEM = "system"
    SENSOR = "sensor"
    MEMORY_RETRIEVAL = "memory_retrieval"
    EXTERNAL_API = "external_api"


class ActionStatus(Enum):
    PLANNED = "planned"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class ActionType(Enum):
    NOOP = "noop"
    RESPOND = "respond"
    TOOL_CALL = "tool_call"
    CODE_REVIEW = "code_review"
    CODE_EDIT = "code_edit"


# ── Nested value objects ───────────────────────────────────────


@dataclass(frozen=True)
class PerceptionData:
    """Output of the perception stage — what the input IS."""
    raw_input: str = ""
    intent: str = ""
    emotion: str = ""
    risk: float = 0.0  # 0.0–1.0
    entities: list[str] = field(default_factory=list)
    confidence: float = 0.5  # 0.0–1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PerceptionData:
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in allowed}
        return cls(**filtered)


@dataclass
class RepresentationData:
    """Output of representation — structured features and embedding."""
    features: dict[str, float] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    raw_text: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepresentationData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AttentionData:
    """Output of attention — what was selected and why."""
    selected_items: list[str] = field(default_factory=list)
    attention_scores: dict[str, float] = field(default_factory=dict)
    attention_reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttentionData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class InternalState:
    """
    Dynamic internal state — evolves with every event.

    NOTE: Values are clamped to [0, 1] for this MVP implementation.
    This is a practical constraint, not a theoretical limit.
    Future versions may allow different ranges per state dimension
    (e.g. negativity for valence, unbounded for drive).
    """
    curiosity: float = 0.5
    caution: float = 0.3
    confidence: float = 0.5
    uncertainty: float = 0.2
    trust: float = 0.5
    motivation: float = 0.5
    novelty: float = 0.0
    goal_pressure: float = 0.0

    def clamp_all(self) -> None:
        for f in self.__dataclass_fields__.values():
            val = getattr(self, f.name)
            setattr(self, f.name, max(0.0, min(1.0, val)))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InternalState:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MemoryData:
    """Retrieved memories relevant to the current event."""
    retrieved_memories: list[dict[str, Any]] = field(default_factory=list)
    memory_scores: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PredictionData:
    """Output of prediction — what the system expects will happen."""
    predicted_outcome: str = ""
    success_probability: float = 0.5
    predicted_risk: float = 0.0
    prediction_confidence: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PredictionData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DecisionData:
    """Output of decision — why this action was chosen."""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    selected_action: str = ""
    decision_score: float = 0.5
    decision_reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ActionData:
    """The action taken and its execution status."""
    action_type: str = "noop"
    action_payload: dict[str, Any] = field(default_factory=dict)
    status: str = "planned"
    planned: bool = True
    actual: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class OutcomeData:
    """What actually happened after the action."""
    actual_outcome: str = ""
    success: bool = False
    error_message: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutcomeData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class FeedbackData:
    """Comparison of prediction vs outcome."""
    reward: float = 0.0  # can be negative
    prediction_error: float = 0.0
    user_feedback: str = ""
    evaluation: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LearningData:
    """What changed in the system as a result of this event."""
    learning_signal: str = ""
    memory_updates: list[str] = field(default_factory=list)
    state_updates: dict[str, float] = field(default_factory=dict)
    policy_updates: list[str] = field(default_factory=list)
    prediction_updates: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LearningData:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Core Event ─────────────────────────────────────────────────


class CortexEvent:
    """
    Unified data structure flowing through the full cognitive lifecycle.

    Standard lifecycle (strict linear progression via advance_to):
      INPUT → PERCEPTION → REPRESENTATION → ATTENTION → STATE
      → MEMORY → PREDICTION → DECISION → ACTION → OUTCOME → FEEDBACK → LEARNING

    Non-linear information flows are allowed at the module level (Phase 2+):
      - Memory can feed directly into Prediction or Attention
      - Feedback can update Internal State or Memory
      - Prediction can feed back into Decision without re-predicting

    Each stage has typed nested dataclasses to enforce data contracts:
      PerceptionData, RepresentationData, AttentionData, InternalState,
      MemoryData, PredictionData, DecisionData, ActionData,
      OutcomeData, FeedbackData, LearningData
    """

    # Valid stage progression
    STAGE_ORDER = (
        "INPUT", "PERCEPTION", "REPRESENTATION", "ATTENTION",
        "STATE", "MEMORY", "PREDICTION", "DECISION",
        "ACTION", "OUTCOME", "FEEDBACK", "LEARNING",
    )

    def __init__(
        self,
        raw_input: str = "",
        source: Source | str = Source.SYSTEM,
        session_id: str | None = None,
    ) -> None:
        self.id: str = uuid.uuid4().hex[:12]
        self.timestamp: str = datetime.now(timezone.utc).isoformat()
        self.session_id: str = session_id or uuid.uuid4().hex[:8]
        self.stage: str = "INPUT"
        self.raw_input: str = raw_input

        # Typed nested fields — all start empty
        self.perception: PerceptionData = PerceptionData(raw_input=raw_input)
        self.representation: RepresentationData = RepresentationData(raw_text=raw_input)
        self.attention: AttentionData = AttentionData()
        self.state: InternalState = InternalState()
        self.memory: MemoryData = MemoryData()
        self.prediction: PredictionData = PredictionData()
        self.decision: DecisionData = DecisionData()
        self.action: ActionData = ActionData()
        self.outcome: OutcomeData = OutcomeData()
        self.feedback: FeedbackData = FeedbackData()
        self.learning: LearningData = LearningData()

    # ── Stage transitions ─────────────────────────────────────

    def advance_to(self, target_stage: str) -> None:
        """Move to target_stage only if it is exactly the next stage in sequence."""
        if target_stage not in self.STAGE_ORDER:
            raise ValueError(f"Unknown stage: {target_stage}")
        current_idx = self.STAGE_ORDER.index(self.stage)
        target_idx = self.STAGE_ORDER.index(target_stage)
        if target_idx != current_idx + 1:
            raise ValueError(
                f"Must advance one stage at a time: {self.stage} → {target_stage}"
            )
        self.stage = target_stage

    def perceive(self, data: PerceptionData | dict[str, Any] | None = None) -> CortexEvent:
        """Update perception and advance to PERCEPTION stage."""
        if isinstance(data, dict):
            data = PerceptionData.from_dict(data)
        if data is not None:
            self.perception = data
        if self.stage == "INPUT":
            self.advance_to("PERCEPTION")
        return self

    def represent(self, data: RepresentationData | dict[str, Any] | None = None) -> CortexEvent:
        """Update representation and advance to REPRESENTATION stage."""
        if isinstance(data, dict):
            data = RepresentationData.from_dict(data)
        if data is not None:
            self.representation = data
        if self.stage == "PERCEPTION":
            self.advance_to("REPRESENTATION")
        return self

    def attend(self, data: AttentionData | dict[str, Any] | None = None) -> CortexEvent:
        """Update attention and advance to ATTENTION stage."""
        if isinstance(data, dict):
            data = AttentionData.from_dict(data)
        if data is not None:
            self.attention = data
        if self.stage == "REPRESENTATION":
            self.advance_to("ATTENTION")
        return self

    def update_state(self, data: InternalState | dict[str, Any] | None = None) -> CortexEvent:
        """Update internal state, clamp values, advance to STATE stage."""
        if isinstance(data, dict):
            data = InternalState.from_dict(data)
        if data is not None:
            self.state = data
            self.state.clamp_all()
        if self.stage == "ATTENTION":
            self.advance_to("STATE")
        return self

    def retrieve_memory(self, data: MemoryData | dict[str, Any] | None = None) -> CortexEvent:
        """Update retrieved memories and advance to MEMORY stage."""
        if isinstance(data, dict):
            data = MemoryData.from_dict(data)
        if data is not None:
            self.memory = data
        if self.stage == "STATE":
            self.advance_to("MEMORY")
        return self

    def predict(self, data: PredictionData | dict[str, Any] | None = None) -> CortexEvent:
        """Update prediction and advance to PREDICTION stage."""
        if isinstance(data, dict):
            data = PredictionData.from_dict(data)
        if data is not None:
            self.prediction = data
        if self.stage == "MEMORY":
            self.advance_to("PREDICTION")
        return self

    def decide(self, data: DecisionData | dict[str, Any] | None = None) -> CortexEvent:
        """Update decision and advance to DECISION stage."""
        if isinstance(data, dict):
            data = DecisionData.from_dict(data)
        if data is not None:
            self.decision = data
        if self.stage == "PREDICTION":
            self.advance_to("DECISION")
        return self

    def act(self, data: ActionData | dict[str, Any] | None = None) -> CortexEvent:
        """Update action and advance to ACTION stage."""
        if isinstance(data, dict):
            data = ActionData.from_dict(data)
        if data is not None:
            self.action = data
        if self.stage == "DECISION":
            self.advance_to("ACTION")
        return self

    def evaluate(self, data: OutcomeData | dict[str, Any] | None = None,
                 feedback: FeedbackData | dict[str, Any] | None = None) -> CortexEvent:
        """Record outcome and compute feedback in one call (convenience method)."""
        if isinstance(data, dict):
            data = OutcomeData.from_dict(data)
        if isinstance(feedback, dict):
            feedback = FeedbackData.from_dict(feedback)
        if data is not None:
            self.record_outcome(data)
        if feedback is not None:
            self.compute_feedback(feedback)
        return self

    def record_outcome(self, data: OutcomeData | dict[str, Any] | None = None) -> CortexEvent:
        """
        Record what actually happened in the real world.
        Outcome is a factual observation, not a system evaluation.
        """
        if isinstance(data, dict):
            data = OutcomeData.from_dict(data)
        if data is not None:
            self.outcome = data
        if self.stage == "ACTION":
            self.advance_to("OUTCOME")
        return self

    def compute_feedback(self, data: FeedbackData | dict[str, Any] | None = None) -> CortexEvent:
        """
        Compute the system's evaluation signal by comparing prediction against outcome.
        Feedback is derived, not directly observed — it is the bridge to learning.
        """
        if isinstance(data, dict):
            data = FeedbackData.from_dict(data)
        if data is not None:
            self.feedback = data
        if self.stage == "OUTCOME":
            self.advance_to("FEEDBACK")
        return self

    def learn(self, data: LearningData | dict[str, Any] | None = None) -> CortexEvent:
        """Update learning and advance to LEARNING stage."""
        if isinstance(data, dict):
            data = LearningData.from_dict(data)
        if data is not None:
            self.learning = data
        if self.stage == "FEEDBACK":
            self.advance_to("LEARNING")
        return self

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (nested dataclasses converted recursively)."""
        def _convert(v: Any) -> Any:
            if hasattr(v, "__dataclass_fields__"):
                return {k: _convert(val) for k, val in asdict(v).items()}
            if isinstance(v, Enum):
                return v.value
            return v
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "stage": self.stage,
            "raw_input": self.raw_input,
            "perception": _convert(self.perception),
            "representation": _convert(self.representation),
            "attention": _convert(self.attention),
            "state": _convert(self.state),
            "memory": _convert(self.memory),
            "prediction": _convert(self.prediction),
            "decision": _convert(self.decision),
            "action": _convert(self.action),
            "outcome": _convert(self.outcome),
            "feedback": _convert(self.feedback),
            "learning": _convert(self.learning),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CortexEvent:
        """Deserialize from a plain dict — reconstructs the full event."""
        event = cls(
            raw_input=data.get("raw_input", ""),
            session_id=data.get("session_id"),
        )
        event.id = data.get("id", event.id)
        event.timestamp = data.get("timestamp", event.timestamp)
        event.stage = data.get("stage", "INPUT")

        def _restore(cls_type, key: str, raw: Any) -> None:
            if raw and key in data:
                setattr(event, key, cls_type.from_dict(raw))

        _restore(PerceptionData, "perception", data.get("perception"))
        _restore(RepresentationData, "representation", data.get("representation"))
        _restore(AttentionData, "attention", data.get("attention"))
        _restore(InternalState, "state", data.get("state"))
        _restore(MemoryData, "memory", data.get("memory"))
        _restore(PredictionData, "prediction", data.get("prediction"))
        _restore(DecisionData, "decision", data.get("decision"))
        _restore(ActionData, "action", data.get("action"))
        _restore(OutcomeData, "outcome", data.get("outcome"))
        _restore(FeedbackData, "feedback", data.get("feedback"))
        _restore(LearningData, "learning", data.get("learning"))

        return event

    @classmethod
    def from_json(cls, json_str: str) -> CortexEvent:
        return cls.from_dict(json.loads(json_str))

    def copy(self) -> CortexEvent:
        """Deep copy — useful for branching experiments."""
        return self.from_dict(self.to_dict())

    def summary(self) -> str:
        """Human-readable summary of the event's current state."""
        lines = [
            f"[{self.stage}] id={self.id} session={self.session_id}",
            f"  input: {self.raw_input[:60]}{'...' if len(self.raw_input) > 60 else ''}",
        ]
        if self.perception.intent:
            lines.append(f"  intent: {self.perception.intent}")
        if self.prediction.predicted_outcome:
            lines.append(f"  predicted: {self.prediction.predicted_outcome} "
                         f"(p={self.prediction.success_probability:.2f})")
        if self.decision.selected_action:
            lines.append(f"  decided: {self.decision.selected_action}")
        if self.action.status != "planned":
            lines.append(f"  action: {self.action.status} — {self.action.action_type}")
        if self.outcome.actual_outcome:
            lines.append(f"  outcome: {'success' if self.outcome.success else 'failure'}")
        if self.learning.learning_signal:
            lines.append(f"  learning: {self.learning.learning_signal}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"CortexEvent(id={self.id!r}, stage={self.stage!r}, input={self.raw_input!r})"
