# NeuroCortex Independent Action Learning Evaluation

**Date:** 2026-09-09  
**Experiment:** Validate NeuroCortex Action/Policy Learning闭环  
**Status:** Architecture Audit Complete

---

## 1. Environment

| Component | Status |
|-----------|--------|
| OpenClaw | Running (agent: main) |
| NeuroCortex | Running on port 9100 |
| Python | 3.12 |
| Experience Store | ~/.neurocortex_memory.jsonl (2603 existing + 130 new) |
| Action Statistics | ~/.neurocortex_action_statistics.json (5 entries) |
| Observation Log | ~/.neurocortex_observation_log.jsonl (130 records) |

---

## 2. Actual Architecture

### Data Flow (Current)

```
OpenClaw Input (message)
    ↓
NeuroCortex.process(raw_input)
    ↓
Perception: BilingualPerception._detect_intent() → intent
    ↓
Representation: MockRepresentation (no-op)
    ↓
Attention: MockAttention (no-op)
    ↓
State: BasicStateModule.update_state()
    ↓
Memory: MockMemory.retrieve()
    ↓
Prediction: ExperiencePredictionModule.predict()
    ↓
Decision: BasicDecision._decide() ← HARDCODED INTENT_ACTION_MAP
    ↓
Action: BasicAction._execute()
    ↓
Outcome: PersistentOutcome.provide() ← PATTERN-BASED (not real execution)
    ↓
Feedback: MockFeedback.compute_feedback()
    ↓
Learning: ExperienceLearningModule.learn()
```

### Decision Module Analysis

**File:** `neuro-cortex/src/neurocortex/decision/decision.py`

```python
# Lines 16-22: Hardcoded intent → action mapping
INTENT_ACTION_MAP: dict[str, str] = {
    "create": "code_edit",
    "fix": "code_review",
    "learn": "respond",
    "optimize": "tool_call",
    "deploy": "tool_call",
}
```

**Decision Logic (simplified):**
1. Detect intent from raw_input
2. Look up INTENT_ACTION_MAP
3. Generate candidates: `[selected_action, noop]`
4. Select action based on rules (risk, confidence)
5. **NEVER reads ActionLearning statistics**
6. **NEVER uses PolicyEngine**

### Action Learning Bridge Analysis

**File:** `neuro-cortex/src/neurocortex/action_learning/bridge.py`

```python
# Line 17-21: Purpose
"""
  - NEUROCORTEX_ACTION_LEARNING=false (default) → candidates returned
    unchanged, record_outcome() is a no-op, zero behavior change.
  - ACTION_LEARNING_SHADOW_ONLY=true → ranking computed and recorded but
    candidate ORDER is untouched (Shadow Runtime support).
"""
```

**Status in server.py:**
- `action_bridge` is instantiated (line 38)
- `record_event_outcome()` is called when `ACTION_LEARNING_ENABLED=true` (line 146)
- `rank_candidates()` is **NEVER called** ← Critical gap

### PolicyEngine Analysis

**File:** `neuro-cortex/src/neurocortex/policy/engine.py`

- Fully implemented with `choose_action()` method
- Reads from ActionLearningEngine rankings
- Provides decision_status: "decided" / "no_evidence" / "insufficient_evidence"
- **NOT INSTANTIATED in server.py** ← Not used

---

## 3. Dataset

### Total Records
- **Total observations:** 130
- **Success:** 114 (87.7%)
- **Failure:** 16 (12.3%)
- **Unknown:** 0

### Intent Distribution (Situation Proxy)
| Intent | Count | Success Rate |
|--------|-------|--------------|
| review | 46 | 100% |
| general | 40 | 75% |
| explain | 10 | 100% |
| fix | 10 | 70% |
| create | 8 | 75% |
| optimize | 6 | 83% |
| test | 6 | 100% |
| deploy | 4 | 100% |

### Unique Situations
- **By raw_input (first 50 chars):** 129 unique
- **By intent:** 8 unique
- **With >1 sample:** 1 (repeated task)

### Actions Observed
| Action | Count | % |
|--------|-------|---|
| respond | 102 | 78.5% |
| code_review | 10 | 7.7% |
| tool_call | 10 | 7.7% |
| code_edit | 8 | 6.2% |

---

## 4. Candidate Action Quality

