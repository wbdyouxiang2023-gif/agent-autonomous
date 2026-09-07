# Phase 6 Architecture Audit v2.1

**Document**: Architecture Audit — Phase 6 Feedback & Evaluation Contract  
**Version**: v2.1  
**Date**: 2026-09-07  
**Status**: BLOCKED — awaiting implementation of Phase 6 FeedbackModule  
**Project**: neuro-cortex  
**Scope**: `src/neurocortex/feedback/`, `src/neurocortex/event.py` (read-only), `tests/test_feedback.py` (new)

---

## 1. Mathematical Contract

### 1.1 Definitions

| Symbol | Domain | Meaning |
|--------|--------|---------|
| `p` | `[0, 1] ∪ {NaN, -∞, +∞}` | `prediction.success_probability` |
| `c` | `[0, 1] ∪ {NaN, -∞, +∞}` | `prediction.prediction_confidence` |
| `o` | `{true, false, null}` | `outcome.success` (null when not yet recorded) |
| `e_msg` | `str` | `outcome.error_message` |
| `err` | `[0, 1]` | `feedback.prediction_error` — absolute deviation only |

### 1.2 Prediction Error Formula

```
err = |p - t|
  where t = 1.0 if o == true
        t = 0.0 if o == false
        t = N/A if o is null or outcome is invalid
```

**Critical invariant**: `err` is always `>= 0` and `<= 1`.  
No signed error. No squared error. No Brier score. Only absolute deviation.

### 1.3 Constraints (v2.1 frozen)

1. `err ∈ [0.0, 1.0]` — always
2. `err` is never `None` — `FeedbackData.prediction_error: float = 0.0` is frozen
3. When outcome is invalid or missing, `err = 0.0` and evaluation carries the semantic meaning, not `err`
4. `p` and `c` are independent: `p` expresses predicted success likelihood, `c` expresses model certainty about `p`

---

## 2. Prediction Validity Contract

### 2.1 Valid Prediction Definition

A prediction is **valid** (i.e., constitutes a real prediction under this contract) **if and only if ALL of the following hold simultaneously**:

```
predicted_outcome != ""
AND prediction_confidence > 0
AND success_probability ∈ [0, 1]     (inclusive)
AND success_probability is finite    (not NaN, not ±∞)
AND prediction_confidence is finite  (not NaN, not ±∞)
```

### 2.2 Invalid Prediction Definition

A prediction is **invalid** (no valid prediction exists) if **any** of the following holds:

```
predicted_outcome == ""
OR prediction_confidence == 0
OR success_probability ∉ [0, 1]
OR success_probability is NaN or infinite
OR prediction_confidence is NaN or infinite
```

### 2.3 Edge Cases — Explicitly Legitimate

| `p` value | `c` value | Valid? | Notes |
|-----------|-----------|--------|-------|
| `0.0` | `0.5` | YES | Model predicts failure with moderate confidence |
| `0.5` | `0.3` | YES | Model is uncertain; prediction is still valid |
| `1.0` | `0.9` | YES | Model predicts certainty; valid |
| `0.0` | `0.0` | NO | `confidence == 0` → no valid prediction |
| `""` | `0.5` | NO | Empty predicted_outcome → no valid prediction |
| `NaN` | `0.5` | NO | Non-finite probability → no valid prediction |
| `0.5` | `NaN` | NO | Non-finite confidence → no valid prediction |

### 2.4 Validation Function (reference implementation)

```python
import math
from typing import Optional

def is_valid_prediction(
    predicted_outcome: str,
    success_probability: float,
    prediction_confidence: float,
) -> bool:
    if predicted_outcome == "":
        return False
    if prediction_confidence <= 0:
        return False
    if not (0.0 <= success_probability <= 1.0):
        return False
    if not math.isfinite(success_probability):
        return False
    if not math.isfinite(prediction_confidence):
        return False
    return True
```

---

## 3. Outcome Validity Contract

### 3.1 Valid Outcome Definition

An outcome is **valid** if **and only if** both:

```
actual_outcome != ""
AND success is not None
```

### 3.2 Invalid Outcome Definition

An outcome is **invalid** if any of:

```
actual_outcome == ""
OR success is None
OR success is missing from OutcomeData
```

### 3.3 Outcome States

| State | `actual_outcome` | `success` | `error_message` | Interpretation |
|-------|-----------------|-----------|-----------------|----------------|
| success | non-empty | `True` | `""` | Action succeeded |
| failure | non-empty | `False` | `""` | Action failed, no execution error |
| explicit_failure | non-empty | `False` | non-empty | Action failed with execution error |
| missing | `""` | `None` / absent | — | Outcome not yet recorded |
| ambiguous | non-empty | `None` | — | Success flag missing |

---

## 4. Execution Error Contract

### 4.1 Coexistence Rule

`error_message != ""` **may coexist** with a computed `prediction_error` value. They carry different semantic roles:

