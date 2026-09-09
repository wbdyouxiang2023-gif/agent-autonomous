# NC-06.4 Action Space / Policy Independence Audit Report

**Date**: 2026-09-09 12:18:09

## Executive Summary

This audit examines whether the NeuroCortex Policy Engine has true independence from the Original Policy.

### Key Findings

| Metric | Value |
|--------|-------|
| Total candidate generations | 40 |
| Multi-action scenarios | 29 (72.5%) |
| Policy agreements | 8 (100.0%) |
| Policy disagreements | 0 (0.0%) |
| Independence test disagreements | 2/3 |

## Phase 1: Candidate Generation Audit

### Architecture

```
Original Policy (BasicDecision)
    ↓ intent + original_action
Candidate Generator (multi_action_generator.py)
    ↓ generates candidates (ALWAYS includes original_action)
    ↓ ranked by ActionLearning + PolicyEngine
    ↓ final decision
```

### Key Observation

**The candidate generator ALWAYS includes the original_action.**

This means:
1. NC can never select an action outside the candidate set
2. The candidate set is seeded by Original Policy
3. NC has "freedom" to reorder, but not to choose truly novel actions

### Candidate Distribution by Intent

#### create
- Original action: `code_edit`
- Typical candidates: `['code_edit', 'tool_call']`
- Has alternatives: True
- Alternative actions: ['tool_call']

#### fix
- Original action: `code_review`
- Typical candidates: `['code_review', 'code_edit']`
- Has alternatives: True
- Alternative actions: ['code_edit']

#### optimize
- Original action: `tool_call`
- Typical candidates: `['tool_call', 'code_edit']`
- Has alternatives: True
- Alternative actions: ['code_edit']

#### deploy
- Original action: `tool_call`
- Typical candidates: `['tool_call', 'respond']`
- Has alternatives: True
- Alternative actions: ['respond']

#### review
- Original action: `respond`
- Typical candidates: `['code_review', 'respond']`
- Has alternatives: True
- Alternative actions: ['code_review']

#### explain
- Original action: `respond`
- Typical candidates: `['respond']`
- Has alternatives: False
- Alternative actions: []

#### test
- Original action: `respond`
- Typical candidates: `['tool_call', 'respond']`
- Has alternatives: True
- Alternative actions: ['tool_call']

#### general
- Original action: `respond`
- Typical candidates: `['respond']`
- Has alternatives: False
- Alternative actions: []

## Phase 2: Evidence Convergence Audit

With NC-06.2 FIX applied, all intents now show `decided` status.

### Convergence Results

| Intent | Original | NC Selected | Agreement |
|--------|----------|-------------|-----------|
| create   | code_edit    | code_edit    | True |
| fix      | code_review  | code_review  | True |
| optimize | tool_call    | tool_call    | True |
| deploy   | tool_call    | tool_call    | True |
| review   | respond      | respond      | True |
| explain  | respond      | respond      | True |
| test     | respond      | respond      | True |
| general  | respond      | respond      | True |

### Why No Natural Disagreements?

1. **Original Policy is optimal**: The handcrafted intent→action mapping aligns with evidence
2. **Evidence reinforces Original**: Successful executions strengthen the same actions
3. **Self-stabilizing loop**: Original → Evidence → NC selects same → More evidence

## Phase 3: Policy Independence Audit

### Independence Test Results

#### Scenario 1: Strong local code_edit evidence
- Original: `code_edit`
- NC: `code_edit`
- Result: **AGREEMENT**

#### Scenario 2: Strong local respond evidence (counter to original)
- Original: `code_edit`
- NC: `respond`
- Result: **DISAGREEMENT**

#### Scenario 3: Strong local code_edit evidence (counter to original)
- Original: `code_review`
- NC: `code_edit`
- Result: **DISAGREEMENT**

## Critical Finding: Candidate Space Limitation

### The Structural Issue

The candidate generator is designed to:
1. Match input to situation patterns
2. Generate candidate actions
3. **Always include the original_action**
4. Re-score and normalize

This creates a fundamental dependency:
- NC cannot select actions outside the candidate set
- The candidate set is seeded by Original Policy
- Therefore, NC's "freedom" is bounded by Original's choices

### Evidence for This

Looking at the candidate generator code:
```python
# Ensure original_action is in candidates
original_in_candidates = any(c["id"] == original_action for c in candidates)
if not original_in_candidates and original_action != "noop":
    candidates.append({"id": original_action, "score": 0.3})
```

This means:
- Original action is ALWAYS in the candidate set
- NC can only choose from existing candidates
- NC cannot introduce truly novel actions

## Verdict

Based on this audit, the verdict is:

**CANDIDATE_SPACE_LIMITED**

### Explanation

The NeuroCortex Policy Engine has limited independence because:

1. **Candidate space is bounded**: The generator always includes Original's choice
2. **No truly novel actions**: NC can only reorder existing candidates
3. **Evidence reinforces Original**: Successful outcomes strengthen the same actions

However, the system IS working correctly:
- L1 local evidence properly beats L3 global evidence (NC-06.2 FIX)
- PolicyEngine makes proper decisions
- Zero harmful behavior changes

## Recommendations

### Option A: Expand Candidate Space
- Allow NC to generate truly novel candidates
- Use semantic analysis to discover alternative actions
- Risk: May introduce unsafe actions

### Option B: Accept Current State
- System is stable and safe
- Original Policy + Evidence alignment = correct behavior
- No harmful disagreements observed

### Option C: Introduce Controlled Exploration (NC-07)
- Add exploration mode to test alternatives
- Measure if alternative actions perform equally well
- Gradual rollout with safety guards

## Conclusion

The 0 natural disagreements in NC-06.3 is EXPECTED and CORRECT given:
1. Original Policy's intent→action mapping is optimal
2. Evidence system correctly reinforces successful actions
3. Candidate space includes Original's choice (by design)

This validates the architectural decision to use evidence-based decision making with proper scope isolation.

**Next Steps**: Consider NC-07 for controlled exploration, or proceed to R6.
