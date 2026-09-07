# Phase 7 Architecture Audit v1 — Decision Module

**Document**: Architecture Audit — Phase 7 Decision Module  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: BLOCKED — awaiting implementation of Phase 7 DecisionModule  
**Project**: neuro-cortex  
**Baseline**: Commit 078f8fc (Phase 6 frozen), 260 PASS / 0 FAIL

---

## 1. Current Code Reality

### 1.1 Decision Data Structure (event.py:141-151)

```python
@dataclass
class DecisionData:
    """Output of decision — why this action was chosen."""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    selected_action: str = ""
    decision_score: float = 0.5
    decision_reason: str = ""
```

**Observations**:
- `candidates` is `list[dict[str, Any]]` — untyped, flexible but inconsistent with other typed dataclasses
- `selected_action` is a string, not an enum — matches `ActionType` values but not enforced
- `decision_score` defaults to 0.5 (same as other score fields)
- `decision_reason` is free-form text
- **No `decision_confidence` field** — exists in PredictionData but not DecisionData
- **No `expected_value` field** — not present
- **No `risk_adjusted_score` field** — not present

### 1.2 Current MockDecision (modules/__init__.py:119-141)

```python
class MockDecision(DecisionModule):
    """Basic decision: choose action based on perceived intent."""

    def process(self, event: CortexEvent) -> CortexEvent:
        intent = event.perception.intent
        action_map = {
            "create": "code_edit",
            "fix": "code_review",
            "learn": "respond",
            "optimize": "tool_call",
            "deploy": "tool_call",
        }
        action_type = action_map.get(intent, "respond")
        event.decide(DecisionData(
            candidates=[
                {"id": action_type, "score": 0.8},
                {"id": "noop", "score": 0.2},
            ],
            selected_action=action_type,
            decision_score=0.8,
            decision_reason=f"intent={intent} → action={action_type}",
        ))
        return event
```

**Observations**:
- Current implementation ONLY reads `event.perception.intent`
- Does NOT read: prediction, feedback, state, memory, risk
- Has a hardcoded intent→action lookup table
- Always produces `decision_score=0.8` regardless of context
- Does NOT use prediction errors or evaluation signals

### 1.3 Frozen Test Expectations

| Test | Assertion | Current Behavior |
|------|-----------|-----------------|
| `test_process_populates_all_stages` | `e.decision.selected_action != ""` | Always non-empty |
| `test_prediction_before_decision` | `e.decision.selected_action != ""` | Always non-empty |
| `test_decision_before_action` | `e.decision.selected_action != ""` | Always non-empty |
| `test_perception_intent_flows_to_decision` | `e.decision.selected_action == "code_review"` | Maps "fix" → "code_review" |
| `test_full_lifecycle_with_separate_outcome` | `e.decision.selected_action` (truthy) | Always truthy |
| `test_decision_failure` | `e.status == "error"`, `e.error_stage == "DECISION"` | FailingDecision raises |

### 1.4 Decision Interface (interfaces.py:60-65)

```python
class DecisionModule(ABC):
    """Select an action from available candidates."""

    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...
```

**Note**: The interface docstring says "Select an action from available candidates" — this implies candidates should be provided/considered, not just intent→action mapping.

---

## 2. Decision Responsibility

### 2.1 Decision ≠ Action

| Aspect | Decision | Action |
|--------|----------|--------|
| Role | "What should we do?" | "Do it" |
| Input | Perception + Prediction + State | Decision |
| Output | selected_action, decision_reason | status, action_payload |
| Executes? | NO | YES (via OutcomeProvider) |
| Risk-aware? | YES (should be) | NO |

### 2.2 Core Decision Question

Given the current event state at DECISION stage, which action should be selected?

**Answer**: A deterministic, rule-based function that maps (perception, prediction, state) → (selected_action, decision_score, decision_reason).

---

## 3. Input Contract

### 3.1 Field-by-Field Analysis

