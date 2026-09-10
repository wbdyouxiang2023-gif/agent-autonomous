# NC-08C.5 — Capability Boundary & Failure Injection

**Trial ID:** NC08C5-FI  
**Date:** 2026-09-09  
**Policy Version:** NC-08C.0 (frozen)  
**Status:** COMPLETE

---

## 1. Executive Summary

NC-08C.5 tested whether NC's evidence-based decision-making actually improves outcomes compared to Original policy.

| Metric | Original | NC V2 | Δ |
|--------|----------|-------|---|
| N | 24 | 36 | — |
| Task Completion | 21/24 = **87.5%** | 24/36 = **66.7%** | **-20.8pp** |
| Execution Success | 21/24 = 87.5% | 24/36 = 66.7% | -20.8pp |
| NC Direct Control | — | 29/36 = 80.6% | — |
| NC Abstain | — | 7/36 = 19.4% | — |
| Action Differences | — | 5/36 = 13.9% | — |

**Key Finding:** NC performed WORSE than Original (-20.8pp). Evidence-based decisions led to incorrect actions on ambiguous tasks.

---

## 2. Experimental Design

### Task Categories (60 tasks total)

| Category | N | Purpose | Evidence Status |
|----------|---|---------|-----------------|
| code_symbol | 10 | Code symbol location | Strong evidence for search_files |
| file_read | 10 | File reading | Strong evidence for read_file |
| terminal_info | 10 | Terminal commands | Strong evidence for terminal |
| evidence_poor | 10 | No historical evidence | Should ABSTAIN |
| file_search | 10 | File search | Strong evidence for search_files |
| ambiguous | 10 | Ambiguous situations | Mixed evidence |

### Failure Injection Design

1. **Evidence-correct tasks**: Where evidence supports the optimal action
2. **Evidence-poor tasks**: Where no evidence exists (should trigger ABSTAIN)
3. **Ambiguous tasks**: Where evidence might mislead

---

## 3. Evidence Utilization Analysis

### Evidence Level Distribution (NC)

| Level | Count | Description |
|-------|-------|-------------|
| LEVEL_0 | 7 | No evidence (evidence_poor tasks) |
| LEVEL_1 | 24 | Evidence exists but doesn't change action |
| LEVEL_2 | 0 | Evidence changes ranking only |
| LEVEL_3 | 5 | Evidence changes action |
| LEVEL_4 | 0 | Changed action improves outcome |

**Evidence Utilization Rate:** 84.4% (30/36 tasks had some evidence)

### Critical Finding: LEVEL_3 Failures

All 5 LEVEL_3 tasks (where NC changed action based on evidence) FAILED:

| Task ID | Category | Original Action | NC Action | Evidence | Result |
|---------|----------|-----------------|-----------|----------|--------|
| T054 | ambiguous | search_files | read_file | ev=5, conf=1.0 | ❌ FAILED |
| T052 | ambiguous | search_files | read_file | ev=5, conf=1.0 | ❌ FAILED |
| T059 | ambiguous | search_files | read_file | ev=5, conf=1.0 | ❌ FAILED |
| T056 | ambiguous | search_files | read_file | ev=5, conf=1.0 | ❌ FAILED |
| T057 | ambiguous | search_files | read_file | ev=5, conf=1.0 | ❌ FAILED |

**Root Cause:** Evidence incorrectly supported `read_file` for "查看代码结构" tasks, but `search_files` was the correct action.

---

## 4. ABSTAIN Analysis

### Correct Abstains (7/7)

All 7 evidence_poor tasks correctly triggered ABSTAIN:

```
NC08C5-T032 (evidence_poor): reason=low_confidence:conf=None ✅
NC08C5-T033 (evidence_poor): reason=low_confidence:conf=None ✅
NC08C5-T034 (evidence_poor): reason=low_confidence:conf=None ✅
NC08C5-T037 (evidence_poor): reason=low_confidence:conf=None ✅
NC08C5-T038 (evidence_poor): reason=low_confidence:conf=None ✅
NC08C5-T039 (evidence_poor): reason=low_confidence:conf=None ✅
NC08C5-T040 (evidence_poor): reason=low_confidence:conf=None ✅
```

**ABSTAIN Accuracy:** 100% (7/7 correct)

---

## 5. Per-Category Breakdown

| Category | Original TC | NC TC | NC Direct | NC Abstain | Δ |
|----------|-------------|-------|-----------|------------|---|
| code_symbol | 4/4 (100%) | 6/6 (100%) | 6 | 0 | 0pp |
| file_read | 4/4 (100%) | 6/6 (100%) | 6 | 0 | 0pp |
| terminal_info | 3/3 (100%) | 7/7 (100%) | 7 | 0 | 0pp |
| file_search | 5/5 (100%) | 5/5 (100%) | 5 | 0 | 0pp |
| **ambiguous** | **5/5 (100%)** | **0/5 (0%)** | 5 | 0 | **-100pp** ❌ |
| evidence_poor | 0/3 (0%) | 0/7 (0%) | 0 | 7 | 0pp |

**Critical Finding:** NC failed 100% on ambiguous tasks where it changed action based on misleading evidence.

---

