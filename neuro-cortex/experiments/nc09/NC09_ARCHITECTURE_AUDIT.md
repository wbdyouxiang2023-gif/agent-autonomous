# NC-09 Architecture Audit

**Date:** 2026-09-09  
**Status:** AUDIT COMPLETE  
**Critical Finding:** LEARNING_LOOP_MISSING (by default)

---

## 1. Current Architecture

### Learning Pipeline

```
CortexEvent
    ↓
PERCEPTION → intent detected
    ↓
DECISION → candidates generated
    ↓
ACTION → action executed
    ↓
OUTCOME → real outcome recorded
    ↓
FEEDBACK → evaluation computed
    ↓
LEARNING → Experience captured (if stage == FEEDBACK)
    ↓
ExperienceStore (JSONL)
```

### Action Learning Bridge (Separate Path)

```
Decision Stage
    ↓
candidates (list)
    ↓
ActionLearningBridge.rank_candidates()
    ↓
ranked candidates (if enabled)
    ↓
Action Execution
    ↓
record_event_outcome()
    ↓
StatisticsStore (JSON)
```

---

## 2. Critical Configuration Issues

### Default State (CURRENT)

| Component | Default | Status |
|-----------|---------|--------|
| NEUROCORTEX_ACTION_LEARNING | false | **DISABLED** ❌ |
| ACTION_LEARNING_SHADOW_ONLY | true | Shadow mode only |
| REAL_EXECUTION_BRIDGE_ENABLED | false | No real execution |
| semantic_transfer_enabled | false | No semantic transfer |

### Impact

**With defaults:**
- Experience Learning Module: Captures experiences to JSONL ✅
- Action Learning Bridge: DISABLED - no ranking adaptation ❌
- Real Execution: DISABLED - no real outcomes ❌

**Result:** No true Learning → Adaptation loop exists by default.

---

## 3. Key Components Analysis

### A. Experience / Memory Writing
**File:** `src/neurocortex/learning/experience_learner.py`

```python
def process(self, event: CortexEvent) -> CortexEvent:
    if event.stage == "FEEDBACK" and self._is_valid_for_experience(event):
        experience = Experience.from_event(event)
        self._store.save(experience)  # → ~/.neurocortex_memory.jsonl
```

**Status:** ✅ WORKING - experiences are captured

### B. Outcome Writing
**File:** `src/neurocortex/event.py` (OutcomeData)

```python
@dataclass
class OutcomeData:
    actual_outcome: str = ""
    success: bool = False
    error_message: str = ""
    task_completed: bool | None = None  # Level 4.0
    completion_source: str = "unknown"
```

**Status:** ✅ WORKING - outcomes recorded with task_completed

### C. Action Ranking with History
**File:** `src/neurocortex/action_learning/engine.py`

```python
def rank_actions(self, situation, candidates, experiences):
    # Hierarchical evidence lookup:
    # L1: exact situation + action
    # L2: intent + action
    # L3: global action
    # L4: semantic transfer
```

**Status:** ⚠️ EXISTS but DISABLED by default

### D. Situation → Task Type Mapping
**File:** `src/neurocortex/perception/classifier_v4.py`

```python
def classify_v4(situation: str) -> ClassificationResult:
    # Context-aware classification
    # Returns (task_type, action, confidence)
```

**Status:** ✅ FIXED in C.7/C.8

---

## 4. Learning Loop Gap Analysis

### Current Gap

```
ROUND 1: S1 → Action A → REAL OUTCOME
    ↓
Experience captured to JSONL ✅
    ↓
Statistics NOT updated ❌ (bridge disabled)
    ↓
ROUND 2: S2 (similar) → Action A (same ranking) ❌
    ↓
NO ADAPTATION observed
```

### Required Fix for NC-09

1. **Enable Action Learning**: `NEUROCORTEX_ACTION_LEARNING=true`
2. **Disable Shadow Mode**: `ACTION_LEARNING_SHADOW_ONLY=false`
3. **Enable Real Execution**: `REAL_EXECUTION_BRIDGE_ENABLED=true`
4. **Use V4 Classifier**: For proper situation matching

---

## 5. Data Flow Verification

### Experience Storage
- **Path:** `~/.neurocortex_memory.jsonl`
- **Format:** JSONL with Experience schema
- **Update Mechanism:** Append-only

### Action Statistics Storage
- **Path:** `~/.neurocortex_action_statistics.json`
- **Format:** JSON with situation|action keys
- **Update Mechanism:** Atomic writes

### Current State
```bash
$ ls -la ~/.neurocortex*.json*
-rw-r--r-- 1 root root 8448 Sep  9 12:32 ~/.neurocortex_memory.jsonl
-rw-r--r-- 1 root root    0 Sep  9 11:06 ~/.neurocortex_action_statistics.json
```

**Finding:** Experience store has data, but action statistics are empty (learning never enabled).

---

## 6. Conclusion

### LEARNING_LOOP Status: MISSING (by default)

The current NeuroCortex has:
1. ✅ Experience capture (Memory)
2. ✅ Outcome recording
3. ❌ Disabled learning bridge (no ranking adaptation)
4. ❌ Disabled real execution (no real outcomes)

### For NC-09, We Must:
1. Enable `NEUROCORTEX_ACTION_LEARNING=true`
2. Enable `ACTION_LEARNING_SHADOW_ONLY=false`
3. Enable `REAL_EXECUTION_BRIDGE_ENABLED=true`
4. Create controlled experiment with clear before/after comparison

---

## 7. Recommendations

1. **Immediate:** Enable learning bridge for NC-09 experiment
2. **Experimental Design:** Use isolated statistics path to avoid polluting production
3. **Verification:** Track ranking changes between Round 1 and Round 2
4. **Causality:** Ensure adaptation is caused by learning, not random chance
