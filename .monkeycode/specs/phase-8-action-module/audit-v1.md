# Phase 8 Architecture Audit v1 — Action Module

**Document**: Architecture Audit — Phase 8 Action Module  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: BLOCKED — awaiting implementation of Phase 8 ActionModule  
**Project**: neuro-cortex  
**Baseline**: Commit 546b42e (Phase 7 frozen), 298 PASS / 0 FAIL

---

## 1. Current Code Reality

### 1.1 ActionData Schema (event.py:154-165)

```python
@dataclass
class ActionData:
    """The action taken and its execution status."""
    action_type: str = "noop"
    action_payload: dict[str, Any] = field(default_factory=dict)
    status: str = "planned"
    planned: bool = True
    actual: bool = False
```

**Observations**:
- `action_type`: string (not enum-enforced, but should match `ActionType` values)
- `action_payload`: untyped dict — holds execution parameters
- `status`: string — one of `ActionStatus` values ("planned"/"executing"/"success"/"failure"/"skipped")
- `planned`: bool — whether action was planned
- `actual`: bool — whether action was actually executed

**Missing from schema** (future evolution candidates):
- No `timeout` field
- No `retry_count` field
- No `execution_id` field
- No `result_data` field (where does actual execution result go?)

### 1.2 Action Enums (event.py:27-40)

```python
class ActionStatus(Enum):
    PLANNED = "planned"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"

class ActionType(Enum):
    NOOP = "noop"
    RESPOND = "respond"
    TOOL_CALL = "tool_call"
    CODE_REVIEW = "code_review"
    CODE_EDIT = "code_edit"
```

**Observations**:
- Only 5 action types defined
- No `SHELL_EXECUTE`, `FILE_WRITE`, `HTTP_CALL`, `FEISHU_MESSAGE` — these are intentionally absent
- `ActionStatus.EXECUTING` is defined but never used in any current test

### 1.3 ActionModule Interface (interfaces.py:68-73)

```python
class ActionModule(ABC):
    """Execute the selected action. Records action data but NOT the outcome."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...
```

**Critical docstring note**: "Records action data but NOT the outcome."  
This means ActionModule writes `event.action` but does NOT call `event.record_outcome()`.

### 1.4 Action Directory Status

```
neuro-cortex/src/neurocortex/action/__init__.py  (0 bytes, empty)
```

**No BasicAction implementation exists.** The directory is a placeholder.

### 1.5 Current MockAction (modules/__init__.py:130-143)

```python
class MockAction(ActionModule):
    """Basic action: execute and record action data only. Does NOT produce outcome."""

    def process(self, event: CortexEvent) -> CortexEvent:
        action_type = event.decision.selected_action
        payload = {"text": event.raw_input}
        event.act(ActionData(
            action_type=action_type,
            action_payload=payload,
            status="success",
            planned=True,
            actual=True,
        ))
        return event
```

**Observations**:
- Reads ONLY `event.decision.selected_action` and `event.raw_input`
- Does NOT read: perception, prediction, state, memory, feedback, outcome
- Does NOT execute anything real — always returns `status="success"`
- Creates a synthetic payload `{"text": raw_input}`
- Does NOT advance stage (stage advancement happens via `event.act()` which calls `advance_to("ACTION")`)

### 1.6 Current MockOutcomeProvider (modules/__init__.py:146-166)

```python
class MockOutcomeProvider(OutcomeProvider):
    """Default outcome provider: always reports success."""

    def provide(self, event: CortexEvent) -> CortexEvent:
        event.record_outcome(OutcomeData(
            actual_outcome=f"action '{event.action.action_type}' completed",
            success=True,
        ))
        return event


class FailingOutcomeProvider(OutcomeProvider):
    """Outcome provider that always reports failure."""

    def provide(self, event: CortexEvent) -> CortexEvent:
        event.record_outcome(OutcomeData(
            actual_outcome="outcome failed",
            success=False,
            error_message="simulated failure",
        ))
        return event
```

### 1.7 Pipeline Order (cortex.py:36-48)

