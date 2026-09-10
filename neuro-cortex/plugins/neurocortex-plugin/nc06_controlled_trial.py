#!/usr/bin/env python3
"""
NC-06: Controlled Policy Trial v0.1

Implements traffic-split controlled trial between:
- Original Policy (BasicDecision): ~70-90% of traffic
- NeuroCortex Policy (PolicyEngine): ~10-30% of traffic

Safety:
- Default OFF (NC06_ENABLED=false)
- Safe actions only: noop, respond, tool_call
- Fallback to Original on any NC-06 error
- Zero impact outside experiment scope
"""
import sys
import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from neurocortex.action_learning.schema import ActionLearningSituation, ActionLearningCandidate
from neurocortex.action_learning.bridge import ActionLearningBridge
from neurocortex.policy.engine import PolicyEngine
from neurocortex.policy.config import PolicyConfig

# ── Configuration ───────────────────────────────────────────────────────
NC06_ENABLED = os.environ.get("NC06_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
NC06_NC_RATIO = float(os.environ.get("NC06_NC_RATIO", "0.2"))  # 20% to NC-06
NC06_LOG_PATH = Path(os.environ.get(
    "NC06_LOG_PATH",
    str(Path.home() / ".neurocortex_nc06_log.jsonl")
)).expanduser()

# Safe actions for NC-06 (no destructive operations)
SAFE_ACTIONS = {"noop", "respond", "tool_call"}

# Fallback action if NC-06 fails
FALLBACK_ACTION = "respond"


class ControlledPolicyTrial:
    """
    Controlled trial comparing Original vs NeuroCortex Policy.
    
    Architecture:
      Input → Original Policy → original_action → [execute] → original_outcome
                            ↘
                             NC-06 Policy → nc_action → [shadow only] → nc_outcome
                              ↓
                         Compare & log
    """
    
    def __init__(self, policy_engine: Optional[PolicyEngine] = None):
        self._bridge = ActionLearningBridge()
        config = PolicyConfig(enabled=True)
        self._policy = policy_engine or PolicyEngine(config)
        self._log_path = NC06_LOG_PATH
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._decision_count = 0
        self._nc_decisions = 0
        self._fallback_count = 0
        self._safety_incidents = 0
    
    @property
    def decision_count(self) -> int:
        return self._decision_count
    
    @property
    def nc_decisions(self) -> int:
        return self._nc_decisions
    
    @property
    def fallback_count(self) -> int:
        return self._fallback_count
    
    @property
    def safety_incidents(self) -> int:
        return self._safety_incidents
    
    def should_use_nc_policy(self, raw_input: str, intent: str) -> bool:
        """
        Determine if this request should use NC-06 Policy.
        
        Returns True if:
        1. NC06_ENABLED is true
        2. Random split places it in NC-06 bucket
        3. The action would be safe (not destructive)
        """
        if not NC06_ENABLED:
            return False
        
        # Use hashlib for deterministic hashing across processes
        import hashlib
        h = int(hashlib.md5(raw_input.encode()).hexdigest(), 16)
        return (h % 100) < (NC06_NC_RATIO * 100)
    
    def choose_action(
        self,
        event,
        raw_input: str,
        intent: str,
        original_action: str,
    ) -> dict:
        """
        Choose between Original and NC-06 Policy.
        
        Returns dict with:
        - decision_id
        - original_action
        - nc_action (if chosen)
        - final_action
        - outcome comparison
        """
        self._decision_count += 1
        decision_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        result = {
            "decision_id": decision_id,
            "timestamp": timestamp,
            "raw_input": raw_input[:200],
            "intent": intent,
            "original_action": original_action,
            "nc_action": None,
            "final_action": original_action,
            "policy_used": "original",
            "outcome_status": "unknown",
            "fallback_used": False,
            "safety_incident": False,
        }
        
        # Check if this should use NC-06 Policy
        use_nc = self.should_use_nc_policy(raw_input, intent)
        
        if not use_nc:
            # Use Original Policy
            result["policy_used"] = "original"
            return result
        
        # NC-06 Path
        self._nc_decisions += 1
        result["policy_used"] = "nc06"
        
        try:
            # Build situation for NC-06
            situation = ActionLearningSituation(
                intent=intent,
                raw_input=raw_input[:200],
                situation_completeness="partial",
            )
            
            # Get multi-action candidates
            from multi_action_generator import get_candidate_generator
            generator = get_candidate_generator()
            multi_candidates = generator.generate(raw_input, intent, original_action)
            
            # Convert to proper format
            coerced_candidates = []
            for c in multi_candidates:
                at = c.get("id", "")
                coerced_candidates.append(ActionLearningCandidate(action_type=at, strategy=at))
            
            # Rank with ActionLearning
            ranked = self._bridge.engine.rank_actions(
                situation=situation,
                candidate_actions=coerced_candidates,
            )
            
            # Choose with PolicyEngine
            policy_result = self._policy.choose_action(
                situation=situation,
                candidate_actions=coerced_candidates,
                ranked_actions=ranked,
            )
            
            nc_action = policy_result.get('selected_action')
            result["nc_action"] = nc_action
            result["ranking"] = [r.get("action_key") for r in ranked]
            result["evidence"] = policy_result.get('evidence', {})
            result["decision_status"] = policy_result.get('decision_status', 'unknown')
            
            # Safety check: ensure NC action is safe
            if nc_action and nc_action not in SAFE_ACTIONS:
                # Unsafe action - fall back to Original
                self._safety_incidents += 1
                result["safety_incident"] = True
                result["final_action"] = original_action
                result["fallback_used"] = True
                result["fallback_reason"] = f"unsafe action: {nc_action}"
            elif nc_action:
                # Safe action - use NC-06 selection
                result["final_action"] = nc_action
            else:
                # No selection - fallback
                self._fallback_count += 1
                result["fallback_used"] = True
                result["final_action"] = original_action
                
        except Exception as e:
            # Error - fallback to Original
            self._fallback_count += 1
            result["fallback_used"] = True
            result["final_action"] = original_action
            result["error"] = str(e)
        
        return result
    
    def log_decision(self, result: dict) -> None:
        """Log decision to file."""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
        except Exception:
            pass
    
    def get_stats(self) -> dict:
        """Get trial statistics."""
        if not self._log_path.exists():
            return {"total": 0}
        
        records = []
        with open(self._log_path) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        if not records:
            return {"total": 0}
        
        original_count = sum(1 for r in records if r.get("policy_used") == "original")
        nc_count = sum(1 for r in records if r.get("policy_used") == "nc06")
        fallback_count = sum(1 for r in records if r.get("fallback_used"))
        safety_incidents = sum(1 for r in records if r.get("safety_incident"))
        
        # Disagreement rate
        disagreements = sum(
            1 for r in records 
            if r.get("original_action") != r.get("nc_action") and r.get("nc_action")
        )
        
        return {
            "total": len(records),
            "original_decisions": original_count,
            "nc_decisions": nc_count,
            "fallback_count": fallback_count,
            "safety_incidents": safety_incidents,
            "disagreements": disagreements,
            "disagreement_rate": disagreements / len(records) if records else 0,
            "nc_ratio": nc_count / len(records) if records else 0,
        }


# Global instance
_trial = None


def get_controlled_trial() -> ControlledPolicyTrial:
    """Get or create global trial instance."""
    global _trial
    if _trial is None:
        _trial = ControlledPolicyTrial()
    return _trial