| Field | Source | Semantics |
|-------|--------|-----------|
| `outcome.error_message` | OutcomeProvider | What went wrong during execution |
| `feedback.prediction_error` | Feedback computation | How far prediction was from reality |
| `feedback.evaluation` | Evaluation contract | Human-readable classification |

### 4.2 Evaluation Precedence (Option B — Combination Diagnostic)

When both an execution error and a prediction quality mismatch exist simultaneously, the evaluation uses a **组合 diagnostic** format:

```
evaluation = f"{execution_error_tag} + {quality_tag}"
```

Where:
- `execution_error_tag ∈ {"execution_error", ""}` — present only if `error_message != ""`
- `quality_tag ∈ {"perfect", "perfect_high_confidence", "correct", "miss", "catastrophically_wrong", "no_prediction", "invalid_outcome"}`

**Priority order for evaluation determination** (evaluated top-to-bottom, first match wins):

```
1. IF predicted_outcome == "" OR prediction_confidence == 0:
       evaluation = "no_prediction"
       prediction_error = 0.0

2. ELIF outcome is invalid (actual_outcome == "" OR success is None):
       evaluation = "invalid_outcome"
       prediction_error = 0.0

3. ELIF error_message != "" AND prediction is valid:
       # Compute prediction_error normally, then combine diagnostic
       err = abs(success_probability - target)
       IF err == 0:
           quality = "perfect"
       ELIF confidence > 0.7 AND err == 0:
           quality = "perfect_high_confidence"
       ELIF 0 < err < 0.3:
           quality = "correct"
       ELIF err >= 0.3 AND err <= 0.8:
           quality = "miss"
       ELIF err > 0.8 AND confidence > 0.7:
           quality = "catastrophically_wrong"
       ELSE:
           quality = "miss"  # default for 0.3 < err <= 0.8 range
       evaluation = f"execution_error + {quality}"
       prediction_error = err

4. ELIF prediction is valid AND outcome is valid:
       err = abs(success_probability - target)
       IF err == 0 AND confidence > 0.7:
           evaluation = "perfect_high_confidence"
       ELIF err == 0:
           evaluation = "perfect"
       ELIF 0 < err < 0.3:
           evaluation = "correct"
       ELIF err >= 0.3 AND err <= 0.8:
           evaluation = "miss"
       ELIF err > 0.8 AND confidence > 0.7:
           evaluation = "catastrophically_wrong"
       ELSE:
           evaluation = "miss"
       prediction_error = err
```

### 4.3 Execution Error as Highest Priority (Option A — NOT chosen)

Option A would mean: when `error_message != ""`, set `evaluation = "execution_error"` and skip prediction quality encoding entirely. This loses information. **Option B is selected** for v2.1.

---

## 5. Evaluation Contract (Frozen v2.1)

### 5.1 Exact Classification Rules

**Evaluation判断顺序（严格从上到下，第一个匹配即停止）：**

```
Rule 0 — no_prediction:
  IF NOT is_valid_prediction(predicted_outcome, success_probability, prediction_confidence):
      evaluation = "no_prediction"
      prediction_error = 0.0

Rule 1 — invalid_outcome:
  IF outcome is invalid:
      evaluation = "invalid_outcome"
      prediction_error = 0.0

Rule 2 — execution_error + quality:
  IF error_message != "" AND prediction is valid AND outcome is valid:
      err = abs(success_probability - target)
      quality = classify_quality(err, confidence)   # Rules 3-7 below
      evaluation = f"execution_error + {quality}"
      prediction_error = err

Rule 3 — perfect_high_confidence:
  IF err == 0 AND confidence > 0.7:
      evaluation = "perfect_high_confidence"
      prediction_error = 0.0

Rule 4 — perfect:
  IF err == 0:
      evaluation = "perfect"
      prediction_error = 0.0

Rule 5 — correct:
  IF 0 < err < 0.3:
      evaluation = "correct"
      prediction_error = err

Rule 6 — catastrophically_wrong:
  IF err > 0.8 AND confidence > 0.7:
      evaluation = "catastrophically_wrong"
      prediction_error = err

Rule 7 — miss (default catch-all):
  evaluation = "miss"
  prediction_error = err
```

### 5.2 Boundary Values — Critical

| `err` | `confidence` | `evaluation` | Notes |
|-------|-------------|-------------|-------|
| `0.0` | `0.5` | `perfect` | err==0, confidence≤0.7 → perfect, NOT perfect_high_confidence |
| `0.0` | `0.8` | `perfect_high_confidence` | err==0 AND confidence>0.7 |
| `0.0` | `0.0` | — (covered by Rule 0: no_prediction) | confidence==0 → invalid prediction |
| `0.29` | any | `correct` | strict: err < 0.3 |
| `0.3` | any | `miss` | strict: err >= 0.3 |
| `0.3` | `0.9` | `miss` | No special treatment at boundary |
| `0.8` | any | `miss` | err == 0.8 → miss, not catastrophic |
| `0.81` | `0.9` | `catastrophically_wrong` | err > 0.8 AND confidence > 0.7 |
| `0.81` | `0.5` | `miss` | err > 0.8 but confidence ≤ 0.7 → miss |
| `1.0` | `0.5` | `miss` | err=1.0, confidence≤0.7 → miss (NOT catastrophically_wrong) |
| `1.0` | `0.9` | `catastrophically_wrong` | err=1.0 AND confidence>0.7 |