```python
_STAGES = (
    ("PERCEPTION",   "perceive"),
    ("REPRESENTATION", "represent"),
    ("ATTENTION",    "attend"),
    ("STATE",        "update_state"),
    ("MEMORY",       "retrieve_memory"),
    ("PREDICTION",   "predict"),
    ("DECISION",     "decide"),
    ("ACTION",       "act"),            # ← Phase 8 targets this
    ("OUTCOME",      "obtain_outcome"), # ← Separate from Action
    ("FEEDBACK",     "compute_feedback"),
    ("LEARNING",     "learn"),
)
```

**Key insight**: ACTION and OUTCOME are SEPARATE stages with SEPARATE modules.
- ActionModule → writes `event.action`, advances to ACTION
- OutcomeProvider → writes `event.outcome`, advances to OUTCOME

### 1.8 Frozen Test Expectations for Action

| Test | Assertion | Current Behavior |
|------|-----------|-----------------|
| `test_process_populates_all_stages` | `e.action.status == "success"` | MockAction always success |
| `test_decision_before_action` | `e.action.status == "success"` | Always success |
| `test_action_before_feedback` | `e.action.status == "success"` | Always success |
| `test_action_failure` | `e.status == "error"`, `e.error_stage == "ACTION"` | FailingAction raises |
| `test_action_success_then_outcome_success` | `e.action.status == "success"`, `e.outcome.success is True` | Both success |
| `test_action_success_outcome_failure` | `e.action.status == "success"`, pipeline errors at OUTCOME | Action success, outcome fails |
| `test_action_failure_outcome_failure` | `e.status == "error"`, `e.error_stage == "ACTION"` | Action fails, no outcome |
| `test_no_outcome_provider_stays_at_action` | `e.stage == "ACTION"` | No provider = no progress |

---

## 2. Action Responsibility

### 2.1 Three-Layer Separation

```
┌─────────────────────────────────────────────────────────┐
│  Decision  │ "What should we do?" → selected_action     │
├─────────────────────────────────────────────────────────┤
│  Action    │ "Do it" → records action execution status  │
├─────────────────────────────────────────────────────────┤
│  Outcome   │ "What happened?" → records world result    │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Action MUST NOT:

| Forbidden | Reason |
|-----------|--------|
| Re-decide | That's Decision's job |
| Predict | That's Prediction's job |
| Evaluate | That's Feedback's job |
| Learn | That's Learning's job |
| Read Feedback | Feedback is in the future (stage 10) |
| Read Outcome | Outcome is in the future (stage 9) |
| Modify State | State is managed by StateModule |
| Modify Memory | Memory is managed by MemoryModule |
| Execute arbitrary code | Needs permission gate |

### 2.3 Action MUST:

| Required | Reason |
|----------|--------|
| Read DecisionData | Primary input — what to execute |
| Read Decision.selected_action | The symbolic action to perform |
| Read Decision.decision_score | For safety gate (low score → skip?) |
| Read Decision.decision_reason | For logging/audit |
| Write event.action | Record execution status |
| Advance to ACTION stage | Via event.act() |

---

## 3. Decision → Action Contract

### 3.1 What Action Reads from DecisionData

| DecisionData Field | Read? | Usage |
|-------------------|-------|-------|
| `selected_action` | **READ** | Which action type to execute |
| `decision_score` | **READ** | Safety gate: if < threshold, skip/abstain |
| `decision_reason` | **READ-ONLY** | Logging/audit, not used for logic |
| `candidates` | **READ-ONLY** | Audit trail, not used for execution |

### 3.2 Schema Gap Analysis

**Current DecisionData**:
```python
@dataclass
class DecisionData:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    selected_action: str = ""
    decision_score: float = 0.5
    decision_reason: str = ""
```

**Problem**: Decision selects `selected_action="code_edit"` but provides NO parameters for WHAT to edit.

**Current MockAction workaround**: `payload = {"text": event.raw_input}` — puts raw input into payload.

**This is a design gap, not a bug.** In a real system:
- Decision would need to include execution parameters
- OR Action would need to extract parameters from context (raw_input, perception, etc.)

**Phase 8 v1 approach**: Action reads `selected_action` from Decision, and uses `event.raw_input` as fallback parameter source. This maintains backward compatibility with existing tests.

### 3.3 Schema Evolution Proposal (DEFERRED)

```python
# Future: DecisionData could include execution parameters
@dataclass
class DecisionData:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    selected_action: str = ""
    decision_score: float = 0.5
    decision_reason: str = ""
    execution_params: dict[str, Any] = field(default_factory=dict)  # NEW
