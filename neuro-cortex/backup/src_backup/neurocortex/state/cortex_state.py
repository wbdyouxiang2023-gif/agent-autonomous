"""CortexState - persistent working state for NeuroCortex session."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=False)
class CortexState:
    """
    Authoritative persistent working state for a NeuroCortex session.

    Properties:
    - Session-scoped: survives across events within one Cortex instance
    - Deterministic: same event sequence → same state (ignoring timestamp)
    - UTF-8 native: Chinese text preserved exactly
    - Reserved fields: curiosity (Phase 5+)

    NOT:
    - Cross-process persistent (no database/files)
    - Long-term memory (Phase 5+ Memory module)
    - Semantic understanding (deterministic heuristics only)
    """

    uncertainty: float = 0.2
    confidence: float = 0.5
    active_goal: str = ""
    recent_inputs: list[str] = field(default_factory=list)
    last_updated: Optional[datetime] = None

    # RESERVED for Phase 5+: curiosity dynamics
    _curiosity_reserved: float = 0.5

    @property
    def curiosity(self) -> float:
        """Reserved field - returns default value. Do not modify in Phase 4."""
        return self._curiosity_reserved

    def update_from_event(self, event: "CortexEvent") -> None:
        """
        Single authoritative state transition.

        Rules:
        1. Uncertainty: inversely proportional to perception confidence
        2. Confidence: increases on success, decreases on explicit failure
        3. Active goal: extracted from intent or request pattern
        4. Recent inputs: append raw_input, cap at 10
        5. Timestamp: metadata only, not used in transitions
        """
        # 1. Uncertainty update
        perf_conf = event.perception.confidence
        if perf_conf > 0.6:
            self.uncertainty = max(0.0, self.uncertainty - 0.05)
        elif perf_conf < 0.3:
            self.uncertainty = min(1.0, self.uncertainty + 0.1)

        # 2. Confidence update (based on outcome semantics)
        if event.outcome.success:
            self.confidence = min(1.0, self.confidence + 0.05)
        elif not event.outcome.success and event.outcome.actual_outcome != "":
            # Explicit failure: success=False AND non-empty outcome
            self.confidence = max(0.0, self.confidence - 0.1)
            self.uncertainty = min(1.0, self.uncertainty + 0.1)
        # else: unknown/no outcome → no transition

        # 3. Active goal update (working goal candidate, heuristic)
        goal = self._extract_goal_candidate(event)
        if goal:
            self.active_goal = goal

        # 4. Recent inputs buffer (UTF-8 preserved, no truncation)
        self.recent_inputs.append(event.raw_input)
        if len(self.recent_inputs) > 10:
            self.recent_inputs = self.recent_inputs[-10:]

        # 5. Timestamp (metadata only)
        self.last_updated = datetime.now(timezone.utc)

    def _extract_goal_candidate(self, event: "CortexEvent") -> str:
        """
        Extract working goal candidate from event.

        This is a DETERMINISTIC HEURISTIC, not semantic understanding.

        Priority:
        1. If intent is known → use intent label
        2. If input_type is "request" → extract from request pattern
        3. Otherwise → empty string (no goal candidate)
        """
        # Case 1: Known intent
        if (
            event.perception.intent
            and event.perception.intent != "unknown"
        ):
            return event.perception.intent

        # Case 2: Request pattern (Chinese/English heuristic)
        if event.perception.metadata.get("input_type") == "request":
            return self._strip_request_prefix(event.raw_input)

        # Case 3: No goal
        return ""

    @staticmethod
    def _strip_request_prefix(text: str) -> str:
        """
        Remove common request prefixes to extract core task.
        String manipulation, not semantic understanding.
        """
        prefixes = [
            "帮我", "请帮我", "能不能帮我", "我想", "需要",
            "help me", "please help", "I want to", "can you",
        ]
        for prefix in prefixes:
            if text.startswith(prefix):
                return text[len(prefix):].strip()
        return text[:50]

    def to_internal_state(self) -> "InternalState":
        """Create per-event snapshot. One-way projection."""
        from neurocortex.event import InternalState
        return InternalState(
            uncertainty=self.uncertainty,
            confidence=self.confidence,
            curiosity=self._curiosity_reserved,
            motivation=0.5,
        )

    def to_dict(self) -> dict:
        """Serialize state (for debugging/future phases)."""
        return {
            "uncertainty": self.uncertainty,
            "confidence": self.confidence,
            "active_goal": self.active_goal,
            "recent_inputs": self.recent_inputs,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CortexState":
        """Deserialize state with invariant guarantees."""
        # Clamp numeric fields
        uncertainty = max(0.0, min(1.0, data.get("uncertainty", 0.2)))
        confidence = max(0.0, min(1.0, data.get("confidence", 0.5)))

        # Cap recent_inputs to 10
        recent_inputs = list(data.get("recent_inputs", []))
        if len(recent_inputs) > 10:
            recent_inputs = recent_inputs[-10:]

        return cls(
            uncertainty=uncertainty,
            confidence=confidence,
            active_goal=data.get("active_goal", ""),
            recent_inputs=recent_inputs,
        )

    def reset(self) -> None:
        """Return to initial state."""
        self.uncertainty = 0.2
        self.confidence = 0.5
        self.active_goal = ""
        self.recent_inputs = []
        self.last_updated = None

    def __eq__(self, other: object) -> bool:
        """Equality excluding timestamp (deterministic comparison)."""
        if not isinstance(other, CortexState):
            return NotImplemented
        return (
            self.uncertainty == other.uncertainty
            and self.confidence == other.confidence
            and self.active_goal == other.active_goal
            and self.recent_inputs == other.recent_inputs
            # last_updated intentionally excluded
        )

    def __repr__(self) -> str:
        return (
            f"CortexState(uncertainty={self.uncertainty:.2f}, "
            f"confidence={self.confidence:.2f}, "
            f"goal={self.active_goal!r})"
        )
