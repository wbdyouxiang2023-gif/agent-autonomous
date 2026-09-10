"""Action Learning tests — Level 3.5-C/D (situation-aware)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from neurocortex.action_learning.config import ActionLearningConfig
from neurocortex.action_learning.engine import ActionLearningEngine, StatisticsStore
from neurocortex.action_learning.schema import (
    ActionLearningCandidate,
    ActionLearningOutcome,
    ActionLearningSituation,
)
from neurocortex.action_learning.bridge import ActionLearningBridge
from neurocortex.action_learning.matcher import match_situation, degrade_for_legacy


def _situation(intent: str = "fix", task_type: str | None = None, error_type: str | None = None, raw: str = "") -> ActionLearningSituation:
    return ActionLearningSituation(
        intent=intent,
        task_type=task_type,
        error_type=error_type,
        context_features={},
        raw_input=raw,
        situation_completeness="partial" if task_type is None else "full",
    )


def _make_experience(intent: str, action_type: str, success: bool, raw: str = "", error_type: str | None = None,
                     predicted_prob: float = 0.9, confidence: float = 0.95) -> dict:
    return {
        "experience_id": f"exp-{intent}-{action_type}-{success}-{abs(hash(raw))}",
        "timestamp": "2026-09-01T00:00:00+00:00",
        "raw_input": raw or f"{intent} {action_type}",
        "intent": intent,
        "action_type": action_type,
        "predicted_outcome": "whatever",
        "predicted_prob": predicted_prob,
        "actual_outcome": "done",
        "success": success,
        "prediction_error": 0.1,
        "evaluation": "ok",
        "confidence": confidence,
        "uncertainty": 0.05,
        "context_tags": [f"intent:{intent}", f"action:{action_type}", "outcome:success" if success else "outcome:failure"],
    }


def _engine(tmp_path: Path, enabled: bool = True, **kwargs) -> ActionLearningEngine:
    cfg = ActionLearningConfig(
        enabled=enabled,
        statistics_path=tmp_path / "stats.json",
        shadow_only=False,
        **kwargs,
    )
    return ActionLearningEngine(cfg)


def _bridge(tmp_path: Path, enabled: bool = True, shadow: bool = False, **kwargs) -> ActionLearningBridge:
    cfg = ActionLearningConfig(
        enabled=enabled,
        statistics_path=tmp_path / "stats.json",
        shadow_only=shadow,
        **kwargs,
    )
    return ActionLearningBridge(cfg)


# ── 1. no evidence ──────────────────────────────────────────────────────


def test_no_evidence(tmp_path):
    eng = _engine(tmp_path)
    ranked = eng.rank_actions(_situation(), ["code_review", "code_edit"])
    assert len(ranked) == 2
    for r in ranked:
        assert r["evidence_status"] == "no_evidence"
        assert r["score"] is None
        assert r["support_count"] == 0


# ── 2. first success ────────────────────────────────────────────────────


def test_first_success(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation(), "code_review", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(_situation(), ["code_review", "code_edit"])
    cr = next(r for r in ranked if r["action_key"] == "code_review")
    ce = next(r for r in ranked if r["action_key"] == "code_edit")
    assert cr["support_count"] == 1 and cr["success_count"] == 1
    assert cr["estimated_success"] == pytest.approx(0.5278, abs=0.001)
    assert ce["evidence_status"] == "no_evidence"
    assert ranked[0]["action_key"] == "code_review"


# ── 3. first failure ────────────────────────────────────────────────────


def test_first_failure(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation(), "code_review", ActionLearningOutcome(success=False))
    ranked = eng.rank_actions(_situation(), ["code_review", "code_edit"])
    cr = next(r for r in ranked if r["action_key"] == "code_review")
    assert cr["support_count"] == 1 and cr["failure_count"] == 1
    assert cr["estimated_success"] == pytest.approx(0.4722, abs=0.001)


# ── 4. mixed success/failure ────────────────────────────────────────────


def test_mixed_outcomes(tmp_path):
    eng = _engine(tmp_path)
    for s in (True, True, False):
        eng.record_outcome(_situation(), "tool_call", ActionLearningOutcome(success=s))
    ranked = eng.rank_actions(_situation(), ["tool_call"])
    r = ranked[0]
    assert r["support_count"] == 3
    assert r["success_count"] == 2 and r["failure_count"] == 1
    assert r["estimated_success"] == pytest.approx(0.5375, abs=0.001)


# ── 5. Laplace smoothing ────────────────────────────────────────────────


def test_laplace_smoothing(tmp_path):
    eng = _engine(tmp_path, smoothing_alpha=1.0, smoothing_beta=1.0)
    eng.record_outcome(_situation(), "respond", ActionLearningOutcome(success=True))
    r = eng.rank_actions(_situation(), ["respond"])[0]
    assert r["estimated_success"] == pytest.approx(0.5278, abs=0.001)
    assert r["estimated_success"] < 1.0


# ── 6. confidence ───────────────────────────────────────────────────────


def test_confidence_grows_with_support(tmp_path):
    eng = _engine(tmp_path)
    for s in (True, True, True):
        eng.record_outcome(_situation(), "code_edit", ActionLearningOutcome(success=s))
    ranked = eng.rank_actions(_situation(), ["code_edit"])
    assert ranked[0]["confidence"] == pytest.approx(3 / (3 + 5), abs=0.001)


# ── 7. multiple actions ─────────────────────────────────────────────────


def test_multiple_actions(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation(), "code_review", ActionLearningOutcome(success=True))
    eng.record_outcome(_situation(), "tool_call", ActionLearningOutcome(success=False))
    ranked = eng.rank_actions(_situation(), ["code_review", "tool_call", "respond"])
    assert len(ranked) == 3
    assert {r["action_key"] for r in ranked} == {"code_review", "tool_call", "respond"}


# ── 8. ranking rules ────────────────────────────────────────────────────


def test_ranking_evidence_first(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation(), "code_review", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(_situation(), ["code_edit", "code_review"])
    assert ranked[0]["action_key"] == "code_review"


def test_ranking_score_then_support(tmp_path):
    eng = _engine(tmp_path)
    for _ in range(3):
        eng.record_outcome(_situation(), "code_review", ActionLearningOutcome(success=True))
    eng.record_outcome(_situation(), "tool_call", ActionLearningOutcome(success=True))
    eng.record_outcome(_situation(), "tool_call", ActionLearningOutcome(success=True))
    eng.record_outcome(_situation(), "tool_call", ActionLearningOutcome(success=False))
    ranked = eng.rank_actions(_situation(), ["tool_call", "code_review"])
    assert ranked[0]["action_key"] == "code_review"
    assert ranked[1]["action_key"] == "tool_call"


# ── 9-11. situation matching levels ─────────────────────────────────────


def test_exact_match_level1(tmp_path):
    eng = _engine(tmp_path)
    exp = _make_experience("fix", "code_review", True, raw="fix import ModuleNotFoundError")
    exp["situation"] = {
        "intent": "fix", "task_type": "import", "error_type": "ModuleNotFoundError",
        "context_features": {}, "situation_completeness": "full",
    }
    ranked = eng.rank_actions(
        _situation("fix", task_type="import", error_type="ModuleNotFoundError"),
        ["code_review"], experiences=[exp],
    )
    assert ranked[0]["match_level"] == 1


def test_intent_tasktype_level2(tmp_path):
    eng = _engine(tmp_path)
    exp = _make_experience("fix", "code_review", True, raw="fix import")
    exp["situation"] = {
        "intent": "fix", "task_type": "import", "error_type": None,
        "context_features": {}, "situation_completeness": "full",
    }
    ranked = eng.rank_actions(_situation("fix", task_type="import"), ["code_review"], experiences=[exp])
    assert ranked[0]["match_level"] == 2


def test_intent_only_level3(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(_situation("fix"), ["code_review"])
    assert ranked[0]["match_level"] == 3


def test_global_fallback_level4(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(_situation("deploy"), ["code_review"])
    assert ranked[0]["match_level"] == 3


def test_no_fake_level2_without_tasktype(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(_situation("fix"), ["code_review"])
    assert ranked[0]["match_level"] == 3


# ── 12. irrelevant experience ───────────────────────────────────────────


def test_irrelevant_experience_not_evidence(tmp_path):
    eng = _engine(tmp_path)
    exp = _make_experience("create", "code_edit", True, raw="build a game")
    ranked = eng.rank_actions(_situation("fix"), ["code_review"], experiences=[exp])
    assert ranked[0]["support_count"] == 0
    assert ranked[0]["evidence_status"] == "no_evidence"


# ── 13. cold start ──────────────────────────────────────────────────────


def test_cold_start_returns_none_scores(tmp_path):
    eng = _engine(tmp_path)
    ranked = eng.rank_actions(_situation("fix"), ["noop", "respond"])
    assert all(r["score"] is None for r in ranked)
    assert all(r["evidence_status"] == "no_evidence" for r in ranked)


# ── 14. predicted_prob ignored ──────────────────────────────────────────


def test_predicted_prob_never_used(tmp_path):
    eng = _engine(tmp_path)
    exp = _make_experience("fix", "code_review", False, raw="fix import", predicted_prob=0.9)
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=False))
    ranked_with_exp = eng.rank_actions(_situation("fix"), ["code_review"], experiences=[exp])
    ranked_plain = eng.rank_actions(_situation("fix"), ["code_review"])
    assert ranked_with_exp[0]["estimated_success"] == pytest.approx(ranked_plain[0]["estimated_success"], abs=0.001)


# ── 15. prediction confidence ignored ───────────────────────────────────


def test_prediction_confidence_ignored(tmp_path):
    eng = _engine(tmp_path)
    exp_high = _make_experience("fix", "code_review", True, raw="fix a", confidence=0.99)
    exp_low = _make_experience("fix", "code_review", True, raw="fix b", confidence=0.01)
    r_high = eng.rank_actions(_situation("fix"), ["code_review"], experiences=[exp_high])[0]
    r_low = eng.rank_actions(_situation("fix"), ["code_review"], experiences=[exp_low])[0]
    assert r_high["estimated_success"] == pytest.approx(r_low["estimated_success"], abs=0.001)


# ── 16. outcome=None ignored ────────────────────────────────────────────


def test_outcome_none_ignored(tmp_path):
    eng = _engine(tmp_path)
    exp = _make_experience("fix", "code_review", True, raw="fix x")
    exp["success"] = None
    ranked = eng.rank_actions(_situation("fix"), ["code_review"], experiences=[exp])
    assert ranked[0]["support_count"] == 0
    assert ranked[0]["evidence_status"] == "no_evidence"


# ── 17. feature flag disabled ───────────────────────────────────────────


def test_feature_flag_disabled(tmp_path):
    eng = _engine(tmp_path, enabled=False)
    assert eng.record_outcome(_situation(), "code_review", ActionLearningOutcome(success=True)) is False
    ranked = eng.rank_actions(_situation(), ["code_review", "code_edit"])
    assert all(r["support_count"] == 0 for r in ranked)


def test_bridge_disabled_passthrough(tmp_path):
    br = _bridge(tmp_path, enabled=False)
    cands = [{"id": "code_edit", "score": 0.8}, {"id": "code_review", "score": 0.7}]
    assert br.rank_candidates(cands) == cands


# ── 18. persistence ─────────────────────────────────────────────────────


def test_persistence(tmp_path):
    eng1 = _engine(tmp_path)
    eng1.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    eng2 = _engine(tmp_path)
    ranked = eng2.rank_actions(_situation("fix"), ["code_review"])
    assert ranked[0]["support_count"] == 1
    assert ranked[0]["success_count"] == 1


# ── 19. corrupted statistics ────────────────────────────────────────────


def test_corrupted_statistics(tmp_path):
    stats_path = tmp_path / "stats.json"
    stats_path.write_text("{ this is not valid json !!!", encoding="utf-8")
    eng = ActionLearningEngine(ActionLearningConfig(enabled=True, statistics_path=stats_path))
    ranked = eng.rank_actions(_situation("fix"), ["code_review"])
    assert ranked[0]["support_count"] == 0
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    assert json.loads(stats_path.read_text(encoding="utf-8"))["intent:fix|action:code_review"]["success_count"] == 1


# ── 20. atomic write ────────────────────────────────────────────────────


def test_atomic_write(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation(), "respond", ActionLearningOutcome(success=True))
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []
    data = json.loads((tmp_path / "stats.json").read_text(encoding="utf-8"))
    assert data["intent:fix|action:respond"]["total_count"] == 1


# ── 21. exception fallback ──────────────────────────────────────────────


def test_engine_exception_falls_back(tmp_path, monkeypatch):
    br = _bridge(tmp_path, enabled=True)
    cands = [{"id": "code_edit", "score": 0.8}, {"id": "code_review", "score": 0.7}]

    def boom(*a, **k):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(br.engine, "rank_actions", boom)
    assert br.rank_candidates(cands) == cands


# ── 22. explainability ──────────────────────────────────────────────────


def test_explainability(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=False))
    ranked = eng.rank_actions(_situation("fix"), ["code_review", "code_edit"])
    text = eng.explain(ranked)
    assert "2 successes / 3 attempts" in text
    assert "code_review" in text


# ── 23. counterfactual ranking ──────────────────────────────────────────


def test_counterfactual_ranking(tmp_path):
    eng = _engine(tmp_path)
    for _ in range(4):
        eng.record_outcome(_situation("fix", error_type="ModuleNotFoundError"), "inspect_import_path", ActionLearningOutcome(success=True))
    for _ in range(2):
        eng.record_outcome(_situation("fix", error_type="ModuleNotFoundError"), "modify_sys_path", ActionLearningOutcome(success=True))
        eng.record_outcome(_situation("fix", error_type="ModuleNotFoundError"), "modify_sys_path", ActionLearningOutcome(success=False))
    ranked = eng.rank_actions(
        _situation("fix", error_type="ModuleNotFoundError"),
        ["modify_sys_path", "inspect_import_path", "rebuild_venv"],
    )
    assert ranked[0]["action_key"] == "inspect_import_path"
    assert ranked[0]["estimated_success"] > ranked[1]["estimated_success"]


# ── 24. REAL learning loop ──────────────────────────────────────────────


def test_real_learning_loop(tmp_path):
    stats_path = tmp_path / "stats.json"
    eng = ActionLearningEngine(ActionLearningConfig(enabled=True, statistics_path=stats_path, shadow_only=False))
    sit = _situation("fix")
    a, b = "code_review", "code_edit"

    ranked = eng.rank_actions(sit, [a, b])
    assert ranked[0]["evidence_status"] == "no_evidence" and ranked[1]["evidence_status"] == "no_evidence"

    eng.record_outcome(sit, a, ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(sit, [a, b])
    assert ranked[0]["action_key"] == a
    assert ranked[0]["estimated_success"] > 0.5

    eng.record_outcome(sit, a, ActionLearningOutcome(success=False))
    ranked_after_fail = eng.rank_actions(sit, [a, b])
    a_after_fail = next(r for r in ranked_after_fail if r["action_key"] == a)
    assert a_after_fail["estimated_success"] == pytest.approx(0.5, abs=0.01)

    for _ in range(3):
        eng.record_outcome(sit, b, ActionLearningOutcome(success=True))
    ranked_final = eng.rank_actions(sit, [a, b])
    assert ranked_final[0]["action_key"] == b
    assert ranked_final[0]["estimated_success"] > ranked_final[1]["estimated_success"]

    data = json.loads(stats_path.read_text(encoding="utf-8"))
    assert data["intent:fix|action:code_review"]["success_count"] == 1 and data["intent:fix|action:code_review"]["failure_count"] == 1
    assert data["intent:fix|action:code_edit"]["success_count"] == 3 and data["intent:fix|action:code_edit"]["failure_count"] == 0


# ── shadow mode ─────────────────────────────────────────────────────────


def test_shadow_only_does_not_reorder(tmp_path):
    br = _bridge(tmp_path, enabled=True, shadow=True)
    eng = br.engine
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    cands = [{"id": "code_edit", "score": 0.8}, {"id": "code_review", "score": 0.7}]
    result = br.rank_candidates(cands, situation=_situation("fix"))
    assert [c["id"] for c in result] == ["code_edit", "code_review"]


# ── legacy experience handling ──────────────────────────────────────────


def test_legacy_experience_only_intent_level(tmp_path):
    eng = _engine(tmp_path)
    legacy = _make_experience("fix", "code_review", True, raw="fix import")
    ranked = eng.rank_actions(_situation("fix"), ["code_review"], experiences=[legacy])
    assert ranked[0]["match_level"] in (3, 4)


def test_legacy_no_fake_situation():
    from neurocortex.action_learning.schema import situation_from_legacy_experience
    legacy = _make_experience("fix", "code_review", True)
    sit = situation_from_legacy_experience(legacy)
    assert sit.task_type is None and sit.error_type is None
    assert sit.situation_completeness == "partial"


# ── situation schema invariants ─────────────────────────────────────────


def test_situation_schema_no_fabrication():
    sit = _situation("fix")
    assert sit.task_type is None
    assert sit.error_type is None
    assert sit.context_features == {}
    assert sit.situation_completeness == "partial"


def test_action_key_is_action_type():
    cand = ActionLearningCandidate(action_type="code_review", strategy="code_review")
    assert cand.action_key == "code_review"
    cand2 = ActionLearningCandidate(action_type="tool_call")
    assert cand2.action_key == "tool_call"
    assert cand2.strategy == "tool_call"


def test_matcher_legacy_degrade():
    q = _situation("fix", task_type="import")
    legacy_sit = _situation("fix")
    level, weight = degrade_for_legacy(q, legacy_sit)
    assert level == 3
    q2 = _situation("deploy")
    level2, _ = degrade_for_legacy(q2, legacy_sit)
    assert level2 == 4


# ── Level 3.5-D: situation-aware statistics + outcome truth ─────────────


def test_situation_a_vs_b_different_ranking(tmp_path):
    stats_path = tmp_path / "stats.json"
    eng = ActionLearningEngine(ActionLearningConfig(enabled=True, statistics_path=stats_path))
    sit_a = _situation("fix")
    sit_b = _situation("create")
    act_a, act_b = "code_edit", "respond"

    for _ in range(2):
        eng.record_outcome(sit_a, act_a, ActionLearningOutcome(success=True))
        eng.record_outcome(sit_a, act_b, ActionLearningOutcome(success=False))
    for _ in range(2):
        eng.record_outcome(sit_b, act_a, ActionLearningOutcome(success=False))
        eng.record_outcome(sit_b, act_b, ActionLearningOutcome(success=True))

    ra = eng.rank_actions(sit_a, [act_a, act_b])
    rb = eng.rank_actions(sit_b, [act_a, act_b])
    assert ra[0]["action_key"] == act_a
    assert rb[0]["action_key"] == act_b
    assert ra[0]["action_key"] != rb[0]["action_key"]


def test_situation_aware_keys_on_disk(tmp_path):
    stats_path = tmp_path / "stats.json"
    eng = ActionLearningEngine(ActionLearningConfig(enabled=True, statistics_path=stats_path))
    eng.record_outcome(_situation("fix"), "code_edit", ActionLearningOutcome(success=True))
    eng.record_outcome(_situation("create"), "code_edit", ActionLearningOutcome(success=False))
    data = json.loads(stats_path.read_text(encoding="utf-8"))
    assert "intent:fix|action:code_edit" in data
    assert "intent:create|action:code_edit" in data
    assert "code_edit" not in data


def test_situation_specific_preferred_over_global(tmp_path):
    stats_path = tmp_path / "stats.json"
    eng = ActionLearningEngine(ActionLearningConfig(enabled=True, statistics_path=stats_path))
    sit_a = _situation("fix")
    sit_b = _situation("create")
    eng.record_outcome(sit_a, "tool_call", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_a, "tool_call", ActionLearningOutcome(success=True))
    for _ in range(6):
        eng.record_outcome(sit_b, "tool_call", ActionLearningOutcome(success=False))
    eng.record_outcome(sit_b, "respond", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_b, "respond", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_b, "respond", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(sit_a, ["tool_call", "respond"])
    assert ranked[0]["action_key"] == "tool_call"
    assert ranked[0]["match_level"] == 1


def test_global_fallback_when_specific_insufficient(tmp_path):
    stats_path = tmp_path / "stats.json"
    eng = ActionLearningEngine(ActionLearningConfig(enabled=True, statistics_path=stats_path))
    sit_a = _situation("fix")
    sit_b = _situation("create")
    eng.record_outcome(sit_a, "tool_call", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_b, "tool_call", ActionLearningOutcome(success=True))
    eng.record_outcome(sit_b, "tool_call", ActionLearningOutcome(success=False))
    eng.record_outcome(sit_b, "tool_call", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(sit_a, ["tool_call"])
    assert ranked[0]["support_count"] == 4
    assert ranked[0]["match_level"] == 3


def test_unknown_outcome_not_learned(tmp_path):
    stats_path = tmp_path / "stats.json"
    eng = ActionLearningEngine(ActionLearningConfig(enabled=True, statistics_path=stats_path))
    sit = _situation("fix")
    assert eng.record_outcome(sit, "code_edit", ActionLearningOutcome(success=None)) is False
    ranked = eng.rank_actions(sit, ["code_edit"])
    assert ranked[0]["support_count"] == 0
    assert ranked[0]["evidence_status"] == "no_evidence"


def test_mock_outcome_not_in_production_stats(tmp_path):
    from neurocortex.action_learning.outcome_adapter import OutcomeAdapter, ExecutionResult
    adapter = OutcomeAdapter(require_real=True)
    mock = ExecutionResult(success=True, actual_outcome="mock-ok", source="mock")
    od = adapter.to_outcome_data(mock)
    assert od.success is None
    assert not adapter.is_learning_eligible(od)
    real = ExecutionResult(success=True, actual_outcome="real-ok", source="real")
    od2 = adapter.to_outcome_data(real)
    assert od2.success is True
    assert adapter.is_learning_eligible(od2)


def test_predicted_prob_confidence_not_in_score(tmp_path):
    eng = _engine(tmp_path)
    eng.record_outcome(_situation("fix"), "code_review", ActionLearningOutcome(success=True))
    e1 = _make_experience("fix", "code_review", True, raw="a", predicted_prob=0.99, confidence=0.99)
    e2 = _make_experience("fix", "code_review", True, raw="b", predicted_prob=0.01, confidence=0.01)
    r1 = eng.rank_actions(_situation("fix"), ["code_review"], experiences=[e1])[0]
    r2 = eng.rank_actions(_situation("fix"), ["code_review"], experiences=[e2])[0]
    assert r1["estimated_success"] == r2["estimated_success"]