```

**NOT implemented in Phase 8 v1.**

---

## 4. Input Boundary

### 4.1 Field-by-Field Analysis

| Source | Field | Type | READ / READ-ONLY / FORBIDDEN | Rationale |
|--------|-------|------|-------------------------------|-----------|
| Decision | selected_action | str | **READ** | Primary execution command |
| Decision | decision_score | float | **READ** | Safety gate threshold check |
| Decision | decision_reason | str | **READ-ONLY** | Audit/logging |
| Decision | candidates | list[dict] | **READ-ONLY** | Audit/logging |
| Perception | intent | str | **FORBIDDEN** | Decision already consumed this |
| Perception | risk | float | **FORBIDDEN** | Decision already consumed this |
| Prediction | success_probability | float | **FORBIDDEN** | Prediction is done |
| Prediction | predicted_risk | float | **FORBIDDEN** | Prediction is done |
| InternalState | uncertainty | float | **FORBIDDEN** | State is snapshot, not for execution |
| InternalState | confidence | float | **FORBIDDEN** | Same reason |
| MemoryData | retrieved_memories | list[dict] | **FORBIDDEN** | Memory is for Learning, not Action |
| FeedbackData | evaluation | str | **FORBIDDEN** | Feedback is in the future |
| FeedbackData | prediction_error | float | **FORBIDDEN** | Same reason |
| OutcomeData | success | bool | **FORBIDDEN** | Outcome is in the future |
| CortexState | active_goal | str | **FORBIDDEN** | State mutation forbidden |
| raw_input | str | str | **READ** | Fallback parameter source |

### 4.2 Minimal Input Principle

Action should read ONLY:
1. `event.decision.selected_action` — what to execute
2. `event.decision.decision_score` — whether to execute (safety gate)
3. `event.raw_input` — fallback context for parameter extraction

**Everything else is FORBIDDEN.**

---

## 5. Symbolic Actions

### 5.1 ActionType Values and Their Meanings

| ActionType | Symbolic Meaning | Phase 8 v1 Behavior |
|------------|-----------------|---------------------|
| `noop` | Do nothing | Record status="success", return immediately |
| `respond` | Generate text response | Record status="success" (mock: no actual LLM call) |
| `code_review` | Review code changes | Record status="success" (mock: no actual file read) |
| `code_edit` | Edit code file | Record status="success" (mock: no actual file write) |
| `tool_call` | Call external tool | Record status="success" (mock: no actual tool execution) |

### 5.2 Critical Distinction

**Symbolic action ≠ Real execution.**

In Phase 8 v1:
- `selected_action = "code_edit"` means "the system DECIDED to edit code"
- It does NOT mean "the system actually wrote to a file"
- Actual file writing requires: permission check → parameter validation → execution → outcome observation

**Phase 8 v1 MockAction behavior**: Always record `status="success"`, never execute real side effects.

---

## 6. Hermes Tool Boundary

### 6.1 Current Architecture

```
NeuroCortex
    ↓ (via ActionModule.process)
Action (MockAction)
    ↓ (writes event.action)
OutcomeProvider (MockOutcomeProvider)
    ↓ (writes event.outcome)
Feedback (BasicFeedback)
    ↓ (writes event.feedback)
Learning (MockLearning)
```

**No Hermes integration exists.** The system is fully self-contained.

### 6.2 Future Architecture Options

**Option A: Direct Integration (NOT recommended)**
```
Action → HermesTool.execute(...) → OutcomeProvider
```
Problems: tight coupling, hard to test, no permission boundary.

**Option B: Gateway/Adapter Pattern (RECOMMENDED)**
```
Action → ExecutionRequest → PermissionGate → HermesAdapter → Hermes Tools
                                          ↓
                                    ActionResult → OutcomeProvider
