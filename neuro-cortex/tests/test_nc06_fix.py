"""NC-06.2 FIX: Evidence Scope Isolation Tests

These tests validate that:
1. Global evidence cannot dominate sufficient local evidence
2. Local evidence beats global evidence when both exist
3. Global fallback works when local evidence is absent
4. match_level is recorded correctly
5. Ranking remains ordered (top_score >= second_score)
6. insufficient_evidence is based on evidence validity, not negative gap
7. create case works correctly
8. optimize case works correctly
9. Anti-self-reinforcement regression test passes
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from neurocortex.action_learning.engine import ActionLearningEngine, StatisticsStore
from neurocortex.action_learning.config import ActionLearningConfig
from neurocortex.action_learning.schema import ActionLearningSituation, ActionLearningCandidate, ActionLearningOutcome
from neurocortex.policy.engine import PolicyEngine
from neurocortex.policy.config import PolicyConfig


def _situation(intent: str = "create", raw: str = "") -> ActionLearningSituation:
    return ActionLearningSituation(
        intent=intent,
        task_type=None,
        error_type=None,
        context_features={},
        raw_input=raw,
        situation_completeness="partial",
    )


def _engine(tmp_path: Path, enabled: bool = True) -> ActionLearningEngine:
    cfg = ActionLearningConfig(
        enabled=enabled,
        statistics_path=tmp_path / "stats.json",
        shadow_only=False,
    )
    return ActionLearningEngine(cfg)


def _policy(min_evidence: int = 2) -> PolicyEngine:
    return PolicyEngine(PolicyConfig(enabled=True, min_evidence=min_evidence))


class TestEvidenceScopeIsolation:
    """FIX 2: Evidence scope isolation - L1 should not be compared with L3 directly."""

    def test_local_evidence_beats_global(self, tmp_path):
        """When local evidence exists, global popularity should not override it."""
        eng = _engine(tmp_path)
        
        # Record local evidence for create|code_edit: 36 successes
        for _ in range(36):
            eng.record_outcome(_situation("create"), "code_edit", ActionLearningOutcome(success=True))
        
        # Record global evidence for respond: 122 successes  
        for _ in range(122):
            eng.record_outcome(_situation("fix"), "respond", ActionLearningOutcome(success=True))
        
        # Evaluate create intent
        ranked = eng.rank_actions(_situation("create"), ["code_edit", "respond"])
        
        # code_edit should be ranked first (local L1 evidence)
        assert ranked[0]["action_key"] == "code_edit", \
            f"Expected code_edit first, got {ranked[0]['action_key']}"
        assert ranked[0]["match_level"] == 1, "code_edit should have L1 match"
        assert ranked[1]["action_key"] == "respond", \
            f"Expected respond second, got {ranked[1]['action_key']}"
        assert ranked[1]["match_level"] == 3, "respond should have L3 match"

    def test_global_fallback_when_local_absent(self, tmp_path):
        """When no local evidence, global should still work as fallback."""
        eng = _engine(tmp_path)
        
        # Record global evidence for respond (no local intent evidence)
        for _ in range(50):
            eng.record_outcome(_situation("general"), "respond", ActionLearningOutcome(success=True))
        
        # Evaluate fix intent - no local evidence
        ranked = eng.rank_actions(_situation("fix"), ["respond", "code_edit"])
        
        # respond should be ranked via global fallback
        respond = next(r for r in ranked if r["action_key"] == "respond")
        assert respond["match_level"] == 3, "respond should have L3 match (global)"
        assert respond["support_count"] == 50

    def test_match_level_is_recorded(self, tmp_path):
        """match_level must be recorded for each candidate."""
        eng = _engine(tmp_path)
        
        # Create L1 evidence
        for _ in range(10):
            eng.record_outcome(_situation("create"), "code_edit", ActionLearningOutcome(success=True))
        
        # Create L3 evidence
        for _ in range(10):
            eng.record_outcome(_situation("fix"), "respond", ActionLearningOutcome(success=True))
        
        ranked = eng.rank_actions(_situation("create"), ["code_edit", "respond"])
        
        for r in ranked:
            assert r["match_level"] is not None, f"match_level missing for {r['action_key']}"
        
        code_edit = next(r for r in ranked if r["action_key"] == "code_edit")
        respond = next(r for r in ranked if r["action_key"] == "respond")
        assert code_edit["match_level"] == 1
        assert respond["match_level"] == 3


class TestRankingOrder:
    """Verify ranking order is maintained."""

    def test_ranking_order_preserved(self, tmp_path):
        """Top score must be >= second score."""
        eng = _engine(tmp_path)
        
        # Create conflicting evidence
        for _ in range(10):
            eng.record_outcome(_situation("create"), "code_edit", ActionLearningOutcome(success=True))
        for _ in range(100):
            eng.record_outcome(_situation("general"), "respond", ActionLearningOutcome(success=False))
        
        ranked = eng.rank_actions(_situation("create"), ["code_edit", "respond"])
        
        scores = [r["score"] for r in ranked]
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1)), \
            f"Ranking not ordered: {scores}"


class TestPolicyDecision:
    """FIX 3: PolicyEngine decision logic."""

    def test_create_case_decided(self, tmp_path):
        """create intent with code_edit evidence should return decided."""
        eng = _engine(tmp_path)
        policy = _policy(min_evidence=1)
        
        # Simulate create|code_edit = 36 evidence
        for _ in range(20):
            eng.record_outcome(_situation("create"), "code_edit", ActionLearningOutcome(success=True))
        
        sit = _situation("create")
        cands = [ActionLearningCandidate("code_edit", "code_edit"), 
                 ActionLearningCandidate("respond", "respond")]
        ranked = eng.rank_actions(sit, cands)
        result = policy.choose_action(sit, cands, ranked)
        
        assert result["decision_status"] == "decided", \
            f"Expected decided, got {result['decision_status']}: {result['decision_reason']}"
        assert result["selected_action"] == "code_edit"

    def test_optimize_case_decided(self, tmp_path):
        """optimize intent with tool_call evidence should return decided."""
        eng = _engine(tmp_path)
        policy = _policy(min_evidence=1)
        
        # Simulate optimize|tool_call = 32 evidence
        for _ in range(20):
            eng.record_outcome(_situation("optimize"), "tool_call", ActionLearningOutcome(success=True))
        
        sit = _situation("optimize")
        cands = [ActionLearningCandidate("tool_call", "tool_call"),
                 ActionLearningCandidate("code_edit", "code_edit")]
        ranked = eng.rank_actions(sit, cands)
        result = policy.choose_action(sit, cands, ranked)
        
        assert result["decision_status"] == "decided", \
            f"Expected decided, got {result['decision_status']}: {result['decision_reason']}"

    def test_insufficient_evidence_not_negative_gap(self, tmp_path):
        """insufficient_evidence should not be triggered by negative gap bug."""
        eng = _engine(tmp_path)
        policy = _policy(min_evidence=1)
        
        # Create scenario where global respond > local code_edit
        for _ in range(10):
            eng.record_outcome(_situation("create"), "code_edit", ActionLearningOutcome(success=True))
        for _ in range(100):
            eng.record_outcome(_situation("general"), "respond", ActionLearningOutcome(success=True))
        
        sit = _situation("create")
        cands = [ActionLearningCandidate("code_edit", "code_edit"),
                 ActionLearningCandidate("respond", "respond")]
        ranked = eng.rank_actions(sit, cands)
        
        # After FIX, code_edit should be first (local > global)
        assert ranked[0]["action_key"] == "code_edit"
        
        result = policy.choose_action(sit, cands, ranked)
        
        # Should be decided, not insufficient_evidence
        assert result["decision_status"] == "decided"


class TestAntiSelfReinforcement:
    """Anti-self-reinforcement regression tests."""

    def test_global_does_not_dominate_local(self, tmp_path):
        """Global evidence should not dominate local evidence with sufficient support."""
        eng = _engine(tmp_path)
        
        # Local: create|code_edit = 36 samples
        for _ in range(36):
            eng.record_outcome(_situation("create"), "code_edit", ActionLearningOutcome(success=True))
        
        # Global: respond = 122 samples
        for _ in range(122):
            eng.record_outcome(_situation("fix"), "respond", ActionLearningOutcome(success=True))
        
        ranked = eng.rank_actions(_situation("create"), ["code_edit", "respond"])
        
        # code_edit (L1) should beat respond (L3) despite lower count
        assert ranked[0]["action_key"] == "code_edit"
        assert ranked[0]["match_level"] == 1
        assert ranked[1]["action_key"] == "respond"
        assert ranked[1]["match_level"] == 3

    def test_local_respond_when_supported(self, tmp_path):
        """If local evidence supports respond, Policy should select respond."""
        eng = _engine(tmp_path)
        
        # Local: create|respond = 20 successes
        for _ in range(20):
            eng.record_outcome(_situation("create"), "respond", ActionLearningOutcome(success=True))
        
        ranked = eng.rank_actions(_situation("create"), ["code_edit", "respond"])
        
        # respond should be first (local evidence)
        assert ranked[0]["action_key"] == "respond"
        assert ranked[0]["match_level"] == 1


class TestRealDataRegression:
    """Test with real historical data from ~/.neurocortex_action_statistics.json"""

    def test_real_create_intent(self, tmp_path, monkeypatch):
        """Test create intent with real statistics."""
        # Use real stats file
        real_stats = Path.home() / ".neurocortex_action_statistics.json"
        if not real_stats.exists():
            pytest.skip("Real statistics file not found")
        
        # Copy to temp location for testing
        import shutil
        test_stats = tmp_path / "real_stats.json"
        shutil.copy(real_stats, test_stats)
        
        eng = ActionLearningEngine(ActionLearningConfig(
            enabled=True,
            statistics_path=test_stats,
            shadow_only=False,
        ))
        policy = PolicyEngine(PolicyConfig(enabled=True, min_evidence=1))
        
        # Test create intent
        sit = _situation("create")
        cands = [ActionLearningCandidate("code_edit", "code_edit"),
                 ActionLearningCandidate("respond", "respond")]
        ranked = eng.rank_actions(sit, cands)
        result = policy.choose_action(sit, cands, ranked)
        
        # With FIX: code_edit should be ranked first (local L1 evidence)
        if ranked:
            assert ranked[0]["action_key"] == "code_edit", \
                f"Expected code_edit first, got {ranked[0]['action_key']}"
            assert ranked[0]["match_level"] == 1

    @pytest.mark.parametrize("intent", ["fix", "optimize", "deploy", "review", "explain", "test", "general"])
    def test_all_intents_rank_correctly_intent(self, tmp_path, intent):
        """Regression test for all intents."""
        real_stats = Path.home() / ".neurocortex_action_statistics.json"
        if not real_stats.exists():
            pytest.skip("Real statistics file not found")
        
        import shutil
        test_stats = tmp_path / "real_stats.json"
        shutil.copy(real_stats, test_stats)
        
        eng = ActionLearningEngine(ActionLearningConfig(
            enabled=True,
            statistics_path=test_stats,
            shadow_only=False,
        ))
        
        sit = _situation(intent)
        
        # Get candidates based on intent
        if intent in ("create", "fix"):
            cands = ["code_edit", "respond"]
        elif intent == "optimize":
            cands = ["tool_call", "code_edit"]
        else:
            cands = ["respond", "tool_call"]
        
        ranked = eng.rank_actions(sit, cands)
        
        # Verify ranking is ordered by score
        scores = [r["score"] for r in ranked if r["score"] is not None]
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
