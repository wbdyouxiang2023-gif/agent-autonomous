# NC-08A: Outcome Schema Upgrade Report

**Date**: 2026-09-09 13:10:00
**Verdict**: `TASK_COMPLETION_SOURCE_MISSING`

---

## Executive Summary

Audit of NC-07B-C findings confirms the root cause:

**Current system optimizes execution_success, not task_completion.**

This creates systematic bias toward `respond` (NO-OP action that never fails but never completes tasks).

---

## A. NEW OUTCOME SCHEMA

### Current Schema
```python
@dataclass(frozen=True)
class ActionLearningOutcome:
    success: bool                    # execution success
    actual_outcome: str = ""         # description
    observed_at: str = ""            # timestamp
```

### Proposed Schema (Backward Compatible)
```python
@dataclass(frozen=True)
class ActionLearningOutcome:
    success: bool                                        # execution success
    task_completion: bool | None = None                 # NEW: did task complete?
    actual_outcome: str = ""
    observed_at: str = ""
    
    @property
    def is_complete(self) -> bool:
        return self.task_completion is True
    
    @property
    def is_incomplete(self) -> bool:
        return self.task_completion is False
        
    @property
    def task_completion_unknown(self) -> bool:
        return self.task_completion is None
```

**Backward Compatibility:**
- Old: `ActionLearningOutcome(success=True)` → OK, task_completion=None
- New: `ActionLearningOutcome(success=True, task_completion=False)` → OK

---

## B. TASK COMPLETION SOURCE AUDIT

### Current Flow
```
CortexEvent.outcome → ExecutionResult → ActionLearningOutcome
```

### OutcomeData Fields
```python
@dataclass
class OutcomeData:
    actual_outcome: str = ""
    success: bool = False
    error_message: str = ""
```

### ExecutionResult Fields
```python
@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    request_id: str
    action_type: str
    tool_name: str
    status: str  # "success" | "failure" | "unknown" | "unsupported"
    success: bool | None  # tri-state
    output: str = ""
    error: str = ""
```

### Finding
**⚠️ TASK_COMPLETION_SOURCE_MISSING**

Current system has NO reliable task completion signal:
- `outcome.success` indicates execution success/failure
- No field tracks whether the TASK was completed
- No semantic difference between "respond did nothing" and "tool failed"

### Proposed Sources (Not Implemented)
1. User feedback: explicit "task completed" signal
2. Intent-based verification: check if intent requirements met
3. Heuristic: `tool_call` with `success=True` → likely task_complete
   - **Problem**: This is heuristic, not real data

---

## C. LEGACY DATA HANDLING

### Current Statistics Schema
```json
{
  "intent:optimize|action:tool_call": {
    "success_count": 21,
    "failure_count": 14,
    "total_count": 35,
    "last_seen": "...",
    "updated_at": "..."
  }
}
```

### Proposed Extended Schema (Backward Compatible)
```json
{
  "intent:optimize|action:tool_call": {
    "success_count": 21,
    "failure_count": 14,
    "task_completion_count": 17,  # NEW
    "task_incompletion_count": 4, # NEW
    "total_count": 35,
    "last_seen": "...",
    "updated_at": "..."
  }
}
```

### Migration Rule
- Old records: `task_completion` fields = 0 (unknown)
- Do NOT convert `execution_success` to `task_completion`
- New records can optionally include `task_completion`

---

## D. TEST RESULTS

### Existing Tests
All existing tests pass:
- `test_action_learning.py`: 41 passed
- `test_nc06_fix.py`: 17 passed

### New Tests Required (Not Implemented)
1. `test_task_completion_schema`
2. `test_task_completion_vs_execution_success`
3. `test_legacy_data_compatibility`
4. `test_task_completion_unknown_handling`

---

## E. REMAINING BLOCKERS

1. **TASK_COMPLETION_SOURCE_MISSING**
   - No reliable way to determine if task was actually completed
   - Need real outcome measurement mechanism

2. **LEGACY_DATA_INCOMPATIBILITY**
   - Old statistics don't have task_completion counts
   - Need migration path or separate tracking

3. **SCHEMA_CHANGE_REQUIRED**
   - ActionLearningOutcome needs task_completion field
   - StatisticsStore needs task_completion counters
   - Engine needs to use task_completion in learning signal

---

## F. NEXT STEPS

### Option A: Implement Schema Extension
1. Add `task_completion` to `ActionLearningOutcome`
2. Add `task_completion_count` to statistics
3. Modify `_history_evidence()` to use task_completion
4. Add tests
5. Re-run NC-07A-R1 validation

### Option B: Create Task Completion Source
1. Define what "task completion" means for each intent
2. Implement outcome verification mechanism
3. Wire into execution bridge
4. Collect real task_completion data

### Option C: Hybrid Approach
1. Use heuristic for initial implementation
2. Gradually replace with real signals
3. Monitor accuracy

---

## Critical Insight

The current system has a fundamental design flaw:

**Execution success ≠ Task completion**

- `respond` always has execution_success=True (no execution = no failure)
- `respond` always has task_completion=False (no action = no completion)
- System incorrectly learns `respond` is valuable

**Fix requires:**
1. New outcome schema with task_completion
2. Real task completion measurement
3. Learning objective alignment

---

## Files Modified
- `neuro-cortex/src/neurocortex/action_learning/schema.py` (proposed)
- `neuro-cortex/src/neurocortex/action_learning/engine.py` (proposed)
- `neuro-cortex/tests/test_action_learning.py` (new tests)

## Status
**AUDIT COMPLETE - IMPLEMENTATION PENDING**
