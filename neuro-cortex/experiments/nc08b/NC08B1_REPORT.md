# NC-08B.1 — Situation-Level Completion Evidence

**Date:** 2026-09-09
**Status:** Controlled real-data collection — situation-level comparable groups

---

## DATA

```
TOTAL_OBSERVATIONS = 130  (80 original + 50 new situation-level)
NEW_OBSERVATIONS   = 50   (controlled, experimental_action_control=true)

TRUE     = 95   (50 old + 45 new)
FALSE    = 30   (25 old + 5 new)
UNKNOWN  = 5    (5 old + 0 new)
```

New data audit: 50/50 provenance=`real_agent_execution`, 50/50
`experimental_action_control=true`, task_completed ∈ {True,False,None} valid.

## COMPARABLE_GROUPS (5 groups, each ≥2 actions × ≥5 valid labels)

| GROUP | TASK_TYPE | ACTION_A | A_VALID | A_COMP_RATE | ACTION_B | B_VALID | B_COMP_RATE |
|-------|-----------|----------|---------|-------------|----------|---------|-------------|
| G1 | locate_known_file | search_files | 5 | 1.000 | terminal | 5 | 1.000 |
| G2 | read_known_content | read_file | 5 | 1.000 | terminal | 5 | 1.000 |
| G3 | get_python_version | terminal | 5 | 1.000 | read_file | 5 | 1.000 |
| G4 | search_code_symbol | search_files | 5 | **1.000** | terminal | 5 | **0.000** |
| G5 | check_disk_space | terminal | 5 | 1.000 | read_file | 5 | 1.000 |

**KEY GROUP — G4 (search_code_symbol):**
- search_files (grep -r): exec=1.000, comp=**1.000** — reliably locates symbol
- terminal (find -exec grep -l): exec=1.000, comp=**0.000** — command ran
  successfully but produced no matching path output (execution OK, task
  NOT completed)

This is a REAL, data-driven "safe but ineffective" action within the SAME
situation — exactly the evidence NC-08B lacked.

```
REAL_AGENT_EXECUTION_CONFIRMED = YES
DATA_PROVENANCE_VALID          = YES
```

## EXPERIMENTAL FAIRNESS

- Same situation, same completion criteria, same verifier per group
- Only the action differs (forced via experimental_action_control=true)
- task_completed decided by independent verifier against real environment
  state (file existence, content match, version match, symbol presence)
- No synthetic/hypothetical data, no success→completion inference,
  no action-name→completion hardcoding

## TEST

```
RELATED_TESTS   = 70/70 passed (test_event + nc08a*)
FULL_TEST       = 572 passed / 18 failed / 8 skipped
NEW_REGRESSIONS = NO (18 failures unchanged baseline)
```

## SAFETY

```
PRODUCTION_POLICY_CHANGED   = NO
REAL_ACTION_EXECUTED        = controlled experiment only (sandbox)
HISTORICAL_DATA_MODIFIED    = NO (original 80 untouched)
PUSHED                      = NO
MASTER_DELETED              = NO
BACKUP_TAGS_DELETED         = NO
```

## FINAL_VERDICT

```
COMPARABLE_COMPLETION_EVIDENCE_READY
```

Rationale:
- 5 comparable groups now exist (was 0)
- Each group: 2 distinct actions × ≥5 valid completion labels
- G4 demonstrates same-situation action divergence (1.000 vs 0.000)
  driven purely by real verifier results
- Data provenance valid; controlled experiment marking explicit
- Foundation ready for situation-level execution-vs-completion ranking
  comparison (NC-08C later, per instructions — not started here)