| Source | Field | Type | READ / READ-ONLY / FORBIDDEN | Rationale |
|--------|-------|------|-------------------------------|-----------|
| Perception | `intent` | str | **READ** | Primary decision signal — maps to action types |
| Perception | `risk` | float [0,1] | **READ** | Risk-awareness for safety |
| Perception | `confidence` | float [0,1] | **READ-ONLY** | Confidence in perception affects decision certainty |
| Representation | `features` | dict | **FORBIDDEN** | Representation is hash-based, no semantic value |
| InternalState | `uncertainty` | float [0,1] | **READ** | State uncertainty affects decision caution |
| InternalState | `confidence` | float [0,1] | **READ** | State confidence affects risk tolerance |
| InternalState | `caution` | float [0,1] | **READ** | Direct caution signal for risk-averse decisions |
| MemoryData | `retrieved_memories` | list[dict] | **FORBIDDEN** | Memory retrieval is empty in current phase |
| PredictionData | `predicted_outcome` | str | **READ** | What the system expects will happen |
| PredictionData | `success_probability` | float [0,1] | **READ** | Likelihood of success |
| PredictionData | `predicted_risk` | float [0,1] | **READ** | Predicted risk level |
| PredictionData | `prediction_confidence` | float [0,1] | **READ** | Certainty about prediction |
| FeedbackData | `prediction_error` | float | **FORBIDDEN** | Feedback comes AFTER Decision in pipeline |
| FeedbackData | `evaluation` | str | **FORBIDDEN** | Feedback comes AFTER Decision in pipeline |
| OutcomeData | `success` | bool | **FORBIDDEN** | Outcome comes AFTER Action |

### 3.2 Decision should NOT read prediction_error

**Reason**: The evaluation pipeline is linear:
```
PREDICTION → DECISION → ACTION → OUTCOME → FEEDBACK
```

At DECISION stage, FEEDBACK has not yet been computed. `prediction_error` does not exist. Accessing it would either:
1. Read the default value (0.0) from the previous event's feedback (if any) — semantically wrong
2. Read uninitialized data — unreliable

**Conclusion**: FORBIDDEN. Decision cannot use future feedback.

---

## 4. Output Contract

### 4.1 Required Outputs (from DecisionData schema)

| Field | Type | Required | Semantics |
|-------|------|----------|-----------|
| `selected_action` | str | YES | The action type chosen (noop/respond/tool_call/code_review/code_edit) |
| `decision_score` | float [0,1] | YES | Confidence in this decision (0.0 = no confidence, 1.0 = absolute certainty) |
| `decision_reason` | str | YES | Human-readable explanation of why this action was chosen |
| `candidates` | list[dict] | OPTIONAL | Alternative actions considered (for audit/debugging) |

### 4.2 Missing Fields — Schema Evolution Needed

The current `DecisionData` lacks:
- `decision_confidence` — distinct from `decision_score`
- `risk_level` — the assessed risk of this decision
- `expected_value` — if utility-based decision making is added later

**However**: Phase 7 v1 MUST work with the frozen schema. No new fields can be added.

### 4.3 DecisionData Output Contract (v1)

```python
event.decide(DecisionData(
    selected_action=<str>,           # REQUIRED: one of ActionType values or ""
    decision_score=<float [0,1]>,    # REQUIRED: confidence in selection
    decision_reason=<str>,           # REQUIRED: why this action
    candidates=<list[dict]>,         # OPTIONAL: alternatives considered
))
```

---

## 5. Prediction → Decision Relationship

### 5.1 Current State

Prediction produces:
- `predicted_outcome`: str
- `success_probability`: float [0,1]
- `predicted_risk`: float [0,1]
- `prediction_confidence`: float [0,1]

Decision currently uses:
- Only `perception.intent`

Decision SHOULD use:
- `prediction.predicted_outcome` — what will happen if we act
- `prediction.success_probability` — likelihood of success
- `prediction.predicted_risk` — predicted risk level
- `prediction.prediction_confidence` — how sure we are about the prediction

### 5.2 The Multi-Candidate Problem

Current `PredictionData` supports only ONE prediction per event:
```python
predicted_outcome: str = ""         # singular, not a list
success_probability: float = 0.5    # single value
predicted_risk: float = 0.0         # single value
prediction_confidence: float = 0.5  # single value
```

This means:
- Decision CANNOT ask "what if we do A vs B vs C?" because prediction is singular
- Decision must select from a fixed set of action types
- Prediction is about the overall event, not per-action

**Schema Evolution Proposal**: Future phases could add:
```python
# Hypothetical future schema
@dataclass
class ActionPrediction:
    action_type: str
    predicted_outcome: str
    success_probability: float
    risk: float

@dataclass  
class PredictionData:
    # Current fields...
    action_predictions: list[ActionPrediction] = field(default_factory=list)
```

**For Phase 7 v1**: Decision works with the existing singular prediction. It selects from a predefined action set based on intent + prediction quality.

---

## 6. Risk Semantics

### 6.1 Two Risk Sources

| Source | Field | Meaning |
|--------|-------|---------|
| Perception | `perception.risk` | Risk perceived from input analysis |
| Prediction | `prediction.predicted_risk` | Risk predicted based on state + perception |

**Current relationship** (from BasicPrediction):
```python
# In _high_risk_prediction, _high_uncertainty_prediction, etc.
predicted_risk = clamp(risk, 0.0, 1.0)  # Mirrors perception.risk
```