### Distribution
| Candidate Set | Count | % |
|---------------|-------|---|
| ('noop', 'respond') | 102 | 78.5% |
| ('code_review', 'noop') | 10 | 7.7% |
| ('noop', 'tool_call') | 10 | 7.7% |
| ('code_edit', 'noop') | 8 | 6.2% |

### True Multi-Action Decisions
- **Records with ≥2 non-noop candidates:** 0/130 (0%)
- **Definition:** Both candidates must be executable actions (not noop)
- **Result:** No true action comparison exists

### noop Ratio
- **noop appears in candidates:** 130/130 (100%)
- **noop as selected action:** 0/130 (0%)
- **Interpretation:** noop is always a "loss" option, never selected

---

## 5. Situation × Action Matrix

### By Intent (only situation key available)

| Intent | Action | Success | Failure | Total | Rate |
|--------|--------|---------|---------|-------|------|
| review | respond | 46 | 0 | 46 | 100% |
| general | respond | 30 | 10 | 40 | 75% |
| explain | respond | 10 | 0 | 10 | 100% |
| fix | code_review | 7 | 3 | 10 | 70% |
| create | code_edit | 6 | 2 | 8 | 75% |
| optimize | tool_call | 5 | 1 | 6 | 83% |
| test | respond | 6 | 0 | 6 | 100% |
| deploy | tool_call | 4 | 0 | 4 | 100% |

### Support Analysis
| Support Level | Count |
|---------------|-------|
| >= 1 | 126 |
| >= 2 | 3 |
| >= 3 | 1 |
| >= 5 | 0 |
| >= 10 | 0 |

**Finding:** Only 3 Situation×Action pairs have support >= 2, and none have enough for statistical significance.

---

## 6. Temporal Split Analysis

### Timeline
- **First record:** 2026-09-09T01:02:27.291485+00:00
- **Last record:** 2026-09-09T01:05:03.014849+00:00
- **Duration:** 2.6 minutes

### Batch Distribution
| Batch Size | Count |
|------------|-------|
| 25 records | 1 batch |
| 32 records | 1 batch |
| 33 records | 1 batch |
| 40 records | 1 batch |

**Leakage Check:**
- All records from single session
- No temporal separation between train/test
- Cannot perform strict temporal evaluation

---

## 7. Baselines

### Baseline A: Random Policy
- **Definition:** Randomly select from candidate_actions
- **Candidates per decision:** Always 2 (selected, noop)
- **Random success rate prediction:** ~50% (if equally likely)

### Baseline B: NeuroCortex Learned Policy
- **Status:** NOT IMPLEMENTED
- **Reason:** ActionLearningBridge.rank_candidates() never called
- **PolicyEngine:** Exists but not instantiated

### Baseline C: Default (Current) Policy
- **Definition:** INTENT_ACTION_MAP lookup → deterministic selection
- **Success rate:** 87.7% overall
- **Nature:** Rule-based, not learned

---

## 8. NeuroCortex Policy

### Current Behavior
The current "policy" is:
1. Detect intent from input
2. Map intent → action via hardcoded dictionary
3. Always select the mapped action (never noop)
4. Generate candidates [selected, noop]

### Learning Status
- **Statistics collected:** Yes (when enabled)
- **Statistics used:** No
- **Policy improved:** No

---

## 9. Test Results

| Policy | Decisions | Success | Failure | Success Rate |
|--------|-----------|---------|---------|--------------|
| Random (theoretical) | 130 | ~65 | ~65 | ~50% |
| NeuroCortex Learned | N/A | N/A | N/A | N/A |
| NeuroCortex Default | 130 | 114 | 16 | 87.7% |

**Result:** Cannot compare learned vs random because learning is not connected.

---

## 10. Leakage Audit

| Check | Status |
|-------|--------|
| Test participates in decision | N/A (no split) |
| Test outcome enters statistics early | No (shadow mode) |
| Shuffle | No shuffle performed |
| Duplicate | None (130 unique records) |
| Timestamp contamination | All from same session |
| Synthetic outcome | No (all real from PersistentOutcome) |
| LLM judge | No |
| Manual labels | No |

**Finding:** No leakage, but also no valid test because learning is not connected.

---

## 11. Root Cause Analysis

### Why Can't We Validate Learning?

