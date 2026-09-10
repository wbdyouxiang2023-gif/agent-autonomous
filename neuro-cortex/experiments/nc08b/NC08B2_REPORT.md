# NC-08B.2 — Situation-level Ranking Validation

**Date:** 2026-09-09
**Status:** OFFLINE validation — no production change, no new execution

---

## DATA

```
OLD = 80 (unchanged) | NEW = 50 | TOTAL = 130
provenance ✓ experimental_action_control ✓ task_completed 3-state ✓
```

## PER-GROUP RESULTS

| GROUP | ACTION | EXEC_RATE | COMP_RATE | EXEC_RANK | COMP_RANK | EXEC_TOP | COMP_TOP | ACTUAL_BEST_COMP |
|-------|--------|-----------|-----------|-----------|-----------|----------|----------|------------------|
| check_disk_space | read_file | 1.000 | 1.000 | 1 | 1 | read_file | read_file | [read_file, terminal] TIE |
| | terminal | 1.000 | 1.000 | 2 | 2 | | | |
| get_python_version | read_file | 1.000 | 1.000 | 1 | 1 | read_file | read_file | [read_file, terminal] TIE |
| | terminal | 1.000 | 1.000 | 2 | 2 | | | |
| locate_known_file | search_files | 1.000 | 1.000 | 1 | 1 | search_files | search_files | [search_files, terminal] TIE |
| | terminal | 1.000 | 1.000 | 2 | 2 | | | |
| read_known_content | read_file | 1.000 | 1.000 | 1 | 1 | read_file | read_file | [read_file, terminal] TIE |
| | terminal | 1.000 | 1.000 | 2 | 2 | | | |
| **search_code_symbol** | **search_files** | **1.000** | **1.000** | **1** | **1** | search_files | **search_files** | **search_files** |
| | **terminal** | **1.000** | **0.000** | **2** | **2** | | | |

## SUMMARY

```
TOTAL_COMPARABLE_GROUPS = 5
RANKING_CHANGED_GROUPS  = 0  (top-1 unchanged)
RANKING_UNCHANGED_GROUPS= 5
EXECUTION_TIES          = 5  (exec model cannot distinguish ANY group)
COMPLETION_TIES         = 4  (4 groups both 1.000; G4 resolved 1.0 vs 0.0)
EXECUTION_ALIGNMENT     = 5/5 (via deterministic name tie-breaker, NOT evidence)
COMPLETION_ALIGNMENT    = 5/5 (G4 driven by real completion evidence)
```

## G4_RESULT (search_code_symbol)

```
search_files:  exec=1.000  comp=1.000
terminal:      exec=1.000  comp=0.000

Execution model: TIE (1.0 = 1.0) — CANNOT distinguish the two actions
Completion model: selects search_files (1.0 vs 0.0) — REAL distinction

✅ Verified: completion model selects search_files; exec model blind.
```

## KEY OBSERVATION (honest reporting)

- **All 5 groups are execution ties (1.000=1.000)** — the controlled
  experiment produced successful execution for both actions in every group.
  Execution-success ranking therefore provides ZERO situation-level
  discrimination in this dataset.
- The 5/5 EXECUTION_ALIGNMENT is **spurious**: it comes from the documented
  deterministic tie-breaker (action-name lexicographic order), NOT from
  evidence. When both actions tie at 1.000, exec alignment is a coin-flip
  artifact.
- **COMPLETION_ALIGNMENT 5/5 is meaningful only in G4**, where completion
  evidence (1.0 vs 0.0) resolves the tie that execution cannot.
- RANKING_CHANGED_GROUPS=0 is structural (top-1 unchanged by the
  tie-breaker), but the real signal is **tie → resolved**: completion
  model turns 5 execution ties into 4 ties + 1 resolved distinction.

## SCIENTIFIC VERDICT

```
MECHANISM_VALIDATED          = YES
  (completion rate True/(True+False) computed per situation×action,
   None excluded, deterministic, reproducible)

RANKING_CHANGE_DETECTED      = PARTIAL
  (top-1 unchanged; but execution ties resolved by completion evidence —
   the change appears as tie→resolution, G4: exec 1.0=1.0 → comp 1.0 vs 0.0)

OUTCOME_ALIGNMENT_OBSERVED   = YES
  (G4: completion model uniquely identifies search_files as the
   actually-completing action; execution model cannot)

POLICY_SUPERIORITY_VALIDATED = NO
  (no NC-08C controlled policy trial; observational only)
```

## TEST

```
RELATED_TESTS   = 70/70 passed (test_event + nc08a*)
FULL_TEST       = 572 passed / 18 failed / 8 skipped
BASELINE_FAILURES = 18 (unchanged: test_creators 9 + nested-regression 9)
NEW_REGRESSIONS = NO
```

## SAFETY

```
PRODUCTION_POLICY_CHANGED   = NO
REAL_ACTION_EXECUTED        = NO (offline read-only)
HISTORICAL_DATA_MODIFIED    = NO (130 obs untouched)
PUSHED                      = NO
MASTER_DELETED              = NO
BACKUP_TAGS_DELETED         = NO
```

## FINAL_VERDICT

```
COMPLETION_RANKING_OUTCOME_ALIGNMENT_OBSERVED
```

**Honest limitation:** with only 5 comparable groups, all execution-tied,
the evidence is concentrated in G4. Completion-based ranking demonstrates
the mechanism works and aligns with real completion in the one group where
completion differs. This is NOT statistical proof and NOT policy
superiority — it is observational alignment of the mechanism.

**Next (NOT started):** NC-08C controlled policy trial would need more
groups with varied completion outcomes to claim superiority.
