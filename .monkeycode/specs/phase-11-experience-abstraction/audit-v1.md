# Phase 11 Architecture Audit v1 — Experience Abstraction / Reusable Experience

**Document**: Architecture Audit — Phase 11 Experience Abstraction  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: APPROVED FOR PHASE 11 IMPLEMENTATION  
**Project**: neuro-cortex  
**Baseline**: Commit b3ab0c8 (Phase 10 frozen), 376 PASS / 0 FAIL

---

## 1. Current Architecture

### 1.1 Existing Modules

```
neuro-cortex/src/neurocortex/
├── action/           ✓ Phase 8: BasicAction
├── attention/        (empty)
├── cortex.py         ✓ Orchestration
├── decision/         ✓ Phase 7: BasicDecision
├── event.py          ✓ CortexEvent + all Data classes
├── feedback/         ✓ Phase 6: BasicFeedback
├── interfaces.py     ✓ All Module protocols
├── learning/         (empty)
├── memory/           (empty - placeholder)
├── modules/__init__.py ✓ Mock implementations
├── perception/       ✓ Phase 3: MockPerception
├── prediction/       ✓ Phase 5: BasicPrediction
├── representation/   ✓ Phase 3: MockRepresentation
└── state/            ✓ Phase 4: CortexState, BasicStateModule
```

### 1.2 Current Memory System

**MemoryData** (event.py:118-125):
```python
@dataclass
class MemoryData:
    """Retrieved memories relevant to the current event."""
    retrieved_memories: list[dict[str, Any]] = field(default_factory=list)
    memory_scores: dict[str, float] = field(default_factory=dict)
```

**MockMemory** (modules/__init__.py:96-104):
```python
class MockMemory(MemoryModule):
    def process(self, event):
        event.retrieve_memory(MemoryData(
            retrieved_memories=[],  # Always empty
            memory_scores={},
        ))
        return event
```

**Current State**: Memory module exists but returns empty retrieval. No persistence, no retrieval, no experience storage.

### 1.3 Current Learning System

**LearningData** (event.py:194-204):
```python
@dataclass
class LearningData:
    learning_signal: str = ""
    memory_updates: list[str] = field(default_factory=list)
    state_updates: dict[str, float] = field(default_factory=dict)
    policy_updates: list[str] = field(default_factory=list)
    prediction_updates: dict[str, float] = field(default_factory=dict)
```

**MockLearning** (modules/__init__.py:189-201):
- Records signal as "positive" or "negative"
- Does NOT write to memory
- Does update CortexState (via cortex.py:100)

### 1.4 Event Pipeline (from event.py:214-220)

```
Standard lifecycle:
INPUT → PERCEPTION → REPRESENTATION → ATTENTION → STATE
→ MEMORY → PREDICTION → DECISION → ACTION → OUTCOME → FEEDBACK → LEARNING

Non-linear flows allowed:
- Memory can feed directly into Prediction or Attention
- Feedback can update Internal State or Memory
- Prediction can feed back into Decision without re-predicting
```

---

## 2. Current Experience Path

### 2.1 What Happens Currently

```
Event completes (stage=LEARNING)
    ↓
Cortex.process() checks: if event.stage == "LEARNING"
    ↓
CortexState.update_from_event(event)  [cortex_state.py:41-79]
    ↓
State changes: uncertainty, confidence, active_goal, recent_inputs
    ↓
Event ends. No Experience object created.
```

### 2.2 Current "Experience" is Just State

| Aspect | Current Implementation |
|--------|----------------------|
| Storage | CortexState (in-memory, session-scoped) |
| Retrieval | None |
| Structure | Flat numeric values (uncertainty, confidence) |
| Content | Aggregated statistics, not episodic |
| Lifetime | Tied to Cortex instance |

**Verdict**: Current system has **State Adaptation** (Level 1-2), NOT **Experience-Based Adaptation** (Level 3).

---

## 3. State vs Experience vs Memory

### 3.1 Definitions

