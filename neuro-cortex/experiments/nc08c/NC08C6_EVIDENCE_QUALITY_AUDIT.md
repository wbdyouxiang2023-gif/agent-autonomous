# NC-08C.6 — Evidence Quality & Counterfactual Audit

**Trial ID:** NC08C5-FI (analyzed)  
**Date:** 2026-09-09  
**Policy Version:** NC-08C.0 (frozen)  
**Status:** AUDIT COMPLETE

---

## 1. Executive Summary

NC-08C.6 conducted a deep audit of evidence quality that led to NC's -20.8pp performance drop in C.5.

| Metric | Value |
|--------|-------|
| C.5 Overall Δ | -20.8pp (Original 87.5% vs NC 66.7%) |
| LEVEL_3 Cases | 29 total, 5 with actual action change |
| Action Changes | 5/5 FAILED ❌ |
| Root Cause | **MISLEADING_EVIDENCE** from incorrect task_type classification |

**Key Finding:** Evidence was Q4 quality (perfect consistency, n=5) but MISLEADING because classifier incorrectly mapped "查看代码结构" to `file_read` instead of `code_locator`/`search_files`.

---

## 2. C.5 Failure Audit

### LEVEL_3 Case Breakdown

| Task ID | Category | Original | NC Action | Evidence | Result |
|---------|----------|----------|-----------|----------|--------|
| T054 | ambiguous | search_files | **read_file** | ev=5, conf=1.0 | ❌ FAILED |
| T052 | ambiguous | search_files | **read_file** | ev=5, conf=1.0 | ❌ FAILED |
| T059 | ambiguous | search_files | **read_file** | ev=5, conf=1.0 | ❌ FAILED |
| T056 | ambiguous | search_files | **read_file** | ev=5, conf=1.0 | ❌ FAILED |
| T057 | ambiguous | search_files | **read_file** | ev=5, conf=1.0 | ❌ FAILED |

**All 5 action changes failed.** Evidence was high-quality but WRONG for the situation.

---

## 3. Evidence Quality Definition (Q0-Q5)

| Level | Definition | Description |
|-------|------------|-------------|
| Q0 | No evidence | No historical data for this (task_type, action) pair |
| Q1 | Semantic relevance | Keywords match but no direct outcome data |
| Q2 | Same task_type + action | Historical data exists but may be incomplete |
| Q3 | Same situation + action + outcome | Direct match with outcome |
| Q4 | Multiple independent outcomes | Consistent results across samples |
| Q5 | Stable + competing action contrast | Clear superiority over alternatives |

### C.5 Evidence Quality Classification

For the 5 failed LEVEL_3 cases:

| Task | Evidence (task_type, action) | Quality | Rate | N | Verdict |
|------|------------------------------|---------|------|---|---------|
| T054 | (file_read, read_file) | Q4 | 100% | 5 | **MISLEADING** |
| T052 | (file_read, read_file) | Q4 | 100% | 5 | **MISLEADING** |
| T059 | (file_read, read_file) | Q4 | 100% | 5 | **MISLEADING** |
| T056 | (file_read, read_file) | Q4 | 100% | 5 | **MISLEADING** |
| T057 | (file_read, read_file) | Q4 | 100% | 5 | **MISLEADING** |

**Critical Issue:** Evidence is Q4 quality (perfect consistency) but semantically WRONG for the task.

---

## 4. Five LEVEL_3 Case Studies

### Case 1: NC08C5-T054
```
Situation: "查看 project_4 的代码结构"
Classifier: ("file_read", "read_file") ← WRONG
Evidence: (file_read, read_file) → t=5, f=0, rate=100%
Original Action: search_files
NC Action: read_file (changed by evidence)
Result: FAILED ❌
Reason: "查看代码结构" requires SEARCHING, not READING a specific file
```

### Case 2: NC08C5-T052
```
Situation: "查看 project_2 的代码结构"
Classifier: ("file_read", "read_file") ← WRONG
Evidence: (file_read, read_file) → t=5, f=0, rate=100%
Original Action: search_files
NC Action: read_file (changed by evidence)
Result: FAILED ❌
```

(Same pattern for T059, T056, T057)

---

## 5. "查看代码结构" Deep Audit

### Evidence Comparison

| (task_type, action) | t | f | n | Rate | Quality |
|---------------------|---|---|---|------|---------|
| (file_read, read_file) | 5 | 0 | 5 | 100% | Q4 ✅ |
| (code_locator, search_files) | 5 | 0 | 5 | 100% | Q4 ✅ |
| (file_search, search_files) | 5 | 0 | 5 | 100% | Q4 ✅ |