```
Benefits:
- Permission boundary isolated
- Hermes can be swapped/mocked
- Dry-run mode possible
- Timeout/retry handling centralized
- Audit trail via ExecutionRequest/ActionResult

### 6.3 Phase 8 v1 Position

**NO Hermes integration.** Phase 8 v1 is a mock/simulation layer.

Future Phase 9+ will introduce:
- `ExecutionRequest` dataclass
- `PermissionGate` module
- `HermesAdapter` interface
- `ActionResult` dataclass

---

## 7. Side Effects Classification

### 7.1 Side Effect Tiers

| Tier | Definition | Examples | Phase 8 v1 |
|------|-----------|----------|------------|
| **PURE** | No observable change | Computing a score, formatting text | ALLOWED |
| **LOCAL SIDE EFFECT** | Changes in-process state | Writing to `event.action`, updating local variables | ALLOWED |
| **EXTERNAL SIDE EFFECT** | Changes outside process | File write, HTTP call, shell command | **FORBIDDEN** |
| **HIGH-RISK SIDE EFFECT** | Irreversible external change | Database delete, production deploy, API token rotation | **FORBIDDEN** |

### 7.2 Phase 8 v1 Rule

**ActionModule may ONLY produce PURE or LOCAL SIDE EFFECTS.**

All EXTERNAL and HIGH-RISK side effects are deferred to future phases with proper permission gates.

---

## 8. Permission Model

### 8.1 Permission Components Audit

| Component | IMPLEMENT NOW | DEFER | FORBIDDEN |
|-----------|--------------|-------|-----------|
| Capability check | NO | — | — |
| Permission allowlist | NO | Phase 9 | — |
| Permission denylist | NO | Phase 9 | — |
| Confirmation prompt | NO | Phase 9 | — |
| Dry-run mode | NO | Phase 9 | — |
| Execution mode (strict/relaxed) | NO | Phase 9 | — |
| Timeout | NO | Phase 9 | — |
| Retry | NO | Phase 9 | — |
| Rollback | NO | Phase 10 | — |
| Idempotency check | NO | Phase 10 | — |

### 8.2 Rationale

Phase 8 v1 is a **mock/simulation**. There is no real execution, so there is no real permission to check.

Real permission modeling belongs to Phase 9 (Execution Gateway).

---

## 9. Safety Gate

### 9.1 Pre-Execution Checks

| Check | Condition | Action |
|-------|-----------|--------|
| Missing Decision | `selected_action == ""` | ABSTAIN (status="skipped") |
| Unknown action | `selected_action` not in known types | FAIL (raise ValueError) |
| Noop | `selected_action == "noop"` | NO-OP (status="success", instant return) |
| Low decision_score | `decision_score < 0.3` | ABSTAIN (status="skipped") |
| Valid action | All checks pass | EXECUTE (status="success") |

### 9.2 Safety Gate Rules (v1)

```python
def safety_gate(selected_action: str, decision_score: float) -> str:
    """Returns: 'execute', 'skip', or 'fail'"""
    if not selected_action:
        return "skip"  # missing decision
    if selected_action == "noop":
        return "execute"  # noop is always safe
    if decision_score < 0.3:
        return "skip"  # too uncertain
    known = {"respond", "code_review", "code_edit", "tool_call"}
    if selected_action not in known:
        return "fail"  # unknown action type
    return "execute"