| Concept | Definition | Current Status |
|---------|-----------|----------------|
| **State** | Current internal condition (uncertainty, confidence) | ✓ Implemented |
| **Experience** | Structured record of a past event with context | ✗ Not implemented |
| **Memory** | Storage system for experiences | ✗ Placeholder only |
| **Pattern** | Abstracted rule derived from multiple experiences | ✗ Not implemented |
| **Knowledge** | Stable, generalizable patterns | ✗ Not implemented |

### 3.2 Key Distinctions

**State ≠ Experience**:
- State: "I am uncertain right now" (numeric, current)
- Experience: "Last time I tried fix-task, it failed because X" (structured, past)

**Experience ≠ Memory**:
- Experience: The content (what happened)
- Memory: The storage system (where it's kept)

**Memory ≠ Knowledge**:
- Memory: Raw stored experiences
- Knowledge: Abstractions derived from patterns in experiences

### 3.3 Required Separation

Phase 11 must maintain clear boundaries:

```
Event
  ↓ (produces)
Experience (structured record)
  ↓ (stored by)
Memory Store
  ↓ (retrieved by)
Memory Module
  ↓ (activated as)
Experience Context
  ↓ (combined with)
Prediction
```

---

## 4. Experience Schema

### 4.1 Minimal Viable Experience

Based on audit of current data structures, minimum Experience fields:

| Field | Type | Required | Rationale |
|-------|------|----------|-----------|
| `experience_id` | str | YES | Unique identifier |
| `timestamp` | str | YES | When experienced |
| `raw_input` | str | YES | Original input |
| `intent` | str | YES | Perceived intent |
| `prediction_outcome` | str | YES | What was predicted |
| `prediction_prob` | float | YES | Predicted probability |
| `action_type` | str | YES | What was done |
| `outcome_success` | bool | YES | What happened |
| `outcome_text` | str | OPTIONAL | Actual outcome |
| `prediction_error` | float | YES | How wrong was prediction |
| `evaluation` | str | OPTIONAL | Feedback evaluation label |
| `context_tags` | list[str] | OPTIONAL | For retrieval filtering |

### 4.2 Fields NOT Needed (for Phase 11)

| Field | Reason Excluded |
|-------|-----------------|
| `embedding` | Requires ML/vector DB |
| `semantic_summary` | Requires LLM |
| `pattern_id` | Pattern mining is future work |
| `confidence_score` | Can derive from prediction_error |
| `importance_weight` | Over-engineering for v1 |

### 4.3 Experience Dataclass Proposal

```python
@dataclass
class Experience:
    """Structured record of a past event for future reuse."""
    experience_id: str
    timestamp: str
    raw_input: str
    intent: str
    prediction_outcome: str
    prediction_prob: float
    action_type: str
    outcome_success: bool
    outcome_text: str = ""
    prediction_error: float = 0.0
    evaluation: str = ""
    context_tags: list[str] = field(default_factory=list)
```

---

## 5. Experience Lifecycle

### 5.1 Proposed Lifecycle States

```
RAW_EVENT ──→ CAPTURED ──→ STORED ──→ RETRIEVED ──→ ACTIVATED ──→ CONSUMED
                  ↑
                  │
            (optional validation)
```

| Stage | Description | Responsibility |
|-------|-------------|----------------|
| RAW_EVENT | Event just completed | Cortex (automatic) |
| CAPTURED | Experience object created from event | LearningModule (new) |
| STORED | Experience saved to persistent store | ExperienceStore (new) |
| RETRIEVED | Experiences fetched for new event | ExperienceRetriever (new) |
| ACTIVATED | Retrieved experiences influence prediction | PredictionModule (modified) |
| CONSUMED | Experience used, may be aged out | ExperienceStore (optional) |

### 5.2 When to Discard

Phase 11 v1 does NOT implement automatic expiration. All stored experiences remain available. Future phases may add:
- Recency-based decay
- Confidence-based pruning
- Redundancy removal

---

## 6. Storage Options

### 6.1 Comparison Matrix

| Option | Pros | Cons | Phase 11 Suitability |
|--------|------|------|---------------------|
| **A. JSONL File** | Simple, deterministic, human-readable | Linear scan, no query | ✓ RECOMMENDED for v1 |
| **B. SQLite** | Structured queries, indexing | External dependency, more complex | Phase 12+ |
| **C. Vector Store** | Semantic search | Requires ML model, non-deterministic | Phase 13+ |
| **D. In-Memory Dict** | Fast, no I/O | Lost on restart, no persistence | Not suitable |

### 6.2 Recommendation: JSONL File

**Rationale**:
1. Deterministic — same input → same file writes
2. Human-readable — debuggable
3. Simple — no external dependencies
4. Scalable enough for Phase 11 experiments (100-1000 experiences)
5. Easy to test — file I/O is straightforward

**File Format**:
```jsonl
{"experience_id": "abc123", "timestamp": "...", "raw_input": "...", ...}
{"experience_id": "def456", "timestamp": "...", "raw_input": "...", ...}
```

---

## 7. Retrieval Options

### 7.1 Comparison Matrix

| Method | Pros | Cons | Phase 11 Suitability |
|--------|------|------|---------------------|
| **Exact Match** | Simple, deterministic | Too rigid | Baseline |
| **Keyword Match** | Flexible, deterministic | May miss semantically similar | ✓ RECOMMENDED for v1 |
| **Feature Similarity** | Captures structure | Needs feature extraction | Phase 12+ |
| **Embedding Similarity** | Semantic understanding | Requires ML model | Phase 13+ |

### 7.2 Recommendation: Keyword/Tag-Based Retrieval

**Strategy**:
1. Extract keywords from `raw_input` and `context_tags`
2. Score stored experiences by keyword overlap
3. Return top-k most relevant experiences

**Why not embedding?**:
- Current Representation module produces deterministic hash-based features
- No embedding model available in Phase 11 scope
- Keyword matching is sufficient for controlled experiments

---

## 8. Similarity vs Relevance

### 8.1 Critical Distinction

**Similarity**: "How close is this experience to the current input?"
**Relevance**: "Will this experience help make a better decision?"

### 8.2 Why Similarity ≠ Relevance

Example:
- Experience: "fix production database failure" (high risk, catastrophic outcome)
- Current: "fix typo in local log file" (low risk, trivial)
- Similarity: HIGH (both are "fix" tasks)
- Relevance: LOW (different risk profiles, different contexts)

### 8.3 Phase 11 Mitigation

Include `risk` and `outcome_quality` in Experience schema:
- High-risk past failures should weight differently
- Low-confidence experiences should be downweighted
- Contradictory experiences need conflict resolution

**For v1**: Simple keyword matching with optional tag filtering is sufficient.

---

## 9. Activation Rules

### 9.1 When to Activate Retrieved Experience

| Condition | Action |
|-----------|--------|
| No relevant experiences | Normal prediction (no change) |
| 1-2 relevant experiences | Adjust prediction based on past outcomes |
| 3+ relevant experiences | Aggregate signal, weight by recency/confidence |
| Conflicting experiences | Flag contradiction, prefer recent/high-confidence |
| Irrelevant experiences | Ignore |

### 9.2 Prediction Adjustment Logic

```python
# Pseudocode for experience-influenced prediction
base_prediction = predict_from_perception(input)

if relevant_experiences:
    # Weight past outcomes
    success_count = sum(1 for e in experiences if e.outcome_success)
    total = len(experiences)
    experience_probability = success_count / total
    
    # Blend with base prediction
    adjusted_probability = 0.7 * base_prediction.p + 0.3 * experience_probability
else:
    adjusted_probability = base_prediction.p
```

### 9.3 Safety Rules

1. **Never override** high-certainty predictions with low-confidence experiences
2. **Always preserve** the base prediction as fallback
3. **Weight by recency** — newer experiences matter more
4. **Flag contradictions** — don't silently ignore conflicting data

---

## 10. Memory Contamination Risks

### 10.1 Risk Categories

| Risk | Description | Mitigation |
|------|-------------|------------|
| **Bad Experience** | One-off failure treated as permanent rule | Weight by recurrence, not single events |
| **Wrong Experience** | Incorrectly attributed past event | Include confidence in experience |
| **Low-Confidence Experience** | Experience from uncertain prediction | Downweight low-confidence sources |
| **Contradictory Experience** | Past success vs current failure | Keep both, flag contradiction |
| **Outdated Experience** | Old experience no longer relevant | Recency weighting |
| **Stale Pattern** | Generalization from insufficient data | Require minimum sample size |

### 10.2 No Automatic Filtering in v1

Phase 11 does NOT implement automatic experience deletion or modification. All experiences are preserved. This is intentional:
1. Simpler to implement and test
2. Allows experimentation with different weighting schemes
3. Future phases can add intelligent curation

---

## 11. Experience Consolidation

### 11.1 What is Consolidation?

Combining multiple similar experiences into an abstracted pattern:
- Experience 1: "fix A failed because of timeout"
- Experience 2: "fix B failed because of timeout"
- Pattern: "fix tasks often timeout under load"

### 11.2 Phase 11 Position

**NOT IMPLEMENTED in v1.**

Rationale:
1. Consolidation requires pattern recognition
2. Pattern recognition may require heuristics or ML
3. v1 should focus on basic capture → retrieve → activate loop
4. Consolidation can be added in Phase 12+

### 11.3 Interface Reserved

```python
# Future interface (not implemented in v1)
class ExperienceConsolidator:
    def consolidate(self, experiences: list[Experience]) -> list[Pattern]:
        ...
```

---

## 12. Experience → Behavior Path

### 12.1 Complete Causal Chain

```
Event A completes
    ↓
LearningModule captures Experience
    ↓
ExperienceStore.save(experience)
    ↓
Event B starts
    ↓
ExperienceRetriever.retrieve(query=B)
    ↓
Retrieved experiences injected into Prediction
    ↓
Prediction adjusts based on experience signal
    ↓
Decision uses adjusted prediction
    ↓
Action follows decision
```

### 12.2 New Modules Required

| Module | Responsibility | Files |
|--------|---------------|-------|
| `Experience` | Dataclass for stored experience | `event.py` (add) |
| `ExperienceStore` | Persist/retrieve experiences | `memory/experience_store.py` |
| `ExperienceRetriever` | Find relevant experiences | `memory/experience_retriever.py` |
| `ExperienceLearningModule` | Capture experience from event | `learning/experience_learner.py` |
| `ExperiencePredictionModule` | Adjust prediction with experience | `prediction/experience_prediction.py` |

### 12.3 Modified Modules

| Module | Change |
|--------|--------|
| `interfaces.py` | Add `ExperienceModule` protocol |
| `cortex.py` | Wire new modules into pipeline |
| `modules/__init__.py` | Add mock implementations |

---

## 13. Control / Treatment Experiments

### 13.1 Experiment Design

**Control Group** (no experience):
```
Input X → Perception → ... → Prediction (no memory) → Decision → Action
```

**Treatment Group** (with experience):
```
Phase 1: Build experience
  Input X → ... → Experience captured → Stored

Phase 2: Retrieve and use
  Input X → Perception → ... → Prediction (with memory) → Decision → Action
```

### 13.2 Expected Results

| Metric | Control | Treatment | Expected Difference |
|--------|---------|-----------|---------------------|
| Prediction probability | P_base | P_experience | P_experience ≠ P_base |
| Prediction outcome | Out_base | Out_experience | May differ |
| Decision action | Act_base | Act_experience | May differ |
| Decision score | Score_base | Score_experience | May differ |

### 13.3 Causality Proof

To prove experience CAUSED the behavior change:
1. Same input X in both cases
2. Same perception, representation, state
3. Only difference: experience injection
4. Observation: different prediction/decision/action

---

## 14. Causal Design

### 14.1 Key Variables

| Variable | Control | Treatment |
|----------|---------|-----------|
| Input | X | X (identical) |
| Perception | Same | Same |
| State | Same | Same |
| Memory | Empty | Has relevant experience |
| Prediction | P1 | P2 (potentially different) |
| Decision | D1 | D2 (potentially different) |
| Action | A1 | A2 (potentially different) |

### 14.2 What Counts as "Different Behavior"

Behavior change is confirmed if ANY of:
- `prediction.outcome` differs
- `prediction.probability` differs by > threshold
- `decision.selected_action` differs
- `decision.score` differs by > threshold
- `action.action_type` differs

### 14.3 Required Tests

1. **No experience, no change**: Control group produces stable behavior
2. **With experience, potential change**: Treatment group may produce different behavior
3. **Causality**: Difference is attributable to experience, not randomness

---

## 15. Embedding Assessment

### 15.1 Current State

- `RepresentationData` has `embedding: list[float]` field
- Current implementation produces `[float(len(tokens)) / 10.0]` — a single scalar
- NO semantic embedding model exists

### 15.2 Should We Add Embeddings?

**NO for Phase 11.**

Rationale:
1. No embedding model available
2. Would introduce non-determinism
3. Keyword/tag matching sufficient for v1 experiments
4. Can add later as optional enhancement

### 15.3 Future Option

If embeddings are added later:
- Use deterministic hash-based features
- Or add optional ML provider (pluggable)
- Never hard-depend on external models

---

## 16. LLM Assessment

### 16.1 Should We Use LLM?

**NO for Phase 11.**

Rationale:
1. Non-deterministic
2. Requires external API
3. Adds cost and latency
4. Hallucination risk
5. Testing difficulty

### 16.2 Alternative

Use deterministic heuristics:
- Keyword extraction
- Tag matching
- Simple scoring

### 16.3 Future Option

If LLM abstraction is needed:
- Create pluggable `ExperienceAbstractionProvider` interface
- Default: deterministic heuristic
- Optional: LLM-based abstraction

---

## 17. Experience Quality

### 17.1 Quality Factors

| Factor | Description | How to Measure |
|--------|-------------|----------------|
| `prediction_confidence` | How confident was the prediction | From PredictionData |
| `prediction_error` | How wrong was the prediction | From FeedbackData |
| `outcome_reliability` | How reliable was the outcome | Inferred from outcome_type |
| `recency` | How recent is the experience | Timestamp comparison |
| `repeatability` | How often similar situations occurred | Count of similar experiences |

### 17.2 Quality Score (Proposed)

```python
def calculate_quality(experience: Experience) -> float:
    # Higher is better
    error_penalty = experience.prediction_error  # 0-1, lower is better
    confidence_bonus = 1.0 - experience.prediction_confidence if not experience.outcome_success else experience.prediction_confidence
    recency_bonus = 1.0  # Simplified: newer = better
    return (1.0 - error_penalty) * 0.5 + confidence_bonus * 0.3 + recency_bonus * 0.2
```

### 17.3 Phase 11 Position

Basic quality calculation included. Advanced quality-based filtering deferred.

---

## 18. Performance / Resource Analysis

### 18.1 Scale Estimates

| Scale | Experience Count | Linear Scan | SQLite | Notes |
|-------|-----------------|-------------|--------|-------|
| Small | 100 | <1ms | <1ms | Both fine |
| Medium | 1,000 | ~10ms | <1ms | Linear ok |
| Large | 10,000 | ~100ms | <10ms | Consider index |
| Enterprise | 100,000 | ~1s | ~10ms | Need index |

### 18.2 Phase 11 Target

Target: 100-1000 experiences for experiments.
Linear scan on JSONL is acceptable.

### 18.3 Optimization Path

If performance becomes an issue:
1. Add simple in-memory index (experience_id → line number)
2. Migrate to SQLite
3. Add vector index (future)

---

## 19. Frozen Boundary Check

### 19.1 Files to NOT Modify

| File | Status | Reason |
|------|--------|--------|
| `event.py` | UNCHANGED | Schema frozen |
| `interfaces.py` | UNCHANGED | Protocol frozen |
| `cortex.py` | UNCHANGED | Pipeline frozen |
| `perception/*` | UNCHANGED | Phase 3 frozen |
| `representation/*` | UNCHANGED | Phase 3 frozen |
| `state/*` | UNCHANGED | Phase 4 frozen |
| `prediction/*` | UNCHANGED | Phase 5 frozen |
| `decision/*` | UNCHANGED | Phase 7 frozen |
| `action/*` | UNCHANGED | Phase 8 frozen |
| `feedback/*` | UNCHANGED | Phase 6 frozen |

### 19.2 New Files to Create

| File | Purpose |
|------|---------|
| `memory/experience.py` | Experience dataclass |
| `memory/experience_store.py` | JSONL persistence |
| `memory/experience_retriever.py` | Keyword-based retrieval |
| `learning/experience_learner.py` | Capture experience from event |
| `tests/test_phase11.py` | Experiment tests |

### 19.3 Minimal Modification Required

**interfaces.py**: Add `ExperienceModule` protocol (interface extension, not modification of existing)

**cortex.py**: Wire new modules (configuration, not behavior change)

**modules/__init__.py**: Add mock implementations

---

## 20. Phase 11 MVP Proposal

### 20.1 Minimum Viable Product

**Core Loop**:
1. Capture: After each event, create Experience object
2. Store: Save to JSONL file
3. Retrieve: On new event, find similar experiences
4. Activate: Adjust prediction based on retrieved experiences

### 20.2 Components

```
ExperienceCapture (LearningModule)
    ↓ writes to
ExperienceStore (JSONL file)
    ↑ reads by
ExperienceRetriever
    ↓ injects into
PredictionModule (via new ExperiencePredictionMixin)
```

### 20.3 What's NOT Included

- Pattern mining
- Automatic experience deletion
- Embedding-based similarity
- LLM-based abstraction
- Real-time learning during event
- Cross-session persistence (beyond file)

---

## 21. Explicit Non-Goals

### 21.1 Phase 11 Will NOT Do

| Item | Reason |
|------|--------|
| Neural network training | Requires ML framework |
| Embedding model | Requires external service |
| LLM integration | Non-deterministic, costly |
| Semantic search | Requires embeddings |
| Automatic curation | Over-engineering for v1 |
| Real-time adaptation | Complexity |
| Multi-modal memory | Out of scope |
| Cross-instance sharing | Single Cortex per run |

### 21.2 Phase 11 Will NOT Modify

- Existing frozen modules
- Existing tests (except adding new)
- Event schema (except adding Experience dataclass)
- Cortex pipeline order

---

## 22. Test Matrix (30+ Tests)

### 22.1 Experience Capture (5 tests)

| Test | Description |
|------|-------------|
| T01 | Experience captured after successful event |
| T02 | Experience captured after failed event |
| T03 | Experience contains all required fields |
| T04 | Experience ID is unique |
| T05 | Experience timestamp is set |

### 22.2 Experience Storage (5 tests)

| Test | Description |
|------|-------------|
| T06 | Experience persisted to JSONL |
| T07 | Multiple experiences stored sequentially |
| T08 | Stored experience can be loaded |
| T09 | File is valid JSONL format |
| T10 | Empty store handled gracefully |

### 22.3 Experience Retrieval (5 tests)

| Test | Description |
|------|-------------|
| T11 | Retrieval returns empty when no experiences |
| T12 | Retrieval finds exact keyword match |
| T13 | Retrieval finds partial keyword match |
| T14 | Retrieval scores experiences by relevance |
| T15 | Retrieval respects top-k limit |

### 22.4 Experience Activation (5 tests)

| Test | Description |
|------|-------------|
| T16 | Prediction adjusts with relevant experience |
| T17 | No experience → no adjustment |
| T18 | Low-confidence experience has less influence |
| T19 | Recent experience weighted more |
| T20 | Multiple experiences aggregated |

### 22.5 Control vs Treatment (5 tests)

| Test | Description |
|------|-------------|
| T21 | Control group stable behavior |
| T22 | Treatment group may change behavior |
| T23 | Same input, different experience → different prediction |
| T24 | Causality: experience is only variable |
| T25 | Deterministic: same experience → same result |

### 22.6 Edge Cases (5 tests)

| Test | Description |
|------|-------------|
| T26 | Empty experience handled |
| T27 | Malformed JSONL recovered gracefully |
| T28 | No relevant experience → fallback to base prediction |
| T29 | Contradictory experiences flagged |
| T30 | Experience quality score calculated |

### 22.7 Regression (1 test)

| Test | Description |
|------|-------------|
| T31 | All 376 existing tests pass |

---

## 23. Acceptance Criteria

### 23.1 Core Criteria

| ID | Criterion | Pass Condition |
|----|-----------|----------------|
| AC-1 | Experience captured from event | Experience object created with all fields |
| AC-2 | Experience persisted | File written, readable |
| AC-3 | Experience retrieved | Relevant experiences found |
| AC-4 | Experience influences prediction | P_with ≠ P_without |
| AC-5 | Causality verified | Only variable is experience |
| AC-6 | Control group stable | Behavior consistent without experience |
| AC-7 | Deterministic | Same input + experience → same output |
| AC-8 | No frozen file modification | event.py, interfaces.py unchanged (except additions) |
| AC-9 | Regression passes | 376 existing tests pass |
| AC-10 | Isolation | Different Cortices don't share experiences |

---

## 24. Risks

### 24.1 Architecture Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Experience store becomes bottleneck | MEDIUM | Start with JSONL, optimize later |
| Retrieval too slow at scale | LOW | Linear scan OK for v1 scale |
| Experience pollution from bad data | MEDIUM | Quality scoring, flagging |
| Over-reliance on past experiences | LOW | Weight by recency/confidence |
| Forgetting current context | HIGH | Base prediction always primary |

### 24.2 Implementation Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Schema drift | LOW | Frozen schema, additive changes only |
| Test brittleness | MEDIUM | Focus on behavior, not exact values |
| File I/O errors | LOW | Exception handling, graceful fallback |

---

## 25. Final Verdict

### 25.1 Summary

**Phase 11 is architecturally sound and feasible.**

Key findings:
1. Current system has State Adaptation but NOT Experience-Based Adaptation
2. Memory module exists but is empty (placeholder)
3. Experience schema is simple and well-defined
4. JSONL storage + keyword retrieval is sufficient for v1
5. No ML/LLM required
6. Minimal code changes needed (new modules, no frozen modifications)

### 25.2 Recommended Approach

**Minimal MVP**:
1. Add `Experience` dataclass to event.py
2. Create `ExperienceStore` with JSONL persistence
3. Create `ExperienceRetriever` with keyword matching
4. Create `ExperienceLearningModule` to capture experiences
5. Modify Prediction to optionally use retrieved experiences
6. Add 30+ tests
7. Verify 376 regression tests still pass

### 25.3 What Makes This Different from Phase 10

| Aspect | Phase 10 | Phase 11 |
|--------|----------|----------|
| Learning target | CortexState (numeric) | Experience Store (structured) |
| Retrieval | None | Keyword-based |
| Behavior change | Via state thresholds | Via experience injection |
| Specificity | Global (all events) | Episodic (specific past events) |
| Reusability | Implicit | Explicit |

---

## Final Verdict

**APPROVED FOR PHASE 11 IMPLEMENTATION**

Phase 11 should implement:
- Experience capture from events
- JSONL-based experience storage
- Keyword-based experience retrieval
- Experience-influenced prediction
- Full experimental verification

No frozen files need modification (except additions).
No ML/LLM required.
Deterministic, testable, minimal.

---

*Audit v1 generated 2026-09-07. No code modified. No commit. No push.*
