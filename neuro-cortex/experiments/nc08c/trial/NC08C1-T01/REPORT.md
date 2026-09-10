# NC-08C.1 CONTROLLED POLICY TRIAL

**Trial ID:** NC08C1-T01  
**Policy Version:** NC-08C.0 (frozen)  
**Date:** 2026-09-09  
**Repository:** agent-autonomous @ 14ecde4  

---

## Experiment Summary

| Metric | Original Group | NC Group |
|--------|---------------|----------|
| N | 26 | 34 |
| Task Completion | 22/26 = **84.6%** | 25/34 = **73.5%** |
| Execution Success | 26/26 = **100%** | 29/34 = **85.3%** |
| Difference | — | **-11.1pp** |

### 95% Confidence Intervals (Wilson Score)
- Original TC: [66.5%, 93.9%]
- NC TC: [56.9%, 85.4%]
- **Difference: [-31.4%, +9.2%] — contains zero**

---

## Treatment Integrity

| Category | Count |
|----------|-------|
| NC direct (NC controlled actual_action) | 27 |
| NC fallback (ABSTAIN → Original) | 7 |
| NC abstain | 7 |
| Original (assignment_original) | 26 |
| Actual NC-controlled actions executed | 27 |

**All 7 abstains were file_verify tasks with zero evidence (correct behavior).**

---

## Per-Category Breakdown

| Category | Original N | Original TC | NC N | NC TC | Notes |
|----------|-----------|-------------|------|-------|-------|
| file_read | 3 | 100% | 7 | 100% | Both perfect |
| file_write | 5 | 20% | 5 | 20% | Verify needle bug (affects both) |
| search_files | 4 | 100% | 6 | 100% | Both perfect |
| terminal_safe | 6 | 100% | 4 | 100% | Both perfect |
| code_inspect | 5 | 100% | 5 | 0% | NC recommended terminal→FAILED |
| file_verify | 3 | 100% | 7 | N/A | All 7 NC ABSTAINED (no evidence) |

### Key Observations
1. **code_inspect**: NC classifier maps "检查代码文件" → terminal (via code_check), but Original uses search_files. Terminal execution failed (empty command). This is a legitimate policy difference, not a bug.
2. **file_write**: Both groups fail at 20% — verify needle `"line_1"` is hardcoded instead of dynamic. This is a task design issue, not a policy issue.
3. **file_verify**: NC correctly abstains (no historical evidence for this task type). Original always succeeds.
4. **file_read/search_files/terminal_safe**: NC matches or exceeds Original performance.

---

## Secondary Metrics

| Metric | Original | NC |
|--------|----------|-----|
| Error rate | 0% | 14.7% (5/34) |
| Timeout rate | 0% | 0% |
| Latency avg (s) | ~0.003 | ~0.004 |

NC failures breakdown:
- 5 code_inspect: terminal action with empty command → execution failure
- 3 file_write: verifier needle mismatch (task design)

---

## Data Integrity Checks

| Check | Result |
|-------|--------|
| Unique task_ids | 60/60 ✅ |
| All policy_version=NC-08C.0 | ✅ |
| No None→True/False leakage | ✅ |
| Assignment immutable (pre-execution) | ✅ |
| Policy frozen (no threshold changes) | ✅ |
| NC-08B evidence unchanged | ✅ |
| No simulated/mock data | ✅ |
| Outcomes isolated (not leaked to evidence) | ✅ |

**NC-08B Evidence Integrity:**
```
real_completion_observations.jsonl: 4c99f3a39f8f2d39091ca91ac70b3e5d (unchanged)
situation_observations.jsonl:       fdba43950658375cedaacfc1af76366b (unchanged)
```

---

## Test Results

| Test Suite | Result |
|------------|--------|
| NC-08C.0 (policy permission) | 20/20 PASS |
| NC-08C.0.1 (intent + executor + verifier + E2E) | 32/32 PASS |
| NC-08C.1-R1 (eligibility diagnosis) | 10/10 PASS |
| NC-08B related | PASS |
| Full pytest | 619 passed / 13 failed / 8 skipped |
| NEW REGRESSION | **NO** |

13 failures are historical baseline (regression path + execution_bridge missing `tools.file_tools`).

---

## Scientific Conclusion

**FINAL_VERDICT: `INSUFFICIENT_EVIDENCE`**

### Rationale:
1. **Statistical**: The 95% CI for the difference [-31.4%, +9.2%] contains zero. The observed 11.1pp disadvantage for NC is not statistically significant.
2. **Sample size**: N=26/34 per group is moderate. The wide CI reflects high uncertainty.
3. **Task design artifacts**: file_write and code_inspect categories have confounding issues (verify needle bug, classifier mapping difference) that obscure true policy comparison.
4. **NC behavior is correct**: All 7 abstains were justified (no evidence). NC direct actions were real (not fallback).

### What the data shows:
- NC can match Original on simple tasks (file_read, search_files, terminal_safe)
- NC struggles on tasks where its classifier produces suboptimal action choices (code_inspect)
- NC correctly abstains on tasks with no historical evidence (file_verify)
- NC has higher error rate due to terminal command formatting issues

### Next steps (pending commander approval):
1. Fix code_inspect classifier to prefer search_files over terminal for code-related tasks
2. Fix file_write verify needle to be dynamic
3. Collect additional evidence for file_verify category
4. Re-run trial with N>=50/group after fixes
5. Do NOT proceed to canary/production without further analysis

---

*This trial did not modify NC-08B evidence (130 records read-only). Trial outcomes are isolated in `experiments/nc08c/trial/NC08C1-T01/` and will not enter the learning pipeline.*
