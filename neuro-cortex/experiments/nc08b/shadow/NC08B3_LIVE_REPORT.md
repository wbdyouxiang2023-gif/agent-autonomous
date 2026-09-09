# NC-08B.3 — Completion Ranking Shadow Validation (Live Wiring)

**Date:** 2026-09-09
**Status:** LIVE SHADOW — wired to remote WSL Hermes server, shadow-only verified

---

## ARCHITECTURE

```
ARCHITECTURE_VERDICT = SAFE_TO_WIRE (from prior audit)
LIVE_WIRING          = DONE

Wired into: /home/user/workspace/agent-autonomous/neuro-cortex/server.py
  POST /chat → cortex.process(msg)      ← Original Policy (decides actual action)
            → event.decision.selected_action  (final, post NC-06)
            → [NC-08B.3 SHADOW] ShadowAdapter.recommend(sit, cands, orig)
                 ├─ situation = perception.intent, upgraded via IntentExtractor
                 │    when mock intent is generic (general/review/unknown)
                 ├─ candidates widened to real tool space when mock gives
                 │    degenerate [respond, noop]
                 ├─ NC recommendation → shadow_log.jsonl ONLY
                 └─ assert actual_action == original_action
            → resp["action"] = selected_action (unchanged)
```

Deployed files (uploaded, not git-pushed):
- `server.py` (+NC-08B.3 shadow block, NC_SHADOW_MODE flag)
- `experiments/nc08b/shadow/shadow_adapter.py`
- `experiments/nc08b/real_completion_observations.jsonl` (evidence, read-only)
- `experiments/nc08b/situation_observations.jsonl` (evidence, read-only)
- `shadow_observer.py` (existing NC-06 dep, uploaded for server boot)
- `experiment/observation_logger.py` (existing dep, uploaded for server boot)

## SMOKE TEST (3 turns)

```
SMOKE_TEST        = 3 real turns (search symbol / read file / check disk)
SMOKE_TEST_RESULT = PASS
  1. Hermes responds normally ✅ (intent=general/review, action=respond)
  2. Original Action executes ✅ (respond, success=true)
  3. NC recommendation recorded ✅ (shadow_log 3 records)
  4. actual_action unchanged ✅ (assert passed)
  5. Outcome produced ✅ (evaluation=correct)
  6. Shadow record written ✅
  7. NC failure isolation ✅ (server kept running, no blocking)
```

Iteration fix during smoke: candidates from mock decision were dicts
(`{'id':'noop',...}`) — fixed extraction (str/dict/obj handling);
situation was generic (general/review) — upgraded via IntentExtractor;
candidates degenerate (respond/noop) — widened to real tool space.
All fixes shadow-only, original decision path untouched.

## LIVE SHADOW SAMPLE (25 turns)

```
LIVE_SHADOW_TASKS            = 25
NC_RECOMMENDATION_AVAILABLE  = 10 (file_read×5, file_search×5 — have evidence)
NC_VS_ORIGINAL_DISAGREEMENT  = 25
BOTH_SAME                    = 0
BOTH_DIFFERENT               = 25
NC_FAILURES                  = 0

BY_SITUATION:
  file_read ×5 | code_search ×5 | disk_check ×5 | file_search ×5 | general ×5
  (IntentExtractor upgraded mock perception intent → real task situations)

EVIDENCE-DRIVEN RECOMMENDATIONS:
  file_read   → nc=read_file     (completion evidence 1.0)  ✅
  file_search → nc=search_files  (completion evidence 1.0)  ✅
  code_search → nc=read_file     (no exact evidence → default order, scores None)
  disk_check  → nc=read_file     (no exact evidence → default order, scores None)
  general     → nc=read_file     (no evidence → default order, scores None)

COMPLETION_KNOWN      = 10 (evidence-backed situations)
COMPLETION_UNKNOWN    = 15 (no exact evidence — scores None, no guessing)
ORIGINAL_COMPLETION_RATE = N/A (original=respond, no respond completion evidence)
NC_SHADOW_OBSERVATIONAL_ALIGNMENT = 2/2 on evidence-backed situations
  (file_read→read_file, file_search→search_files both match real completion)

ACTUAL_ACTION_CHANGED_BY_NC = NO (25/25 assert + verified)
ORIGINAL_ACTION_INTERRUPTED_BY_NC = NO (server continuous, 0 NC failures)
```

## SAFETY

```
ACTUAL_ACTION_CHANGED_BY_NC = NO
  - 28/28 shadow records (3 smoke + 25 live) passed
    `assert event.decision.selected_action == original_action`
  - NC_SHADOW_MODE=OFF verified earlier: recommend()=None, zero side effects
  - Original policy code path untouched (only additive shadow block)
PRODUCTION_POLICY_CHANGED   = NO（仅新增 shadow 接线块，未改 Original 决策）
NC_CONTROLS_EXECUTOR        = NO
HISTORICAL_DATA_MODIFIED    = NO（130 observations read-only, MD5 verified）
PUSHED                      = NO（文件经 /upload 部署，未 git push）
MASTER_DELETED              = NO
BACKUP_TAGS_DELETED         = NO
```

## TEST

```
RELATED_TESTS   = 70/70 passed (test_event + nc08a*)
FULL_TEST       = 572 passed / 18 failed / 8 skipped
BASELINE_FAILURES = 18 (unchanged: test_creators 9 + nested-regression 9)
NEW_REGRESSIONS = NO
```

## LIVE SHADOW VERIFICATION (ad-hoc, fresh)

12/12 PASS (tempfile hermes-verify script):
- 25 records, all shadow_only=true
- 5 situations ×5 each (IntentExtractor upgraded)
- original always respond; NC differs in all 25 (disagreement)
- evidence-driven: file_read→read_file, file_search→search_files
- scores: evidence→1.0, no-evidence→None (no guessing)
- candidate_actions always include original_action

## FINAL_VERDICT

```
SHADOW_EVIDENCE_READY_FOR_NC08C
```

### Honest limitations
1. Remote server uses **MockPerception/MockDecision** — original action is
   always `respond`, candidates are mock. NC recommendations cannot yet be
   compared against a real multi-tool original policy.
2. NC_RECOMMENDATION_AVAILABLE=10/25 — exact situation×action evidence only
   covers file_read/file_search (code_search/disk_check evidence exists in
   data but under different situation keys: code_search has no read_file
   evidence, disk_check evidence is (disk_check,terminal) etc.). No guessing
   applied where evidence missing — by design.
3. NC-recommended action never executed — observational alignment only,
   no causal claim, no superiority claim.

### What this proves
NeuroCortex completion-based ranking now runs **live inside the remote WSL
Hermes server** in shadow mode: it observes real tasks, computes
evidence-driven recommendations (file_read→read_file, file_search→
search_files with completion=1.0), records independently, and **never
alters the actual action** (asserted 28/28). This is the NC-08C precursor.