Prediction copies perception risk in most cases. The two values are correlated but not identical.

### 6.2 Decision Rule for Risk

**HIGH RISK + HIGH PROBABILITY CASE** (the critical test case):
```
p(success) = 0.95
risk = 1.0
```

Should this be executed?

**Answer**: NO. High risk should suppress execution regardless of high success probability.

**Rule**:
```
IF perceived_risk >= 0.8 AND prediction_confidence > 0.5:
    selected_action = "noop"  # abstain
    decision_reason = "high risk detected, abstaining"
ELIF predicted_risk >= 0.6 AND success_probability < 0.5:
    selected_action = "noop"  # risky and unlikely to succeed
    decision_reason = "high risk with low success probability"
ELSE:
    selected_action = map_from_intent(intent)
```

### 6.3 Risk-Averse Default

When in doubt, choose noop. This is the safe default.

---

## 7. Uncertainty Semantics

### 7.1 Four Distinct Uncertainty/Confidence Values

| Value | Source | Range | Meaning |
|-------|--------|-------|---------|
| `state.uncertainty` | InternalState | [0,1] | System's overall uncertainty about its model |
| `state.confidence` | InternalState | [0,1] | System's overall confidence in its model |
| `perception.confidence` | PerceptionData | [0,1] | Confidence in current perception |
| `prediction.prediction_confidence` | PredictionData | [0,1] | Confidence in current prediction |

**CRITICAL**: These are FOUR SEPARATE values. Do NOT conflate them.

### 7.2 Phase 7 v1 Usage

| Value | Read? | Use Case |
|-------|-------|----------|
| `perception.confidence` | YES | If very low (< 0.3), consider abstaining |
| `prediction.prediction_confidence` | YES | Low confidence → prefer safer actions |
| `state.confidence` | NO | InternalState is a snapshot, not used for real-time decisions |
| `state.uncertainty` | NO | Same reason as above |

---

## 8. Unknown / Abstention Semantics

### 8.1 Decision Tree for Unknown Cases

```
IF predicted_outcome == "" AND prediction_confidence == 0:
    → "no_prediction" → selected_action = "noop"
    
IF intent == "unknown" AND risk < 0.6 AND uncertainty < 0.6:
    → selected_action = "respond" (ask for clarification)
    
IF risk >= 0.8:
    → selected_action = "noop" (abstain on high risk)
    
IF prediction_confidence < 0.3 AND success_probability < 0.5:
    → selected_action = "noop" (low confidence + low probability)
    
IF raw_input == "":
    → selected_action = "noop" (nothing to do)
    
ELSE:
    → selected_action = map_from_intent(intent)
```

### 8.2 Known Intent → Action Mapping

| Intent | Action | Rationale |
|--------|--------|-----------|
| "create" | "code_edit" | Creating something requires editing |
| "fix" | "code_review" | Fixing requires reviewing first |
| "learn" | "respond" | Learning is informational |
| "optimize" | "tool_call" | Optimization often needs tools |
| "deploy" | "tool_call" | Deployment needs tool execution |
| "unknown" | "respond" | Unknown intent → ask |
| "" | "noop" | No intent → do nothing |

---

## 9. State Boundary

### 9.1 Decision MUST NOT Modify

| Target | Reason |
|--------|--------|
| `event.state` | State is updated by StateModule, not Decision |
| `CortexState` | Persistent state is only updated at LEARNING stage |
| `event.perception` | Perception is final after PERCEPTION stage |
| `event.prediction` | Prediction is final after PREDICTION stage |

### 9.2 Read-Only Access

Decision reads:
- `event.perception.intent`
- `event.perception.risk`
- `event.perception.confidence`
- `event.state.uncertainty` (read-only for context)
- `event.prediction.*`
- `event.state.confidence` (read-only for context)

---

## 10. Memory Boundary

### 10.1 Decision and Memory

**Decision does NOT read memory in Phase 7 v1.**

Reasons:
1. Memory module returns empty in current implementation
2. Adding memory access would couple Decision to Memory internals
3. Memory is more relevant for Learning than Decision

**Deferred to**: Phase 8 or later, when Memory module has persistent storage.

---

## 11. Learning Boundary

### 11.1 Decision and Learning

**Decision does NOT trigger Learning.**

Learning is a separate stage that runs AFTER Feedback. Decision produces no learning signal.

**Forbidden in Phase 7**:
- Policy updates
- Parameter changes
- State modifications
- Any form of self-improvement

---

## 12. Action Boundary

### 12.1 Decision Does NOT Execute

