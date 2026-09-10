# NC-08B — Completion-based Action Learning (Offline Experiment Report)

**Date:** 2026-09-09
**Status:** OFFLINE EXPERIMENT — no production change
**Data:** 80 real observations (provenance=real_agent_execution)

---

## DATA

```
TOTAL_OBSERVATIONS = 80
TRUE              = 50
FALSE             = 25
UNKNOWN           = 5
VALID_LABELS      = 75
```

Provenance audit: all 80 = `real_agent_execution`, no synthetic/hypothetical,
no success→completion inference, no action-name hardcoding (every action has
mixed completion states), SUCCESS_WITHOUT_COMPLETION = 15.

## ACTION STATISTICS

| action | n | exec_ok | exec_rate | tc_T | tc_F | tc_N | completion_rate |
|--------|---|---------|-----------|------|------|------|-----------------|
| read_file | 10 | 5 | 0.500 | 5 | 5 | 0 | 0.500 |
| search_files | 15 | 15 | 1.000 | 10 | 5 | 0 | 0.667 |
| terminal | 40 | 35 | 0.875 | 25 | 10 | 5 | 0.714 |
| write_file | 15 | 15 | 1.000 | 10 | 5 | 0 | 0.667 |

Note: search_files and write_file have perfect execution success (1.000) but
lower completion (0.667) — the 15 "success without completion" cases.

## RANKING

```
MODEL A (execution_success):
  1. search_files (1.000)
  2. write_file   (1.000)
  3. terminal     (0.875)
  4. read_file    (0.500)

MODEL B (task_completion):
  1. terminal     (0.714)
  2. search_files (0.667)
  3. write_file   (0.667)
  4. read_file    (0.500)

COMPARABLE_GROUPS = 0
RANKING_CHANGED   = 0 (within-group, no comparable groups exist)
RANKING_UNCHANGED = 0
```

**Global ranking changed:** Model A top = search_files/write_file (exec=1.0);
Model B top = terminal (comp=0.714). Execution-based ranking over-ranks
search_files/write_file whose true completion is only 0.667.

## SAFE BUT INEFFECTIVE

```
HIGH_EXECUTION_LOW_COMPLETION_ACTIONS:
  search_files  exec=1.000  comp=0.667  gap=0.333  n=15
  write_file    exec=1.000  comp=0.667  gap=0.333  n=15
```

Data-driven (no action-name heuristic): these actions execute without error
but fail to complete the task (ghost-file search/append scenarios). This is
real evidence that execution_success overstates value.

## REPLAY

```
OBSERVATIONAL_REPLAY = PASS (limited)
COUNTERFACTUAL_LIMITATION = No cross-execution of different actions within
  the same situation exists in the data; replay is observational, not causal.
  Cannot claim "choosing terminal would have completed more tasks".
```

## SCIENTIFIC VERDICT

```
COMPLETION_SIGNAL_USABLE          = YES (75 valid labels, 3-state signal,
                                    meaningful distribution, no pollution)
RANKING_CHANGE_DETECTED           = YES (global: Model A top ≠ Model B top;
                                    within-group: NOT TESTABLE, 0 comparable groups)
OUTCOME_ALIGNMENT_VALIDATED       = PARTIAL (completion rate corrects the
                                    over-ranking of exec=1.0/comp=0.667 actions;
                                    no situation-level causal proof)
POLICY_SUPERIORITY_VALIDATED      = NO (no controlled real policy trial)
```

## TEST

```
RELATED_TESTS   = 70/70 passed (test_event + nc08a*)
FULL_TEST       = 572 passed / 18 failed / 8 skipped
BASELINE_FAILURES = 18 (test_creators 9 + nested-regression 9, unchanged)
NEW_REGRESSIONS = NO
```

## SAFETY

```
PRODUCTION_POLICY_CHANGED   = NO
REAL_ACTION_EXECUTED        = NO (offline read-only)
HISTORICAL_DATA_MODIFIED    = NO
PUSHED                      = NO
MASTER_DELETED              = NO
BACKUP_TAGS_DELETED         = NO
```

## FINAL_VERDICT

```
COMPLETION_RANKING_CHANGE_DETECTED
```

Rationale:
- completion signal is usable (75 valid labels, no pollution)
- completion-based ranking differs from execution-based ranking at the
  global level (top action changes)
- real "safe but ineffective" pattern detected (exec=1.0 but comp=0.667)
- NOT POLICY_SUPERIORITY — no controlled trial, no situation-level
  counterfactual, 0 comparable within-group structures in current data

**Limitation note:** current data has 1 action per task_type (no within-
situation action alternatives), so ranking change is demonstrated globally,
not per-situation. NC-08C controlled trial needs multi-action situations.
