# NC-09 Learning Core Freeze

**Date:** 2026-09-09  
**Status:** FROZEN  
**Gate:** PASS

---

## 1. Freeze Trigger

NC-09 FINAL independent validation passed all criteria:

- 3/3 groups completed with correct adaptations
- REAL outcome → learning → ranking change → action adaptation demonstrated
- Zero negative transfer between families
- All regression tests pass (41 passed)
- NC-08B evidence MD5 unchanged

---

## 2. Frozen Components

### 2.1 Situation → Learning Key Architecture
```python
# family:<CANONICAL_FAMILY>|action:<action_type>
# Canonical families defined in classifier_v4.py
TASK_TYPE_TO_FAMILY = {
    "code_locator": "CODE_LOCATION",
    "code_search": "CODE_LOCATION",
    "file_search": "FILE_SEARCH",
    "file_read": "FILE_READ",
    "code_inspect": "CODE_INSPECTION",
    "code_check": "CODE_QUALITY",
    "terminal": "GENERIC_COMMAND",
    # ... etc
}
```

### 2.2 Outcome → Learning Pipeline
- `record_outcome()` derives `effective_success` from execution + task completion
- Partial failures (success=True, task_completion=False) treated as failures
- Task completion recorded separately for transparency

### 2.3 Learning → Ranking Pipeline
- `rank_actions()` uses situation-specific statistics with canonical families
- No-evidence actions use prior rate when failed actions exist in pool
- Match-level penalties applied (L1=1.0, L2=0.9, L3=0.7, L4=0.5)

### 2.4 Ranking → Action Adaptation Interface
- Bridge returns ranked candidates in non-shadow mode
- `shadow_only=False` enables actual reordering

### 2.5 Safety / Abstention Boundary
- `enabled=False` → passthrough (no learning)
- `outcome.success=None` → ignored (no learning)
- Engine exceptions → candidates returned unchanged

---

## 3. Validated Configuration

```python
ActionLearningConfig(
    enabled=True,
    statistics_path="<isolated_path>",
    shadow_only=False,
    situation_evidence_threshold=1,
    smoothing_alpha=1,
    smoothing_beta=1,
    confidence_k=5,
    prior_rate=0.5,
    history_weight=0.6,
    semantic_weight=0.3,
    recency_weight=0.1,
)
```

---

## 4. Proven Capabilities

| Capability | Evidence |
|------------|----------|
| Success reinforcement | Group A: search_files reinforced in CODE_LOCATION |
| Failure suppression | Group B: terminal suppressed in FILE_READ |
| Cross-type generalization | code_locator + code_search share CODE_LOCATION |
| Family isolation | CODE_LOCATION ≠ FILE_READ ≠ CODE_INSPECTION |
| Causality traceable | experience_id → key → ranking change → action change |

---

## 5. Limitations

1. **Single-experience threshold**: Current threshold=1 means even one experience affects ranking
2. **Laplace smoothing floor**: Actions with only failures still score ~0.25-0.33, never reaching 0
3. **Static family mapping**: Families are hardcoded; no dynamic learning of family boundaries
4. **No semantic transfer**: Level 5.1 semantic transfer is OFF by default

---

## 6.禁止修改 (Unless Production Bug)

The following files are FROZEN:
- `src/neurocortex/action_learning/engine.py` (situation_key, record_outcome, _sort_ranked)
- `src/neurocortex/perception/classifier_v4.py` (TASK_TYPE_TO_FAMILY)
- `src/neurocortex/action_learning/schema.py` (ActionLearningSituation, ActionLearningOutcome)

Changes allowed ONLY for:
- Clear production-level bugs
- Performance fixes (no behavior changes)
- Documentation updates

---

**LEARNING_CORE = FROZEN**
