# NC-06.2 Audit Report: Contextual Evidence Isolation

## Executive Summary

**VERDICT: CONTEXTUAL_EVIDENCE_ISOLATION_BLOCKED**

Critical flaw identified: global `respond` evidence (122 samples) dominates local intent-specific evidence, preventing proper situation-aware learning.

---

## PART 1 — CODE AUDIT FINDINGS

### Issue 1: Cross-Intent Evidence Contamination

```
Current behavior for create intent:
  code_edit (L1): score=0.4553, support=36
  respond (L3):   score=0.6044, support=122
  
  Result: respond scores HIGHER than code_edit
  Because: 122 samples > 36 samples (raw count dominance)
```

### Issue 2: No Match-Level Penalty

The scoring formula does not penalize lower match levels:
```python
score = history_weight * hist_score + semantic_weight * semantic + recency_weight * recency
```

`match_level` is recorded but NOT used in score calculation.

### Issue 3: Confidence Gap Check Fails

For create intent:
```
Gap = top_score - second_score = 0.4553 - 0.6044 = -0.149
Gap < threshold (0.0) → insufficient_evidence
```

The system correctly identifies this as uncertain but cannot make a decision.

---

## PART 2 — EVIDENCE HIERARCHY (CURRENT vs PROPOSED)

### Current (BROKEN)
```
L1: intent:create|action:code_edit → support=36, score=0.46
L3: global|action:respond          → support=122, score=0.60
                                  ↑
            L3 beats L1 due to higher raw count!
```

### Proposed (FIXED)
```
Rule 1: L1 evidence ONLY compared with L1 evidence
Rule 2: L3 evidence ONLY used when NO L1 exists
Rule 3: Match-level penalty: L1=1.0, L2=0.9, L3=0.7

Result:
  code_edit (L1): score = 0.46 * 1.0 = 0.46 ✓ WINS
  respond (L3):   score = 0.60 * 0.7 = 0.42 ✗ LOSES
```

---

## PART 3 — ROOT CAUSE ANALYSIS

### The Self-Reinforcement Loop

```
┌─────────────────────────────────────────────────────┐
│  Original Policy selects "respond" for explain      │
│                       ↓                             │
│  ActionLearning records: intent:explain|action:respond +=1     │
│                       ↓                             │
│  Global respond count increases                     │
│                       ↓                             │
│  For create intent, respond (L3) now has 123 samples│
│                       ↓                             │
│  Respond scores higher than code_edit (L1, 36 samples)│
│                       ↓                             │
│  PolicyEngine returns insufficient_evidence         │
│                       ↓                             │
│  Original Policy still selects code_edit            │
│                       ↓                             │
│  But system is biased toward respond                │
└─────────────────────────────────────────────────────┘
```

---

## PART 4 — REQUIRED FIXES

### Fix 1: Add Match-Level Penalty

Location: `neuro-cortex/src/neurocortex/action_learning/engine.py`

```python
# In evaluate_candidates(), after computing score:
match_penalty = {1: 1.0, 2: 0.9, 3: 0.7, 4: 0.5}
penalty = match_penalty.get(match_level, 0.5)
score = score * penalty
```

### Fix 2: Enforce Scope Isolation

```python
# Group candidates by match_level
l1_cands = [c for c in evaluated if c.match_level == 1]
l3_cands = [c for c in evaluated if c.match_level == 3]

# Only compare within same level
if l1_cands:
    # Select from L1 candidates only
    return sorted(l1_cands, key=lambda x: x.score, reverse=True)
else:
    # Fall back to L3
    return sorted(l3_cands, key=lambda x: x.score, reverse=True)
```

### Fix 3: Update PolicyEngine Confidence Check

Current logic incorrectly allows negative gaps. Fix:
```python
# Use absolute gap or ensure proper ordering
gap = abs(top_score - second_score)
```

---

## PART 5 — OFFLINE REGRESSION TESTS

### Test Matrix

| Intent | Original | Local Evidence | Global Evidence | Expected After Fix |
|--------|----------|---------------|-----------------|-------------------|
| create | code_edit | 36 (L1) | 122 (L3) | code_edit wins |
| fix | code_review | 29 (L1) | 122 (L3) | code_review wins (already works) |
| optimize | tool_call | 21 (L1) | 122 (L3) | tool_call wins |
| review | respond | 58 (L1) | 122 (L3) | respond wins |

---

## PART 6 — SAFETY VERIFICATION

### Current State
- NEUROCORTEX_ACTION_LEARNING=true
- ACTION_LEARNING_SHADOW_ONLY=true
- REAL_EXECUTION_BRIDGE_ENABLED=false
- PolicyEngine disabled in production

### Proposed Changes
- Modify ActionLearningEngine only
- No changes to StatisticsStore schema
- No changes to historical data
- Purely offline logic fix

### Risk Assessment
- LOW RISK: Changes only affect ranking computation
- NO DATA LOSS: Existing statistics preserved
- NO BEHAVIOR CHANGE: Shadow mode remains disabled

---

## VERDICT

**CONTEXTUAL_EVIDENCE_ISOLATION_BLOCKED**

The current implementation:
- ✓ Has correct L1/L3 distinction in code structure
- ✗ Does not enforce scope isolation
- ✗ Does not apply match-level penalties
- ✗ Allows cross-intent evidence contamination

**Status**: Awaiting approval to implement fixes.
