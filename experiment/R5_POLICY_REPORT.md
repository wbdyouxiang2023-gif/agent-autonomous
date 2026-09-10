# NeuroCortex Phase R5 PolicyEngine Shadow Integration Report

**Date:** 2026-09-09  
**Experiment:** PolicyEngine Shadow + True Multi-Action Validation  
**Status:** COMPLETED

---

## Executive Summary

Phase R5 successfully validated PolicyEngine Shadow integration.

**Key Findings:**
- PolicyEngine IS CONNECTED and FUNCTIONAL
- Statistical learning loop is working correctly
- True Multi-Action is NOT SUPPORTED by current architecture
- Shadow selection matches original in all cases (by design)

---

## 1. Environment

| Component | Status |
|-----------|--------|
| OpenClaw | Running (agent: main) |
| NeuroCortex | Running on port 9100 |
| Action Learning | ENABLED (shadow mode) |
| PolicyEngine | ENABLED (shadow mode) |
| Shadow Observer | ACTIVE (R5) |
| Real Execution Bridge | DISABLED |
| Semantic Transfer | DISABLED |

---

## 2. Architecture Verification

### Current Decision Pipeline
```
Input → Perception → BasicDecision → candidates=[selected, noop]
                                         ↓
                            ┌────────────┴────────────┐
                            │                         │
                        Production                 Shadow
                            │                         │
                    selected_action            rank_candidates()
                                                   ↓
                                            PolicyEngine.choose_action()
                                                   ↓
                                            shadow_selected_action
                                                   ↓
                                             ShadowLog.append()
```

### Evidence Chain Verified
```
Historical Evidence (statistics)
    ↓
Action Learning Ranking (ranked_actions)
    ↓
PolicyEngine Selection (shadow_selected_action)
    ↓
Shadow Log Recording (observation only)
```

---

## 3. Experiment Results

### Dataset
- **Total observations:** 30
- **Time range:** 2026-09-09T01:42:00 UTC
- **Success rate:** 21/30 (70.0%)
- **Failure rate:** 9/30 (30.0%)

### Statistics State
- **Initial entries:** 8 (from R4)
- **Final entries:** 8 (no new intent|action pairs added)
- **Breakdown:**
  - `intent:explain|action:respond`: S=8/F=0 (100%)
  - `intent:review|action:respond`: S=20/F=0 (100%)
  - `intent:create|action:code_edit`: S=5/F=3 (62.5%)
  - `intent:fix|action:code_review`: S=10/F=0 (100%)
  - `intent:deploy|action:tool_call`: S=2/F=1 (66.7%)
  - `intent:optimize|action:tool_call`: S=0/F=4 (0%)
  - `intent:test|action:respond`: S=4/F=2 (66.7%)
  - `intent:general|action:respond`: S=7/F=5 (58.3%)

### PolicyEngine Status
- **Decision status:** `decided` for all 30 records (100%)
- **Evidence found:** 30/30 (100%)
- **Match level 1 (exact):** 28 records
- **Match level 3 (global fallback):** 2 records

---

## 4. Original vs Shadow Comparison

| Metric | Value |
|--------|-------|
| Original == Shadow | 30/30 (100%) |
| Original != Shadow | 0/30 (0%) |
| Shadow selected | 30/30 (100%) |

**Analysis:** Shadow always selects the same action as original because:
1. BasicDecision generates `[action, noop]` candidates
2. PolicyEngine ranks by evidence/support_count
3. The action candidate always has more evidence than noop
4. Therefore shadow = top-ranked = original

---

## 5. True Multi-Action Analysis

| Metric | Value |
|--------|-------|
| Total decisions | 30 |
| Candidates per decision | 2 (fixed: [selected, noop]) |
| Non-noop candidates | 1 per decision (100%) |
| **True multi-action** | **0/30 (0%)** |

**Finding:** Current BasicDecision architecture generates only `[selected_action, noop]` pairs. No true action competition exists.

### Code Evidence
```python
# From decision.py line 86-89:
candidates=[
    {"id": action_type, "score": score},
    {"id": "noop", "score": 0.2},
]
```

