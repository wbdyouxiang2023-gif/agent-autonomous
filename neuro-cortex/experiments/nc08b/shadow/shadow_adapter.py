#!/usr/bin/env python3
"""NC-08B.3 — Completion Ranking Shadow Adapter.

SHADOW-ONLY. Never influences actual Hermes action selection.

Given a situation + candidate actions + real completion evidence,
produces a completion-based ranking recommendation and logs it to an
independent shadow log. The actual action is ALWAYS the original policy's
choice — the adapter only observes and recommends.

Feature flag: NC_SHADOW_MODE (default OFF). When OFF, the adapter is a
no-op passthrough with zero side effects.

Safety invariant:
    actual_action == original_action  (asserted on every record)
"""
from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MODEL_VERSION = "nc08b3-shadow-v1"
FLAG = os.environ.get("NC_SHADOW_MODE", "off").strip().lower() in ("1", "true", "yes", "on")

# Real completion evidence source (read-only)
EVIDENCE_PATH = Path(__file__).parent.parent / "real_completion_observations.jsonl"
SITUATION_PATH = Path(__file__).parent.parent / "situation_observations.jsonl"

# Shadow log output (independent, never production experience)
SHADOW_DIR = Path(__file__).parent
SHADOW_LOG = SHADOW_DIR / "shadow_log.jsonl"


def _load_evidence() -> dict[tuple[str, str], dict]:
    """Load real completion evidence: (task_type, action) -> {t, f, n}."""
    agg: dict[tuple[str, str], dict] = defaultdict(lambda: {"t": 0, "f": 0, "n": 0})
    for p in (EVIDENCE_PATH, SITUATION_PATH):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").strip().splitlines():
            if not line:
                continue
            o = json.loads(line)
            key = (o.get("task_type"), o.get("selected_action"))
            agg[key]["n"] += 1
            if o.get("task_completed") is True:
                agg[key]["t"] += 1
            elif o.get("task_completed") is False:
                agg[key]["f"] += 1
    return dict(agg)


def _completion_rate(ev: dict | None) -> float | None:
    """True / (True + False). None excluded. None if no valid evidence."""
    if ev is None or (ev["t"] + ev["f"]) == 0:
        return None
    return ev["t"] / (ev["t"] + ev["f"])


def rank_by_completion(situation: str, candidate_actions: list[str],
                       evidence: dict[tuple[str, str], dict]) -> list[dict]:
    """Completion-based ranking of candidate actions for a situation.

    Scores each candidate by completion_rate from real evidence.
    Candidates with no valid evidence get score=None (ranked last, no guess).
    Deterministic tie-breaker: support count then action name.
    """
    scored = []
    for a in candidate_actions:
        ev = evidence.get((situation, a))
        rate = _completion_rate(ev)
        support = (ev["t"] + ev["f"]) if ev else 0
        scored.append({"action": a, "score": rate, "support": support})
    # None scores last; else desc by (score, support), asc name
    scored.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), -r["support"], r["action"]))
    return scored


class ShadowAdapter:
    """Shadow completion-ranking recommender. Never executes actions."""

    def __init__(self, enabled: bool | None = None):
        self.enabled = FLAG if enabled is None else enabled
        self._evidence = _load_evidence() if self.enabled else {}

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    def recommend(self, situation: str, candidate_actions: list[str],
                  original_action: str) -> dict | None:
        """Compute shadow recommendation.

        Returns None when disabled (zero side effects). When enabled,
        logs a shadow record with the safety assertion
        actual_action == original_action.
        """
        if not self.enabled:
            return None
        ranking = rank_by_completion(situation, candidate_actions, self._evidence)
        nc_top = ranking[0]["action"] if ranking else None
        # completion evidence for original action (observational only)
        ev_orig = self._evidence.get((situation, original_action))
        orig_rate = _completion_rate(ev_orig)

        rec = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": str(uuid.uuid4())[:8],
            "situation": situation,
            "candidate_actions": candidate_actions,
            "original_action": original_action,
            "nc_recommended_action": nc_top,
            "nc_ranking": [r["action"] for r in ranking],
            "nc_scores": {r["action"]: r["score"] for r in ranking},
            "original_completion_rate": orig_rate,
            "model_version": MODEL_VERSION,
            "shadow_only": True,
        }
        # ⚠️ SAFETY: shadow must NEVER change the actual action
        assert rec["original_action"] == original_action
        self._log(rec)
        return rec

    def _log(self, rec: dict) -> None:
        SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SHADOW_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def make_adapter() -> ShadowAdapter:
    return ShadowAdapter()
