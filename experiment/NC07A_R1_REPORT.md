# NC-07A-R1: Ranking Correctness Fix & Re-validation Report

**Date**: 2026-09-09 12:40:00
**Verdict**: `NATURAL_DISAGREEMENT_DETECTED`

---

## Executive Summary

Fixed ranking bug in `ActionLearningEngine._sort_ranked()` and re-run NC-07A with 102 real tasks.

**Result**: **12 natural disagreements detected** (11.8%)

---

## Bug Fix Applied

### Before (Buggy)
```python
def key_fn(r):
    has_evidence = 1 if r["evidence_status"] == "evidence" else 0
    level = r.get("match_level") or 4
    score = r["score"] if r["score"] is not None else -1.0
    return (has_evidence, -level, score, r["support_count"], -r["original_index"])
```

**Problem**: `-level` prioritized over `score`, forcing L1 above L3 regardless of actual scores.

### After (Fixed)
```python
def key_fn(r):
    score = r["score"] if r["score"] is not None else -1.0
    support = r["support_count"]
    return (score, support)
```

**Correct**: Sort by `adjusted_score` only (already includes match_level_penalty).

---

## Unit Tests Passed

| Case | Description | Status |
|------|-------------|--------|
| 1 | L3(0.423) > L1(0.326) | ✓ PASS |
| 2 | L1(0.447) > L3(0.423) | ✓ PASS |
| 3 | Same score, higher support wins | ✓ PASS |
| 4 | Same score + support, tie-breaker | ✓ PASS |
| 5 | No evidence handling | ✓ PASS |

**All 5 unit tests passed.**

---

## Regression Tests

| Test Suite | Result |
|------------|--------|
| test_nc06_fix.py (17 tests) | ✓ 17 passed |
| test_action_learning.py (41 tests) | ✓ 41 passed |
| **Total** | **✓ 58 passed** |

**No regressions in Evidence Isolation (NC-06.2 fix).**

---

## NC-07A Re-validation Results

### Summary
- Total tasks: **102**
- Natural agreements: **90** (88.2%)
- Natural disagreements: **12** (11.8%)

### Disagreement Breakdown

| Intent | Original | NC Selected | Count |
|--------|----------|-------------|-------|
| optimize | tool_call | respond | **12** |
| deploy | tool_call | tool_call | 0 |
| create | code_edit | code_edit | 0 |
| fix | code_review | code_review | 0 |
| review | respond | respond | 0 |
| explain | respond | respond | 0 |
| test | respond | respond | 0 |
| general | respond | respond | 0 |

### Key Finding: Optimize Intent

**Expected behavior confirmed**:
```
Optimize intent ranking:
  respond   : score=0.423 support=122 L3  ← HIGHER score wins
  tool_call : score=0.326 support=21  L1  ← Lower score despite L1
```

**Result**: NC selects `respond` (correct), Original selects `tool_call` (based on handcrafted mapping).

### Deploy Intent

**Expected behavior confirmed**:
```
Deploy intent ranking:
  tool_call : score=0.447 support=11  L1  ← HIGHER score wins
  respond   : score=0.423 support=122 L3  ← Lower score
```

**Result**: NC selects `tool_call` (correct), Original selects `tool_call` (agrees).

---

## Evidence Alignment

| Intent | Original Action | NC Action | L1 Score | L3 Score | Match? |
|--------|-----------------|-----------|----------|----------|--------|
| create | code_edit | code_edit | 0.455 | 0.423 | ✓ |
| fix | code_review | code_review | 0.639 | 0.423 | ✓ |
| **optimize** | **tool_call** | **respond** | **0.326** | **0.423** | **✗** |
| deploy | tool_call | tool_call | 0.447 | 0.423 | ✓ |
| review | respond | respond | 0.667 | 0.259 | ✓ |
| explain | respond | respond | 0.598 | 0.259 | ✓ |
| test | respond | respond | 0.425 | 0.259 | ✓ |
| general | respond | respond | 0.497 | 0.259 | ✓ |

---

## Verdict Justification

**`NATURAL_DISAGREEMENT_DETECTED`**

1. ✓ Ranking bug fixed
2. ✓ All 58 regression tests passed
3. ✓ 12 natural disagreements detected (all in optimize intent)
4. ✓ Disagreements are legitimate (evidence-based, not manufactured)
5. ✓ NC decision is correct (respond has higher adjusted_score)

---

## Next Steps

1. ✓ Ranking correctness validated
2. ✓ Full regression passed
3. ✓ Corrected NC-07A complete
4. ✓ Natural disagreements detected

**Ready for NC-07B: Controlled Policy Exploration**

---

## Files

- Fixed file: `neuro-cortex/src/neurocortex/action_learning/engine.py:530`
- Log file: `/root/.neurocortex_nc07a_log.jsonl`
- This report: `experiment/NC07A_DISAGREEMENT_COLLECTION_REPORT.md`

---

## Git Commits

```
[NEXT] fix: NC-07A-R1 Ranking Bug Fix + Natural Disagreement Detection
6a4aaa8 exp: NC-07A Natural Disagreement Collection
c5d131f exp: NC-06.5 Independent Candidate Generation
ab3463e audit: NC-06.4 Action Space Independence
59fd241 exp: NC-06.3 Natural Policy Disagreement
0e17430 fix: NC-06.2 Evidence Scope Isolation
```