**Problem 1: Decision Module Doesn't Use Learning**
```python
# decision.py - No reference to ActionLearningBridge
class BasicDecision(DecisionModule):
    def _decide(self, intent, risk, perf_conf, pred, raw_input):
        # Uses only INTENT_ACTION_MAP
        action_type = INTENT_ACTION_MAP.get(intent, "respond")
        # Never calls action_bridge.rank_candidates()
```

**Problem 2: Bridge Not Connected**
```python
# server.py - Only records outcome, never ranks
def _process_with_action_learning(raw_input):
    event = _original_process(raw_input)
    if ACTION_LEARNING_ENABLED:
        action_bridge.record_event_outcome(event)  # Records only
        # Missing: action_bridge.rank_candidates() before decision
    return event
```

**Problem 3: No True Multi-Action Comparison**
- All decisions have candidates: [action, noop]
- Never: [action_A, action_B] where both are executable
- Cannot compare "which action is better"

**Problem 4: Situation Key Too Coarse**
- Uses `intent` as situation key
- 129 unique raw_inputs → only 8 unique situations
- No fine-grained situation awareness

---

## 12. Final Verdict

### Required Conditions for Validation
1. ✅ 130+ real experiences
2. ✅ candidate_actions observable
3. ✅ original_selected_action observable
4. ✅ real outcomes recorded
5. ❌ Action Learning connected to decision pipeline
6. ❌ True multi-action decisions (≥2 non-noop candidates)
7. ❌ Situation clustering with repeated samples
8. ❌ PolicyEngine instantiated and used

### Current Status

**VERDICT: NO_VALIDATED_POLICY_IMPROVEMENT**

**Reason:** The Action Learning infrastructure exists (StatisticsStore, ActionLearningEngine, ActionLearningBridge, PolicyEngine) but is NOT CONNECTED to the decision pipeline. The system operates in "shadow mode" where statistics are collected but never used for decisions.

### What Would Be Needed

To validate policy improvement, the following minimal changes are required:

1. **Connect Bridge to Decision:**
   ```python
   # In server.py, modify _process_with_action_learning:
   if ACTION_LEARNING_ENABLED and not ACTION_LEARNING_SHADOW_ONLY:
       # Rank candidates BEFORE decision
       ranked = action_bridge.rank_candidates(
           candidates=event.decision.candidates,
           situation=situation_from_event(event),
           raw_input=raw_input,
           intent=event.perception.intent
       )
       # Update event with ranked candidates
       event.decision.candidates = ranked
   ```

2. **Enable Non-Shadow Mode:**
   ```python
   ACTION_LEARNING_SHADOW_ONLY = False
   ACTION_LEARNING_ENABLED = True
   ```

3. **Add True Multi-Action Candidates:**
   - Modify decision module to generate multiple executable actions
   - Example: [respond, code_edit, tool_call] instead of [respond, noop]

4. **Improve Situation Granularity:**
   - Use semantic similarity or clustering
   - Group similar tasks together

### Recommendation

**Do NOT proceed with temporal evaluation.** The architecture does not support it yet.

**Next step:** Enable action learning in non-shadow mode and run experiments with true multi-action candidates to collect meaningful training data.

---

## Appendix: Code Locations

| Component | File | Class/Function |
|-----------|------|----------------|
| Decision Module | `neuro-cortex/src/neurocortex/decision/decision.py` | `BasicDecision._decide()` |
| Action Module | `neuro-cortex/src/neurocortex/action/action.py` | `BasicAction._execute()` |
| Outcome Provider | `neuro-cortex/server.py` | `PersistentOutcome.provide()` |
| Experience Store | `neuro-cortex/src/neurocortex/memory/experience_store.py` | `ExperienceStore` |
| Action Stats | `~/.neurocortex_action_statistics.json` | JSON file |
| Bridge | `neuro-cortex/src/neurocortex/action_learning/bridge.py` | `ActionLearningBridge` |
| Engine | `neuro-cortex/src/neurocortex/action_learning/engine.py` | `ActionLearningEngine` |
| Policy Engine | `neuro-cortex/src/neurocortex/policy/engine.py` | `PolicyEngine` |
| Server | `neuro-cortex/server.py` | `Handler.do_POST()` |

---

**Report Generated:** 2026-09-09  
**Agent:** NeuroCortex Independent Experiment Agent