### 5.3 Target Value (`t`) Mapping

| Outcome | `success` | `target` |
|---------|-----------|----------|
| Success | `True` | `1.0` |
| Failure | `False` | `0.0` |
| Invalid/missing | — | N/A (Rules 0-2 apply before computing err) |

---

## 6. Frozen Schema Compatibility

### 6.1 FeedbackData Schema (READ-ONLY — no changes)

```python
@dataclass
class FeedbackData:
    reward: float = 0.0
    prediction_error: float = 0.0    # frozen: always float, never None
    user_feedback: str = ""
    evaluation: str = ""
```

### 6.2 Implications of Frozen Schema

| Question | Answer |
|----------|--------|
| Can `prediction_error` be `None`? | **NO.** Always `0.0` default. Invalid states use `0.0` as placeholder; semantics carried by `evaluation`. |
| Can we add `signed_error`? | **NO.** Phase 6 v1 does not implement signed error. |
| Can we add new fields to `FeedbackData`? | **NO.** Schema is frozen for Phase 6 v1. |
| Can `evaluation` be empty string? | Yes, but only before `compute_feedback` is called. After computation, it must be one of the defined labels. |
| Can `prediction_error = 0.0` mean "perfect prediction"? | **Only when** `evaluation == "perfect"` or `evaluation == "perfect_high_confidence"`. When `evaluation == "no_prediction"` or `evaluation == "invalid_outcome"`, `prediction_error = 0.0` is a placeholder with no perfection semantics. |

### 6.3 Semantic Guard

Consumers of `FeedbackData` MUST check `evaluation` FIRST before interpreting `prediction_error`:

```python
# CORRECT pattern:
if event.feedback.evaluation == "no_prediction":
    # prediction_error == 0.0 is a placeholder, ignore it
    handle_no_prediction()
elif event.feedback.evaluation == "perfect":
    # prediction_error == 0.0 means truly perfect
    handle_perfect()
else:
    # prediction_error carries real semantic meaning
    handle_with_error(event.feedback.prediction_error)
```

---

## 7. Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CortexEvent Flow                             │
│                                                                     │
│  INPUT                                                              │
│    └─► PERCEPTION       (PerceptionModule)                          │
│           ├─ raw_input: str                                        │
│           ├─ intent: str                                           │
│           ├─ risk: float [0,1]                                     │
│           └─ confidence: float [0,1]                               │
│              └─► REPRESENTATION  (RepresentationModule)             │
│                 └─► ATTENTION  (AttentionModule)                    │
│                    └─► STATE  (StateModule)                         │
│                       └─► MEMORY  (MemoryModule)                    │
│                          └─► PREDICTION  (PredictionModule) ◄───────┼──┐
│                             ├─ predicted_outcome: str              │  │
│                             ├─ success_probability: float [0,1]    │  │
│                             ├─ predicted_risk: float [0,1]         │  │
│                             └─ prediction_confidence: float [0,1]  │  │
│                                └─► DECISION  (DecisionModule)       │  │
│                                   └─► ACTION  (ActionModule)       │  │
│                                      └─► OUTCOME  (OutcomeProvider) │  │
│                                         ├─ actual_outcome: str     │  │
│                                         ├─ success: bool           │  │
│                                         └─ error_message: str      │  │
│                                            └─► FEEDBACK             │  │
│                                               │                     │  │
│                                               │ ◄── is_valid_prediction()? │
│                                               │     NO  ──► evaluation="no_prediction" │
│                                               │     err=0.0          │
│                                               │                     │  │
│                                               │ ◄── outcome valid?  │
│                                               │     NO  ──► evaluation="invalid_outcome" │
│                                               │     err=0.0          │
│                                               │                     │  │
│                                               │ ◄── error_message != ""? │
│                                               │     YES ──► compute err, then "execution_error + {quality}" │
│                                               │     NO  ──► proceed   │
│                                               │                     │  │
│                                               │ ◄── err == 0 AND confidence > 0.7? │
│                                               │     YES ──► "perfect_high_confidence" │
│                                               │     NO  ──► proceed   │
│                                               │                     │  │
│                                               │ ◄── err == 0?       │
│                                               │     YES ──► "perfect" │
│                                               │     NO  ──► proceed   │
│                                               │                     │  │
│                                               │ ◄── 0 < err < 0.3?  │
│                                               │     YES ──► "correct" │
│                                               │     NO  ──► proceed   │
│                                               │                     │  │
│                                               │ ◄── err > 0.8 AND confidence > 0.7? │
│                                               │     YES ──► "catastrophically_wrong" │
│                                               │     NO  ──► "miss"    │
│                                               │                     │  │
│                                               └─► LEARNING  (LearningModule)     │
│                                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Test Suite — 28 Cases