```

---

## 10. ActionResult vs OutcomeData Boundary

### 10.1 Current Separation

```
ActionModule → event.action (ActionData)
OutcomeProvider → event.outcome (OutcomeData)
```

**This is correct and must be preserved.**

### 10.2 Why Two Separate Data Structures?

| Aspect | ActionData | OutcomeData |
|--------|-----------|-------------|
| Who writes | ActionModule | OutcomeProvider |
| What it records | Execution STATUS | World RESULT |
| Example | status="success", action_type="code_edit" | actual_outcome="file modified", success=True |
| Semantics | System-side observation | World-side observation |

**Key distinction**: An action can SUCCEED (system executed it) but the OUTCOME can FAIL (world result was bad).

Example: `code_edit` action succeeds (file was written), but `outcome.success=False` (tests still fail after edit).

### 10.3 Phase 8 v1 Requirement

**ActionModule writes ActionData. OutcomeProvider writes OutcomeData. NO CROSS-WRITE.**

---

## 11. State Boundary

### 11.1 Action MUST NOT Modify

| Target | Field | Reason |
|--------|-------|--------|
| `event.state` | `uncertainty` | Managed by StateModule |
| `event.state` | `confidence` | Managed by StateModule |
| `event.state` | `curiosity` | Reserved for future |
| `CortexState` | `active_goal` | Updated at LEARNING stage |
| `CortexState` | `recent_inputs` | Updated at LEARNING stage |
| `event.perception` | Any field | Frozen after PERCEPTION |
| `event.prediction` | Any field | Frozen after PREDICTION |
| `event.feedback` | Any field | Future stage |
| `event.outcome` | Any field | Future stage |

### 11.2 Exception: None

**No exceptions.** Action is strictly read-only for all state except `event.action`.

---

## 12. Memory Boundary

### 12.1 Action and Memory

| Operation | Allowed? | Reason |
|-----------|----------|--------|
| Read `event.memory.retrieved_memories` | **FORBIDDEN** | Memory retrieval is for Decision/Prediction context, not execution |
| Write to memory | **FORBIDDEN** | Memory writes belong to Learning |
| Modify MemoryData | **FORBIDDEN** | MemoryData is read-only snapshot |

### 12.2 Rationale

Memory is a read-only context source for Decision and Prediction. Action should not depend on memory because:
1. Memory is empty in current implementation
2. Action should be deterministic based on Decision alone
3. Memory-side effects belong to Learning phase

---

## 13. Feedback / Learning Boundary

### 13.1 Action MUST NOT:

| Forbidden Operation | Reason |
|--------------------|--------|
| Read `event.feedback` | Feedback is in the FUTURE (stage 10) |
| Read `event.feedback.reward` | Same reason |
| Read `event.feedback.prediction_error` | Same reason |
| Read `event.feedback.evaluation` | Same reason |
| Trigger Learning | Learning is a separate stage |
| Compute reward | That's Feedback's job |
| Update policy | That's Learning's job |

### 13.2 Pipeline Order Guarantee

```
DECISION (stage 7) → ACTION (stage 8) → OUTCOME (stage 9) → FEEDBACK (stage 10) → LEARNING (stage 11)
```

Action at stage 8 CANNOT access stages 10-11. This is enforced by the linear pipeline.

---

## 14. Failure Semantics

### 14.1 Failure Ownership Matrix

| Failure Type | Owned By | Recovery |
|-------------|----------|----------|
| Missing decision | Decision Module | Return noop |
| Unknown action type | Action Module | Raise ValueError |
| Low decision score | Action Module (safety gate) | Skip (status="skipped") |
| Execution exception | Action Module | Catch, set status="failure", propagate |
| Timeout | Outcome Provider (future) | Not in Phase 8 v1 |
| Permission denied | Permission Gate (future) | Not in Phase 8 v1 |
| External service unavailable | Outcome Provider (future) | Not in Phase 8 v1 |

### 14.2 Action Failure Handling

```python
try:
    # Execute action
    result = self._execute(action_type, payload)
    event.act(ActionData(
        action_type=action_type,
        action_payload=payload,
        status="success",
        planned=True,
        actual=True,
    ))
except Exception as exc:
    event.status = "error"
    event.error = str(exc)
    event.error_stage = "ACTION"
    event.act(ActionData(
        action_type=action_type,
        action_payload=payload,
        status="failure",
        planned=True,
        actual=False,
    ))
    raise  # Re-raise for Cortex error handling
```

---

## 15. Determinism

### 15.1 Phase 8 v1 Determinism Requirement

Given the same:
- `event.decision.selected_action`
- `event.decision.decision_score`
- `event.raw_input`

The ActionModule MUST produce identical `event.action` every time.

### 15.2 Forbidden Non-Deterministic Sources

| Source | Why Forbidden |
|--------|---------------|
| `random` | Same input → different output |
| `time` / `datetime` | Time-dependent behavior |
| `uuid` | Unique IDs per execution |
| External state | Network, files, databases |
| LLM calls | Non-deterministic generation |

**Phase 8 v1 is pure function**: `ActionModule.process(event) → event` with no side effects beyond `event.action`.

---

## 16. Dry Run

### 16.1 Dry Run Definition

Dry run = execute all checks but produce NO side effects (even `event.action` is not written).

### 16.2 Phase 8 v1 Position

**NOT IMPLEMENTED.**

Rationale:
1. MockAction doesn't produce real side effects anyway
2. Dry run requires a mode flag that propagates through the pipeline
3. Adds complexity without value for simulation

**Deferred to**: Phase 9 (when real execution is introduced).

---

## 17. Hermes Adapter Architecture

### 17.1 Current State

**No Hermes adapter exists.** The system is fully self-contained with MockAction and MockOutcomeProvider.

### 17.2 Recommended Future Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    NeuroCortex Pipeline                      │
│                                                              │
│  DECISION → ACTION → [ExecutionGateway] → OUTCOME → FEEDBACK │
│                          ↓              ↑                    │
│              PermissionGate      ActionResult                │
│                          ↓                              │
│                  HermesAdapter                         │
│                          ↓                              │
│                    Hermes Tools                        │
└──────────────────────────────────────────────────────────────┘
```

