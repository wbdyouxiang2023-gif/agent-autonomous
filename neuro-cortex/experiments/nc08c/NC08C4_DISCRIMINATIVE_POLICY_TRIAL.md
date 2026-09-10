# NC-08C.4 — Discriminative Policy Trial

**Trial ID:** NC08C4-T01  
**Date:** 2026-09-09  
**Policy Version:** NC-08C.0 (frozen)  
**Status:** COMPLETE

---

## 1. Executive Summary

Policy V2 validation complete with discriminative task design:

| Metric | Original | NC V2 | Δ |
|--------|----------|-------|---|
| N | 34 | 26 | — |
| Task Completion | 34/34 = 100% | 26/26 = 100% | 0pp |
| Execution Success | 34/34 = 100% | 26/26 = 100% | 0pp |
| NC Direct Control | — | 26/26 = 100% | — |
| NC Abstain | — | 0/26 = 0% | — |

**Key Achievement:**
- NC went from 0% direct control (C.1) → 38% (C.3) → **100% direct control (C.4)**
- Hard negative tasks now properly handled with evidence-supported actions
- All 13 hard negative tasks completed successfully by both groups

**Conclusion:** Policy V2 fix is working correctly. However, tasks remain too easy to show statistical discrimination.

---

## 2. Historical Discriminative Evidence

### Pattern Identified from NC-08B (130 evidence records)

| Task Type | Action | Success Rate | N |
|-----------|--------|--------------|---|
| search_code_symbol | search_files | 100% | 5 |
| search_code_symbol | terminal | 0% | 5 |
| code_check | terminal | 100% | 5 |
| exact_answer | terminal | 100% | 5 |
| exact_answer_fail | terminal | 0% | 5 |

**Discriminative Insight:**
- `search_code_symbol` tasks should use `search_files`, not `terminal`
- Terminal has 0% completion for code location tasks
- This creates a clear policy difference opportunity

---

## 3. Policy V2 Changes Applied

### Changes Made
1. **Classifier Enhancement**: Added "定位.*函数|定位.*符号" pattern → `code_locator`/`search_files`
2. **Evidence Retrieval**: Multi-key aggregation for code_check/code_locator/code_check_fail
3. **Terminal Command Allow-list**: Expanded `_SAFE_PYTHON_C` to include sys.version queries

### What Was NOT Changed
- `nc_min_confidence` = 0.6 (frozen)
- `nc_min_evidence` = 3 (frozen)
- NC-08B 130 evidence records (read-only, MD5 verified)
- C.1/C.3 original trial data (unchanged)

---

## 4. Task Construction

**Total Tasks:** 60 (new IDs, no C.1/C.3 reuse)

| Category | N | Description | Hard Negative |
|----------|---|-------------|---------------|
| code_locator_hard | 10 | Locate code symbols (search_files vs terminal) | ✅ Yes |
| code_inspect | 10 | Inspect code files for function definitions | No |
| file_search | 10 | Search for keywords in files | No |
| file_read | 10 | Read file contents | No |
| terminal_safe | 10 | Execute safe Python commands | No |
| exact_answer | 10 | Get system information | ✅ Yes (3/10) |

**Hard Negative Definition:**
- Tasks where both actions seem reasonable
- But historical evidence shows different completion rates
- Designed to test if NC chooses evidence-supported action

---

## 5. A/B Assignment

| Group | N | Assignment Method |
|-------|---|-------------------|
| Original | 34 | Hash-based deterministic (nc_ratio=0.5) |
| NC V2 | 26 | Hash-based deterministic (nc_ratio=0.5) |

Assignment determined BEFORE execution. Policy frozen throughout trial.

---

## 6. Outcome Results

### Overall
| Group | N | TC | ES |
|-------|---|-----|-----|
| Original | 34 | 34/34 (100%) | 34/34 (100%) |
| NC V2 | 26 | 26/26 (100%) | 26/26 (100%) |

### Per-Category
| Category | Original TC | NC V2 TC | NC Direct | NC Abstain |
|----------|-------------|----------|-----------|------------|
| code_locator_hard | 6/6 (100%) | 4/4 (100%) | 4 | 0 ✅ |
| code_inspect | 7/7 (100%) | 3/3 (100%) | 3 | 0 ✅ |
| file_search | 7/7 (100%) | 3/3 (100%) | 3 | 0 ✅ |
| file_read | 3/3 (100%) | 7/7 (100%) | 7 | 0 ✅ |
| terminal_safe | 7/7 (100%) | 3/3 (100%) | 3 | 0 ✅ |
| exact_answer | 4/4 (100%) | 6/6 (100%) | 6 | 0 ✅ |
| **Total** | **34/34** | **26/26** | **26** | **0** |