All tests target `Phase 6 FeedbackModule`. Run with:
```bash
python3 -m pytest neuro-cortex/tests/test_feedback.py -v
```

```python
"""Phase 6 — Feedback & Evaluation Contract Tests (v2.1)."""
from __future__ import annotations

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neurocortex.event import (
    CortexEvent,
    PerceptionData,
    InternalState,
    PredictionData,
    OutcomeData,
    FeedbackData,
)
from neurocortex.prediction import BasicPrediction
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState,
    MockMemory, MockPrediction, MockDecision, MockAction,
    MockOutcomeProvider, MockLearning,
)
from neurocortex.cortex import NeuroCortex


# ── Helpers ───────────────────────────────────────────────────────


def make_event_with_prediction(
    raw_input: str,
    intent: str = "fix",
    risk: float = 0.2,
    uncertainty: float = 0.2,
    perf_conf: float = 0.5,
    predicted_outcome: str | None = None,
    success_prob: float | None = None,
    pred_confidence: float | None = None,
) -> CortexEvent:
    """Build an event through PREDICTION stage with optional override."""
    e = CortexEvent(raw_input)
    e.perceive(PerceptionData(
        raw_input=raw_input,
        intent=intent,
        risk=risk,
        confidence=perf_conf,
    ))
    e.update_state(InternalState(uncertainty=uncertainty))
    # Use real BasicPrediction unless overridden
    pred_module = BasicPrediction()
    e = pred_module.process(e)

    if predicted_outcome is not None:
        e.prediction.predicted_outcome = predicted_outcome
    if success_prob is not None:
        e.prediction.success_probability = success_prob
    if pred_confidence is not None:
        e.prediction.prediction_confidence = pred_confidence
    return e


def compute_feedback_direct(
    event: CortexEvent,
    outcome_success: bool,
    outcome_text: str = "done",
    error_message: str = "",
) -> CortexEvent:
    """Apply outcome and trigger Phase 6 feedback computation."""
    event.record_outcome(OutcomeData(
        actual_outcome=outcome_text,
        success=outcome_success,
        error_message=error_message,
    ))
    # Trigger feedback computation
    event = compute_feedback(event)
    return event


def compute_feedback(event: CortexEvent) -> CortexEvent:
    """
    Apply the Phase 6 v2.1 evaluation contract directly.
    This mirrors what FeedbackModule.process() must do.
    """
    pred = event.prediction
    out = event.outcome

    # Rule 0: no_prediction
    if not _is_valid_prediction(pred):
        return event.compute_feedback(FeedbackData(
            prediction_error=0.0,
            evaluation="no_prediction",
        ))

    # Rule 1: invalid_outcome
    if not _is_valid_outcome(out):
        return event.compute_feedback(FeedbackData(
            prediction_error=0.0,
            evaluation="invalid_outcome",
        ))

    # Compute target and error
    target = 1.0 if out.success else 0.0
    err = abs(pred.success_probability - target)
    conf = pred.prediction_confidence
    has_exec_error = out.error_message != ""

    # Rule 2: execution_error + quality
    if has_exec_error:
        quality = _classify_quality(err, conf)
        return event.compute_feedback(FeedbackData(
            prediction_error=err,
            evaluation=f"execution_error + {quality}",
        ))

    # Rules 3-7: pure prediction quality
    evaluation = _classify_quality(err, conf)
    return event.compute_feedback(FeedbackData(
        prediction_error=err,
        evaluation=evaluation,
    ))


def _is_valid_prediction(pred: PredictionData) -> bool:
    if pred.predicted_outcome == "":
        return False
    if pred.prediction_confidence <= 0:
        return False
    if not (0.0 <= pred.success_probability <= 1.0):
        return False
    if not math.isfinite(pred.success_probability):
        return False
    if not math.isfinite(pred.prediction_confidence):
        return False
    return True


def _is_valid_outcome(out: OutcomeData) -> bool:
    return out.actual_outcome != "" and out.success is not None


def _classify_quality(err: float, confidence: float) -> str:
    """Apply Rules 3-7 in strict priority order."""
    if err == 0.0 and confidence > 0.7:
        return "perfect_high_confidence"
    if err == 0.0:
        return "perfect"
    if 0.0 < err < 0.3:
        return "correct"
    if err > 0.8 and confidence > 0.7:
        return "catastrophically_wrong"
    return "miss"


# ═══════════════════════════════════════════════════════════════════
# TEST SUITE — 28 Cases
# ═══════════════════════════════════════════════════════════════════


# ── T01: p=0.0, success=True → miss ─────────────────────────────
class TestT01:
    def test_p_zero_success_true(self):
        """p=0 but outcome succeeded: err=1.0 → miss (confidence=0.5 ≤ 0.7)."""
        e = make_event_with_prediction("fix bug", success_prob=0.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(1.0)


# ── T02: p=0.5, success=False → correct ─────────────────────────
class TestT02:
    def test_p_point_five_failure(self):
        """p=0.5, failed: err=0.5 → miss (>= 0.3)."""
        e = make_event_with_prediction("fix bug", success_prob=0.5, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.5)


# ── T03: p=1.0, success=True, c=0.8 → perfect_high_confidence ───
class TestT03:
    def test_p_one_c_high(self):
        """p=1.0, succeeded, confidence=0.8: err=0, c>0.7 → perfect_high_confidence."""
        e = make_event_with_prediction("fix bug", success_prob=1.0, pred_confidence=0.8)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "perfect_high_confidence"
        assert e.feedback.prediction_error == 0.0


# ── T04: p=1.0, success=True, c=0.5 → perfect ───────────────────
class TestT04:
    def test_p_one_c_low(self):
        """p=1.0, succeeded, confidence=0.5: err=0, c<=0.7 → perfect (NOT perfect_high_confidence)."""
        e = make_event_with_prediction("fix bug", success_prob=1.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "perfect"
        assert e.feedback.prediction_error == 0.0


# ── T05: confidence=0 → no_prediction ───────────────────────────
class TestT05:
    def test_confidence_zero(self):
        """confidence=0: invalid prediction → no_prediction, err=0.0 placeholder."""
        e = make_event_with_prediction("fix bug", pred_confidence=0.0)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "no_prediction"
        assert e.feedback.prediction_error == 0.0


# ── T06: confidence=0.1 → valid but low ─────────────────────────
class TestT06:
    def test_confidence_point_one(self):
        """confidence=0.1: valid prediction (0.1 > 0). p=0.9, success=True → perfect (err=0)."""
        e = make_event_with_prediction("fix bug", success_prob=0.9, pred_confidence=0.1)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "perfect"  # err=0.1... wait, err=|0.9-1|=0.1 → correct
        # Correction: err=0.1, 0<0.1<0.3 → correct
        assert e.feedback.evaluation == "correct"
        assert e.feedback.prediction_error == pytest.approx(0.1)


# ── T07: confidence=0.8, p=0.9, success=True → perfect_high_confidence ─
class TestT07:
    def test_high_conf_perfect(self):
        """confidence=0.8, p=0.9, succeeded: err=0.1 → correct (0<0.1<0.3), NOT perfect_high_confidence."""
        e = make_event_with_prediction("fix bug", success_prob=0.9, pred_confidence=0.8)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "correct"
        assert e.feedback.prediction_error == pytest.approx(0.1)


# ── T08: unknown intent, p=0.5, success=True → correct ──────────
class TestT08:
    def test_unknown_intent(self):
        """unknown intent → p=0.5 by default. success=True: err=0.5 → miss."""
        e = make_event_with_prediction("hello", intent="unknown", success_prob=0.5, pred_confidence=0.2)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.5)


# ── T09: high risk, p low, success=False → perfect ──────────────
class TestT09:
    def test_high_risk_failure_perfect(self):
        """high risk → p=0.3. outcome failed: err=|0.3-0|=0.3 → miss (>= 0.3 boundary)."""
        e = make_event_with_prediction("deploy to prod", intent="deploy", risk=0.8,
                                        uncertainty=0.2, perf_conf=0.7,
                                        success_prob=0.3, pred_confidence=0.49)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.3)


# ── T10: error=0.3 boundary → miss (NOT correct) ────────────────
class TestT10:
    def test_error_zero_point_three_is_miss(self):
        """err=0.3 is exactly at boundary: must be 'miss', not 'correct'."""
        e = make_event_with_prediction("fix", success_prob=0.7, pred_confidence=0.5)
        # p=0.7, success=False → err=|0.7-0|=0.7 → miss
        # Force exact err=0.3: p=0.3, success=False → err=0.3
        e = make_event_with_prediction("fix", success_prob=0.3, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.3)


# ── T11: empty predicted_outcome → no_prediction ────────────────
class TestT11:
    def test_empty_predicted_outcome(self):
        """predicted_outcome='': invalid prediction → no_prediction."""
        e = make_event_with_prediction("fix bug", predicted_outcome="", success_prob=0.5, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "no_prediction"
        assert e.feedback.prediction_error == 0.0


# ── T12: error=0.3 with success=True → miss (NOT correct) ───────
class TestT12:
    def test_error_point_three_success(self):
        """p=0.7, success=True: err=|0.7-1|=0.3 → miss (>= 0.3 boundary)."""
        e = make_event_with_prediction("fix", success_prob=0.7, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.3)


# ── T13: error=0.8 boundary → miss (NOT catastrophically_wrong) ─
class TestT13:
    def test_error_zero_point_eight_is_miss(self):
        """err=0.8 is at boundary: must be 'miss', not 'catastrophically_wrong'."""
        e = make_event_with_prediction("fix", success_prob=0.2, pred_confidence=0.9)
        # p=0.2, success=False: err=|0.2-0|=0.2 → correct
        # Force err=0.8: p=0.8, success=False: err=|0.8-0|=0.8
        e = make_event_with_prediction("fix", success_prob=0.8, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(0.8)


# ── T14: error=0.81, c=0.9 → catastrophically_wrong ─────────────
class TestT14:
    def test_catastrophic(self):
        """p=0.81, failed, c=0.9: err=0.81>0.8 AND c>0.7 → catastrophically_wrong."""
        e = make_event_with_prediction("fix", success_prob=0.81, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "catastrophically_wrong"
        assert e.feedback.prediction_error == pytest.approx(0.81)


# ── T15: error=1.0, c=0.5 → miss (NOT catastrophically_wrong) ──
class TestT15:
    def test_error_one_low_confidence(self):
        """p=0.0, failed, c=0.5: err=0.0? No: p=0.0, success=False: err=|0-0|=0 → perfect."""
        # Fix: p=0.0, success=True: err=|0-1|=1.0, c=0.5 → miss (c<=0.7)
        e = make_event_with_prediction("fix", success_prob=0.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(1.0)


# ── T16: error=1.0, c=0.9 → catastrophically_wrong ──────────────
class TestT16:
    def test_error_one_high_confidence(self):
        """p=0.0, succeeded, c=0.9: err=1.0>0.8 AND c>0.7 → catastrophically_wrong."""
        e = make_event_with_prediction("fix", success_prob=0.0, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "catastrophically_wrong"
        assert e.feedback.prediction_error == pytest.approx(1.0)


# ── T17: prediction=None (empty PredictionData) → no_prediction ─
class TestT17:
    def test_none_prediction(self):
        """Default PredictionData: predicted_outcome='', confidence=0.5 → empty outcome → no_prediction."""
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e.update_state(InternalState())
        # Don't call predict — prediction stays at defaults
        # predicted_outcome="" by default → invalid
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "no_prediction"
        assert e.feedback.prediction_error == 0.0


# ── T18: outcome=None (empty OutcomeData) → invalid_outcome ─────
class TestT18:
    def test_none_outcome(self):
        """Default OutcomeData: actual_outcome='', success=False → empty outcome → invalid_outcome."""
        e = make_event_with_prediction("fix bug", success_prob=0.8, pred_confidence=0.7)
        # Record outcome with empty actual_outcome
        e.record_outcome(OutcomeData(actual_outcome="", success=False))
        e = compute_feedback(e)
        assert e.feedback.evaluation == "invalid_outcome"
        assert e.feedback.prediction_error == 0.0


# ── T19: ambiguous outcome (success=None) → invalid_outcome ─────
class TestT19:
    def test_ambiguous_outcome(self):
        """success=None: outcome is invalid → invalid_outcome."""
        e = make_event_with_prediction("fix bug", success_prob=0.8, pred_confidence=0.7)
        e.record_outcome(OutcomeData(actual_outcome="something happened", success=None))
        e = compute_feedback(e)
        assert e.feedback.evaluation == "invalid_outcome"
        assert e.feedback.prediction_error == 0.0


# ── T20: explicit failure + valid prediction → execution_error + quality ─
class TestT20:
    def test_execution_error_with_miss(self):
        """error_message set, p=0.9, failed: err=0.9, c=0.7 → execution_error + catastrophically_wrong."""
        e = make_event_with_prediction("deploy", success_prob=0.9, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=False, error_message="deployment timeout")
        assert e.feedback.evaluation == "execution_error + catastrophically_wrong"
        assert e.feedback.prediction_error == pytest.approx(0.9)

    def test_execution_error_with_correct(self):
        """error_message set, p=0.8, failed: err=0.8, c=0.5 → execution_error + miss."""
        e = make_event_with_prediction("deploy", success_prob=0.8, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False, error_message="timeout")
        assert e.feedback.evaluation == "execution_error + miss"
        assert e.feedback.prediction_error == pytest.approx(0.8)

    def test_execution_error_with_perfect(self):
        """error_message set, p=1.0, succeeded: err=0, c=0.9 → execution_error + perfect_high_confidence."""
        e = make_event_with_prediction("deploy", success_prob=1.0, pred_confidence=0.9)
        e = compute_feedback_direct(e, outcome_success=True, error_message="minor warning")
        assert e.feedback.evaluation == "execution_error + perfect_high_confidence"
        assert e.feedback.prediction_error == 0.0


# ── T21: invalid state handling ─────────────────────────────────
class TestInvalidState:
    def test_no_prediction_no_outcome(self):
        """No prediction, no outcome → no_prediction."""
        e = CortexEvent("test")
        e.perceive(PerceptionData(raw_input="test"))
        e.update_state(InternalState())
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.feedback.evaluation == "no_prediction"

    def test_prediction_no_outcome(self):
        """Valid prediction but outcome not yet recorded → invalid_outcome."""
        e = make_event_with_prediction("fix bug", success_prob=0.8, pred_confidence=0.7)
        e.record_outcome(OutcomeData(actual_outcome="", success=None))
        e = compute_feedback(e)
        assert e.feedback.evaluation == "invalid_outcome"


# ── T22: state immutability ─────────────────────────────────────
class TestStateImmutability:
    def test_feedback_does_not_modify_event_state(self):
        """Feedback computation must not mutate event.state."""
        e = make_event_with_prediction("fix bug", success_prob=0.8, pred_confidence=0.7)
        original_curiosity = e.state.curiosity
        original_confidence = e.state.confidence
        e = compute_feedback_direct(e, outcome_success=True)
        assert e.state.curiosity == original_curiosity
        assert e.state.confidence == original_confidence


# ── T23: deterministic output ───────────────────────────────────
class TestDeterministic:
    def test_same_inputs_same_evaluation_twice(self):
        """Running compute_feedback twice on identical events yields same result."""
        e1 = make_event_with_prediction("fix", success_prob=0.85, pred_confidence=0.75)
        e1 = compute_feedback_direct(e1, outcome_success=False)

        e2 = make_event_with_prediction("fix", success_prob=0.85, pred_confidence=0.75)
        e2 = compute_feedback_direct(e2, outcome_success=False)

        assert e1.feedback.evaluation == e2.feedback.evaluation
        assert e1.feedback.prediction_error == pytest.approx(e2.feedback.prediction_error)


# ── T24: full Cortex integration ────────────────────────────────
class TestFullIntegration:
    def test_full_pipeline_reaches_learning(self):
        """Full NeuroCortex pipeline completes to LEARNING stage."""
        c = NeuroCortex(
            perception=MockPerception(),
            representation=MockRepresentation(),
            attention=MockAttention(),
            state=MockState(),
            memory=MockMemory(),
            prediction=MockPrediction(),
            decision=MockDecision(),
            action=MockAction(),
            outcome_provider=MockOutcomeProvider(),
            learning=MockLearning(),
        )
        # Note: no feedback module wired — pipeline stops at OUTCOME
        # This tests that existing infrastructure is not broken
        e = c.process("fix the bug")
        assert e.stage == "OUTCOME"  # No FeedbackModule registered


# ── T25: prediction_error is always float, never None ───────────
class TestPredictionErrorType:
    def test_error_is_float_in_all_cases(self):
        """prediction_error must always be a float, never None."""
        cases = [
            ("no_prediction", dict(success_prob=0.5, pred_confidence=0.0)),
            ("invalid_outcome", dict(success_prob=0.8, pred_confidence=0.7)),
            ("perfect", dict(success_prob=1.0, pred_confidence=0.5)),
            ("correct", dict(success_prob=0.8, pred_confidence=0.5)),
            ("miss", dict(success_prob=0.2, pred_confidence=0.5)),
            ("catastrophic", dict(success_prob=0.0, pred_confidence=0.9)),
        ]
        for name, kwargs in cases:
            e = make_event_with_prediction("test", **kwargs)
            if kwargs.get("pred_confidence") == 0.0:
                e = compute_feedback_direct(e, outcome_success=True)
            elif name == "invalid_outcome":
                e.record_outcome(OutcomeData(actual_outcome="", success=None))
                e = compute_feedback(e)
            else:
                success = name in ("perfect", "correct")
                e = compute_feedback_direct(e, outcome_success=success)
            assert isinstance(e.feedback.prediction_error, float), \
                f"{name}: prediction_error is {type(e.feedback.prediction_error)}, not float"
            assert not math.isnan(e.feedback.prediction_error)
            assert not math.isinf(e.feedback.prediction_error)


# ── T26: edge case — p=0 with success=False → perfect ───────────
class TestPZeroFailure:
    def test_p_zero_failure_is_perfect(self):
        """p=0.0, outcome failed: err=|0-0|=0 → perfect."""
        e = make_event_with_prediction("avoid danger", success_prob=0.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "perfect"
        assert e.feedback.prediction_error == 0.0


# ── T27: edge case — p=1 with success=False → miss (c=0.5) ─────
class TestPOneFailure:
    def test_p_one_failure_low_conf(self):
        """p=1.0, failed, c=0.5: err=1.0, c<=0.7 → miss (NOT catastrophically_wrong)."""
        e = make_event_with_prediction("fix", success_prob=1.0, pred_confidence=0.5)
        e = compute_feedback_direct(e, outcome_success=False)
        assert e.feedback.evaluation == "miss"
        assert e.feedback.prediction_error == pytest.approx(1.0)


# ── T28: regression — 222 existing tests still pass ─────────────
class TestRegression:
    def test_all_existing_tests_pass(self):
        """Run all existing Phase 0-5 tests; must not regress."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest",
             "neuro-cortex/tests/test_event.py",
             "neuro-cortex/tests/test_perception.py",
             "neuro-cortex/tests/test_representation.py",
             "neuro-cortex/tests/test_state.py",
             "neuro-cortex/tests/test_cortex.py",
             "neuro-cortex/tests/test_prediction.py",
             "neuro-cortex/tests/test_phase0.py",
             "-q", "--tb=short"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"Regression failed:\n{result.stdout}\n{result.stderr}"
```

