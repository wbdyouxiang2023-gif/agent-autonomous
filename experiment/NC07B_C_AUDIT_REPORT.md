# NC-07B-C: Outcome Utility / Policy Bias Audit Report

**Date**: 2026-09-09 13:00:00
**Verdict**: `LEARNING_OBJECTIVE_MISALIGNED`

---

## Executive Summary

Audit of NC Policy reveals systematic bias toward `respond` due to:
1. **Outcome schema incomplete**: No `task_completion` field
2. **Learning objective misaligned**: Optimizes `execution_success`, not task value
3. **Evidence accumulation bias**: `respond` has 122 global successes vs 21 local for `tool_call`

---

## A. Optimize Candidate Space Audit

### Generated Candidates (NC-07A-R1)
```
['tool_call', 'code_edit', 'respond']
```

| Action | raw_score | adjusted_score | support | match_level | evidence_scope |
|--------|-----------|----------------|---------|-------------|----------------|
| respond | 0.6044 | 0.4230 | 122 | L3 | global |
| tool_call | 0.3260 | 0.3260 | 21 | L1 | local |
| code_edit | 0.4552 | 0.3186 | 36 | L3 | global |

### Key Findings
- ✅ `respond` always in candidate space
- ✅ `tool_call` always in candidate space
- ⚠️ `code_review` NOT in optimize candidate space (by design)
- ⚠️ `code_edit` included but has lower adjusted_score than `respond`

---

## B. Ranking Objective Audit

### Code Path
```python
# engine.py:274-290
raw_score = (
    self._config.history_weight * hist_score      # 0.6 * success_rate
    + self._config.semantic_weight * semantic      # 0.3 * semantic (off)
    + self._config.recency_weight * recency        # 0.1 * recency_bonus
)
adjusted_score = raw_score * ml_penalty           # L1=1.0, L3=0.7
```

### What is Optimized?
**execution_success ONLY**

The `hist_score` is derived from:
```python
alpha = 1.0, beta = 1.0  # Laplace smoothing
hist_score = (success + alpha) / (support + alpha + beta)
```

This is purely **success rate** of execution. There is NO:
- `task_completion`
- `quality`
- `user_satisfaction`
- `value_delivered`

### Evidence
File: `neuro-cortex/src/neurocortex/action_learning/engine.py:425-435`
```python
def _history_evidence(self, stats):
    success = int(stats.get("success_count", 0))
    failure = int(stats.get("failure_count", 0))
    support = success + failure
    # ... Laplace smoothing ...
    hist_score = smoothed * confidence + prior_rate * (1.0 - confidence)
    return {"history_score": hist_score, ...}
```

---

## C. Outcome Schema Audit

### Current Schema
File: `neuro-cortex/src/neurocortex/action_learning/schema.py:45-55`
```python
@dataclass(frozen=True)
class ActionLearningOutcome:
    success: bool
    actual_outcome: str = ""
    observed_at: str = ""
```

### Missing Fields
| Field | Status | Impact |
|-------|--------|--------|
| `execution_success` | ✅ EXISTS | Primary signal |
| `task_completion` | ❌ MISSING | **ROOT CAUSE** |
| `failure` | ✅ EXISTS | Inverse of success |
| `latency` | ❌ MISSING | Not in learning signal |
| `cost` | ❌ MISSING | Not in learning signal |
| `quality` | ❌ MISSING | Not in learning signal |
| `noop` | ❌ MISSING | No way to detect |

### Verdict
**`TASK_COMPLETION_NOT_IN_LEARNING_SIGNAL`**

---

## D. Counterfactual Audit

### Using NC-07B-A v2 Data

**Current Policy (execution_success only):**
- `respond`: 95% success (always "succeeds" because no execution)
- `tool_call`: 50% success (actually attempts optimization)

**Policy A: execution_success only**
- Winner: `respond` (95% > 50%)
- NC selects: `respond` ✅ Matches observed behavior

**Policy B: task_completion only**
- `respond`: 5% completion (never completes task)
- `tool_call`: 50% completion (attempts and sometimes completes)
- Winner: `tool_call` (50% > 5%)
- NC would select: `tool_call`

