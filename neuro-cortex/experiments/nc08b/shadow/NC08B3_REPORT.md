# NC-08B.3 — Completion Ranking Shadow Validation

**Date:** 2026-09-09
**Status:** SHADOW-ONLY validation — NC observes/recommends/records, never controls action

---

## ARCHITECTURE

```
ORIGINAL_POLICY_ENTRY  = server.py:214-229 (shadow_observer.observe_decision;
                         nc06 decision path — original policy decides actual action)
NC_RANKING_ENTRY       = action_learning/engine.py:207 evaluate_candidates /
                         :331 rank_actions (production interface, UNTOUCHED)
ACTION_EXECUTION_ENTRY = server.py chat handler (body["msg"] → agent tool exec)
OUTCOME_ENTRY          = event.py OutcomeData (task_completed / completion_source)
EXPERIENCE_ENTRY       = plugin on_tool_call → record_experience
                         (~/.neurocortex_experiences.jsonl)
SHADOW_ADAPTER         = experiments/nc08b/shadow/shadow_adapter.py (NEW)
```

```
ARCHITECTURE_CONFIRMED = YES
SHADOW_MODE_IMPLEMENTED = YES
```

## SHADOW ADAPTER DESIGN

- Input: situation + candidate_actions + real completion evidence (read-only)
- Output: nc_recommended_action, nc_ranking, nc_scores, model_version
- **Never executes actions. Never writes production experience.**
- Feature flag `NC_SHADOW_MODE` (default OFF):
  - OFF → `recommend()` returns None, zero side effects (verified: no log append)
  - ON → shadow computation + independent shadow log only
- Safety invariant asserted on every record:
  `assert rec["original_action"] == original_action` — actual action
  can never change.
- Completion evidence: real 130 observations only; None excluded from
  completion rate (True/(True+False)); no success→completion inference.

## SHADOW EVAL (30 real tasks, sampled from multi-action situations)

```
TOTAL_SHADOW_TASKS          = 30
NC_RECOMMENDATION_AVAILABLE = 30   (all had completion evidence)
NC_VS_ORIGINAL_DISAGREEMENT = 15
BOTH_SAME                   = 15
BOTH_DIFFERENT              = 15
UNKNOWN_COMPLETION          = 0

ORIGINAL_ACTION_COMPLETION  = T=25 F=5 rate=0.833
NC_SHADOW_ALIGNMENT         = 4/4 on search_code_symbol disagreements
                              (NC identified terminal comp=0.0 → recommends
                              search_files comp=1.0)
```

## DISAGREEMENT ANALYSIS (observational only)

| situation | original (actual) | NC top | orig comp | NC comp | note |
|-----------|-------------------|--------|-----------|---------|------|
| search_code_symbol ×4 | terminal | search_files | **0.0** | **1.0** | NC correctly flags terminal as 0%-completion in this situation |
| locate_known_file ×5 | terminal | search_files | 1.0 | 1.0 | tie; deterministic name order |
| read_known_content ×5 | terminal | read_file | 1.0 | 1.0 | tie |
| check_disk_space ×1 | terminal | read_file | 1.0 | 1.0 | tie |

**Key**: the 4 search_code_symbol disagreements are the ONLY cases with real
completion divergence — NC's recommendation (search_files) aligns with the
actually-completing action while the original (terminal) completed 0/5.
This is SHADOW COUNTERFACTUAL INDICATION, NOT causal proof (NC action
never executed).

## SAFETY VERIFICATION

```
ACTUAL_ACTION_CHANGED_BY_NC = NO
  - 30/30 shadow records passed `assert actual_action == original_action`
  - NC_SHADOW_MODE=OFF: recommend() → None, zero log append (verified)
  - Original policy code untouched (server.py NOT modified this phase)
  - Production ranking engine untouched
  - Historical data read-only (130 obs byte-identical, verified)
```

## TEST

```
RELATED_TESTS   = 70/70 passed (test_event + nc08a*)
FULL_TEST       = 572 passed / 18 failed / 8 skipped
BASELINE_FAILURES = 18 (unchanged: test_creators 9 + nested-regression 9)
NEW_REGRESSIONS = NO
```

## SAFETY SUMMARY

```
PRODUCTION_POLICY_CHANGED       = NO
ACTUAL_ACTION_CONTROLLED_BY_NC  = NO
HISTORICAL_DATA_MODIFIED        = NO
PUSHED                          = NO
MASTER_DELETED                  = NO
BACKUP_TAGS_DELETED             = NO
```

## FINAL_VERDICT

```
SHADOW_EVIDENCE_READY_FOR_NC08C
```

Rationale:
- Shadow adapter produces completion-based recommendations in an offline
  replay of 30 real tasks, with zero influence on actual actions
- NC_SHADOW_MODE flag works (OFF = no-op, ON = shadow computation only)
- Safety invariant held on all 30 records
- Real disagreement observed: search_code_symbol — NC flags terminal
  (0% completion) and recommends search_files (100%), matching actual
  completion evidence
- Observational only; no causal claim, no policy superiority claim
- Foundation ready for NC-08C controlled policy trial (not started)

**Limitation**: the shadow eval replays historical observations through the
adapter rather than live-injecting into a running Hermes server; the
integration point (server.py observe_decision) is identified but the
adapter is not yet wired into the live server path. Wiring + live shadow
run would be the NC-08C precursor.