### Hard Negative Focus
| Subset | Original | NC V2 | Δ |
|--------|----------|-------|---|
| Total HN | 6/6 (100%) | 7/7 (100%) | 0pp |
| code_locator_hard | 6/6 (100%) | 4/4 (100%) | 0pp |
| exact_answer (HN) | 0/0 | 3/3 (100%) | — |

---

## 7. Code Inspect/Locator Analysis

### Before Fix (C.1/C.3)
```
Situation: "定位函数 find_symbol_N 在源码中的位置"
Classifier → None (no match)
Evidence lookup → Failed
Result: ABSTAIN (0 NC direct)
```

### After Fix (C.4)
```
Situation: "定位函数 find_symbol_N 在源码中的位置"
Classifier → ('code_locator', 'search_files') ✅
Evidence lookup → ('code_locator', 'search_files'): t=5, f=0, rate=1.0
Ranking → search_files recommended
Result: NC DIRECT with conf=1.0, ev=5 ✅
```

**Improvement:** NC went from 0/10 direct (C.1) → 1/5 direct (C.3) → **4/4 direct (C.4)**

---

## 8. Failure Taxonomy

| Code | Category | Count | Description |
|------|----------|-------|-------------|
| F1 | Intent/Situation Error | 0 | — |
| F2 | Candidate Generation Error | 0 | — |
| F3 | Evidence Retrieval Error | 0 | **FIXED** ✅ |
| F4 | Evidence Quality Error | 0 | — |
| F5 | Ranking Error | 0 | — |
| F6 | Confidence Error | 0 | — |
| F7 | Action Execution Error | 0 | **FIXED** ✅ |
| F8 | Verifier Error | 0 | — |
| F9 | Environment/Task Design Error | 0 | — |
| F10 | Other | 0 | — |

**Zero failures.** All previous failure modes resolved.

---

## 9. Statistical Analysis

### Overall
- Original: 34/34 = 100%
- NC V2: 26/26 = 100%
- Difference: 0pp

### 95% Wilson Score Confidence Intervals
- Original TC: [89.9%, 100.0%]
- NC V2 TC: [87.1%, 100.0%]
- Difference: Cannot be computed (both 100%)

### Hard Negative Subgroup
- Original: 6/6 = 100%
- NC V2: 7/7 = 100%
- Difference: 0pp

### Interpretation
Tasks are too easy (all succeed). Cannot detect policy difference at 100% completion rates. The improvement is in **control acquisition** (NC now gets to act), not necessarily in **completion rate improvement**.

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

13 failures are historical baseline (same as all previous trials).

---

## 11. Data Integrity

| Check | Result |
|-------|--------|
| NC-08B 130 evidence unchanged | ✅ PASS (MD5 verified) |
| C.1 original data unchanged | ✅ PASS |
| C.3 original data unchanged | ✅ PASS |
| No simulated/mock data | ✅ PASS |
| Policy frozen during trial | ✅ PASS |
| Assignment immutable | ✅ PASS |
| Outcomes isolated | ✅ PASS |
| No online learning | ✅ PASS |

**NC-08B Evidence Integrity:**
```
real_completion_observations.jsonl: 4c99f3a39f8f2d39091ca91ac70b3e5d (unchanged)
situation_observations.jsonl:       fdba43950658375cedaacfc1af76366b (unchanged)
```

---

## 12. Limitations

1. **Sample Size:** N=60 total (34+26) is moderate but adequate for directionality.
2. **Task Difficulty:** All tasks completed successfully by both groups. No natural failure mode.
3. **No Discrimination:** Both policies achieve 100% on these tasks. Cannot claim superiority.
4. **Hard Negative Design:** While designed to be discriminative, the sandbox environment makes both actions succeed.

---

## 13. Final Verdict

### `PROMISING_INCONCLUSIVE`

**What's Proven:**
1. ✅ Policy V2 fix is correct and working
2. ✅ Evidence retrieval bug is resolved (F3 fixed)
3. ✅ NC now achieves 100% direct control (was 38% in C.3)
4. ✅ Hard negative tasks properly classified and executed
5. ✅ No new regressions introduced

**What's NOT Proven:**
1. ⚠️ NC is statistically better than Original (both at 100%)
2. ⚠️ Policy improvement translates to real-world advantage
3. ⚠️ NC would outperform Original on harder tasks

**Key Achievement:**
- NC policy control rate: C.1 (0%) → C.3 (38%) → C.4 (100%)
- This proves the fix enables NC to actually participate in decision-making

**Next Steps (Pending Commander Approval):**
1. Design tasks with genuine failure modes (not just easy success)
2. Introduce time pressure or resource constraints
3. Add adversarial tasks where Original might fail
4. Consider human-evaluated quality metrics beyond binary completion
5. Do NOT enter canary/production without further validation

---

*Independent validation complete. C.1 and C.3 data preserved. NC-08B evidence untouched.*
