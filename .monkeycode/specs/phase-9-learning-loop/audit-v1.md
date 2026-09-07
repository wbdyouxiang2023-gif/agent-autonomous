# Phase 9 Architecture Audit v1 — Learning Loop Closure

**Document**: Architecture Audit — Phase 9 Learning → State Closure  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: APPROVED FOR PHASE 9 IMPLEMENTATION  
**Project**: neuro-cortex  
**Baseline**: Commit 00ac18f (Phase 8 frozen), 334 PASS / 0 FAIL

---

## 1. Current Architecture

### 1.1 True Call Chain

```
Event 1:
  raw_input
    ↓
  Cortex.process()
    ↓
  event.state = CortexState.to_internal_state()  # Snapshot A
    ↓
  [Pipeline: Perception → Representation → Attention → State → Memory → 
            Prediction → Decision → Action → Outcome → Feedback → Learning]
    ↓
  CortexState.update_from_event(event)           # Learn from Event 1
    ↓
  Event 1 ends

Event 2:
  raw_input
    ↓
  Cortex.process()
    ↓
  event.state = CortexState.to_internal_state()  # Snapshot B (should include learning)
    ↓
  [Pipeline...]
    ↓
  CortexState.update_from_event(event)           # Learn from Event 2
```

### 1.2 Source of Truth

**CortexState is the authoritative persistent state.**

| Component | Role | Source of Truth? |
|-----------|------|------------------|
| `CortexState` | Persistent session state | **YES** — authoritative |
| `event.state` | Per-event snapshot | NO — derived from CortexState |
| `StateModule` | Pipeline adapter | NO — should not compute state |

### 1.3 Current Relationship

```
CortexState (persistent)
    ↓ to_internal_state()
event.state (per-event snapshot)
    ↓ pipeline processing
CortexState.update_from_event() (learning)
```

This is **correct by design**. The issue is that MockState breaks this flow.

---

## 2. Source of Truth — Confirmed

**CortexState is the single source of truth for persistent state.**

Evidence:
- `cortex.py:93`: `event.state = self._state_store.to_internal_state()` — snapshot from CortexState
- `cortex.py:100`: `self._state_store.update_from_event(event)` — commit learning to CortexState
- `cortex_state.py:121-129`: `to_internal_state()` creates one-way projection

**Verification**: BasicStateModule preserves CortexState values:
```
Event 1: CortexState(0.20/0.50) → Event.state(0.20/0.50) → CortexState(0.15/0.55)
Event 2: CortexState(0.15/0.55) → Event.state(0.15/0.55) → CortexState(0.10/0.60)
Event 3: CortexState(0.10/0.60) → Event.state(0.10/0.60) → CortexState(0.05/0.65)
```

This proves the **CortexState ↔ event.state snapshot mechanism works correctly**.

---

## 3. StateModule Audit

### 3.1 BasicStateModule (Production)

```python
class BasicStateModule(StateModule):
    def process(self, event: CortexEvent) -> CortexEvent:
        if not event.state:
            event.state = InternalState()
        event.update_state()
        return event
```

**Behavior**: Pure passthrough. Does NOT compute state values. Relies on CortexState snapshot.

**Status**: ✅ CORRECT

### 3.2 MockState (Tests)

```python
class MockState(StateModule):
    def process(self, event: CortexEvent) -> CortexEvent:
        novelty = min(len(event.raw_input) / 100.0, 1.0)
        event.update_state(InternalState(
            curiosity=0.5 + novelty * 0.3,
            motivation=0.6,
            confidence=0.5,
            uncertainty=1.0 - novelty,
        ))
        return event
```

**Behavior**: Computes state from raw_input length, **ignoring CortexState**.

**Status**: ❌ BREAKS LEARNING LOOP

### 3.3 Root Cause

When MockState runs, it overwrites `event.state` with values computed from input length:
- Input "fix a bug" (9 chars) → novelty=0.09 → uncertainty=0.91
- This happens for EVERY event, regardless of CortexState learning

Result:
```
Event 1: CortexState learns → uncertainty drops to 0.15
Event 2: MockState resets event.state → uncertainty jumps back to 0.91
         BasicPrediction sees 0.91 → p=0.50 (high uncertainty path)
```

The learning loop is broken at the **StateModule level**, not at CortexState level.

---

## 4. Cross-Event Experiment Results

### Experiment A: BasicStateModule + Continuous Success