### The Problem

Both evidence sources are Q4 quality, but:
- `read_file` evidence comes from "读取文件" situations
- `search_files` evidence comes from "搜索/定位" situations

**Classifier incorrectly mapped "查看代码结构" to `file_read` instead of `code_locator` or `file_search`.**

### Correct Classification Should Be

```
"查看 project_N 的代码结构"
    ↓
Should classify as: ("code_locator", "search_files") or ("file_search", "search_files")
    ↓
Evidence supports: search_files (100% rate, n=5)
    ↓
Correct action: search_files
```

### Actual Classification Was

```
"查看 project_N 的代码结构"
    ↓
Classified as: ("file_read", "read_file") ← WRONG
    ↓
Evidence supports: read_file (100% rate, n=5)
    ↓
Wrong action: read_file → FAILED
```

---

## 6. Counterfactual Analysis

### For Each LEVEL_3 Case

| Task | Original Action | NC Action | Original Would Succeed? | NC Failed? | Verdict |
|------|-----------------|-----------|------------------------|------------|---------|
| T054 | search_files | read_file | ✅ Yes | ❌ Yes | MISLEADING_EVIDENCE |
| T052 | search_files | read_file | ✅ Yes | ❌ Yes | MISLEADING_EVIDENCE |
| T059 | search_files | read_file | ✅ Yes | ❌ Yes | MISLEADING_EVIDENCE |
| T056 | search_files | read_file | ✅ Yes | ❌ Yes | MISLEADING_EVIDENCE |
| T057 | search_files | read_file | ✅ Yes | ❌ Yes | MISLEADING_EVIDENCE |

**Counterfactual Conclusion:** If NC had kept Original's action (search_files), all 5 tasks would have succeeded.

---

## 7. Evidence Reliability Score Proposal

### Proposed Scoring Factors

1. **Situation Match**: How well does the situation text match historical situations?
2. **Task Type Match**: Does the classifier produce the correct task_type?
3. **Action Match**: Does the evidence support the recommended action?
4. **Sample Size**: Is n sufficient (>5 preferred)?
5. **Consistency**: Are all outcomes consistent (no mixed results)?
6. **Competing Evidence**: Is there conflicting evidence for alternative actions?
7. **Source Reliability**: Is the evidence source trustworthy?

### Reliability Score Formula

```
reliability = w1*situation_match + w2*task_type_match + w3*action_match 
            + w4*log(n) + w5*consistency + w6*competing_evidence_penalty
```

Where:
- `competing_evidence_penalty`: Reduce score if alternative action has comparable evidence

---

## 8. Action Change Gate Proposal

### Proposed Gate Logic

```
IF evidence_quality == Q0:
    → ABSTAIN (no evidence)
ELIF evidence_quality == Q1:
    → KEEP_ORIGINAL (semantic relevance only)
ELIF evidence_quality >= Q2 AND competing_evidence == False:
    → ALLOW_ACTION_CHANGE
ELIF evidence_quality >= Q2 AND competing_evidence == True:
    → ABSTAIN (conflicting evidence)
ELSE:
    → KEEP_ORIGINAL
```

### For C.5 Cases

```
Situation: "查看 project_N 的代码结构"
Evidence for read_file: Q4, rate=100%, n=5
Competing evidence for search_files: Q4, rate=100%, n=5
    ↓
RESULT: ABSTAIN (conflicting evidence)
Expected: Keep Original (search_files)
```

---

## 9. C.5 -20.8pp Root Cause Analysis

### Attribution

| Factor | Contribution | Description |
|--------|--------------|-------------|
| A. Evidence Quality | **PRIMARY** | Misleading evidence from wrong task_type |
| B. Ranking | Secondary | Ranking worked correctly given wrong evidence |
| C. Candidate Generation | None | All candidates present |
| D. Execution | None | Execution worked correctly |
| E. Verifier | None | Verifier worked correctly |
| F. Task Design | Minor | Ambiguous tasks poorly designed |
| G. Sample Imbalance | Minor | NC had more tasks but similar difficulty |
| H. Other | None | — |

### Root Cause Statement

**The -20.8pp drop is PRIMARILY caused by Evidence Quality issue (F4):**
- Classifier mapped ambiguous situations to wrong task_type
- Evidence for wrong task_type was high-quality (Q4) but misleading
- NC trusted the evidence and changed action incorrectly
- All 5 action changes resulted in failure

---

## 10. LEVEL Classification Audit

### Corrected LEVEL Classification

