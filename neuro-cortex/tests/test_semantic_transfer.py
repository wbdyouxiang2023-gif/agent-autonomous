"""Situation Similarity & Evidence Transfer tests — Level 5.1 (17 required)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from neurocortex.action_learning import (
    ActionLearningConfig, ActionLearningEngine,
    ActionLearningSituation, ActionLearningOutcome,
    similarity, transfer_gate, compute_transfer_weight, build_borrowed_evidence,
)


def _engine(tmp_path, semantic=True, high=0.45, low=0.25):
    return ActionLearningEngine(ActionLearningConfig(
        enabled=True, shadow_only=True,
        statistics_path=tmp_path / "stats.json",
        semantic_transfer_enabled=semantic,
        semantic_high_threshold=high,
        semantic_low_threshold=low,
    ))


def _sit(intent, raw):
    return ActionLearningSituation(intent=intent, raw_input=raw, situation_completeness="partial")


# ── 1. identical → 1.0 ──────────────────────────────────────────────────


def test_identical_similarity_1():
    r = similarity("inspect file content", "inspect file content")
    assert r.score == pytest.approx(1.0, abs=0.001)


# ── 2. clearly similar → high ──────────────────────────────────────────


def test_similar_high():
    r = similarity("inspect file content", "read file content")
    assert r.score >= 0.40  # shares "file content" — clearly similar


# ── 3. clearly unrelated → low ─────────────────────────────────────────


def test_unrelated_low():
    r = similarity("inspect file content", "deploy application to staging")
    assert r.score < 0.60


# ── 4. empty input ─────────────────────────────────────────────────────


def test_empty_input():
    r = similarity("", "inspect file content")
    assert r.score == 0.0
    r2 = similarity("inspect file content", "")
    assert r2.score == 0.0
    r3 = similarity("", "")
    assert r3.score == 0.0


# ── 5. punctuation ─────────────────────────────────────────────────────


def test_punctuation():
    r1 = similarity("inspect file content!", "inspect file content?")
    r2 = similarity("inspect, file; content", "inspect file content")
    assert r1.score >= 0.9
    assert r2.score >= 0.9


# ── 6. case normalization ──────────────────────────────────────────────


def test_case_normalization():
    r = similarity("Inspect File Content", "inspect file content")
    assert r.score == pytest.approx(1.0, abs=0.001)


# ── 7. deterministic ───────────────────────────────────────────────────


def test_deterministic():
    a, b = "inspect file content", "check file contents"
    assert similarity(a, b).score == similarity(a, b).score


# ── 8. threshold boundary ──────────────────────────────────────────────


def test_threshold_boundary():
    assert transfer_gate(0.70, high=0.70, low=0.60) == "transfer"
    assert transfer_gate(0.60, high=0.70, low=0.60) == "discounted"
    assert transfer_gate(0.59, high=0.70, low=0.60) == "no_transfer"
    assert transfer_gate(0.65, high=0.70, low=0.60) == "discounted"
    w = compute_transfer_weight(0.7, "transfer", high=0.70, low=0.60)
    assert w == pytest.approx(0.7)
    assert compute_transfer_weight(0.5, "no_transfer") == 0.0


# ── 9. no evidence ─────────────────────────────────────────────────────


def test_no_evidence_no_transfer(tmp_path):
    eng = _engine(tmp_path)
    ranked = eng.rank_actions(_sit("check", "check file content"), ["read_file", "search"])
    # No known situation → no borrowed evidence
    assert all(r["evidence_status"] == "no_evidence" for r in ranked)
    assert all(r["borrowed_from"] is None for r in ranked)


# ── 10. semantic transfer ──────────────────────────────────────────────


def test_semantic_transfer(tmp_path):
    eng = _engine(tmp_path)
    known = _sit("inspect", "inspect file content")
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(known, "search", ActionLearningOutcome(success=False))
    eng.record_outcome(known, "search", ActionLearningOutcome(success=False))

    novel = _sit("check", "check file content")
    ranked = eng.rank_actions(novel, ["read_file", "search"], known_situations=[known])
    rf = next(r for r in ranked if r["action_key"] == "read_file")
    assert rf["evidence_status"] == "evidence"
    assert rf["borrowed_from"] is not None
    assert rf["match_level"] == 4  # semantic (derived)


# ── 11. unrelated no-transfer ──────────────────────────────────────────


def test_unrelated_no_transfer(tmp_path):
    eng = _engine(tmp_path)
    known = _sit("inspect", "inspect file content")
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))

    for raw in ("deploy application", "restart service", "create database", "send email"):
        novel = _sit("deploy", raw)
        ranked = eng.rank_actions(novel, ["read_file", "search"], known_situations=[known])
        # Unrelated → NO semantic transfer: borrowed_from must be None and
        # match_level must NOT be 4. (It may show GLOBAL_FALLBACK L3 because
        # global statistics exist — that is the pre-existing mechanism, not
        # semantic transfer. NO_EVIDENCE is only when no stats exist at all.)
        for r in ranked:
            assert r["borrowed_from"] is None, f"{raw} wrongly semantic-transferred"
            assert r["match_level"] != 4, f"{raw} wrongly semantic-transferred"
            assert r["match_level"] in (None, 3), f"{raw} unexpected match_level={r['match_level']}"


# ── 12. borrowed evidence marked ───────────────────────────────────────


def test_borrowed_evidence_marked(tmp_path):
    eng = _engine(tmp_path)
    known = _sit("inspect", "inspect file content")
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    novel = _sit("check", "check file content")
    ranked = eng.rank_actions(novel, ["read_file"], known_situations=[known])
    rf = ranked[0]
    assert rf["borrowed_from"] == ["intent:inspect|action:read_file"]
    assert rf["match_level"] == 4


# ── 13. original statistics unchanged ──────────────────────────────────


def test_original_stats_unchanged(tmp_path):
    eng = _engine(tmp_path)
    known = _sit("inspect", "inspect file content")
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    before = eng.store.snapshot()

    # Semantic transfer ranking must NOT modify stats
    novel = _sit("check", "check file content")
    eng.rank_actions(novel, ["read_file", "search"], known_situations=[known])
    after = eng.store.snapshot()
    assert before == after
    assert after["intent:inspect|action:read_file"]["success_count"] == 2


# ── 14. unknown outcome not updated ────────────────────────────────────


def test_unknown_not_updated(tmp_path):
    eng = _engine(tmp_path)
    known = _sit("inspect", "inspect file content")
    assert eng.record_outcome(known, "read_file", ActionLearningOutcome(success=None)) is False
    before = eng.store.snapshot()
    assert before == {}


# ── 15. persistence ────────────────────────────────────────────────────


def test_persistence(tmp_path):
    eng1 = _engine(tmp_path)
    known = _sit("inspect", "inspect file content")
    eng1.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    eng2 = _engine(tmp_path)
    novel = _sit("check", "check file content")
    ranked = eng2.rank_actions(novel, ["read_file"], known_situations=[known])
    assert ranked[0]["evidence_status"] == "evidence"
    assert ranked[0]["borrowed_from"] is not None


# ── 16. existing Action Learning regression ────────────────────────────


def test_action_learning_regression(tmp_path):
    # Without semantic transfer enabled, behavior is unchanged
    eng = ActionLearningEngine(ActionLearningConfig(
        enabled=True, shadow_only=True,
        statistics_path=tmp_path / "stats.json",
        semantic_transfer_enabled=False,
    ))
    sit = _sit("fix", "fix import error")
    eng.record_outcome(sit, "code_edit", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(sit, ["code_edit", "respond"])
    assert ranked[0]["action_key"] == "code_edit"
    assert ranked[0]["borrowed_from"] is None  # no semantic field leakage
    # situation-aware ranking still works
    sit2 = _sit("create", "create module")
    eng.record_outcome(sit2, "respond", ActionLearningOutcome(success=True))
    r2 = eng.rank_actions(sit2, ["code_edit", "respond"])
    assert r2[0]["action_key"] == "respond"


# ── 17. existing Policy regression ─────────────────────────────────────


def test_policy_regression(tmp_path):
    from neurocortex.policy import PolicyConfig, PolicyEngine

    eng = _engine(tmp_path, semantic=True)
    pol = PolicyEngine(PolicyConfig(enabled=True, shadow_only=True, min_evidence=2, log_path=tmp_path / "p.jsonl"))
    known = _sit("inspect", "inspect file content")
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(known, "read_file", ActionLearningOutcome(success=True))
    eng.record_outcome(known, "search", ActionLearningOutcome(success=False))
    eng.record_outcome(known, "search", ActionLearningOutcome(success=False))

    # Policy on the KNOWN situation (exact evidence) still works
    d = pol.choose_action(known, ["read_file", "search"], engine=eng)
    assert d["selected_action"] == "read_file"
    assert d["decision_status"] == "decided"

    # Policy on a NOVEL situation: borrowed evidence counts toward support,
    # but min_evidence=2 means it can still decide if borrowed support >= 2
    novel = _sit("check", "check file content")
    d2 = pol.choose_action(novel, ["read_file", "search"], engine=eng)
    # read_file has borrowed support=2 (from known), search borrowed=2
    # (both are >= min_evidence) → policy decides on ranking
    assert d2["selected_action"] in ("read_file", "search")


# ── helper for similarity matrix ───────────────────────────────────────


def test_similarity_matrix_known_vs_cases():
    known = "inspect file content"
    similar = ["check file content", "review file contents"]
    unrelated = ["deploy application", "restart service", "create database", "send email"]
    sim_scores = [similarity(known, s).score for s in similar]
    unrel_scores = [similarity(known, u).score for u in unrelated]
    # Similar cases must score higher than unrelated cases
    assert min(sim_scores) > max(unrel_scores), f"overlap: sim={sim_scores} unrel={unrel_scores}"
