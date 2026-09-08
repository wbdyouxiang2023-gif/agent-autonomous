"""Action Learning Engine — real-outcome-driven, situation-aware action value learning.

Level 3.5-D:
  - Statistics keyed by situation_key + action_key (NOT bare action_key).
    situation_key = "intent:<intent>" for phase 1 (task_type/error_type are
    absent in the current Event schema and are NEVER fabricated).
  - Hierarchical evidence lookup per candidate:
        L1 exact situation + action
        L2 intent + action
        L3 global action (fallback only, never overrides specific)
  - Learning gate: only success=True / success=False update statistics.
    UNKNOWN (success=None) NEVER updates. predicted_prob / confidence /
    uncertainty / prediction_error are NEVER read as outcomes.

Storage (~/.neurocortex_action_statistics.json):
    {
      "intent:fix|action:code_edit": {success_count, failure_count, total_count,
                                       last_seen, updated_at},
      ...
    }
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import ActionLearningConfig
from .matcher import match_situation
from .schema import (
    ActionLearningCandidate,
    ActionLearningOutcome,
    ActionLearningSituation,
)

if TYPE_CHECKING:
    from ..event import Experience

NO_EVIDENCE = None


def situation_key(situation: ActionLearningSituation) -> str:
    """Build the situation identity used in statistics keys (phase 1: intent)."""
    intent = (situation.intent or "").strip().lower()
    return f"intent:{intent}" if intent else "intent:__none__"


def stat_key(situation_key_str: str, action_key: str) -> str:
    return f"{situation_key_str}|action:{action_key}"


def parse_stat_key(key: str) -> tuple[str, str]:
    if "|action:" in key:
        sit, _, act = key.partition("|action:")
        return sit, act
    return "intent:__global__", key


class StatisticsStore:
    """JSON persistence for situation-aware action statistics (atomic writes)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path).expanduser() if path else None
        self._data: dict[str, dict[str, Any]] = {}
        self._dirty = False
        if self._path and self._path.exists():
            self._load()

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return
            self._data = raw
        except (json.JSONDecodeError, OSError, TypeError):
            self._data = {}

    def save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix=self._path.name + ".", suffix=".tmp", dir=str(self._path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
            self._dirty = False
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    def get_for(self, situation_key_str: str, action_key: str) -> dict[str, Any] | None:
        return self.get(stat_key(situation_key_str, action_key))

    def get_global_for(self, action_key: str) -> dict[str, Any] | None:
        entries = []
        for k, v in self._data.items():
            _, act = parse_stat_key(k)
            if act == action_key:
                entries.append(v)
        if not entries:
            return None
        return {
            "success_count": sum(int(e.get("success_count", 0)) for e in entries),
            "failure_count": sum(int(e.get("failure_count", 0)) for e in entries),
            "total_count": sum(int(e.get("total_count", 0)) for e in entries),
            "last_seen": max((e.get("last_seen", "") for e in entries), default=""),
            "updated_at": max((e.get("updated_at", "") for e in entries), default=""),
        }

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {k: dict(v) for k, v in self._data.items()}

    def record(self, sit_key: str, action_key: str, success: bool, observed_at: str) -> None:
        key = stat_key(sit_key, action_key)
        entry = self._data.get(key)
        if entry is None:
            entry = {
                "success_count": 0,
                "failure_count": 0,
                "total_count": 0,
                "last_seen": "",
                "updated_at": "",
            }
            self._data[key] = entry
        if success:
            entry["success_count"] = int(entry.get("success_count", 0)) + 1
        else:
            entry["failure_count"] = int(entry.get("failure_count", 0)) + 1
        entry["total_count"] = int(entry.get("total_count", 0)) + 1
        entry["last_seen"] = observed_at
        entry["updated_at"] = observed_at
        self._dirty = True

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._dirty

    def clear(self) -> None:
        self._data = {}
        self._dirty = True


def _age_days(ts: str, now: datetime | None = None) -> float:
    if not ts:
        return 0.0
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return max(0.0, (now - dt).total_seconds() / 86400.0)
    except (ValueError, TypeError):
        return 0.0


class ActionLearningEngine:
    """Evaluate & rank candidate actions using situation-aware real-outcome statistics."""

    def __init__(self, config: ActionLearningConfig | None = None, store: StatisticsStore | None = None) -> None:
        self._config = config or ActionLearningConfig()
        self._store = store or StatisticsStore(self._config.statistics_path)

    @property
    def config(self) -> ActionLearningConfig:
        return self._config

    @property
    def store(self) -> StatisticsStore:
        return self._store

    def evaluate_candidates(
        self,
        situation: ActionLearningSituation,
        candidates: list[ActionLearningCandidate | str],
        experiences: list["Experience"] | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate each candidate for a situation (situation-aware)."""
        cands = [self._coerce_candidate(c) for c in candidates]
        if not cands:
            return []

        sit_key = situation_key(situation)
        threshold = self._config.situation_evidence_threshold

        evaluated = []
        for idx, cand in enumerate(cands):
            specific = self._store.get_for(sit_key, cand.action_key)
            global_stats = self._store.get_global_for(cand.action_key)

            specific_support = (
                int(specific.get("success_count", 0)) + int(specific.get("failure_count", 0))
                if specific else 0
            )

            if specific is not None and specific_support >= threshold:
                stats = specific
                match_level = 1
            elif global_stats is not None:
                stats = global_stats
                match_level = 3
            else:
                stats = None
                match_level = None

            hist = self._history_evidence(stats) if stats else self._empty_history()

            semantic = 0.0
            sem_level = None
            if experiences:
                semantic, sem_level = self._semantic_evidence(situation, cand, experiences)

            recency = self._recency_bonus(stats) if stats else 0.0

            hist_score = hist["history_score"]
            confidence = hist["confidence"]
            support = hist["support_count"]
            if hist_score is None:
                score = None
                evidence_status = "no_evidence"
            else:
                score = (
                    self._config.history_weight * hist_score
                    + self._config.semantic_weight * semantic
                    + self._config.recency_weight * recency
                )
                score = max(0.0, min(1.0, score))
                evidence_status = "evidence"

            evaluated.append({
                "action_key": cand.action_key,
                "action_type": cand.action_type,
                "strategy": cand.strategy,
                "score": score,
                "estimated_success": hist_score,
                "support_count": support,
                "success_count": hist["success_count"],
                "failure_count": hist["failure_count"],
                "confidence": confidence,
                "semantic_evidence": round(semantic, 4),
                "recency_bonus": round(recency, 4),
                "match_level": match_level if match_level is not None else sem_level,
                "evidence_status": evidence_status,
                "situation_key": sit_key,
                "original_index": idx,
            })

        return self._sort_ranked(evaluated)

    def rank_actions(
        self,
        situation: ActionLearningSituation,
        candidate_actions: list[ActionLearningCandidate | str],
        experiences: list["Experience"] | None = None,
    ) -> list[dict[str, Any]]:
        return self.evaluate_candidates(situation, candidate_actions, experiences)

    def record_outcome(
        self,
        situation: ActionLearningSituation,
        action: ActionLearningCandidate | str,
        outcome: ActionLearningOutcome,
    ) -> bool:
        """Record a REAL outcome into situation-aware statistics.

        Only success=True / success=False update. UNKNOWN (None) is ignored.
        """
        if not self._config.enabled:
            return False
        if outcome.success is None:
            return False
        cand = self._coerce_candidate(action)
        if not cand.action_key:
            return False
        sit_key = situation_key(situation)
        self._store.record(sit_key, cand.action_key, bool(outcome.success), outcome.observed_at)
        self._store.save()
        return True

    def explain(self, ranked: list[dict[str, Any]]) -> str:
        if not ranked:
            return "No candidate actions to explain."
        lines = ["Action Learning explanation:"]
        for r in ranked:
            if r["evidence_status"] == "no_evidence":
                lines.append(
                    f"  {r['action_key']}: no historical evidence (fallback to existing strategy)"
                )
            else:
                lines.append(
                    f"  {r['action_key']}: {r['success_count']} successes / "
                    f"{r['support_count']} attempts (est. success {r['estimated_success']:.2f}, "
                    f"match L{r['match_level']}, conf {r['confidence']:.2f}, score {r['score']:.2f})"
                )
        return "\n".join(lines)

    # ── internals ──────────────────────────────────────────────

    @staticmethod
    def _coerce_candidate(c: ActionLearningCandidate | str) -> ActionLearningCandidate:
        if isinstance(c, str):
            return ActionLearningCandidate(action_type=c, strategy=c)
        return c

    def _empty_history(self) -> dict[str, Any]:
        return {
            "history_score": NO_EVIDENCE,
            "confidence": NO_EVIDENCE,
            "support_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "match_level": None,
        }

    def _history_evidence(self, stats: dict[str, Any]) -> dict[str, Any]:
        success = int(stats.get("success_count", 0))
        failure = int(stats.get("failure_count", 0))
        support = success + failure
        if support == 0:
            return self._empty_history()

        alpha = self._config.smoothing_alpha
        beta = self._config.smoothing_beta
        smoothed = (success + alpha) / (support + alpha + beta)
        confidence = support / (support + self._config.confidence_k)
        hist_score = smoothed * confidence + self._config.prior_rate * (1.0 - confidence)

        return {
            "history_score": round(hist_score, 4),
            "confidence": round(confidence, 4),
            "support_count": support,
            "success_count": success,
            "failure_count": failure,
            "match_level": None,
        }

    def _semantic_evidence(
        self,
        situation: ActionLearningSituation,
        cand: ActionLearningCandidate,
        experiences: list["Experience"],
    ) -> tuple[float, int | None]:
        matched = []
        best_level: int | None = None
        for exp in experiences:
            exp_situation = self._situation_of(exp)
            legacy = self._is_legacy(exp)
            res = match_situation(
                situation, exp_situation, legacy=legacy,
                enabled_levels=self._config.match_levels,
            )
            if res is None:
                continue
            success = self._exp_success(exp)
            if success is None:
                continue
            matched.append((res.level, res.weight, bool(success), 1))
            if best_level is None or res.level < best_level:
                best_level = res.level

        if not matched:
            return 0.0, None

        max_support = max(m for _, _, _, m in matched)
        total = 0.0
        for level, weight, _success, support in matched:
            total += weight * (support / max_support)
        return min(total / len(matched), 1.0), best_level

    @staticmethod
    def _exp_success(exp: "Experience") -> bool | None:
        if isinstance(exp, dict):
            return exp.get("success")
        return getattr(exp, "success", None)

    @staticmethod
    def _situation_of(exp: "Experience") -> ActionLearningSituation:
        from .schema import situation_from_legacy_experience, ActionLearningSituation

        if isinstance(exp, dict):
            sit = exp.get("situation")
            if isinstance(sit, dict):
                return ActionLearningSituation(
                    intent=sit.get("intent", "") or "",
                    task_type=sit.get("task_type"),
                    error_type=sit.get("error_type"),
                    context_features=sit.get("context_features", {}) or {},
                    raw_input=exp.get("raw_input", "") or "",
                    situation_completeness=sit.get("situation_completeness", "partial"),
                )
            return ActionLearningSituation(
                intent=exp.get("intent", "") or "",
                raw_input=exp.get("raw_input", "") or "",
                situation_completeness="partial",
            )
        return situation_from_legacy_experience(exp)

    @staticmethod
    def _is_legacy(exp: "Experience") -> bool:
        if hasattr(exp, "to_dict") and callable(getattr(exp, "to_dict", None)):
            data = exp.to_dict()
        elif isinstance(exp, dict):
            data = exp
        else:
            return True
        return not (data.get("situation") or data.get("action") or data.get("learning_metadata"))

    def _recency_bonus(self, stats: dict[str, Any]) -> float:
        last_seen = stats.get("last_seen", "")
        age = _age_days(last_seen)
        half_life = max(self._config.recency_half_life_days, 0.5)
        return 0.5 ** (age / half_life)

    @staticmethod
    def _sort_ranked(evaluated: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """1. evidence first (L1 > L2 > L3 > none), 2. score, 3. support, 4. original."""
        def key_fn(r: dict[str, Any]) -> tuple:
            has_evidence = 1 if r["evidence_status"] == "evidence" else 0
            level = r.get("match_level") or 4
            score = r["score"] if r["score"] is not None else -1.0
            return (has_evidence, -level, score, r["support_count"], -r["original_index"])

        return sorted(evaluated, key=key_fn, reverse=True)