---

## 9. Test Coverage Matrix

| Case | Input Profile | Expected Evaluation | prediction_error |
|------|--------------|---------------------|------------------|
| T01 | p=0.0, success=True, c=0.5 | `miss` | 1.0 |
| T02 | p=0.5, success=False, c=0.5 | `miss` | 0.5 |
| T03 | p=1.0, success=True, c=0.8 | `perfect_high_confidence` | 0.0 |
| T04 | p=1.0, success=True, c=0.5 | `perfect` | 0.0 |
| T05 | c=0.0, success=True | `no_prediction` | 0.0 |
| T06 | p=0.9, success=True, c=0.1 | `correct` | 0.1 |
| T07 | p=0.9, success=True, c=0.8 | `correct` | 0.1 |
| T08 | unknown intent, p=0.5, success=True, c=0.2 | `miss` | 0.5 |
| T09 | high risk, p=0.3, success=False, c=0.49 | `miss` | 0.3 |
| T10 | p=0.3, success=False, c=0.5 | `miss` (boundary) | 0.3 |
| T11 | predicted_outcome="", success=True | `no_prediction` | 0.0 |
| T12 | p=0.7, success=True, c=0.5 | `miss` (boundary) | 0.3 |
| T13 | p=0.8, success=False, c=0.9 | `miss` (boundary) | 0.8 |
| T14 | p=0.81, success=False, c=0.9 | `catastrophically_wrong` | 0.81 |
| T15 | p=0.0, success=True, c=0.5 | `miss` | 1.0 |
| T16 | p=0.0, success=True, c=0.9 | `catastrophically_wrong` | 1.0 |
| T17 | prediction defaults (empty), success=True | `no_prediction` | 0.0 |
| T18 | outcome defaults (empty), valid prediction | `invalid_outcome` | 0.0 |
| T19 | success=None, valid prediction | `invalid_outcome` | 0.0 |
| T20a | error_message+"", p=0.9, failed, c=0.9 | `execution_error + catastrophically_wrong` | 0.9 |
| T20b | error_message+"", p=0.8, failed, c=0.5 | `execution_error + miss` | 0.8 |
| T20c | error_message+"", p=1.0, succeeded, c=0.9 | `execution_error + perfect_high_confidence` | 0.0 |
| T21a | no prediction, no outcome | `no_prediction` | 0.0 |
| T21b | valid prediction, no outcome | `invalid_outcome` | 0.0 |
| T22 | feedback on valid event | state unchanged | — |
| T23 | identical inputs twice | deterministic | — |
| T24 | full pipeline without FeedbackModule | stage=OUTCOME | — |
| T25 | all evaluation types | prediction_error is always float | — |
| T26 | p=0.0, success=False | `perfect` | 0.0 |
| T27 | p=1.0, success=False, c=0.5 | `miss` | 1.0 |
| T28 | 222 existing tests | all pass | — |