Decision ONLY selects an action. It does NOT:
- Run shell commands
- Write files
- Make network calls
- Call external APIs
- Execute tools
- Use subprocess

Execution happens in the ACTION stage via ActionModule.

---

## 13. Determinism

### 13.1 Phase 7 v1 is Fully Deterministic

Given the same:
- `event.perception.intent`
- `event.perception.risk`
- `event.perception.confidence`
- `event.prediction.success_probability`
- `event.prediction.predicted_risk`
- `event.prediction.prediction_confidence`
- `event.raw_input`

The Decision module MUST produce the same output every time.

No randomness. No sampling. No stochastic selection.

---

## 14. Mathematical / Rule Model

### 14.1 Decision Function

```
Decision(event) → DecisionData

where:
  intent = event.perception.intent
  risk = event.perception.risk
  perf_conf = event.perception.confidence
  p = event.prediction.success_probability
  pred_risk = event.prediction.predicted_risk
  pred_conf = event.prediction.prediction_confidence
  outcome = event.prediction.predicted_outcome

Rules (first match wins):

Rule 0: Empty input
  IF raw_input.strip() == "":
      return DecisionData(selected_action="noop", decision_score=0.0, decision_reason="empty input")

Rule 1: No valid prediction
  IF outcome == "" OR pred_conf <= 0:
      return DecisionData(selected_action="noop", decision_score=0.0, decision_reason="no valid prediction")

Rule 2: High risk abstention
  IF pred_risk >= 0.8 AND pred_conf > 0.5:
      return DecisionData(selected_action="noop", decision_score=0.3, decision_reason="high risk abstention")

Rule 3: Low confidence + low probability
  IF pred_conf < 0.3 AND p < 0.5:
      return DecisionData(selected_action="noop", decision_score=pred_conf, decision_reason="low confidence and low probability")

Rule 4: Known intent with actionable risk
  IF intent != "" AND intent != "unknown" AND pred_risk < 0.8:
      action = intent_to_action(intent)
      score = clamp(pred_conf * 0.9 + (1.0 - pred_risk) * 0.1, 0.3, 0.9)
      return DecisionData(
          selected_action=action,
          decision_score=score,
          decision_reason=f"intent={intent}, risk={pred_risk:.2f}, p={p:.2f}"
      )

Rule 5: Unknown intent → respond
  IF intent == "unknown" OR intent == "":
      return DecisionData(selected_action="respond", decision_score=0.5, decision_reason="unknown intent")

Rule 6: Default fallback
  return DecisionData(selected_action="noop", decision_score=0.0, decision_reason="default fallback")
```

### 14.2 Intent → Action Map

```python
INTENT_ACTION_MAP = {
    "create": "code_edit",
    "fix": "code_review",
    "learn": "respond",
    "optimize": "tool_call",
    "deploy": "tool_call",
}
```

---

## 15. Test Matrix (30+ Cases)

### 15.1 Known Intent Cases (5 tests)

| Test | Input | Expected Action | Rationale |
|------|-------|----------------|-----------|
| T01 | "fix bug" | "code_review" | Known fix intent |
| T02 | "create API" | "code_edit" | Known create intent |
| T03 | "optimize query" | "tool_call" | Known optimize intent |
| T04 | "deploy app" | "tool_call" | Known deploy intent |
| T05 | "learn python" | "respond" | Known learn intent |

### 15.2 Unknown Intent Cases (4 tests)

| Test | Input | Expected Action | Rationale |
|------|-------|----------------|-----------|
| T06 | "hello world" | "respond" | Unknown intent |
| T07 | "" (empty) | "noop" | Empty input |
| T08 | "   " (whitespace) | "noop" | Whitespace-only |
| T09 | None intent | "noop" | No prediction |

### 15.3 High Risk Cases (4 tests)

| Test | Risk | Prob | Expected | Rationale |
|------|------|------|----------|-----------|
| T10 | 0.9 | 0.95 | "noop" | High risk → abstain |
| T11 | 0.8 | 0.5 | "noop" | High risk threshold |
| T12 | 0.7 | 0.9 | <normal> | Below risk threshold |
| T13 | 1.0 | 1.0 | "noop" | Max risk → always abstain |

### 15.4 Low Confidence Cases (3 tests)

| Test | PredConf | Prob | Expected | Rationale |
|------|----------|------|----------|-----------|
| T14 | 0.2 | 0.4 | "noop" | Very low confidence + low prob |
| T15 | 0.3 | 0.6 | <normal> | Borderline confidence |
| T16 | 0.8 | 0.9 | <normal> | High confidence |

### 15.5 Boundary Cases (5 tests)