**Policy C: Combined utility**
```
utility = α * task_completion + β * execution_success - γ * failure
```
With α=1, β=0.5, γ=0.5:
- `respond`: 1*0.05 + 0.5*0.95 - 0.5*0 = 0.525
- `tool_call`: 1*0.50 + 0.5*0.50 - 0.5*0.15 = 0.725

Winner: `tool_call`

### Conclusion
If `task_completion` were in the learning signal, NC would select `tool_call`, not `respond`.

---

## E. Respond Semantics Audit

### From EventType Definition
File: `neuro-cortex/src/neurocortex/event.py:35-40`
```python
class ActionType(Enum):
    NOOP = "noop"
    RESPOND = "respond"      # Text output, no execution
    TOOL_CALL = "tool_call"  # Executes tools
    CODE_REVIEW = "code_review"
    CODE_EDIT = "code_edit"
```

### What `respond` Actually Does
- Generates text response
- Does NOT execute any tools
- Does NOT modify files
- **Cannot fail** (no execution = no failure)
- **Cannot complete tasks** (no action taken)

### Verdict
`respond` is a **NO-OP action** that always reports success but never completes tasks.

---

## F. Root Cause Analysis

### The Bias Chain

```
1. Outcome schema lacks task_completion
         ↓
2. Learning signal = execution_success only
         ↓
3. respond always succeeds (no execution risk)
         ↓
4. respond accumulates 122 global successes
         ↓
5. tool_call has only 21 local successes + 33% failure rate
         ↓
6. adjust_score: respond(0.423) > tool_call(0.326)
         ↓
7. NC selects respond for optimize tasks
         ↓
8. Task completion = 5% (FAIL)
```

### ROOT_CAUSE
**`LEARNING_OBJECTIVE_MISALIGNED`**

The system optimizes for "execution success" but should optimize for "task value delivered".

---

## F. Final Conclusions

### 1. ROOT_CAUSE
`LEARNING_OBJECTURE_MISALIGNED`
- Current objective: `execution_success`
- Required objective: `task_value` or `task_completion`

### 2. CURRENT_POLICY_OBJECTIVE
```
Maximize: P(execution_success | situation, action)
Minimize: P(failure | situation, action)
```

### 3. TASK_COMPLETION_AVAILABLE
**`TASK_COMPLETION_NOT_IN_LEARNING_SIGNAL`**
- Schema: `ActionLearningOutcome` has no `task_completion` field
- Code: `_history_evidence()` only uses `success_count`/`failure_count`
- Fix required: Add `task_completion` to schema and learning signal

### 4. RESPOND_SEMANTICS
**`NO-OP ACTION`**
- Always succeeds (no execution)
- Never completes tasks (no action taken)
- Accumulates false evidence through repeated "successes"

### 5. OPTIMIZE_COUNTERFACTUAL_RESULT
| Policy | Selected Action | Rationale |
|--------|----------------|-----------|
| Current (execution_success) | respond | 95% success rate |
| Counterfactual A (task_completion) | tool_call | 50% completion vs 5% |
| Counterfactual B (combined) | tool_call | Higher utility |

### 6. ARCHITECTURAL_FIX_REQUIRED
**YES** - Multiple fixes needed:
1. Add `task_completion` to `ActionLearningOutcome`
2. Modify `_history_evidence()` to use task completion
3. Add `noop_penalty` or `action_necessity` weight
4. Consider intent-specific outcome models

### 7. RECOMMENDED_NEXT_EXPERIMENT
**`NC-07C: Outcome Schema Extension`**
- Add `task_completion` field to schema
- Re-run NC-07A-R1 with new schema
- Measure if NC now selects `tool_call` for optimize

---

## Appendix: Code References

### Ranking Formula
```python
# engine.py:274-290
raw_score = (
    0.6 * hist_score      # history_weight
    + 0.3 * semantic      # semantic_weight (off)
    + 0.1 * recency       # recency_weight
)
adjusted_score = raw_score * match_level_penalty  # L1=1.0, L3=0.7
```

### History Score Calculation
```python
# engine.py:425-435
hist_score = (success + 1) / (support + 2) * confidence + 0.5 * (1 - confidence)
```

### Outcome Schema
```python
# schema.py:45-55
@dataclass(frozen=True)
class ActionLearningOutcome:
    success: bool           # execution success
    actual_outcome: str     # description
    observed_at: str        # timestamp
    # MISSING: task_completion
```
