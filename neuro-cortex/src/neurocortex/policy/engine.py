"""Policy Engine — Situation → learned ranking → decision.

The policy layer is PURELY a consumer of Action Learning evidence. It
never recomputes outcomes, never reads predicted_prob/confidence, and
never fabricates evidence. It only turns an existing ranking into a
decision.

Decision semantics
------------------
- No evidence at all        → status="no_evidence", selected=None (undecided)
- Evidence below min        → status="insufficient_evidence", selected=None
- Evidence >= min           → status="decided", selected=top ranked action

Output dict (choose_action):
    {
      "situation": {...},
      "candidate_actions": [...],
      "selected_action": str | None,
      "decision_status": "decided"|"no_evidence"|"insufficient_evidence"|"disabled",
      "ranked_actions": [...],     # full Action Learning ranking
      "scores": {...},             # action -> score
      "evidence": {...},           # action -> support_count
      "match_levels": {...},       # action -> match_level
      "decision_reason": str,
      "shadow_only": bool,
    }
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PolicyConfig
from ..action_learning.schema import ActionLearningSituation


class PolicyEngine:
    """Situation → ranked actions → policy decision (consumer of ranking)."""

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self._config = config or PolicyConfig()

    @property
    def config(self) -> PolicyConfig:
        return self._config

    def choose_action(
        self,
        situation: ActionLearningSituation,
        candidate_actions: list[Any],
        ranked_actions: list[dict[str, Any]] | None = None,
        *,
        engine=None,
    ) -> dict[str, Any]:
        """Choose an action for a situation based on Action Learning ranking.

        ``ranked_actions`` may be passed directly (policy consumes ranking),
        or ``engine`` (ActionLearningEngine) may be provided to compute it.
        Policy itself never computes outcomes.
        """
        disabled = not self._config.enabled

        # Build ranking (from provided ranking or engine; never fabricated)
        if ranked_actions is None:
            if engine is None:
                ranked_actions = []
            else:
                ranked_actions = engine.rank_actions(situation, candidate_actions)

        scores = {}
        evidence = {}
        match_levels = {}
        for r in ranked_actions:
            scores[r["action_key"]] = r.get("score")
            evidence[r["action_key"]] = r.get("support_count", 0)
            match_levels[r["action_key"]] = r.get("match_level")

        if disabled or not ranked_actions:
            return {
                "situation": situation.to_dict() if hasattr(situation, "to_dict") else {"intent": getattr(situation, "intent", "")},
                "candidate_actions": [c.action_key if hasattr(c, "action_key") else str(c) for c in candidate_actions],
                "selected_action": None,
                "decision_status": "disabled" if disabled else "no_evidence",
                "ranked_actions": ranked_actions,
                "scores": scores,
                "evidence": evidence,
                "match_levels": match_levels,
                "decision_reason": "policy disabled" if disabled else "no ranking available",
                "shadow_only": self._config.shadow_only,
            }

        top = ranked_actions[0]
        top_support = top.get("support_count", 0)
        top_score = top.get("score")

        if top_score is None:
            return self._decision(
                situation, candidate_actions, ranked_actions,
                scores, evidence, match_levels,
                selected=None, status="no_evidence",
                reason="no evidence: no action has historical support",
            )

        if top_support < self._config.min_evidence:
            return self._decision(
                situation, candidate_actions, ranked_actions,
                scores, evidence, match_levels,
                selected=None, status="insufficient_evidence",
                reason=f"insufficient evidence: top support={top_support} < min_evidence={self._config.min_evidence}",
            )

        # Confidence gap check (optional): top-1 vs top-2
        # FIX 3: Properly handle negative gaps (when ranking is flawed)
        if len(ranked_actions) > 1:
            second_score = ranked_actions[1].get("score")
            if second_score is not None and top_score is not None:
                # Only check gap if top_score >= second_score (valid ranking)
                if top_score >= second_score:
                    gap = top_score - second_score
                    if gap < self._config.confidence_threshold:
                        return self._decision(
                            situation, candidate_actions, ranked_actions,
                            scores, evidence, match_levels,
                            selected=None, status="insufficient_evidence",
                            reason=f"score gap {gap:.3f} < threshold {self._config.confidence_threshold}",
                        )
                # If top_score < second_score, ranking is invalid - treat as error

        return self._decision(
            situation, candidate_actions, ranked_actions,
            scores, evidence, match_levels,
            selected=top["action_key"], status="decided",
            reason=(
                f"top-ranked by Action Learning: {top['action_key']} "
                f"(score={top_score:.3f}, support={top_support}, match=L{top.get('match_level')})"
            ),
        )

    def _decision(self, situation, candidates, ranked, scores, evidence, match_levels,
                  *, selected, status, reason) -> dict[str, Any]:
        return {
            "situation": situation.to_dict() if hasattr(situation, "to_dict") else {"intent": getattr(situation, "intent", "")},
            "candidate_actions": [c.action_key if hasattr(c, "action_key") else str(c) for c in candidates],
            "selected_action": selected,
            "decision_status": status,
            "ranked_actions": ranked,
            "scores": scores,
            "evidence": evidence,
            "match_levels": match_levels,
            "decision_reason": reason,
            "shadow_only": self._config.shadow_only,
        }

    def log_shadow(self, decision: dict[str, Any], *, original_action: str | None = None,
                   log_path: Path | None = None) -> None:
        """Record a shadow policy decision (append-only JSONL)."""
        path = Path(log_path) if log_path else self._config.log_path
        if path is None:
            return
        policy_action = decision.get("selected_action")
        original_action = original_action or ""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "situation": decision.get("situation"),
            "original_action": original_action,
            "policy_action": policy_action,
            "agreement": (original_action == policy_action) if policy_action else None,
            "decision_status": decision.get("decision_status"),
            "candidate_actions": decision.get("candidate_actions"),
            "ranking": [r.get("action_key") for r in decision.get("ranked_actions", [])],
            "scores": decision.get("scores"),
            "support": decision.get("evidence"),
            "match_levels": decision.get("match_levels"),
            "decision_reason": decision.get("decision_reason"),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
