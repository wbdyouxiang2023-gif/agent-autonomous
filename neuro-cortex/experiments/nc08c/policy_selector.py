"""NC-08C.0 — Controlled Policy Permission Architecture.

The Policy Selector is the SINGLE point that decides which policy's action
may enter the Executor.

Modes:
  shadow         NC observes only; actual_action always = original_action
  trial_original Original Policy controls actual_action
  trial_nc       NC may control actual_action (subject to gates + assignment)

Layers of safety (highest first):
  1. NC_KILL_SWITCH=true  → force Original, unconditionally
  2. NC_ENABLE=false      → force Original (first-level insurance)
  3. policy_mode          → shadow/trial_original → Original
  4. experiment_assignment→ only 'nc' assignment may let NC act
  5. NC gates             → ABSTAIN on low confidence / weak evidence /
                             exception / timeout / invalid candidate

Fail-open principle: ANY NC failure → Original action → Executor.
NC can NEVER silently override actual_action; only the Selector, in
trial_nc mode with a valid 'nc' assignment, may set
actual_action = nc_recommended_action.

Learning isolation: a trial task pins policy_version; outcomes recorded
during the trial do NOT mutate the policy under test.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── Version / identity ──────────────────────────────────────────────
POLICY_VERSION = "NC-08C.0"
POLICY_SOURCE_NC = "neurocortex"
POLICY_SOURCE_ORIGINAL = "original"

# ── Config (env-driven, no magic numbers in code) ───────────────────
def _env_bool(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, ""))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, ""))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class PolicyConfig:
    """All tunables are configuration — no scattered magic numbers."""
    nc_enable: bool = field(default_factory=lambda: _env_bool("NC_ENABLE", "false"))
    kill_switch: bool = field(default_factory=lambda: _env_bool("NC_KILL_SWITCH", "false"))
    policy_mode: str = field(default_factory=lambda: os.environ.get("NC_POLICY_MODE", "shadow"))
    nc_min_confidence: float = field(default_factory=lambda: _env_float("NC_MIN_CONFIDENCE", 0.6))
    nc_min_evidence: int = field(default_factory=lambda: _env_int("NC_MIN_EVIDENCE", 5))
    nc_default_fallback: str = field(default_factory=lambda: os.environ.get("NC_FALLBACK", "original"))
    decision_log: str = field(default_factory=lambda: os.environ.get(
        "NC_DECISION_LOG", str(Path(__file__).parent / "policy_decision_log.jsonl")))
    outcome_log: str = field(default_factory=lambda: os.environ.get(
        "NC_OUTCOME_LOG", str(Path(__file__).parent / "policy_outcome_log.jsonl")))

    VALID_MODES = {"shadow", "trial_original", "trial_nc", "canary_nc", "production_nc"}

    def validate(self) -> None:
        if self.policy_mode not in self.VALID_MODES:
            raise ValueError(f"invalid policy_mode: {self.policy_mode}")


# ── Decision result ─────────────────────────────────────────────────
@dataclass
class PolicyDecision:
    timestamp: str
    task_id: str
    situation: str
    candidate_actions: list[str]
    original_action: str
    nc_recommendation: str | None
    nc_confidence: float | None
    nc_evidence_strength: int | None
    nc_abstained: bool
    nc_abstain_reason: str | None
    policy_mode: str
    policy_source: str
    policy_version: str
    experiment_id: str
    experiment_assignment: str
    actual_action: str
    fallback_reason: str | None = None
    nc_failure: bool = False
    nc_failure_type: str | None = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "situation": self.situation,
            "candidate_actions": self.candidate_actions,
            "original_action": self.original_action,
            "nc_recommendation": self.nc_recommendation,
            "nc_confidence": self.nc_confidence,
            "nc_evidence_strength": self.nc_evidence_strength,
            "nc_abstained": self.nc_abstained,
            "nc_abstain_reason": self.nc_abstain_reason,
            "policy_mode": self.policy_mode,
            "policy_source": self.policy_source,
            "policy_version": self.policy_version,
            "experiment_id": self.experiment_id,
            "experiment_assignment": self.experiment_assignment,
            "actual_action": self.actual_action,
            "fallback_reason": self.fallback_reason,
            "nc_failure": self.nc_failure,
            "nc_failure_type": self.nc_failure_type,
        }


# ── Experiment assignment (determined BEFORE execution, not by NC) ──
class ExperimentAssigner:
    """Assigns tasks to experimental groups. Must be called BEFORE execution.

    Assignment never depends on NC recommendation or outcome.
    Deterministic hash-based split; stable per task.
    """

    def __init__(self, experiment_id: str | None = None, nc_ratio: float = 0.5):
        self.experiment_id = experiment_id or f"nc08c0-{uuid.uuid4().hex[:8]}"
        self.nc_ratio = nc_ratio

    def assign(self, task_id: str) -> str:
        """Return 'original' or 'nc'. Deterministic per task_id."""
        h = int(uuid.uuid5(uuid.NAMESPACE_DNS, f"{self.experiment_id}:{task_id}").hex[:4], 16)
        return "nc" if (h / 0xFFFF) < self.nc_ratio else "original"


# ── Two-phase logs ──────────────────────────────────────────────────
class TwoPhaseLogger:
    """Decision log (phase A) + outcome log (phase B, written after execution)."""

    def __init__(self, decision_log: str, outcome_log: str):
        self.decision_log = Path(decision_log)
        self.outcome_log = Path(outcome_log)

    def log_decision(self, d: PolicyDecision) -> None:
        self.decision_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.decision_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")

    def log_outcome(self, decision: PolicyDecision, execution_success: bool,
                    task_completed: bool | None, completion_source: str,
                    actual_outcome: str, error_message: str = "") -> None:
        """Phase B — outcome written AFTER execution. Never fabricated."""
        rec = decision.to_dict()
        rec.update({
            "outcome_written_at": datetime.now(timezone.utc).isoformat(),
            "execution_success": bool(execution_success),
            "task_completed": task_completed,          # None = unknown
            "completion_source": completion_source,
            "actual_outcome": actual_outcome[:300],
            "error_message": error_message,
        })
        self.outcome_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.outcome_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── NC recommender wrapper (fail-open) ──────────────────────────────
class NCRecommender:
    """Wraps the NC-08B.3 ShadowAdapter ranking into a gated recommender.

    Raises/returns structured signals so the Selector can ABSTAIN safely.
    """

    def __init__(self, adapter=None):
        if adapter is None:
            from experiments.nc08b.shadow.shadow_adapter import ShadowAdapter
            adapter = ShadowAdapter(enabled=True)
        self._adapter = adapter

    def recommend(self, situation: str, candidate_actions: list[str],
                  original_action: str) -> dict:
        """Return {recommendation, confidence, evidence_strength, raw}.

        On ANY failure: raise NCRecommenderFailure(failure_type, reason).
        """
        start = time.monotonic()
        try:
            rec = self._adapter.recommend(situation, candidate_actions, original_action)
        except Exception as e:  # timeout/model/retriever/anything
            raise NCRecommenderFailure("exception", f"NC recommend failed: {e}") from e
        if rec is None:
            raise NCRecommenderFailure("unavailable", "NC returned None")
        scores = rec.get("nc_scores") or {}
        top = rec.get("nc_recommended_action")
        if top is None:
            raise NCRecommenderFailure("abstain-no-recommendation", "no top action")
        # evidence strength = valid completion evidence for top action
        ev = scores.get(top)
        # confidence: derived from completion rate (0..1) if available
        confidence = float(ev) if isinstance(ev, (int, float)) and ev is not None else None
        # evidence count: from adapter evidence (support) — recompute from ranking
        support = 0
        for r in (rec.get("nc_ranking") or []):
            pass
        # support counts come from adapter internal — approximate via scores
        evidence_strength = 0
        if confidence is not None:
            # map: confidence value alone insufficient; use adapter evidence lookup
            try:
                from experiments.nc08b.shadow.shadow_adapter import _load_evidence, _completion_rate
                evd = _load_evidence().get((situation, top))
                if evd:
                    evidence_strength = int(evd.get("t", 0)) + int(evd.get("f", 0))
            except Exception:
                evidence_strength = 0
        return {
            "recommendation": top,
            "confidence": confidence,
            "evidence_strength": evidence_strength,
            "raw": rec,
            "latency_s": round(time.monotonic() - start, 4),
        }


class NCRecommenderFailure(Exception):
    def __init__(self, failure_type: str, reason: str):
        super().__init__(reason)
        self.failure_type = failure_type
        self.reason = reason


# ── Policy Selector ─────────────────────────────────────────────────
class PolicySelector:
    """Single decision point: which policy's action reaches the Executor.

    Safety order (strict):
      kill_switch → nc_enable → policy_mode → assignment → gates
    """

    def __init__(self, config: PolicyConfig | None = None,
                 assigner: ExperimentAssigner | None = None,
                 recommender: NCRecommender | None = None,
                 logger: TwoPhaseLogger | None = None):
        self.config = config or PolicyConfig()
        self.config.validate()
        self.assigner = assigner or ExperimentAssigner()
        self.recommender = recommender or NCRecommender()
        self.logger = logger or TwoPhaseLogger(self.config.decision_log,
                                               self.config.outcome_log)

    def select(self, situation: str, candidate_actions: list[str],
               original_action: str, task_id: str | None = None,
               _inject_failure: dict | None = None) -> PolicyDecision:
        """Decide actual_action. Never raises for NC problems (fail-open).

        _inject_failure: TEST-ONLY hook to simulate NC exception/timeout.
        """
        ts = datetime.now(timezone.utc).isoformat()
        tid = task_id or str(uuid.uuid4())[:8]
        cfg = self.config
        fallback_reason = None
        nc_failure = False
        nc_failure_type = None
        nc_rec = None
        nc_conf = None
        nc_ev = None
        nc_abstained = False
        nc_abstain_reason = None

        # ── Layer 1: Kill Switch (highest priority) ─────────────
        if cfg.kill_switch:
            d = PolicyDecision(
                timestamp=ts, task_id=tid, situation=situation,
                candidate_actions=list(candidate_actions),
                original_action=original_action, nc_recommendation=None,
                nc_confidence=None, nc_evidence_strength=None,
                nc_abstained=False, nc_abstain_reason=None,
                policy_mode=cfg.policy_mode, policy_source=POLICY_SOURCE_ORIGINAL,
                policy_version=POLICY_VERSION,
                experiment_id=self.assigner.experiment_id,
                experiment_assignment="original",
                actual_action=original_action,
                fallback_reason="kill_switch",
            )
            self.logger.log_decision(d)
            return d

        # ── Layer 2: NC_ENABLE (first-level insurance) ──────────
        if not cfg.nc_enable:
            d = PolicyDecision(
                timestamp=ts, task_id=tid, situation=situation,
                candidate_actions=list(candidate_actions),
                original_action=original_action, nc_recommendation=None,
                nc_confidence=None, nc_evidence_strength=None,
                nc_abstained=False, nc_abstain_reason=None,
                policy_mode=cfg.policy_mode, policy_source=POLICY_SOURCE_ORIGINAL,
                policy_version=POLICY_VERSION,
                experiment_id=self.assigner.experiment_id,
                experiment_assignment="original",
                actual_action=original_action,
                fallback_reason="nc_enable_false",
            )
            self.logger.log_decision(d)
            return d

        # ── Layer 3: mode gate ──────────────────────────────────
        # shadow & trial_original never let NC act
        if cfg.policy_mode in ("shadow", "trial_original"):
            d = PolicyDecision(
                timestamp=ts, task_id=tid, situation=situation,
                candidate_actions=list(candidate_actions),
                original_action=original_action, nc_recommendation=None,
                nc_confidence=None, nc_evidence_strength=None,
                nc_abstained=False, nc_abstain_reason=None,
                policy_mode=cfg.policy_mode, policy_source=POLICY_SOURCE_ORIGINAL,
                policy_version=POLICY_VERSION,
                experiment_id=self.assigner.experiment_id,
                experiment_assignment="original",
                actual_action=original_action,
                fallback_reason=f"mode_{cfg.policy_mode}",
            )
            self.logger.log_decision(d)
            return d

        # trial_nc (and future canary/production): assignment gate
        assignment = self.assigner.assign(tid) if cfg.policy_mode == "trial_nc" else "nc"
        if assignment != "nc":
            d = PolicyDecision(
                timestamp=ts, task_id=tid, situation=situation,
                candidate_actions=list(candidate_actions),
                original_action=original_action, nc_recommendation=None,
                nc_confidence=None, nc_evidence_strength=None,
                nc_abstained=False, nc_abstain_reason=None,
                policy_mode=cfg.policy_mode, policy_source=POLICY_SOURCE_ORIGINAL,
                policy_version=POLICY_VERSION,
                experiment_id=self.assigner.experiment_id,
                experiment_assignment=assignment,
                actual_action=original_action,
                fallback_reason="assignment_original",
            )
            self.logger.log_decision(d)
            return d

        # ── Layer 4: NC recommendation with gates ───────────────
        try:
            if _inject_failure:
                raise NCRecommenderFailure(_inject_failure.get("type", "exception"),
                                           _inject_failure.get("reason", "injected"))
            r = self.recommender.recommend(situation, candidate_actions, original_action)
            nc_rec = r["recommendation"]
            nc_conf = r["confidence"]
            nc_ev = r["evidence_strength"]

            # invalid candidate check
            if nc_rec not in candidate_actions:
                nc_abstained = True
                nc_abstain_reason = f"invalid_candidate:{nc_rec}"
            # confidence gate
            elif nc_conf is None or nc_conf < cfg.nc_min_confidence:
                nc_abstained = True
                nc_abstain_reason = f"low_confidence:conf={nc_conf}"
            # evidence gate
            elif nc_ev is None or nc_ev < cfg.nc_min_evidence:
                nc_abstained = True
                nc_abstain_reason = f"insufficient_evidence:ev={nc_ev}"
            else:
                nc_abstained = False
        except NCRecommenderFailure as e:
            nc_failure = True
            nc_failure_type = e.failure_type
            nc_abstained = True
            nc_abstain_reason = f"nc_failure:{e.failure_type}"
            fallback_reason = f"nc_{e.failure_type}"

        # decide actual action
        if nc_abstained or nc_failure:
            actual = original_action
            source = POLICY_SOURCE_ORIGINAL
            if fallback_reason is None:
                fallback_reason = "nc_abstain"
        else:
            actual = nc_rec
            source = POLICY_SOURCE_NC

        d = PolicyDecision(
            timestamp=ts, task_id=tid, situation=situation,
            candidate_actions=list(candidate_actions),
            original_action=original_action, nc_recommendation=nc_rec,
            nc_confidence=nc_conf, nc_evidence_strength=nc_ev,
            nc_abstained=nc_abstained, nc_abstain_reason=nc_abstain_reason,
            policy_mode=cfg.policy_mode, policy_source=source,
            policy_version=POLICY_VERSION,
            experiment_id=self.assigner.experiment_id,
            experiment_assignment=assignment,
            actual_action=actual,
            fallback_reason=fallback_reason,
            nc_failure=nc_failure, nc_failure_type=nc_failure_type,
        )
        self.logger.log_decision(d)
        return d

    def record_outcome(self, decision: PolicyDecision, execution_success: bool,
                       task_completed: bool | None, completion_source: str,
                       actual_outcome: str, error_message: str = "") -> None:
        """Phase B — outcome written after execution. task_completed=None
        stays None (unknown); never inferred from success."""
        self.logger.log_outcome(decision, execution_success, task_completed,
                                completion_source, actual_outcome, error_message)
