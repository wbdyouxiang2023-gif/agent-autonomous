"""Policy tests — Level 4.3 (situation-dependent policy decision).

Run:  pytest tests/test_policy.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from neurocortex.policy import PolicyConfig, PolicyEngine
from neurocortex.action_learning import (
    ActionLearningConfig, ActionLearningEngine,
    ActionLearningSituation, ActionLearningOutcome,
)


def _policy(tmp_path, enabled=True, shadow=True, min_evidence=2):
    return PolicyEngine(PolicyConfig(
        enabled=enabled, shadow_only=shadow,
        min_evidence=min_evidence, log_path=tmp_path / "policy.jsonl",
    ))


def _engine(tmp_path):
    return ActionLearningEngine(ActionLearningConfig(
        enabled=True, shadow_only=True, statistics_path=tmp_path / "stats.json",
    ))


def _sit(intent):
    return ActionLearningSituation(intent=intent, raw_input=f"{intent} task", situation_completeness="partial")


# ── disabled / no evidence ─────────────────────────────────────────────


def test_disabled_returns_undecided(tmp_path):
    pol = _policy(tmp_path, enabled=False)
    d = pol.choose_action(_sit("fix"), ["read_file", "search"])
    assert d["decision_status"] == "disabled"
    assert d["selected_action"] is None


def test_no_evidence_returns_undecided(tmp_path):
    pol = _policy(tmp_path, enabled=True)
    eng = _engine(tmp_path)
    d = pol.choose_action(_sit("fix"), ["read_file", "search"], engine=eng)
    assert d["decision_status"] == "no_evidence"
    assert d["selected_action"] is None
    assert "no evidence" in d["decision_reason"]


# ── insufficient evidence below min ────────────────────────────────────


def test_insufficient_evidence(tmp_path):
    pol = _policy(tmp_path, enabled=True, min_evidence=2)
    eng = _engine(tmp_path)
    eng.record_outcome(_sit("fix"), "read_file", ActionLearningOutcome(success=True))  # support=1 < 2
    d = pol.choose_action(_sit("fix"), ["read_file", "search"], engine=eng)
    assert d["decision_status"] == "insufficient_evidence"
    assert d["selected_action"] is None


# ── decided with sufficient evidence ───────────────────────────────────


def test_decided_when_evidence_above_min(tmp_path):
    pol = _policy(tmp_path, enabled=True, min_evidence=2)
    eng = _engine(tmp_path)
    sit = _sit("fix")
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    d = pol.choose_action(sit, ["read_file", "search"], engine=eng)
    assert d["decision_status"] == "decided"
    assert d["selected_action"] == "read_file"
    assert d["evidence"]["read_file"] == 2


# ── situation-dependent policy ─────────────────────────────────────────


def test_situation_dependent_policy(tmp_path):
    pol = _policy(tmp_path, enabled=True)
    eng = _engine(tmp_path)
    sit_x = _sit("inspect")
    sit_y = _sit("locate")

    # X: read_file 2s/1f, search 0s/2f → read_file should win
    eng.record_outcome(sit_x, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_x, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_x, "read_file", ActionLearningOutcome(success=False))
    eng.record_outcome(sit_x, "search", ActionLearningOutcome(success=False))
    eng.record_outcome(sit_x, "search", ActionLearningOutcome(success=False))

    # Y: search 3s, read_file 0s/2f → search should win
    eng.record_outcome(sit_y, "search", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_y, "search", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_y, "search", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_y, "read_file", ActionLearningOutcome(success=False))
    eng.record_outcome(sit_y, "read_file", ActionLearningOutcome(success=False))

    dx = pol.choose_action(sit_x, ["read_file", "search"], engine=eng)
    dy = pol.choose_action(sit_y, ["read_file", "search"], engine=eng)

    assert dx["selected_action"] == "read_file"
    assert dy["selected_action"] == "search"
    assert dx["decision_status"] == "decided" and dy["decision_status"] == "decided"


# ── unknown never updates policy evidence ──────────────────────────────


def test_unknown_not_learned(tmp_path):
    pol = _policy(tmp_path, enabled=True)
    eng = _engine(tmp_path)
    sit = _sit("fix")
    # UNKNOWN outcome must NOT update stats
    assert eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=None)) is False
    d = pol.choose_action(sit, ["read_file", "search"], engine=eng)
    assert d["decision_status"] == "no_evidence"
    assert d["selected_action"] is None


# ── persistence ────────────────────────────────────────────────────────


def test_persistence_keeps_decision(tmp_path):
    pol = _policy(tmp_path, enabled=True)
    eng = _engine(tmp_path)
    sit = _sit("fix")
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    d1 = pol.choose_action(sit, ["read_file", "search"], engine=eng)
    assert d1["selected_action"] == "read_file"

    # reload policy + engine from disk
    pol2 = _policy(tmp_path, enabled=True)
    eng2 = _engine(tmp_path)
    d2 = pol2.choose_action(sit, ["read_file", "search"], engine=eng2)
    assert d2["selected_action"] == "read_file"
    assert d2["evidence"]["read_file"] == 2


# ── shadow log ─────────────────────────────────────────────────────────


def test_shadow_log(tmp_path):
    pol = _policy(tmp_path, enabled=True)
    eng = _engine(tmp_path)
    sit = _sit("fix")
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    d = pol.choose_action(sit, ["read_file", "search"], engine=eng)
    pol.log_shadow(d, original_action="search")  # original decision was search
    entries = [json.loads(l) for l in (tmp_path / "policy.jsonl").read_text().strip().splitlines()]
    assert len(entries) == 1
    e = entries[0]
    assert e["policy_action"] == "read_file"
    assert e["original_action"] == "search"
    assert e["agreement"] is False
    assert e["decision_status"] == "decided"
    assert e["ranking"] == ["read_file", "search"]


def test_shadow_log_agreement_true(tmp_path):
    pol = _policy(tmp_path, enabled=True)
    eng = _engine(tmp_path)
    sit = _sit("fix")
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    d = pol.choose_action(sit, ["read_file", "search"], engine=eng)
    pol.log_shadow(d, original_action="read_file")
    entries = [json.loads(l) for l in (tmp_path / "policy.jsonl").read_text().strip().splitlines()]
    assert entries[0]["agreement"] is True


# ── output schema ──────────────────────────────────────────────────────


def test_output_schema(tmp_path):
    pol = _policy(tmp_path, enabled=True)
    eng = _engine(tmp_path)
    sit = _sit("fix")
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    d = pol.choose_action(sit, ["read_file", "search"], engine=eng)
    for k in ("selected_action", "ranked_actions", "scores", "evidence", "match_levels", "decision_reason", "decision_status", "candidate_actions"):
        assert k in d, f"missing {k}"
    assert isinstance(d["scores"]["read_file"], float)
    assert d["match_levels"]["read_file"] in (1, 2, 3)