```
Event 1: CortexState(0.20→0.15), Event.state(0.20), Prediction.p=0.80
Event 2: CortexState(0.15→0.10), Event.state(0.15), Prediction.p=0.80
Event 3: CortexState(0.10→0.05), Event.state(0.10), Prediction.p=0.80
```

**Result**: ✅ Learning propagates. Event.state correctly inherits CortexState.

### Experiment B: MockState + Continuous Success

```
Event 1: CortexState(0.20→0.15), Event.state(0.91), Prediction.p=0.50
Event 2: CortexState(0.15→0.10), Event.state(0.91), Prediction.p=0.50
Event 3: CortexState(0.10→0.05), Event.state(0.91), Prediction.p=0.50
```

**Result**: ❌ Learning fails to propagate. Event.state always reset to 0.91.

### Experiment C: Multi-Cortex Isolation

```
Cortex 1: Event 1 → unc=0.15, conf=0.55
Cortex 2: Event 1 → unc=0.15, conf=0.55
Cortex 1: Event 2 → unc=0.10, conf=0.60
Cortex 2: Event 2 → unc=0.10, conf=0.60
```

**Result**: ✅ Independent instances, no cross-contamination.

### Experiment D: Continuous Failure

```
CortexState after 5 failures: unc=0.45, conf=0.00
```

**Result**: ✅ Failure learning works correctly.

---

## 5. Root Cause

**File**: `neuro-cortex/src/neurocortex/modules/__init__.py:82-93`  
**Class**: `MockState`  
**Method**: `process()`  
**Logic**: Computes `uncertainty = 1.0 - novelty` from input length, ignoring CortexState.

**Why 334 tests missed it**:
- All tests use MockState
- Tests verify CortexState learning indirectly (test_state.py passes)
- Tests verify event.state exists but don't check if it inherits CortexState
- No test verifies that Prediction sees learned uncertainty across events

**The gap**: Tests check "does CortexState learn?" but not "does learned state affect next Event?"

---

## 6. Minimal Fix

### 6.1 Fix MockState

Modify MockState to preserve CortexState values while adding mock behavior:

```python
class MockState(StateModule):
    """Mock state: preserves learned state, adds mock novelty signal."""

    def process(self, event: CortexEvent) -> CortexEvent:
        # Preserve CortexState learning
        if event.state is None:
            event.state = InternalState()
        
        # Add mock novelty on top of learned state
        novelty = min(len(event.raw_input) / 100.0, 1.0)
        event.state.curiosity = 0.5 + novelty * 0.3
        event.state.motivation = 0.6
        
        # Do NOT override uncertainty/confidence — let CortexState drive them
        event.update_state()
        return event
```

### 6.2 Alternative: Use BasicStateModule in Tests

Change test fixtures to use BasicStateModule instead of MockState:

```python
@pytest.fixture
def full_cortex():
    return NeuroCortex(
        ...
        state=BasicStateModule(),  # Changed from MockState()
        ...
    )
```

**Recommendation**: Use Option 2 (BasicStateModule) for production-like tests, keep MockState for isolated unit tests.

---

## 7. Contract Preservation

| Phase | Contract | Status |
|-------|----------|--------|
| Phase 0-3 | Perception, Representation, Attention, State schema | ✅ Unchanged |
| Phase 4 | CortexState persistence | ✅ Unchanged |
| Phase 5 | Prediction using state.uncertainty | ✅ Unchanged |
| Phase 6 | Feedback evaluation contract | ✅ Unchanged |
| Phase 7 | Decision rules | ✅ Unchanged |
| Phase 8 | Action symbolic execution | ✅ Unchanged |

**No schema changes required.**

---

## 8. New Tests (Phase 9)

### Test 1: Success Learning Propagates
```python
def test_success_learning_propagates_to_next_event(self):
    c = NeuroCortex(state=BasicStateModule(), ...)
    e1 = c.process("fix bug")
    e2 = c.process("fix bug")
    assert e2.state.confidence > e1.state.confidence
```

### Test 2: Failure Learning Propagates
```python
def test_failure_learning_propagates_to_next_event(self):
    c = NeuroCortex(state=BasicStateModule(), 
                    outcome_provider=FailingOutcomeProvider(), ...)
    e1 = c.process("fix bug")
    e2 = c.process("fix bug")
    assert e2.state.uncertainty > e1.state.uncertainty
```

