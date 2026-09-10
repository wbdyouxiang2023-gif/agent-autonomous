#!/usr/bin/env python3
"""
Phase R5: Shadow Learning Observer with PolicyEngine

This module observes the NeuroCortex decision pipeline and records:
- Original decision (from BasicDecision)
- Shadow decision (from PolicyEngine using ActionLearning statistics)
- Real outcome
- Counterfactual observations

IMPORTANT: Zero behavioral change. All logging is append-only.
"""
import sys
import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from neurocortex.action_learning.schema import (
    ActionLearningSituation,
    ActionLearningCandidate,
)
from neurocortex.action_learning.bridge import ActionLearningBridge
from neurocortex.policy.engine import PolicyEngine
from neurocortex.policy.config import PolicyConfig

# Log path
SHADOW_LOG_PATH = Path(os.environ.get(
    "NEUROCORTEX_SHADOW_LOG_PATH",
    str(Path.home() / ".neurocortex_shadow_log.jsonl")
)).expanduser()


class ShadowLearningObserver:
    """
    Observes NeuroCortex decisions and records shadow policy comparisons.
    
    Architecture:
        Input → Perception → BasicDecision → [Shadow Observation] → Action → Outcome
                                         ↓
                                    candidates=[selected, noop]
                                         ↓
                            Shadow: rank_candidates() + choose_action()
                                         ↓
                                    No behavioral change
    """
    
    def __init__(
        self,
        action_bridge: Optional[ActionLearningBridge] = None,
        policy_engine: Optional[PolicyEngine] = None,
        log_path: Optional[Path] = None,
        policy_enabled: bool = False,
    ):
        self._bridge = action_bridge or ActionLearningBridge()
        # Create PolicyEngine with configured settings
        config = PolicyConfig(enabled=policy_enabled)
        self._policy = policy_engine or PolicyEngine(config)
        self._log_path = Path(log_path) if log_path else SHADOW_LOG_PATH
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._policy_enabled = policy_enabled
    
    @property
    def log_path(self) -> Path:
        return self._log_path
    
    def observe_decision(
        self,
        event: Any,
        raw_input: str,
    ) -> dict[str, Any]:
        """
        Observe a decision and record shadow comparison.
        
        Returns the shadow observation record.
        Does NOT modify event or affect execution.
        """
        # Get original decision info
        original_action = getattr(getattr(event, 'decision', None), 'selected_action', '')
        candidates = getattr(getattr(event, 'decision', None), 'candidates', [])
        original_rank = self._get_candidate_rank(candidates, original_action)
        
        # Build situation
        intent = getattr(getattr(event, 'perception', None), 'intent', '')
        situation = ActionLearningSituation(
            intent=intent,
            raw_input=raw_input[:200],
            situation_completeness="partial",
        )
        
        # Capture statistics BEFORE this decision
        stats_before = self._get_current_statistics()
        
        # Run shadow ranking and policy
        shadow_selected = None
        shadow_rank = None
        ranked_actions = []
        decision_status = "disabled"
        evidence = {}
        match_level = None
        scores = {}
        
        try:
            # Convert candidates to proper format
            coerced_candidates = []
            for c in candidates:
                if isinstance(c, dict):
                    at = c.get("id", "")
                    coerced_candidates.append(ActionLearningCandidate(action_type=at, strategy=at))
                else:
                    coerced_candidates.append(c)
            
            # Get ranked actions from bridge
            ranked = self._bridge.engine.rank_actions(
                situation=situation,
                candidate_actions=coerced_candidates,
            )
            ranked_actions = ranked
            
            # Get policy decision (only if enabled)
            if self._policy_enabled:
                policy_result = self._policy.choose_action(
                    situation=situation,
                    candidate_actions=coerced_candidates,
                    ranked_actions=ranked,
                )
            else:
                # Simulate what policy would choose
                policy_result = self._simulate_policy_decision(situation, coerced_candidates, ranked)
            
            shadow_selected = policy_result.get('selected_action')
            decision_status = policy_result.get('decision_status', 'disabled')
            evidence = policy_result.get('evidence', {})
            scores = policy_result.get('scores', {})
            
            # Find shadow rank
            if shadow_selected:
                for idx, r in enumerate(ranked):
                    if r.get('action_key') == shadow_selected:
                        shadow_rank = idx + 1
                        match_level = r.get('match_level')
                        break
            
        except Exception as e:
            # Fail-safe: never let shadow observation break production
            decision_status = "error"
        
        # Get real outcome (if available)
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
            "event_id": getattr(getattr(event, 'id', None), 'hex', str(uuid.uuid4())) if hasattr(getattr(event, 'id', None), 'hex') else str(uuid.uuid4()),
            "raw_input": raw_input[:500],
            "situation": raw_input[:100],
            "intent": intent,
            
            # Original decision
            "candidate_actions": [c.get("id") if isinstance(c, dict) else str(c) for c in candidates],
            "original_selected_action": original_action,
            "original_rank": original_rank,
            
            # Shadow decision
            "shadow_selected_action": shadow_selected,
            "shadow_rank": shadow_rank,
            "agreement": original_action == shadow_selected if shadow_selected else None,
            
            # Evidence
            "ranked_actions": [r.get("action_key") for r in ranked_actions],
            "evidence": evidence,
            "scores": scores,
            "match_level": match_level,
            "decision_status": decision_status,
            
            # Statistics snapshot (before this decision)
            "statistics_before": stats_before,
            
            # Real outcome
            "real_outcome": real_outcome,
            "success": success,
            
            # Metadata
            "observation_only": True,
            "phase": "R5",
            "policy_enabled": self._policy_enabled,
        }
        
        # Append to log
        self._append_log(record)
        
        return record
    
    def _simulate_policy_decision(self, situation, candidates, ranked):
        """Simulate policy decision when policy is disabled."""
        if not ranked:
            return {
                'selected_action': None,
                'decision_status': 'disabled',
                'ranked_actions': ranked,
                'scores': {},
                'evidence': {},
                'match_levels': {},
                'decision_reason': 'policy disabled',
            }
        
        # Find top-ranked action with evidence
        top = None
        for r in ranked:
            if r.get('support_count', 0) > 0:
                top = r
                break
        
        if top is None:
            return {
                'selected_action': None,
                'decision_status': 'no_evidence',
                'ranked_actions': ranked,
                'scores': {r['action_key']: r.get('score') for r in ranked},
                'evidence': {r['action_key']: r.get('support_count', 0) for r in ranked},
                'match_levels': {r['action_key']: r.get('match_level') for r in ranked},
                'decision_reason': 'no evidence available',
            }
        
        return {
            'selected_action': top['action_key'],
            'decision_status': 'decided',
            'ranked_actions': ranked,
            'scores': {r['action_key']: r.get('score') for r in ranked},
            'evidence': {r['action_key']: r.get('support_count', 0) for r in ranked},
            'match_levels': {r['action_key']: r.get('match_level') for r in ranked},
            'decision_reason': f'top-ranked by evidence: {top["action_key"]}',
        }
    
    def _get_candidate_rank(self, candidates: list, selected_action: str) -> int:
        """Get 1-based rank of selected action in candidates."""
        for idx, c in enumerate(candidates):
            cand_id = c.get("id") if isinstance(c, dict) else str(c)
            if cand_id == selected_action:
                return idx + 1
        return 0  # Not found
    
    def _get_current_statistics(self) -> dict[str, Any]:
        """Snapshot current action statistics."""
        try:
            stats_path = Path.home() / ".neurocortex_action_statistics.json"
            if stats_path.exists():
                with open(stats_path) as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _append_log(self, record: dict[str, Any]) -> None:
        """Append observation record to log file."""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            pass  # Never fail on logging
    
    def get_stats(self) -> dict[str, Any]:
        """Get shadow observation statistics."""
        if not self._log_path.exists():
            return {"total": 0}
        
        records = []
        with open(self._log_path) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        if not records:
            return {"total": 0}
        
        agreements = sum(1 for r in records if r.get("agreement") is True)
        disagreements = sum(1 for r in records if r.get("agreement") is False)
        no_evidence = sum(1 for r in records if r.get("decision_status") == "no_evidence")
        insufficient = sum(1 for r in records if r.get("decision_status") == "insufficient_evidence")
        decided = sum(1 for r in records if r.get("decision_status") == "decided")
        
        return {
            "total": len(records),
            "agreements": agreements,
            "disagreements": disagreements,
            "no_evidence": no_evidence,
            "insufficient_evidence": insufficient,
            "decided": decided,
            "agreement_rate": agreements / len(records) if records else 0,
        }


# Global instance
_shadow_observer = None


def get_shadow_observer(policy_enabled: bool = False) -> ShadowLearningObserver:
    """Get or create the global shadow observer."""
    global _shadow_observer
    if _shadow_observer is None:
        _shadow_observer = ShadowLearningObserver(policy_enabled=policy_enabled)
    return _shadow_observer


def observe_and_log(event, raw_input: str, policy_enabled: bool = False) -> dict[str, Any]:
    """Convenience function to observe a decision."""
    observer = get_shadow_observer(policy_enabled=policy_enabled)
    return observer.observe_decision(event, raw_input)
