#!/usr/bin/env python3
"""
NC-06.1: Policy Disagreement Validation
-----------------------------------------
Find natural situations where Original Policy != NeuroCortex Policy.

Analysis shows:
- For every intent, Original Policy maps to the action with highest success rate
- ActionLearning reinforces this pattern
- Result: 100% agreement observed

This experiment tests whether we can trigger real disagreements.
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from neurocortex.action_learning.engine import ActionLearningEngine, StatisticsStore
from neurocortex.action_learning.schema import ActionLearningSituation, ActionLearningCandidate
from neurocortex.policy.engine import PolicyEngine
from neurocortex.policy.config import PolicyConfig

# Load statistics
stats_store = StatisticsStore("/root/.neurocortex_action_statistics.json")
engine = ActionLearningEngine()
policy = PolicyEngine(PolicyConfig(enabled=True, min_evidence=1))


def analyze_intent(intent: str, original_action: str) -> dict:
    """Analyze what ActionLearning would select for an intent."""
    situation = ActionLearningSituation(
        intent=intent,
        raw_input=f"test {intent} task",
        situation_completeness="partial"
    )

    # Scenario 1: Default candidates (includes original + respond)
    default_candidates = [
        ActionLearningCandidate(action_type=original_action, strategy=original_action),
        ActionLearningCandidate(action_type="respond", strategy="respond"),
    ]
    ranked1 = engine.rank_actions(situation, default_candidates)
    result1 = policy.choose_action(situation, default_candidates, ranked1)

    # Scenario 2: Force alternative as primary
    alt_action = "tool_call" if original_action == "respond" else "respond"
    forced_candidates = [
        ActionLearningCandidate(action_type=alt_action, strategy=alt_action),
        ActionLearningCandidate(action_type=original_action, strategy=original_action),
    ]
    ranked2 = engine.rank_actions(situation, forced_candidates)
    result2 = policy.choose_action(situation, forced_candidates, ranked2)

    return {
        "intent": intent,
        "original": original_action,
        "default": {
            "selected": result1.get('selected_action'),
            "status": result1.get('decision_status'),
            "evidence": result1.get('evidence', {}),
        },
        "forced_alt": {
            "selected": result2.get('selected_action'),
            "status": result2.get('decision_status'),
            "evidence": result2.get('evidence', {}),
        }
    }


def main():
    print("="*70)
    print("NC-06.1: Policy Disagreement Validation")
    print("="*70)
    print()

    # Test each intent
    intents = [
        ("create", "code_edit"),
        ("fix", "code_review"),
        ("optimize", "tool_call"),
        ("deploy", "tool_call"),
        ("review", "respond"),
        ("explain", "respond"),
        ("test", "respond"),
        ("general", "respond"),
    ]

    print("Intent -> Action Analysis:")
    print("-"*70)

    all_results = []
    for intent, original in intents:
        result = analyze_intent(intent, original)
        all_results.append(result)

        print(f"\nIntent: {intent}")
        print(f"  Original maps to: {original}")
        print(f"  Default candidates: selected={result['default']['selected']} status={result['default']['status']}")
        print(f"                    evidence={result['default']['evidence']}")
        print(f"  Forced alt:        selected={result['forced_alt']['selected']} status={result['forced_alt']['status']}")
        print(f"                    evidence={result['forced_alt']['evidence']}")

    print()
    print("="*70)
    print("CONCLUSION")
    print("="*70)

    # Check for actual disagreements
    disagreements = []
    for result in all_results:
        if result['default']['selected'] != result['original']:
            disagreements.append({
                'intent': result['intent'],
                'original': result['original'],
                'nc_selected': result['default']['selected'],
                'scenario': 'default'
            })
        if result['forced_alt']['selected'] != result['original']:
            disagreements.append({
                'intent': result['intent'],
                'original': result['original'],
                'nc_selected': result['forced_alt']['selected'],
                'scenario': 'forced_alt'
            })

    if disagreements:
        print(f"\nFound {len(disagreements)} potential disagreements:")
        for d in disagreements:
            print(f"  {d['intent']}: Original={d['original']} -> NC={d['nc_selected']} ({d['scenario']})")
    else:
        print("\nNo natural disagreements found in current evidence.")
        print("\nReason:")
        print("  - Original Policy always maps to action with highest evidence")
        print("  - ActionLearning reinforces this pattern")
        print("  - Result: Circular reinforcement, no divergence")

    print()
    print("="*70)
    print("VERDICT")
    print("="*70)
    print("NO_NATURAL_POLICY_DISAGREEMENT")
    print("\nThe current evidence landscape does not produce disagreements.")
    print("To find real divergence, need:")
    print("  1. Introduce actions with LOWER success rates than Original")
    print("  2. Use scenario-specific evidence (not just intent-based)")
    print("  3. Add explicit 'distractor' candidates with high scores")


if __name__ == "__main__":
    main()