### Test 3: Three Consecutive Successes
```python
def test_three_consecutive_successes_raise_confidence(self):
    c = NeuroCortex(state=BasicStateModule(), ...)
    for i in range(3):
        e = c.process("fix bug")
    assert c.state_store.confidence >= 0.65  # 0.50 + 3*0.05
```

### Test 4: Three Consecutive Failures
```python
def test_three_consecutive_failures_increase_uncertainty(self):
    c = NeuroCortex(state=BasicStateModule(),
                    outcome_provider=FailingOutcomeProvider(), ...)
    for i in range(3):
        e = c.process("fix bug")
    assert c.state_store.uncertainty >= 0.50  # 0.20 + 3*0.10
```

### Test 5: New Event Object Inherits Persistent State
```python
def test_new_event_inherits_persistent_learned_state(self):
    c = NeuroCortex(state=BasicStateModule(), ...)
    e1 = c.process("fix bug")
    # Manually update CortexState
    c.state_store.confidence = 0.8
    e2 = c.process("fix bug")
    # e2 should inherit the manually set confidence
    assert e2.state.confidence == 0.8
```

### Test 6: Events Don't Share Object References
```python
def test_events_do_not_share_state_references(self):
    c = NeuroCortex(state=BasicStateModule(), ...)
    e1 = c.process("fix bug")
    e2 = c.process("fix bug")
    # Modifying e1.state should not affect e2.state
    e1.state.confidence = 0.9
    assert e2.state.confidence != 0.9
```

### Test 7: CortexState vs Event.State Isolation
```python
def test_cortex_state_and_event_state_are_isolated(self):
    c = NeuroCortex(state=BasicStateModule(), ...)
    e = c.process("fix bug")
    # event.state is a snapshot, not a reference
    original_unc = e.state.uncertainty
    c.state_store.uncertainty = 0.0
    assert e.state.uncertainty == original_unc  # Unchanged
```

### Test 8: Same Cortex Multiple Events
```python
def test_same_cortex_multiple_events_learn_cumulatively(self):
    c = NeuroCortex(state=BasicStateModule(), ...)
    initial_conf = c.state_store.confidence
    for _ in range(5):
        c.process("fix bug")
    assert c.state_store.confidence > initial_conf
```

### Test 9: Two Cortex Instances Don't Pollute
```python
def test_two_cortex_instances_are_independent(self):
    c1 = NeuroCortex(state=BasicStateModule(), ...)
    c2 = NeuroCortex(state=BasicStateModule(), ...)
    for _ in range(3):
        c1.process("fix bug")
        c2.process("deploy app")
    assert c1.state_store.confidence != c2.state_store.confidence
```

### Test 10: Regression — 334 Existing Tests
```python
def test_all_existing_tests_pass(self):
    # Run all Phase 0-8 tests
    assert subprocess.run(["pytest", "..."]).returncode == 0
```

---

## 9. Architecture Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| MockState breaks learning in tests | **HIGH** | Fix MockState or use BasicStateModule |
| BasicPrediction doesn't react to low uncertainty | MEDIUM | Already handled (Rule 3 clamps p based on perf_conf) |
| CortexState update happens too late | LOW | By design — commit at LEARNING stage |
| Multiple Cortex instances sharing state | LOW | Isolated by design (each has own CortexState) |
| Event.state mutation affecting future events | LOW | Snapshot is immutable (InternalState is frozen) |

---

## 10. Open Questions

1. **Should MockState be fixed or replaced?**
   - Fix: Preserve CortexState values, add mock novelty
   - Replace: Use BasicStateModule in all integration tests
   
2. **Should BasicPrediction use CortexState directly?**
   - Current: Uses event.state.uncertainty (snapshot)
   - Alternative: Use state_store.uncertainty (persistent)
   - Recommendation: Keep current design (snapshot isolation)

3. **Should Learning module update CortexState directly?**
   - Current: Cortex.process() commits after LEARNING stage
   - Alternative: LearningModule updates CortexState
   - Recommendation: Keep current design (single commit point)

---

## Final Verdict

**APPROVED FOR PHASE 9 IMPLEMENTATION**

The learning loop is architecturally sound. The only issue is MockState breaking the state propagation in tests. Phase 9 should:

1. Fix MockState to preserve CortexState learning
2. Add 10 cross-event learning tests
3. Verify 334 regression tests still pass

No schema changes. No new modules. No architecture reorganization.

---

*Audit v1 generated 2026-09-07. No code modified. No commit. No push.*