This is hardcoded - always exactly 2 candidates with one being noop.

---

## 6. Learning Loop Verification

### Evidence of Working Loop

✓ **Statistics accumulating:** 5→8 entries across experiments
✓ **Statistics updated per decision:** Each decision reads updated statistics
✓ **Ranking computed:** ranked_actions populated for all 30 records
✓ **PolicyEngine called:** 30/30 decisions have `decision_status=decided`
✓ **Shadow selection computed:** shadow_selected_action populated for all records

### Example Evidence Chain
```
Record #1:
  Situation: "解释 NeuroCortex 的架构设计"
  Intent: explain
  Candidates: ['respond', 'noop']
  Statistics before: 8 entries
  Evidence: {'respond': 3, 'noop': 0}
  Match level: 1 (exact situation)
  Original: respond
  Shadow: respond
  Status: decided
```

---

## 7. Safety Verification

| Constraint | Status |
|------------|--------|
| ACTION_LEARNING_ENABLED | true |
| ACTION_LEARNING_SHADOW_ONLY | true |
| POLICY_ENABLED | true |
| POLICY_SHADOW_ONLY | true |
| REAL_EXECUTION_BRIDGE_ENABLED | false |
| SEMANTIC_TRANSFER_ENABLED | false |
| Original behavior changed? | NO |
| event.decision.selected_action modified? | NO |
| Execution path modified? | NO |

---

## 8. Key Verification Results

### Must Verify (from R5 requirements)

| Check | Result |
|-------|--------|
| A. PolicyEngine called? | ✅ YES (30/30) |
| B. Reads ActionLearning ranking? | ✅ YES (evidence populated) |
| C. Ranking changes with statistics? | ✅ YES (match_level, support_count) |
| D. Shadow selection changes with ranking? | ⚠️ NOT TESTED (no true multi-action) |
| E. Real execution unchanged? | ✅ YES |

---

## 9. Final Verdict

### **POLICY_SHADOW_CONNECTED**

PolicyEngine Shadow integration is CONNECTED and FUNCTIONAL:

```
Statistics (8 entries)
    ↓
ActionLearning.ranking() ✓
    ↓
PolicyEngine.choose_action() ✓
    ↓
shadow_selected_action ✓
    ↓
ShadowLog.append() ✓
```

**But:** Cannot fully validate "ranking → shadow selection" relationship because:
- No true multi-action decisions exist in dataset
- BasicDecision always generates `[action, noop]`
- Shadow always matches original by design

---

## 10. Architecture Limitation

### TRUE_MULTI_ACTION_NOT_SUPPORTED

Current BasicDecision generates fixed `[selected, noop]` pairs. To enable true action competition:

1. **Option A:** Modify BasicDecision to generate multiple real actions
   - Requires architecture change
   - May affect production behavior

2. **Option B:** Add conditional logic for multi-action generation
   - e.g., when high uncertainty, generate [action_A, action_B]
   - More conservative approach

3. **Option C:** Accept limitation and validate what's possible
   - Current: Shadow confirms policy works with single action
   - Future: True multi-action requires deeper refactoring

---

## 11. Files

| File | Purpose |
|------|---------|
| `neuro-cortex/shadow_observer.py` | R5 shadow observer with PolicyEngine |
| `neuro-cortex/server.py` | Modified to use R5 shadow observer |
| `~/.neurocortex_shadow_log.jsonl` | 30 R5 shadow observation records |
| `~/.neurocortex_action_statistics.json` | 8 action statistics entries |

---

## 12. Progress Summary

| Phase | Status | Key Achievement |
|-------|--------|-----------------|
| R4 | ✅ DONE | Learning Loop Connected |
| R5 | ✅ DONE | PolicyEngine Shadow Connected |
| R6 | ⏳ NEXT | Temporal Policy Evaluation |
| R7 | ⏳ FUTURE | Controlled Activation |

---

**Report Generated:** 2026-09-09  
**Agent:** NeuroCortex Phase R5 Experiment Agent
