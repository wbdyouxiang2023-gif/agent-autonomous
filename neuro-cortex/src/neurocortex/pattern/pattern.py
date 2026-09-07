"""Pattern dataclass — abstracted rule derived from multiple experiences."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ── Pattern Lifecycle Status ─────────────────────────────────────

PATTERN_LIFECYCLE = (
    "CANDIDATE", "OBSERVED", "SUPPORTED", "STABLE",
    "WEAKENING", "RETIRED",
)


# ── Pattern Schema ───────────────────────────────────────────────

@dataclass
class Pattern:
    """
    Abstracted rule derived from multiple similar experiences.

    A Pattern captures a generalizable relationship between conditions
    (intent + action_type) and outcomes (success rate), extracted from
    groups of experiences that share the same structural context.

    Lifecycle:
      CANDIDATE → OBSERVED → SUPPORTED → STABLE
           ↑         ↓
           └── WEAKENING ←──┘
                   ↓
                RETIRED

    Support Score Model:
      support_score = success_rate * weight(support_count, contradiction_rate)
      - success_rate = success_count / total
      - weight increases with support_count (step function)
      - weight decreases with contradiction_rate
      - NOT a probability: it is a quality weight for experience evidence
    """

    # Identity
    pattern_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_experience_ids: list[str] = field(default_factory=list)

    # Condition (the "when")
    condition_intent: str = ""
    condition_action_type: str = ""

    # Prediction (the "what")
    predicted_outcome: str = ""
    success_rate: float = 0.5

    # Evidence
    support_count: int = 0        # experiences matching this condition
    contradiction_count: int = 0  # experiences that disagree with majority outcome
    support_score: float = 0.0    # 0.0–1.0, quality weight for evidence (NOT a probability)

    # Backward-compatible alias: confidence → support_score
    @property
    def confidence(self) -> float:
        """Deprecated alias for support_score. Use support_score instead."""
        return self.support_score

    @confidence.setter
    def confidence(self, value: float) -> None:
        self.support_score = value

    # Lifecycle
    status: str = "CANDIDATE"     # CANDIDATE | OBSERVED | SUPPORTED | STABLE | WEAKENING | RETIRED
    last_observed_at: str = ""
    last_contradicted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "pattern_id": self.pattern_id,
            "created_at": self.created_at,
            "source_experience_ids": self.source_experience_ids,
            "condition_intent": self.condition_intent,
            "condition_action_type": self.condition_action_type,
            "predicted_outcome": self.predicted_outcome,
            "success_rate": self.success_rate,
            "support_count": self.support_count,
            "contradiction_count": self.contradiction_count,
            "support_score": self.support_score,
            "status": self.status,
            "last_observed_at": self.last_observed_at,
            "last_contradicted_at": self.last_contradicted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Pattern":
        """Deserialize from dict, handling missing fields gracefully.

        Backward-compatible: reads both 'support_score' (new) and
        'confidence' (legacy) field names.
        """
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in allowed}
        # Legacy: map 'confidence' → 'support_score'
        if "confidence" in filtered and "support_score" not in filtered:
            filtered["support_score"] = filtered.pop("confidence")
        return cls(**filtered)

    @classmethod
    def create(
        cls,
        condition_intent: str,
        condition_action_type: str,
        experiences: list[Any],
        predicted_outcome: str = "",
    ) -> "Pattern":
        """
        Factory: build a Pattern from a group of experiences sharing the same condition.

        Args:
            condition_intent: The intent label (e.g., "fix", "create")
            condition_action_type: The action type (e.g., "code_review", "code_edit")
            experiences: List of Experience objects (must have .success, .predicted_prob)
            predicted_outcome: Override outcome text (auto-derived if empty)
        """
        if not experiences:
            return cls(
                condition_intent=condition_intent,
                condition_action_type=condition_action_type,
                predicted_outcome=predicted_outcome or f"{condition_intent}完成",
                success_rate=0.5,
                support_count=0,
                support_score=0.0,
                status="CANDIDATE",
            )

        success_count = sum(1 for e in experiences if e.success)
        failure_count = len(experiences) - success_count
        total = len(experiences)
        success_rate = success_count / total if total > 0 else 0.5

        # Determine majority outcome for contradiction counting
        majority_success = success_count >= failure_count
        contradiction_count = 0
        if majority_success:
            contradiction_count = failure_count
        else:
            contradiction_count = success_count

        # Auto-derived predicted_outcome
        if not predicted_outcome:
            intent_label = condition_intent or "general"
            predicted_outcome = f"{intent_label}完成"

        # Compute support_score using evidence model
        support_score = cls._compute_support_score(success_rate, total, contradiction_count, total)

        # Determine lifecycle status
        status = cls._determine_status(total, contradiction_count, success_rate)

        # Extract source experience IDs
        source_ids = [e.experience_id for e in experiences if hasattr(e, 'experience_id')]

        import uuid as _uuid
        return cls(
            pattern_id=_uuid.uuid4().hex[:12],
            created_at=datetime.now(timezone.utc).isoformat(),
            source_experience_ids=source_ids,
            condition_intent=condition_intent,
            condition_action_type=condition_action_type,
            predicted_outcome=predicted_outcome,
            success_rate=success_rate,
            support_count=total,
            contradiction_count=contradiction_count,
            support_score=support_score,
            status=status,
            last_observed_at=datetime.now(timezone.utc).isoformat(),
            last_contradicted_at=datetime.now(timezone.utc).isoformat() if contradiction_count > 0 else None,
        )

    @staticmethod
    def _compute_support_score(
        success_rate: float,
        support_count: int,
        contradiction_count: int,
        total: int,
    ) -> float:
        """
        Compute pattern support_score from evidence.

        Formula: support_score = success_rate * evidence_weight

        evidence_weight:
          - 0 experiences: 0.0
          - 1-2 experiences: 0.3 (insufficient evidence)
          - 3-4 experiences: 0.6 (emerging evidence)
          - 5+ experiences: 0.9 (substantial evidence)
        - Contradiction penalty: if contradiction_rate > 50%, cap at 0.2
        """
        if total == 0:
            return 0.0

        # Evidence weight based on support count
        if support_count < 3:
            evidence_weight = 0.3
        elif support_count < 5:
            evidence_weight = 0.6
        else:
            evidence_weight = 0.9

        # Contradiction penalty
        contradiction_rate = contradiction_count / total if total > 0 else 0.0
        if contradiction_rate > 0.5:
            # Actively wrong pattern — cap support_score
            return min(success_rate * evidence_weight, 0.2)

        support_score = success_rate * evidence_weight
        return max(0.0, min(1.0, support_score))

    @staticmethod
    def _determine_status(
        support_count: int,
        contradiction_count: int,
        success_rate: float,
    ) -> str:
        """
        Determine pattern lifecycle status from evidence.

        Rules:
          - contradiction_rate > 50% → WEAKENING
          - support_count >= 5 AND contradiction_rate <= 20% → STABLE
          - support_count >= 3 AND contradiction_rate <= 33% → SUPPORTED
          - support_count >= 2 → OBSERVED
          - support_count >= 1 → CANDIDATE
          - contradiction_rate > 50% → WEAKENING (overrides all)
        """
        total = support_count
        if total == 0:
            return "CANDIDATE"

        contradiction_rate = contradiction_count / total

        # Critical: actively contradicting
        if contradiction_rate > 0.5:
            return "WEAKENING"

        if total >= 5 and contradiction_rate <= 0.2:
            return "STABLE"
        if total >= 3 and contradiction_rate <= 1.0 / 3.0:
            return "SUPPORTED"
        if total >= 2:
            return "OBSERVED"
        return "CANDIDATE"

    def retire(self) -> None:
        """Mark pattern as retired."""
        self.status = "RETIRED"
        import datetime as _dt
        self.last_contradicted_at = _dt.datetime.now(timezone.utc).isoformat()

    def is_active(self) -> bool:
        """Check if pattern is usable for prediction."""
        return self.status not in ("RETIRED", "WEAKENING")

    def __repr__(self) -> str:
        return (
            f"Pattern(id={self.pattern_id}, condition=({self.condition_intent!r},"
            f" {self.condition_action_type!r}), rate={self.success_rate:.2f},"
            f" support={self.support_score:.2f}, status={self.status})"
        )