### 17.3 Key Interfaces (Future)

```python
# Execution request — what Action sends to Gateway
@dataclass
class ExecutionRequest:
    action_type: str
    params: dict[str, Any]
    risk_level: float
    timeout_seconds: float = 30.0

# Action result — what Gateway returns to OutcomeProvider
@dataclass
class ActionResult:
    success: bool
    output: str
    error_message: str = ""
    execution_time_ms: float = 0.0
```

### 17.4 Phase 8 v1 Position

**No adapter. No gateway. No Hermes.** Phase 8 v1 is purely MockAction.

---

## 18. Test Matrix (35+ Cases)

### 18.1 Decision Integration (5 tests)

| Test | Input | Expected |
|------|-------|----------|
| T01 | selected_action="code_edit", score=0.8 | status="success", action_type="code_edit" |
| T02 | selected_action="noop", score=0.5 | status="success", action_type="noop" |
| T03 | selected_action="respond", score=0.6 | status="success", action_type="respond" |
| T04 | selected_action="tool_call", score=0.7 | status="success", action_type="tool_call" |
| T05 | selected_action="code_review", score=0.9 | status="success", action_type="code_review" |

### 18.2 Safety Gate (8 tests)

| Test | Input | Expected |
|------|-------|----------|
| T06 | selected_action="" (empty) | status="skipped" |
| T07 | selected_action="unknown_action" | Raises ValueError |
| T08 | decision_score=0.2 (< 0.3 threshold) | status="skipped" |
| T09 | decision_score=0.3 (at threshold) | status="success" |
| T10 | decision_score=0.5 (normal) | status="success" |
| T11 | decision_score=0.0 | status="skipped" |
| T12 | decision_score=1.0 | status="success" |
| T13 | Valid action + score=0.5 | status="success" |

### 18.3 Noop Handling (3 tests)

| Test | Input | Expected |
|------|-------|----------|
| T14 | selected_action="noop" | status="success", instant return |
| T15 | selected_action="noop", score=0.0 | status="success" (noop bypasses score gate) |
| T16 | selected_action="noop", empty input | status="success" |

### 18.4 Unknown Action (3 tests)

| Test | Input | Expected |
|------|-------|----------|
| T17 | selected_action="shell_exec" | Raises ValueError |
| T18 | selected_action="file_write" | Raises ValueError |
| T19 | selected_action="" | status="skipped" (not error) |

### 18.5 Immutability (6 tests)

| Test | Verify |
|------|--------|
| T20 | `event.perception` unchanged after action |
| T21 | `event.prediction` unchanged after action |
| T22 | `event.state` unchanged after action |
| T23 | `event.feedback` unchanged after action |
| T24 | `event.outcome` unchanged after action |
| T25 | `event.memory` unchanged after action |

### 18.6 Determinism (2 tests)

| Test | Verify |
|------|--------|
| T26 | Same input × 10 → identical ActionData |
| T27 | No random/time/uuid in action output |

### 18.7 Full Pipeline Integration (4 tests)

| Test | Verify |
|------|--------|
| T28 | Full pipeline reaches LEARNING with MockAction |
| T29 | Action stage before Outcome stage |
| T30 | Action failure → error_stage="ACTION" |
| T31 | Decision → Action data flow correct |

### 18.8 Regression (1 test)

| Test | Verify |
|------|--------|
| T32 | All 298 existing tests still pass |

### 18.9 Deferred (Not Phase 8 v1)

| Test | Reason |
|------|--------|
| Timeout handling | No real execution in v1 |
| Permission check | No permission gate in v1 |
| Dry run | Deferred to Phase 9 |
| Retry logic | Deferred to Phase 9 |
| Hermes integration | Deferred to Phase 10 |

**Total Phase 8 v1 tests: 32**

---

## 19. Frozen Boundary

### 19.1 Files Confirmed Unchanged

