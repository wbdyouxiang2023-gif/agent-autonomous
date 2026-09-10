#!/usr/bin/env python3
"""
NC-05B: Multi-Action Shadow Observer

Extends R5 shadow observer to support multi-action candidate generation.
Validates: Situation → Multi-Action Candidates → Ranking → Policy Selection

Architecture:
  Input → Perception → BasicDecision → [Original: action, noop]
                                       ↓
                              [Shadow: multi-action candidates]
                                       ↓
                          ActionLearning + PolicyEngine
                                       ↓
                              Shadow Selection (observed only)
"""
import sys
import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from neurocortex.action_learning.schema import (
    ActionLearningSituation,
    ActionLearningCandidate,
)
from neurocortex.action_learning.bridge import ActionLearningBridge
from neurocortex.policy.engine import PolicyEngine
from neurocortex.policy.config import PolicyConfig
from multi_action_generator import get_candidate_generator

SHADOW_LOG_PATH = Path(os.environ.get(
    "NEUROCORTEX_SHADOW_LOG_PATH",
    str(Path.home() / ".neurocortex_nc05b_log.jsonl")
)).expanduser()


class MultiActionShadowObserver:
    """
    Observes decisions with multi-action candidate generation.
    
    Records:
    - Original decision (from BasicDecision)
    - Multi-action candidates (from generator)
    - Shadow ranking and selection
    - Evidence comparison
    """
    
    def __init__(
        self,
        action_bridge: Optional[ActionLearningBridge] = None,
        policy_engine: Optional[PolicyEngine] = None,
        log_path: Optional[Path] = None,
        policy_enabled: bool = False,
    ):
        self._bridge = action_bridge or ActionLearningBridge()
        config = PolicyConfig(enabled=policy_enabled)
        self._policy = policy_engine or PolicyEngine(config)
        self._log_path = Path(log_path) if log_path else SHADOW_LOG_PATH
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._policy_enabled = policy_enabled
        self._generator = get_candidate_generator()
    
    @property
    def log_path(self) -> Path:
        return self._log_path
    
    def observe_decision(
        self,
        event: Any,
        raw_input: str,
    ) -> dict[str, Any]:
        """
        Observe a decision with multi-action candidate generation.
        
        Returns shadow observation record WITHOUT modifying production.
        """
        # Original decision info
        original_action = getattr(getattr(event, 'decision', None), 'selected_action', '')
        original_candidates = getattr(getattr(event, 'decision', None), 'candidates', [])
        original_rank = self._get_candidate_rank(original_candidates, original_action)
        
        # Extract intent
        intent = getattr(getattr(event, 'perception', None), 'intent', '')
        
        # Generate MULTI-ACTION candidates for shadow observation
        multi_candidates = self._generator.generate(raw_input, intent, original_action)
        
        # Count non-noop candidates
        non_noop_count = sum(1 for c in multi_candidates if c.get("id") != "noop")
        is_true_multi = non_noop_count >= 2
        
        # Build situation
        situation = ActionLearningSituation(
            intent=intent,
            raw_input=raw_input[:200],
            situation_completeness="partial" if not is_true_multi else "full",
        )
        
        # Capture statistics BEFORE
        stats_before = self._get_current_statistics()
        
        # Run shadow ranking with MULTI-ACTION candidates
        shadow_selected = None
        shadow_rank = None
        ranked_actions = []
        decision_status = "disabled"
        evidence = {}
        scores = {}
        match_levels = {}
        
        try:
            # Convert multi-candidates to proper format
            coerced_candidates = []
            for c in multi_candidates:
                at = c.get("id", "")
                coerced_candidates.append(ActionLearningCandidate(action_type=at, strategy=at))
            
            # Rank with ActionLearning
            ranked = self._bridge.engine.rank_actions(
                situation=situation,
                candidate_actions=coerced_candidates,
            )
            ranked_actions = ranked
            
            # Get policy decision
            if self._policy_enabled:
                policy_result = self._policy.choose_action(
                    situation=situation,
                    candidate_actions=coerced_candidates,
                    ranked_actions=ranked,
                )
            else:
                policy_result = self._simulate_policy_decision(situation, coerced_candidates, ranked)
            
            shadow_selected = policy_result.get('selected_action')
            decision_status = policy_result.get('decision_status', 'disabled')
            evidence = policy_result.get('evidence', {})
            scores = policy_result.get('scores', {})
            match_levels = policy_result.get('match_levels', {})
            
            # Find shadow rank
            if shadow_selected:
                for idx, r in enumerate(ranked):
                    if r.get('action_key') == shadow_selected:
                        shadow_rank = idx + 1
                        break
            
        except Exception as e:
            decision_status = "error"
        
        # Get real outcome
        real_outcome = None
        success = None
        try:
            outcome = getattr(event, 'outcome', None)
            if outcome:
                real_outcome = getattr(outcome, 'actual_outcome', None)
                success = getattr(outcome, 'success', None)
        except:
            pass
        
        # Build observation record
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": str(uuid.uuid4()),
            "raw_input": raw_input[:500],
            "situation": raw_input[:100],
            "intent": intent,
            
            # Original decision
            "original_candidates": [c.get("id") if isinstance(c, dict) else str(c) for c in original_candidates],
            "original_selected_action": original_action,
            "original_rank": original_rank,
            
            # Multi-action candidates (SHADOW ONLY)
            "multi_action_candidates": multi_candidates,
            "non_noop_candidate_count": non_noop_count,
            "is_true_multi_action": is_true_multi,
            
            # Shadow decision
            "shadow_selected_action": shadow_selected,
            "shadow_rank": shadow_rank,
            "agreement": original_action == shadow_selected if shadow_selected else None,
            
            # Evidence
            "ranked_actions": [r.get("action_key") for r in ranked_actions],
            "evidence": evidence,
            "scores": scores,
            "match_levels": match_levels,
            "decision_status": decision_status,
            
            # Statistics snapshot
            "statistics_before": stats_before,
            
            # Real outcome
            "real_outcome": real_outcome,
            "success": success,
            
            # Metadata
            "phase": "NC-05B",
            "observation_only": True,
            "policy_enabled": self._policy_enabled,
        }
        
        # Append to log
        self._append_log(record)
        
        return record
    
    def _simulate_policy_decision(self, situation, candidates, ranked):
        """Simulate policy when disabled."""
        if not ranked:
            return {'selected_action': None, 'decision_status': 'disabled',
                    'ranked_actions': ranked, 'scores': {}, 'evidence': {},
                    'match_levels': {}, 'decision_reason': 'policy disabled'}
        
        top = next((r for r in ranked if r.get('support_count', 0) > 0), None)
        
        if top is None:
            return {'selected_action': None, 'decision_status': 'no_evidence',
                    'ranked_actions': ranked, 
                    'scores': {r['action_key']: r.get('score') for r in ranked},
                    'evidence': {r['action_key']: r.get('support_count', 0) for r in ranked},
                    'match_levels': {r['action_key']: r.get('match_level') for r in ranked},
                    'decision_reason': 'no evidence'}
        
        return {'selected_action': top['action_key'], 'decision_status': 'decided',
                'ranked_actions': ranked,
                'scores': {r['action_key']: r.get('score') for r in ranked},
                'evidence': {r['action_key']: r.get('support_count', 0) for r in ranked},
                'match_levels': {r['action_key']: r.get('match_level') for r in ranked},
                'decision_reason': f'top-ranked: {top["action_key"]}'}
    
    def _get_candidate_rank(self, candidates, selected_action):
        """Get 1-based rank."""
        for idx, c in enumerate(candidates):
            cand_id = c.get("id") if isinstance(c, dict) else str(c)
            if cand_id == selected_action:
                return idx + 1
        return 0
    
    def _get_current_statistics(self):
        """Snapshot current stats."""
        try:
            stats_path = Path.home() / ".neurocortex_action_statistics.json"
            if stats_path.exists():
                with open(stats_path) as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _append_log(self, record):
        """Append to shadow log."""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except:
            pass
    
    def get_stats(self):
        """Get observation statistics."""
        if not self._log_path.exists():
            return {"total": 0}
        
        records = []
        with open(self._log_path) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        if not records:
            return {"total": 0}
        
        true_multi = sum(1 for r in records if r.get("is_true_multi_action"))
        agreements = sum(1 for r in records if r.get("agreement") is True)
        disagreements = sum(1 for r in records if r.get("agreement") is False)
        decided = sum(1 for r in records if r.get("decision_status") == "decided")
        
        # Generator stats
        gen_stats = self._generator.get_stats()
        
        return {
            "total": len(records),
            "true_multi_action_count": true_multi,
            "true_multi_action_rate": true_multi / len(records),
            "agreements": agreements,
            "disagreements": disagreements,
            "decided": decided,
            "generator_stats": gen_stats,
        }


# Global instance
_observer = None


def get_shadow_observer(policy_enabled: bool = False) -> MultiActionShadowObserver:
    """Get or create global observer."""
    global _observer
    if _observer is None:
        _observer = MultiActionShadowObserver(policy_enabled=policy_enabled)
    return _observer


def observe_and_log(event, raw_input: str, policy_enabled: bool = False) -> dict:
    """Convenience function."""
    obs = get_shadow_observer(policy_enabled=policy_enabled)
    return obs.observe_decision(event, raw_input)