| Test | Input | Expected | Rationale |
|------|-------|----------|-----------|
| T17 | p=0, success=False | "perfect" path → normal action | p=0 but risk low |
| T18 | p=1, success=True | Normal action | High prob, no risk |
| T19 | p=0.5, risk=0.5 | Normal action | Middle ground |
| T20 | risk=0.3, intent="fix" | "code_review" | Low risk known intent |
| T21 | risk=0.85, intent="create" | "noop" | High risk overrides intent |

### 15.6 Immutability Cases (4 tests)

| Test | Verify |
|------|--------|
| T22 | `event.state` unchanged after decision |
| T23 | `event.prediction` unchanged after decision |
| T24 | `event.perception` unchanged after decision |
| T25 | `CortexState` unchanged after decision |

### 15.7 Determinism Cases (2 tests)

| Test | Verify |
|------|--------|
| T26 | Same input → same output (5 iterations) |
| T27 | Decision does not use random |

### 15.8 Integration Cases (3 tests)

| Test | Verify |
|------|--------|
| T28 | Full pipeline reaches LEARNING |
| T29 | Decision stage before Action stage |
| T30 | Decision failure causes error_stage="DECISION" |

### 15.9 Regression (1 test)

| Test | Verify |
|------|--------|
| T31 | All 260 existing tests still pass |

**Total: 31 tests**

---

## 16. Schema Evolution Proposal

### 16.1 Current Limitations

1. **No `decision_confidence` field** — `decision_score` is ambiguous (is it confidence? score? utility?)
2. **No `risk_level` field** — risk assessment not captured in output
3. **No `expected_value` field** — can't express utility-based decisions
4. **Candidates are untyped** — `list[dict[str, Any]]` should be `list[ActionCandidate]`

### 16.2 Proposed Future Schema (NOT for Phase 7 v1)

```python
@dataclass
class ActionCandidate:
    action_type: str
    score: float
    risk: float
    confidence: float

@dataclass
class DecisionData:
    candidates: list[ActionCandidate] = field(default_factory=list)
    selected_action: str = ""
    decision_score: float = 0.5
    decision_confidence: float = 0.5    # NEW: explicit confidence
    decision_reason: str = ""
    risk_level: float = 0.0             # NEW: assessed risk
    expected_value: float = 0.0         # NEW: utility score
```

### 16.3 Evolution Trigger Conditions

- When utility-based decision making is required
- When multi-action comparison is needed
- When risk-adjusted scoring is needed

**Phase 7 v1 does NOT implement any of these.**

---

## 17. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Decision too simplistic | Medium | Start simple, iterate in Phase 8 |
| Confusing perception.risk with prediction.predicted_risk | High | Document clearly, test explicitly |
| Breaking existing MockDecision behavior | High | Keep backward compatibility in tests |
| Over-engineering v1 | Medium | Strict scope: only intent + risk + prediction |
| Decision reading feedback (future stage) | High | Explicitly FORBIDDEN in contract |

---

## 18. Open Questions

1. **Should Decision use `state.caution`?**
   - Currently not used by any module
   - Could be useful for risk-averse decisions
   - **Decision**: Read but don't weight heavily in v1

2. **Should Decision produce candidates even when not using them?**
   - Current MockDecision produces `[action_type, noop]`
   - Useful for debugging/audit
   - **Decision**: Include candidates in output but don't require them for core logic

3. **What happens when intent is "general" (from MockPerception)?**
   - MockPerception returns "general" for unrecognized intents
   - Current MockDecision treats "general" as "respond"
   - **Decision**: Map "general" → "respond" in v1

---

## 19. Final Recommendation

### BLOCKED

**Reason**: Phase 7 v1 DecisionModule has not been implemented. The `decision/` directory exists but is empty (`__init__.py` is 0 bytes). No `BasicDecision` class exists.

**Required before implementation**:
1. Create `src/neurocortex/decision/decision.py` with `BasicDecision` class
2. Implement the rule model from Section 14
3. Add 31 tests in `tests/test_decision.py`
4. Update `MockDecision` in `modules/__init__.py` to use `BasicDecision`
5. Verify all 260+ existing tests still pass
6. Re-issue audit as **APPROVED FOR IMPLEMENTATION** only after tests pass

**Constraints reaffirmed**:
- NO code modification until verdict changes to APPROVED
- NO commit
- NO push
- `event.py` schema unchanged (no new DecisionData fields)
- `interfaces.py` unchanged
- `cortex.py` unchanged
- Frozen Phase 0-6 tests unchanged

---

*Audit v1 generated 2026-09-07. All rules in this document are frozen for Phase 7 v1 implementation.*