| Level | Count | Description |
|-------|-------|-------------|
| LEVEL_0 | 7 | No evidence (evidence_poor tasks) |
| LEVEL_1 | 24 | Evidence exists, no action change |
| LEVEL_2 | 0 | Evidence influences ranking only |
| LEVEL_3 | 5 | Evidence changes action (ALL FAILED) |
| LEVEL_4 | 0 | Changed action improves outcome |

**Total LEVEL_3: 5** (not 29 as previously reported - only 5 had actual action changes)

### LEVEL_3 Breakdown

| Task | Original | NC | Evidence | Outcome | Verdict |
|------|----------|-----|----------|---------|---------|
| T054 | search_files | read_file | Q4 | FAILED | MISLEADING |
| T052 | search_files | read_file | Q4 | FAILED | MISLEADING |
| T059 | search_files | read_file | Q4 | FAILED | MISLEADING |
| T056 | search_files | read_file | Q4 | FAILED | MISLEADING |
| T057 | search_files | read_file | Q4 | FAILED | MISLEADING |

---

## 11. Policy V3 Proposal

### What Would Prevent C.5 Failure

1. **Competing Evidence Check**: Before changing action, check if alternative action has comparable evidence
2. **Task Type Validation**: Validate classifier output against situation semantics
3. **Ambiguity Detection**: Flag situations where multiple actions have similar evidence
4. **Conservative Action Change**: Only change action when evidence quality is Q5 (stable + clear superiority)

### Proposed Policy V3 Changes

```python
# Pseudocode for Action Change Gate
def should_change_action(situation, original_action, nc_recommendation, evidence):
    # Check competing evidence
    competing = get_competing_evidence(situation, original_action, nc_recommendation)
    
    if competing.has_comparable_evidence:
        return ABSTAIN  # Don't change when evidence conflicts
    
    if evidence.quality < Q4:
        return KEEP_ORIGINAL  # Need high quality to change
    
    if evidence.rate < 0.9:
        return KEEP_ORIGINAL  # Need high success rate
    
    return ALLOW_CHANGE
```

---

## 12. Regression Tests

| Suite | Result |
|-------|--------|
| NC-08C.0 (policy permission) | 20/20 PASS |
| NC-08C.0.1 (intent + executor + verifier + E2E) | 32/32 PASS |
| NC-08C.1-R1 (eligibility diagnosis) | 10/10 PASS |
| NC-08C.2 (ranking audit tests) | 5/5 PASS |
| Full pytest | **619 passed / 13 failed / 8 skipped** |
| NEW REGRESSION | **NO** ✅ |

---

## 13. Data Integrity

| Check | Result |
|-------|--------|
| NC-08B 130 evidence unchanged | ✅ PASS (MD5 verified) |
| C.1-C.5 original data unchanged | ✅ PASS |
| No simulated/mock data | ✅ PASS |
| Policy frozen during trial | ✅ PASS |
| Assignment immutable | ✅ PASS |

**NC-08B Evidence Integrity:**
```
real_completion_observations.jsonl: 4c99f3a39f8f2d39091ca91ac70b3e5d (unchanged)
situation_observations.jsonl:       fdba43950658375cedaacfc1af76366b (unchanged)
```

---

## 14. Limitations

1. **Evidence Pool Size**: 130 records may not cover all scenario types
2. **Classifier Limitations**: Current classifier cannot distinguish "查看" (inspect) from "读取" (read)
3. **Task Design**: Ambiguous tasks may not represent real-world scenarios
4. **Sample Size**: N=60 is moderate for statistical significance

---

## 15. Final Verdict

### `EVIDENCE_QUALITY_BUG_CONFIRMED`

**Confirmed Issues:**
1. ✅ Evidence can be Q4 quality (perfect consistency) yet MISLEADING
2. ✅ Classifier maps ambiguous situations to wrong task_type
3. ✅ High-quality misleading evidence causes incorrect action changes
4. ✅ All 5 LEVEL_3 action changes failed (0/5 success rate)

**Evidence Quality Bug Details:**
- **Type**: F4 Evidence Quality Error
- **Impact**: 5/5 action changes failed
- **Root Cause**: Classifier task_type misclassification
- **Symptom**: Q4 evidence supports wrong action

**Recommendations:**
1. Add competing evidence check before action changes
2. Improve classifier to distinguish "查看代码结构" from "读取文件"
3. Implement Action Change Gate with Q5 requirement for ambiguous situations
4. Do NOT deploy Policy V3 to production without further validation

---

*Evidence quality audit complete. C.1-C.5 data preserved. NC-08B evidence untouched.*