| File | Status |
|------|--------|
| `event.py` | UNCHANGED — ActionData schema sufficient for v1 |
| `interfaces.py` | UNCHANGED — ActionModule interface sufficient |
| `cortex.py` | UNCHANGED — pipeline order correct |
| `perception/*` | UNCHANGED |
| `representation/*` | UNCHANGED |
| `state/*` | UNCHANGED |
| `prediction/*` | UNCHANGED |
| `decision/*` | UNCHANGED |
| `feedback/*` | UNCHANGED |
| Phase 0-7 tests | UNCHANGED |

### 19.2 No Schema Evolution Needed

Phase 8 v1 works within existing `ActionData` and `ActionModule` schemas.

**No new fields required.**

---

## 20. Architecture Risks

### 20.1 Risk Matrix

| Risk | Severity | Mitigation |
|------|----------|------------|
| Action executes real side effects without permission | **HIGH** | Phase 8 v1 is mock-only; no real execution |
| Action reads forbidden fields (feedback, outcome) | **MEDIUM** | Code review + test immutability checks |
| Decision→Action parameter gap (no execution params) | **MEDIUM** | Documented as known limitation; future schema evolution |
| MockAction always returns success (hides real failures) | **LOW** | FailingAction exists for error path testing |
| ActionType enum not enforced (string comparison) | **LOW** | Future: use ActionType enum instead of str |
| No timeout handling | **MEDIUM** | Deferred to Phase 9 |
| No retry logic | **MEDIUM** | Deferred to Phase 9 |
| Action directly coupled to raw_input for params | **LOW** | Known workaround; clean in future with ExecutionRequest |

---

## 21. Schema Evolution Proposal

### 21.1 Proposed Future Changes (NOT for Phase 8 v1)

**Proposal 1: Add execution parameters to DecisionData**
```python
@dataclass
class DecisionData:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    selected_action: str = ""
    decision_score: float = 0.5
    decision_reason: str = ""
    execution_params: dict[str, Any] = field(default_factory=dict)  # NEW
```

**Proposal 2: Add ActionResult dataclass**
```python
@dataclass
class ActionResult:
    """Result of action execution, separate from OutcomeData."""
    success: bool = False
    output: str = ""
    error_message: str = ""
    execution_time_ms: float = 0.0
```

**Proposal 3: Add ActionType enum enforcement**
```python
# Current: action_type: str = "noop"
# Proposed: action_type: ActionType = ActionType.NOOP
```

**None of these proposals are implemented in Phase 8 v1.**

---

## 22. Open Questions

1. **Should Action read `event.perception.risk` for risk-aware execution?**
   - Decision already considered risk. Action should trust Decision's judgment.
   - **Answer**: FORBIDDEN. Action reads only Decision + raw_input.

2. **Should Action validate `decision_score` or trust Decision?**
   - Safety gate is Action's responsibility (prevents Decision bugs from causing harm).
   - **Answer**: READ and check. If score < 0.3, skip execution.

3. **Where do execution parameters come from in v1?**
   - Currently: `event.raw_input` as fallback.
   - Future: `DecisionData.execution_params`.
   - **Answer**: Use `event.raw_input` in v1, document as workaround.

4. **Should Action produce OutcomeData directly?**
   - NO. Outcome is OutcomeProvider's responsibility.
   - **Answer**: Action writes ActionData only. OutcomeProvider writes OutcomeData.

---

## 23. Final Recommendation

### BLOCKED

**Reason**: Phase 8 v1 ActionModule has not been implemented. The `action/` directory exists but `__init__.py` is 0 bytes. No `BasicAction` class exists.

**Next steps before implementation**:
1. Create `src/neurocortex/action/action.py` with `BasicAction` class
2. Implement safety gate (missing action → skip, unknown action → fail, low score → skip)
3. MockAction stays as-is in modules/__init__.py (or delegates to BasicAction)
4. Add 32 tests in `tests/test_action.py`
5. Verify all 298 existing tests still pass
6. Re-issue audit as **APPROVED FOR IMPLEMENTATION** only after tests pass

**Constraints reaffirmed**:
- NO code modification until verdict changes to APPROVED
- NO commit
- NO push
- `event.py` schema unchanged
- `interfaces.py` unchanged
- `cortex.py` unchanged
- Frozen Phase 0-7 tests unchanged

---

*Audit v1 generated 2026-09-07. All rules in this document are frozen for Phase 8 v1 implementation.*