## 6. Statistical Analysis

### Overall
- Original: 21/24 = 87.5%
- NC V2: 24/36 = 66.7%
- Difference: **-20.8pp**

### 95% Wilson Score Confidence Intervals
- Original TC: [69.0%, 95.7%]
- NC V2 TC: [50.3%, 79.8%]
- **Difference contains zero** → Not statistically significant

### Ambiguous Subset
- Original: 5/5 = 100%
- NC V2: 0/5 = 0%
- Difference: **-100pp** (statistically significant given small N)

---

## 7. Capability Boundary Findings

### What NC Does Well
1. ✅ **Evidence-poor abstention**: 100% accuracy on no-evidence tasks
2. ✅ **Evidence-correct tasks**: Matches Original on code_symbol, file_read, terminal_info, file_search
3. ✅ **High-confidence decisions**: When evidence is strong and correct

### What NC Fails At
1. ❌ **Misleading evidence**: When evidence supports wrong action (ambiguous tasks)
2. ❌ **Action change risk**: Changing action based on evidence can hurt performance
3. ❌ **LEVEL_4 absence**: Zero cases where evidence changed action AND improved outcome

### Capability Boundary
```
Evidence Quality ──────────────────────────────►
    |
    |  Strong + Correct ──► NC performs well (LEVEL_1)
    |  Strong + Wrong ────► NC performs poorly (LEVEL_3 failures)
    |  None / Weak ───────► NC abstains correctly (LEVEL_0)
    |
    ▼
Task Complexity ──────────────────────────────►
    |
    |  Simple/Clear ──────► Both policies succeed
    |  Ambiguous ─────────► Original succeeds, NC fails
```

---

## 8. Failure Taxonomy

| Code | Category | Count | Description |
|------|----------|-------|-------------|
| F1 | Intent/Situation Error | 0 | — |
| F2 | Candidate Generation Error | 0 | — |
| F3 | Evidence Retrieval Error | 0 | — |
| F4 | Evidence Quality Error | **5** | Misleading evidence for ambiguous tasks |
| F5 | Ranking Error | 0 | — |
| F6 | Confidence Error | 0 | — |
| F7 | Action Execution Error | 0 | — |
| F8 | Verifier Error | 0 | — |
| F9 | Environment/Task Design Error | 0 | — |
| F10 | Other | 0 | — |

**Primary Failure Mode:** F4 Evidence Quality Error

---

## 9. Data Integrity

| Check | Result |
|-------|--------|
| NC-08B 130 evidence unchanged | ✅ PASS (MD5 verified) |
| C.1-C.4 original data unchanged | ✅ PASS |
| No simulated/mock data | ✅ PASS |
| Policy frozen during trial | ✅ PASS |
| Assignment immutable | ✅ PASS |
| Outcomes isolated | ✅ PASS |

**NC-08B Evidence Integrity:**
```
real_completion_observations.jsonl: 4c99f3a39f8f2d39091ca91ac70b3e5d (unchanged)
situation_observations.jsonl:       fdba43950658375cedaacfc1af76366b (unchanged)
```

---

## 10. Regression Tests

| Suite | Result |
|-------|--------|
| NC-08C.0 (policy permission) | 20/20 PASS |
| NC-08C.0.1 (intent + executor + verifier + E2E) | 32/32 PASS |
| NC-08C.1-R1 (eligibility diagnosis) | 10/10 PASS |
| NC-08C.2 (ranking audit tests) | 5/5 PASS |
| Full pytest | **619 passed / 13 failed / 8 skipped** |
| NEW REGRESSION | **NO** ✅ |

---

## 11. Limitations

1. **Sample Size:** N=60 total (24+36) is moderate
2. **Task Design:** Ambiguous tasks may be too adversarial
3. **Evidence Quality:** Current evidence pool (130 records) may not cover all scenario types
4. **Classifier Limitation:** Classifier maps ambiguous situations to evidence-backed actions incorrectly

---

## 12. Final Verdict

### `LEVEL_2_EVIDENCE_INFLUENCE_DEMONSTRATED`

**What's Proven:**
1. ✅ Evidence retrieval works (24/36 tasks had evidence)
2. ✅ Evidence can change action (5/36 tasks showed action change)
3. ✅ Evidence-poor abstention works correctly (7/7 correct)
4. ❌ Evidence does NOT always improve outcomes (-20.8pp overall)
5. ❌ Evidence-based action changes can HURT performance (0/5 on ambiguous)

**What's NOT Proven:**
1. ⚠️ NC is better than Original (actually worse)
2. ⚠️ LEVEL_4 capability (evidence changes action AND improves outcome) = 0 cases
3. ⚠️ General policy superiority

**Key Insight:**
Evidence is a double-edged sword. When evidence is correct, NC performs well. When evidence is misleading (ambiguous tasks), NC performs worse than Original. The system needs better evidence quality validation before action changes.

**Recommendations:**
1. Add evidence quality validation layer
2. Implement evidence conflict detection
3. Consider ensemble approach (evidence + heuristic)
4. Do NOT proceed to canary/production

---

*Independent validation complete. C.1-C.4 data preserved. NC-08B evidence untouched.*