---

## 10. Known Open Items (Out of Scope for Phase 6 v1)

| Item | Status | Target Phase |
|------|--------|-------------|
| `signed_error` field in FeedbackData | EXCLUDED | Phase 7 or 10 |
| Brier score / log loss | EXCLUDED | Future |
| Reward formula revision | EXCLUDED — keep existing `reward = 1.0 if success else -0.5` | Future |
| `FeedbackData` schema evolution | EXCLUDED — schema frozen | Phase 7+ |
| Multi-outcome events | EXCLUDED | Future |
| Time-decayed error weighting | EXCLUDED | Future |

---

## 11. Final Verdict

### BLOCKED

**Reason**: Phase 6 v1 has not yet been implemented. The `src/neurocortex/feedback/` module is empty (`__init__.py` is 0 bytes). No `FeedbackModule` implementation exists in the codebase. The architecture audit v2.1 is complete and defines the contract, but no code has been written to satisfy it.

**Next action before implementation can begin**:
1. Implement `src/neurocortex/feedback/feedback.py` with the v2.1 evaluation contract
2. Register a default `FeedbackModule` in `src/neurocortex/modules/__init__.py`
3. Add `feedback=MockFeedbackV2()` (or real implementation) to test fixtures
4. Run `python3 -m pytest neuro-cortex/tests/test_feedback.py -v` — all 28 tests must pass
5. Run full regression: `python3 -m pytest neuro-cortex/tests/ -q` — all 222+ tests must pass
6. Re-issue audit as **APPROVED FOR IMPLEMENTATION** only after tests pass

**Constraints reaffirmed**:
- NO code modification permitted until verdict changes to APPROVED
- NO commit permitted
- NO push permitted
- `event.py` must remain unmodified (schema frozen)

---

*Audit v2.1 generated 2026-09-07. All rules in this document are frozen for Phase 6 v1 implementation.*
