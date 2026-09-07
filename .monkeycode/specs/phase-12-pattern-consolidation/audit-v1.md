# Phase 12 Architecture Audit v1 — Pattern Consolidation from Experience

**Document**: Architecture Audit — Phase 12 Pattern Formation  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: DRAFT — Under Review  
**Project**: neuro-cortex  
**Baseline**: Commit 98dfcea (Phase 11 frozen), 426 PASS / 0 FAIL  
**Frozen Base**: Commit b3ab0c8 (Phase 10 frozen), 376 PASS / 0 FAIL

---

## 1. Current Architecture

### 1.1 Full Module Map (Phase 0-11)

```
neuro-cortex/src/neurocortex/
├── cortex.py              ✓ NeuroCortex orchestration (11-stage pipeline)
├── event.py               ✓ CortexEvent + 11 Data classes + Experience
├── interfaces.py          ✓ 10 module protocols
├── perception/            ✓ BasicPerception (intent detection)
├── representation/        ✓ BasicRepresentation (token features)
├── attention/             ✗ empty (no-op passthrough)
├── state/                 ✓ CortexState + BasicStateModule
├── memory/                ✓ ExperienceStore, ExperienceRetriever [NEW Phase 11]
├── prediction/            ✓ BasicPrediction, ExperiencePredictionModule [NEW Phase 11]
├── decision/              ✓ BasicDecision (intent→action mapping)
├── action/                ✓ BasicAction (symbolic execution)
├── feedback/              ✓ BasicFeedback (prediction_error classification)
├── learning/              ✓ ExperienceLearningModule [NEW Phase 11]
└── modules/__init__.py    ✓ Mock implementations for testing
```

### 1.2 Pipeline Execution Order (from cortex.py:159-171)

```python
pipeline = [
    ("PERCEPTION",   self._perception,   "perceive"),
    ("REPRESENTATION", self._representation, "represent"),
    ("ATTENTION",    self._attention,    "attend"),
    ("STATE",        self._state,        "update_state"),
    ("MEMORY",       self._memory,       "retrieve_memory"),
    ("PREDICTION",   self._prediction,   "predict"),
    ("DECISION",     self._decision,     "decide"),
    ("ACTION",       self._action,       "act"),
    ("OUTCOME",      self._outcome_provider, "obtain_outcome"),
    ("FEEDBACK",     self._feedback,     "compute_feedback"),
    ("LEARNING",     self._learning,     "learn"),
]
```

### 1.3 Current Data Flow with Phase 11

```
Event.raw_input
  → Perception.intent
  → BasicPrediction(base_prob from intent+risk+uncertainty)
  → ExperiencePredictionModule:
      - Retrieve experiences from store (keyword+tag match)
      - Calculate experience_prob = success_count / total
      - Blend: adjusted = 0.7 * base_prob + 0.3 * experience_prob
      - Write adjusted back to event.prediction
  → Decision (maps intent → action)
  → Action (symbolic execution)
  → OutcomeProvider (real/simulated result)
  → Feedback (prediction_error, evaluation)
  → ExperienceLearningModule:
      - If stage == FEEDBACK and valid: create Experience, save to store
      - Record learning_signal (positive/negative)
      - Advance to LEARNING
```

### 1.4 State Adaptation Path (Separate from Experience)

```
CortexState.update_from_event(event)  [cortex_state.py:41-79]
  ├── uncertainty: ±0.05 (success) / ±0.10 (failure)
  ├── confidence: ±0.05 (success) / ±0.10 (failure)
  ├── active_goal: from intent
  └── recent_inputs: append, cap at 10

BasicPrediction reads event.state.uncertainty (threshold routing)
```

**Key Finding**: There are TWO independent learning paths:
1. **State path** — `CortexState` updates numerics → affects `BasicPrediction` thresholds
2. **Experience path** — `ExperienceStore` stores structured records → `ExperienceRetriever` retrieves → `ExperiencePredictionModule` blends

These two paths operate in parallel and do NOT communicate with each other.

---

## 2. Phase 11 Reality Check

### 2.1 What Phase 11 Actually Achieved

| Component | Implementation | Status |
|-----------|---------------|--------|
| Experience dataclass | 15 fields, from_event factory, to_dict/from_dict | ✓ Complete |
| ExperienceStore | JSONL append-only, in-memory dict cache, malformed-line tolerance | ✓ Complete |
| ExperienceRetriever | Keyword+tag overlap scoring, top-k, deterministic | ✓ Complete |
| ExperienceLearningModule | FEEDBACK-stage capture, validity check, learning signal | ✓ Complete |
| ExperiencePredictionModule | 70/30 blend with base prediction, clamped [0,1] | ✓ Complete |

### 2.2 What Phase 11 Did NOT Achieve

From the final-review-v1.md known limitations:

1. **No experience aging/decay** — All experiences have equal weight regardless of age
2. **Simple keyword matching** — No semantic similarity; "fix a bug" won't match "resolve an issue"
3. **No experience limit** — Store grows unbounded; no eviction policy
4. **Single weighted blend** — Fixed 30% weight, no adaptive weighting
5. **No cross-cortex experience sharing** — Each Cortex instance has isolated experience store
6. **No consolidation** — Each experience is stored independently; no patterns derived
7. **No contradiction resolution** — Conflicting experiences coexist without resolution mechanism
8. **No pattern abstraction** — No "learned rule" emerges from repeated experiences

### 2.3 Boundary Analysis: Is Phase 11 Pure Experience or Already Leaking?

**Checking Experience dataclass (event.py:207-278):**

The Experience dataclass contains:
- `predicted_prob` — This is the base prediction BEFORE experience influence. Clean.
- `confidence` — This is `event.prediction.prediction_confidence` from BasicPrediction. Clean.
- `uncertainty` — This is `event.state.uncertainty`. This is a STATE value, not an EXPERIENCE value. **BORDERLINE**. It captures the system's internal state at the time of the event, which is useful context but technically mixes State and Experience domains.
- `prediction_error` — Derived from feedback. This is a post-hoc measurement. Clean — it's part of the experience record, not a pattern.
- `context_tags` — Extracted from event fields. These are retrieval hooks. Clean.

**Checking ExperienceRetriever (experience_retriever.py):**

The retriever scores experiences by:
1. Tag overlap (0.4 per point) — Uses `context_tags`
2. Keyword overlap (0.1 per point, max 0.3) — Uses `raw_input`
3. Confidence weighting (0.1 × confidence) — Uses `confidence`

**Finding**: The retriever does NOT currently consider `prediction_error`, `success` rate, or `timestamp` in scoring. These are stored in the Experience but unused by the retriever. This means:
- A failed experience and a successful experience with the same tags get the same base score
- Older and newer experiences are treated equally
- The "quality" of an experience (how wrong the prediction was) is invisible to retrieval

**Checking ExperiencePredictionModule (experience_prediction.py):**

The predictor uses:
1. `success_count / total` as `experience_prob` — This IS a form of pattern (frequency-based)
2. Fixed 30% weight — Not adaptive
3. Same `predicted_outcome` text from base — No pattern-level outcome adjustment

**Finding**: The predictor already does a MINIMAL form of pattern recognition (frequency counting of success/failure per retrieved set). But this is EXPERIENCE-LEVEL aggregation, not PATTERN abstraction. It answers "what fraction of similar past events succeeded?" not "is there a general rule that applies here?"

### 2.4 Verdict on Phase 11 Purity

**Phase 11 is CLEAN for Experience abstraction.** No pattern knowledge has leaked into the Experience dataclass or the storage/retrieval pipeline. The frequency counting in ExperiencePredictionModule is a legitimate use of raw experiences for prediction adjustment — it does not constitute pattern formation because:
- It operates on a per-query basis (not stored independently)
- It doesn't generalize beyond the retrieved set
- It doesn't produce a reusable abstraction

---

## 3. State / Experience / Memory / Pattern / Knowledge Boundary

### 3.1 Definitions Grounded in Actual Code

| Concept | What It Is | Where It Lives | Current Implementation |
|---------|-----------|----------------|----------------------|
| **State** | Current internal condition of the system | `CortexState` (state/cortex_state.py) + `InternalState` (event.py:88-114) | Numeric values: uncertainty, confidence, active_goal, recent_inputs. Updated incrementally per event. Thread-local to Cortex instance. |
| **Experience** | A structured record of ONE past event | `Experience` dataclass (event.py:207-294) + `ExperienceStore` (memory/experience_store.py) | 15 fields capturing the complete snapshot of one event. Append-only JSONL. Independent of State. |
| **Memory** | The STORAGE SYSTEM for experiences | `ExperienceStore` + `ExperienceRetriever` (memory/) | Two classes: one for persistence, one for retrieval. "Memory" in the codebase IS the Experience subsystem. |
| **Pattern** | A generalizable rule extracted from MULTIPLE experiences | **NOT IMPLEMENTED** | N/A |
| **Knowledge** | Stable, validated patterns ready for deployment | **NOT IMPLEMENTED** | N/A |

### 3.2 Answering the Six Required Questions

**Q1: Is State "current internal condition" or "statistical result of past experience"?**

**Answer: Both, but they serve different purposes.**

- `CortexState.uncertainty` and `CortexState.confidence` ARE statistical results of past experience (updated by `update_from_event` based on outcome success/failure).
- BUT they are AGGREGATED numerics — they lose all episodic detail. After 10 successes, uncertainty drops from 0.20 to ~0.15, but you cannot tell WHICH 10 successes or WHAT their context was.
- State is for CURRENT-MOMENT adaptation (does the system feel confident right now?).
- Experience is for CONTEXTUAL reuse (what happened last time in a similar situation?).

**Code evidence** (cortex_state.py:41-79):
```python
if event.outcome.success:
    self.confidence = min(1.0, self.confidence + 0.05)
elif not event.outcome.success:
    self.confidence = max(0.0, self.confidence - 0.10)
    self.uncertainty = min(1.0, self.uncertainty + 0.10)
```
State adapts numerically. No episodic memory. No retrieval.

**Q2: Is Experience "one past event" or does it already contain abstracted conclusions?**

**Answer: One past event. Purely episodic.**

The Experience dataclass stores:
- `raw_input` — the exact text
- `intent` — the detected intent (derived, but still specific to this event)
- `action_type` — what action was taken
- `success` — boolean result
- `prediction_error` — how wrong the prediction was
- `context_tags` — retrieval anchors

There is NO field for "generalized rule" or "pattern summary". Each Experience is an atomic record of one event. The dataclass docstring confirms: "Structured record of a past event for future reuse."

**Q3: Is Memory a storage mechanism or a cognitive object?**

**Answer: In the current codebase, Memory IS the storage mechanism + retrieval system.**

The `memory/` package contains:
- `ExperienceStore` — the storage mechanism (JSONL file + dict cache)
- `ExperienceRetriever` — the retrieval mechanism (keyword scoring)

There is no separate "MemoryModule" implementation (MockMemory always returns empty). The Memory interface exists in `interfaces.py` but has no real implementation beyond the Experience subsystem.

**Code evidence** (interfaces.py:44-49):
```python
class MemoryModule(ABC):
    """Retrieve relevant past experiences for the current context."""
    @abstractmethod
    def process(self, event: CortexEvent) -> CortexEvent:
        ...
```

But `MockMemory.process()` always returns `MemoryData(retrieved_memories=[], memory_scores={})`. The ExperienceRetriever is called directly by ExperiencePredictionModule, NOT through the MemoryModule interface. This is an architectural inconsistency.

**Q4: What is the boundary between Pattern and Experience?**

**Answer: An Experience is a single data point. A Pattern is a relationship across multiple data points.**

| Aspect | Experience | Pattern |
|--------|-----------|---------|
| Scope | One event | Many events |
| Content | "I did X, got Y" | "When condition C, action A tends to produce outcome O" |
| Abstraction | Concrete (raw_input preserved) | Abstract (specific details removed) |
| Reusability | Retrieves by similarity to input | Applies to entire class of situations |
| Update | Append new | Merge/revise when contradicted |

**Example**:
- Experience: "fix a bug in login page" → success=True, action=code_review
- Experience: "fix a bug in payment module" → success=True, action=code_review
- Pattern (hypothetical): "When intent=fix, action=code_review produces success with high probability"

The pattern GENERALIZES beyond the specific inputs. It strips away "login page" and "payment module" and keeps only the structural relationship.

**Q5: What is the boundary between Pattern and Knowledge?**

**Answer: Knowledge is a Pattern that has survived sufficient testing to be trusted.**

| Aspect | Pattern | Knowledge |
|--------|---------|-----------|
| Evidence | Supported by some experiences | Supported by many experiences, low contradiction |
| Confidence | Can vary | High and stable |
| Lifetime | Candidate → Observed → Supported → Stable | Stable → Activated |
| Actionability | Reference during retrieval | Direct influence on prediction/decision |
| Reversibility | Easy to discard | Harder to discard (high cost of revision) |

A Pattern becomes Knowledge when it passes reliability thresholds. The key difference is TRUST, not structure.

**Q6: Does Prediction use Experience, Pattern, or both?**

**Answer: Currently ONLY Experience. No Pattern layer exists.**

Code evidence (experience_prediction.py:42-54):
```python
experiences = self._retriever.retrieve(
    raw_input=event.raw_input,
    intent=event.perception.intent,
    ...
)
# ...then directly aggregates success_count / total
```

Prediction retrieves raw experiences and computes a simple frequency. There is no intermediate Pattern abstraction.

---

## 4. Why Pattern Is / Is Not Needed

### 4.1 Does Current Experience-Only Approach Have Problems?

**Problem 1: Retrieval redundancy at scale**

With N experiences, the retriever scans ALL of them for every query. If N=10,000, this is 10,000 score computations per query. Patterns would compress thousands of experiences into tens of rules, reducing retrieval cost dramatically.

**Problem 2: No generalization beyond exact keyword overlap**

Current retriever uses keyword matching. "fix a bug" matches "fix a bug in the login page" but may NOT match "repair a defect in authentication" even though these are the SAME type of task. Patterns encode the structural relationship (intent=fix → action=code_review → success=high) independent of specific wording.

**Problem 3: Contradictory experiences create noise**

With 100 experiences, some will succeed and some will fail. The current 30% blend treats all retrieved experiences equally. A pattern like "fix+code_review → 80% success" is more actionable than "here are 12 similar experiences, 8 succeeded."

**Problem 4: No causal inference**

Current system asks "what happened before?" Pattern system should ask "WHAT CAUSES what outcome?" Knowing that "fix tasks often succeed" is different from knowing "using code_review action CAUSES fix tasks to succeed."

### 4.2 Does Pattern Solve These Problems?

| Problem | Experience-Only | With Pattern |
|---------|----------------|--------------|
| Retrieval redundancy | O(N) scan | O(P) where P << N (patterns compress) |
| Generalization | Keyword match only | Structural match (intent+action+context) |
| Contradictory experiences | All count equally | Pattern confidence weights evidence |
| Causal inference | Correlation only | Pattern can encode action→outcome links |

### 4.3 When Is Pattern NOT Needed?

- **Small scale** (< 100 experiences): Experience retrieval is fast enough, patterns add complexity without benefit
- **Deterministic environments**: If outcomes are fully predictable from input, patterns don't add value
- **One-shot tasks**: If the system rarely repeats similar tasks, episodic memory suffices

**Current situation**: We have ~9 experiences in live testing. At this scale, patterns are premature optimization. But the ARCHITECTURE should be ready for growth.

### 4.4 Verdict

**Pattern IS needed, but NOT as a replacement for Experience. Pattern is a COMPRESSION and GENERALIZATION layer ON TOP of Experience.**

The correct architecture is:
```
Experience (raw records) → Consolidation → Pattern (abstracted rules) → (optional) Knowledge (validated patterns)
```

Experience remains the source of truth. Pattern is a derived view. They coexist.

---

## 5. Pattern v1 Definition

### 5.1 Minimum Viable Pattern

A Pattern v1 must answer: **"Under what conditions does action A tend to produce outcome O?"**

### 5.2 Pattern Schema

```python
@dataclass
class Pattern:
    """Abstracted rule derived from multiple similar experiences."""
    
    # Identity
    pattern_id: str
    created_at: str
    source_experience_ids: list[str]  # Which experiences formed this pattern
    
    # Structure (the "rule")
    condition: str          # When this applies (e.g., "intent=fix AND action=code_review")
    predicted_outcome: str  # What tends to happen
    success_rate: float     # Fraction of supporting experiences that succeeded
    
    # Evidence
    support_count: int      # Number of experiences supporting this pattern
    contradiction_count: int  # Number of experiences contradicting this pattern
    confidence: float       # 0.0-1.0, based on support/contradiction ratio
    
    # Lifecycle
    status: str             # CANDIDATE | OBSERVED | SUPPORTED | STABLE | DECAYED | RETIRED
    last_observed_at: str
    last_contradicted_at: str | None
```

### 5.3 What Pattern v1 Does NOT Include

- No semantic embeddings
- No clustering algorithms
- No causal inference engine
- No learning rate adaptation
- No cross-domain generalization

### 5.4 Pattern v1 IS

- A frequency-counting abstraction over experiences sharing the same `condition`
- Deterministic (same inputs → same pattern)
- Reversible (can be downgraded or retired)
- Independent of Experience (patterns derive from experiences but are stored separately)

---

## 6. Pattern Formation Mechanism

### 6.1 Signals Analysis

| Signal | What It Means | Does It Imply Pattern? |
|--------|--------------|----------------------|
| **Frequency** | How often a condition appears | Necessary but NOT sufficient. Common ≠ correct. |
| **Similarity** | How alike the inputs are | Keyword match is shallow. "fix a bug" and "repair an issue" are similar in meaning but won't match keywords. |
| **Outcome consistency** | Do similar experiences have the same result? | Strongest signal. 5/5 success = reliable pattern. 3/5 = noisy. |
| **Context consistency** | Do the conditions match beyond just intent? | Important. "fix+code_review" vs "fix+code_edit" may have different outcomes. |
| **Success rate** | Fraction of successes among similar experiences | Direct measure of pattern reliability. |
| **Temporal stability** | Does the pattern hold across time? | Recent failures may invalidate old patterns. |
| **Contradiction rate** | How many experiences disagree? | High contradiction → pattern is unreliable. |

### 6.2 Key Insight: Frequency ≠ Pattern

Having 10 experiences of "fix a bug → success" does NOT mean there is a pattern. The pattern exists only if:
1. The experiences share a COMMON STRUCTURE (same intent, similar action, overlapping context)
2. The OUTCOMES are CONSISTENT (not random)
3. The STRUCTURE generalizes beyond the specific instances

**Example where frequency misleads**:
- Experience 1: "fix a bug" → success
- Experience 2: "fix a bug" → success  
- Experience 3: "fix a bug" → success
- Experience 4: "fix a bug" → failure
- Experience 5: "fix a bug" → failure

Frequency says "fix a bug" appeared 5 times. But the pattern is UNCERTAIN (60% success). A naive "majority rules" approach would form a weak pattern. A proper pattern system should represent the UNCERTAINTY.

**Example where similarity misleads**:
- Experience 1: "fix the login bug" → success (action=code_review)
- Experience 2: "deploy to production" → failure (action=tool_call)
- These share keyword "fix" loosely, but the PATTERNS are完全不同.

Similarity must be STRUCTURAL (same intent+action+context tags), not just lexical.

### 6.3 Recommended Formation Algorithm (v1)

```
For each unique (intent, action_type) combination in the experience store:
  1. Gather all experiences matching this combination
  2. Count: success_count, failure_count, total
  3. Compute: success_rate = success_count / total
  4. Compute: confidence = success_rate * sigmoid(total - threshold)
     - Below threshold experiences: CANDIDATE (not enough evidence)
     - Above threshold: pattern strength grows with count
  5. Check contradictions: if any experience in the group has 
     success != majority, increment contradiction_count
  6. Create/update Pattern record
```

This is deterministic, requires no ML, and produces interpretable results.

---

## 7. Pattern Confidence / Evidence Model

### 7.1 Evidence Requirements

| Status | Minimum Support | Max Contradiction | Confidence Range |
|--------|----------------|-------------------|-----------------|
| CANDIDATE | 1 experience | Any | 0.0 - 0.3 |
| OBSERVED | 2 experiences | ≤ 50% | 0.3 - 0.5 |
| SUPPORTED | 3 experiences | ≤ 33% | 0.5 - 0.7 |
| STABLE | 5 experiences | ≤ 20% | 0.7 - 0.9 |
| WEAKENING | Any | > 50% | < 0.3 (regardless of count) |

**Rationale for thresholds**:
- 1 experience is never enough for a pattern (could be coincidence)
- 2 experiences start to show a trend but are fragile
- 3 experiences is the minimum for a "supported" pattern
- 5 experiences provides reasonable statistical confidence for a deterministic system
- >50% contradiction rate means the pattern is actively wrong, regardless of count

### 7.2 Parameters Explained

- **minimum_support**: Number of matching experiences required before a pattern is considered. 3 is the minimum for "SUPPORTED" status.
- **consistency_threshold**: Maximum allowed fraction of contradictory experiences. 33% means at most 1 in 3 experiences can disagree.
- **confidence**: Computed as `success_rate * weight(total)`, where weight increases with experience count but saturates.
- **recency**: Not used in v1. All experiences have equal temporal weight.
- **experience_weight**: Not used in v1. All experiences contribute equally.

### 7.3 Why No Magic Numbers Without Justification

The thresholds above are justified by the system's requirements:
- This is a DETERMINISTIC, RULE-BASED system (no probabilistic guarantees from statistics)
- The goal is SAFETY (don't form false patterns) not COMPLETENESS (find all patterns)
- False patterns are worse than missed patterns (a wrong pattern corrupts behavior; a missing pattern just means less optimization)

---

## 8. Contradiction / Noise / False Pattern Handling

### 8.1 Failure Modes

| Failure Mode | Description | Mitigation |
|-------------|-------------|------------|
| **Error Pattern** | A pattern formed from predominantly wrong experiences | Contraction: high contradiction rate → pattern degrades to CANDIDATE or RETIRED |
| **Confirmation Bias** | System only retrieves experiences that confirm existing beliefs | Pattern formation is GLOBAL (scans ALL experiences), not selective |
| **Majority Bias** | 60% success looks like a strong pattern but is actually weak | Confidence formula requires BOTH high success rate AND sufficient count |
| **Noisy Experience** | Single bad experience corrupts a pattern | Contradiction_count tracks disagreements; high ratio degrades pattern |
| **Contradictory Experience** | New experience directly conflicts with existing pattern | Pattern moves to WEAKENING status; may trigger re-consolidation |
| **Stale Pattern** | Old pattern no longer applies (environment changed) | No decay in v1. Explicit retirement required. |
| **Negative Transfer** | Pattern from domain A incorrectly applied to domain B | Pattern condition includes intent+action; cross-domain patterns have low confidence |

### 8.2 Can Patterns Be Overturned?

**YES.** Pattern lifecycle includes:
- `DECAYED` — Pattern is losing support (contradictions increasing)
- `RETIRED` — Pattern is discarded (contradiction rate > 50% or explicit invalidation)

Retired patterns are removed from active use but PRESERVED in storage for auditability.

### 8.3 Can Patterns Be Downgraded?

**YES.** Pattern status can move down the hierarchy:
- STABLE → SUPPORTED (new contradictions)
- SUPPORTED → OBSERVED (too many contradictions)
- OBSERVED → CANDIDATE (insufficient evidence)
- CANDIDATE → (auto-removed if never reaches OBSERVED after N days)

### 8.4 Critical Safety Property

**A pattern NEVER produces a prediction probability higher than the base prediction's maximum + experience_weight cap.**

Current: `adjusted = 0.7 * base + 0.3 * experience_prob`
With Pattern: `adjusted = 0.5 * base + 0.25 * experience_signal + 0.25 * pattern_signal`

The pattern signal is BOUNDED and SUBSIDIARY. It cannot override the base prediction.

---

## 9. Pattern Lifecycle

### 9.1 Candidate Lifecycle (v1)

```
CANDIDATE → OBSERVED → SUPPORTED → STABLE
     ↑         ↓
     └── WEAKENING ←──┘
             ↓
          RETIRED
```

**Transitions**:
- CANDIDATE → OBSERVED: support_count >= 2 AND contradiction_rate <= 50%
- OBSERVED → SUPPORTED: support_count >= 3 AND contradiction_rate <= 33%
- SUPPORTED → STABLE: support_count >= 5 AND contradiction_rate <= 20%
- Any → WEAKENING: contradiction_rate > 50%
- WEAKENING → RETIRED: no new supporting experiences within observation window
- Any → CANDIDATE: new contradictory experience reduces status

### 9.2 Why This Lifecycle?

- **CANDIDATE**: Too few experiences to trust. Don't use for prediction.
- **OBSERVED**: A trend is visible but fragile. Light influence on prediction.
- **SUPPORTED**: Enough evidence to be useful. Normal prediction influence.
- **STABLE**: Well-tested. Maximum pattern influence.
- **WEAKENING**: Actively being contradicted. Reduce influence.
- **RETIRED**: No longer valid. Remove from prediction pipeline.

### 9.3 Minimum Evidence for Pattern Formation

**Answer: 3 experiences with ≤ 33% contradiction rate.**

Justification:
- 1 experience: Could be coincidence. Not enough.
- 2 experiences: Shows a trend but could still be coincidence. "Observed" level.
- 3 experiences: First point where we can reasonably distinguish signal from noise in a deterministic system.
- 5 experiences: Comfortable confidence for "Stable" patterns.

More than 5 does not significantly improve reliability in a deterministic system (unlike statistical systems where more data = better estimates).

---

## 10. Pattern → Behavior Options

### 10.1 Option A: Pattern → Prediction

```
BasePrediction → ExperiencePrediction → PatternPrediction → Final Prediction
```

**Path**: Pattern adjusts prediction probability, same as current ExperiencePredictionModule.
**Pros**: Minimal architecture change. ExperiencePredictionModule becomes PatternPredictionModule.
**Cons**: Same as current — pattern influence is indirect, through probability blending.
**Risk**: Low. Same bounding mechanism as ExperiencePrediction.

### 10.2 Option B: Experience + Pattern → Prediction

```
BasePrediction → {ExperienceSignal, PatternSignal} → Weighted Blend → Final
```

**Path**: Both raw experiences AND patterns contribute to prediction.
**Pros**: Experiences provide context-specific signal; patterns provide general signal.
**Cons**: More complex weighting. Need to decide how to balance.
**Risk**: Medium. Wrong balance could cause pattern over Influence.
**Formula**: `adjusted = w_base * base + w_exp * experience_prob + w_pat * pattern_prob`
where `w_base + w_exp + w_pat = 1.0`

### 10.3 Option C: Pattern → State

```
Pattern → CortexState.update() → State affects Prediction thresholds
```

**Path**: Patterns update uncertainty/confidence in CortexState, which then affects BasicPrediction routing.
**Pros**: Leverages existing state adaptation path. Patterns influence through the same mechanism as outcomes.
**Cons**: State is aggregate; pattern-specific state is lost. Can't distinguish "I'm uncertain because of X pattern" from "I'm uncertain because of Y."
**Risk**: High. State changes are irreversible (no undo). Pattern errors pollute state permanently.

### 10.4 Option D: Pattern → Decision

```
Pattern → modifies INTENT_ACTION_MAP → Decision chooses different action
```

**Pros**: Most direct behavioral change. Pattern can suggest a DIFFERENT action.
**Cons**: Breaks the clean separation between Prediction and Decision. Decision module becomes pattern-aware.
**Risk**: Very High. Changing action selection based on patterns is a fundamental behavioral shift, not just a probability adjustment.

### 10.5 Recommendation

**Recommended: Option B (Experience + Pattern → Prediction)**

Rationale:
- Preserves the existing ExperiencePredictionModule architecture
- Adds Pattern as a new signal source alongside Experience
- Maintains bounded influence (pattern weight ≤ experience weight)
- Does not touch State or Decision (frozen layers)
- Allows patterns to generalize beyond specific experiences

**Not recommended**:
- Option A: Too simple, doesn't leverage pattern generalization
- Option C: State pollution risk, irreversible
- Option D: Breaks Prediction/Decision separation, highest risk

---

## 11. Recommended Architecture

### 11.1 New Module: PatternConsolidator

```
neuro-cortex/src/neurocortex/pattern/
├── __init__.py              # exports Pattern, PatternConsolidator, PatternRetriever
├── pattern.py               # Pattern dataclass
├── consolidator.py          # Experience → Pattern formation
└── retriever.py             # Pattern retrieval (by condition match)
```

### 11.2 Integration Points

```
ExperienceStore (existing)
    ↓ save
ExperienceLearningModule (existing)
    ↓
[NEW] PatternConsolidator.consolidate()
    ↓ scans ExperienceStore, groups by (intent, action_type)
    ↓ creates/updates Pattern records
    ↓
PatternStore (NEW — JSONL, separate from ExperienceStore)
    ↓
[NEW] PatternRetriever.retrieve(condition)
    ↓
ExperiencePredictionModule.process()
    ↓ NOW reads BOTH experiences AND patterns
    ↓
Prediction (adjusted)
```

### 11.3 Interface Contract

```python
class PatternConsolidator:
    """Examines ExperienceStore and produces/updates Pattern records."""
    def consolidate(self, store: ExperienceStore) -> list[Pattern]:
        """Scan all experiences, produce patterns."""
        ...

class PatternRetriever:
    """Retrieve patterns matching a condition."""
    def retrieve(self, intent: str, action_type: str) -> list[tuple[Pattern, float]]:
        """Return (pattern, confidence) tuples sorted by relevance."""
        ...
```

### 11.4 Dependency Injection

PatternConsolidator is NOT part of the main pipeline. It runs:
- On-demand (when queried by ExperiencePredictionModule)
- OR in background (separate thread/process)
- NOT during the 11-stage pipeline (to avoid blocking)

This keeps Phase 0-11 frozen and adds Pattern as an OPTIONAL enhancement.

---

## 12. Phase 12 MVP

### 12.1 Minimum Viable Pattern System

**What MUST exist:**
1. `Pattern` dataclass (event.py or new pattern/pattern.py)
2. `PatternConsolidator` — groups experiences by (intent, action_type), computes success_rate, confidence, status
3. `PatternStore` — JSONL persistence (same pattern as ExperienceStore)
4. `PatternRetriever` — retrieves patterns by condition match
5. `PatternPredictionModule` — wraps ExperiencePredictionModule, blends pattern signal
6. Tests — minimum 10 tests covering formation, retrieval, confidence, lifecycle

**What MUST NOT exist:**
- No ML/clustering/embeddings
- No real-time consolidation during pipeline
- No pattern→state or pattern→decision modification
- No cross-Cortex pattern sharing
- No pattern aging/decay
- No semantic generalization beyond (intent, action_type) grouping

### 12.2 Implementation Scope

**New files (5):**
1. `src/neurocortex/pattern/pattern.py` — Pattern dataclass
2. `src/neurocortex/pattern/consolidator.py` — PatternConsolidator
3. `src/neurocortex/pattern/store.py` — PatternStore
4. `src/neurocortex/pattern/retriever.py` — PatternRetriever
5. `tests/test_phase12.py` — 10+ tests

**Modified files (3):**
1. `src/neurocortex/prediction/experience_prediction.py` — Add pattern signal blend
2. `src/neurocortex/pattern/__init__.py` — Package exports
3. `tests/test_phase11.py` — Add regression test (no changes to existing tests)

**Total new code**: ~300 lines
**Total new tests**: ~15 tests
**Expected total**: 426 + 15 = 441 PASS

### 12.3 What Phase 12 MVP Does NOT Do

- Does NOT replace ExperiencePredictionModule
- Does NOT modify CortexState
- Does NOT modify BasicPrediction
- Does NOT modify Decision module
- Does NOT modify any frozen Phase 0-11 code
- Does NOT introduce any non-deterministic behavior
- Does NOT require any new dependencies

---

## 13. Required Experiments

### P1: Single Experience → No Pattern
**Input**: 1 experience with intent=fix, success=True
**Expected**: No pattern formed (support_count < 3)
**Verification**: PatternStore.count() == 0

### P2: Two Similar Success Experiences → Candidate Pattern
**Input**: 2 experiences, same intent=fix, both success=True
**Expected**: Pattern created with status=CANDIDATE
**Verification**: Pattern exists, support_count=2, confidence < 0.3

### P3: Three Consistent Experiences → Supported Pattern
**Input**: 3 experiences, same intent=fix, all success=True
**Expected**: Pattern status=SUPPORTED
**Verification**: support_count=3, contradiction_count=0, confidence >= 0.5

### P4: Similar but Different Outcomes → No Strong Pattern
**Input**: 3 experiences, same intent=fix, 2 success + 1 failure
**Expected**: Pattern status=OBSERVED or WEAKENING
**Verification**: contradiction_count=1, confidence < 0.5

### P5: Mixed Success/Failure → Pattern Degradation
**Input**: Start with 5 success experiences (STABLE pattern), then add 3 failures
**Expected**: Pattern degrades to WEAKENING or RETIRED
**Verification**: contradiction_rate > 50% after additions

### P6: Many Repetitive Experiences → Majority Bias Check
**Input**: 10 experiences, 7 success + 3 failure (70% success)
**Expected**: Pattern exists but confidence reflects uncertainty
**Verification**: confidence ~0.6-0.7, not 1.0

### P7: Majority Wrong → Pattern Should Not Form
**Input**: 5 experiences, 4 failure + 1 success
**Expected**: Pattern either not formed or status=RETIRED
**Verification**: If pattern exists, confidence < 0.3

### P8: New Experience Overturns Old Pattern
**Input**: 5 success experiences → pattern STABLE. Then 3 failure experiences.
**Expected**: Pattern moves to WEAKENING → RETIRED
**Verification**: Pattern status=RETIRED, not used in prediction

### P9: Pattern Decay (Time-Based)
**Input**: Pattern formed from old experiences, new experiences don't match
**Expected**: In v1, NO automatic decay. Pattern persists until explicitly retired.
**Verification**: Pattern still exists after time passes (this is a KNOWN LIMITATION)

### P10: Pattern Retirement
**Input**: Pattern with status=STABLE, then contradiction pushes it to RETIRED
**Expected**: Retired pattern is excluded from prediction
**Verification**: Retired pattern returns empty from retriever

### P11: No Relevant Pattern → Fallback to Experience-Only
**Input**: Query for intent that has no patterns
**Expected**: Prediction uses ExperiencePredictionModule normally (same as Phase 11)
**Verification**: Probability unchanged from Phase 11 baseline

### P12: Relevant Pattern → Observable Prediction Change
**Input**: Query for intent with a STABLE pattern (e.g., fix → 90% success)
**Expected**: Prediction probability differs from experience-only baseline
**Verification**: |prob_with_pattern - prob_without_pattern| > 0.05

### P13: Wrong Pattern → Should Not Permanently Pollute
**Input**: Form a pattern from misleading experiences, then add correcting experiences
**Expected**: Pattern degrades and is retired; prediction returns to normal
**Verification**: After correction, prediction matches baseline

### P14: Restart Persistence
**Input**: Create patterns, restart cortex (new instance, load from file)
**Expected**: Patterns reload correctly
**Verification**: PatternStore.count() matches before/after restart

### P15: Cross-Cortex Pattern Isolation
**Input**: Two Cortex instances, different experience stores
**Expected**: Patterns are isolated per instance
**Verification**: Instance A's patterns not visible to Instance B

### P16: Determinism
**Input**: Same 10 experiences, run consolidation twice
**Expected**: Identical patterns produced
**Verification**: Pattern lists are equal (same IDs, same fields)

### P17: Consolidation Cost at Scale
**Input**: 100, 1000, 10000 experiences
**Expected**: Consolidation time grows linearly, not exponentially
**Verification**: Measure and report timing

---

## 14. ML / LLM Necessity

### 14.1 Answer: NO ML Required for Pattern v1

**Why deterministic algorithm is sufficient:**

1. **Pattern formation is grouping + counting** — This is fundamentally a statistical aggregation task, not a learning task. `groupby(intent, action_type)` + `count(success/failure)` is O(N) and deterministic.

2. **No semantic understanding needed** — v1 patterns operate on EXPLICIT fields (intent, action_type). These are already categorized by the Perception module. No embedding or clustering is needed to group experiences.

3. **No adaptation needed** — The pattern formation rules are FIXED (3 experiences min, 33% contradiction max). These don't need to be "learned."

4. **Debuggability** — A deterministic algorithm produces the SAME pattern from the SAME experiences. This is critical for a system where behavioral changes must be traceable.

### 14.2 When Would ML Become Necessary?

| Future Need | Why ML Helps | When to Consider |
|------------|-------------|-----------------|
| Semantic similarity | "fix a bug" ≈ "repair an issue" | When keyword matching proves insufficient (many false negatives) |
| Automatic feature extraction | Discover hidden dimensions beyond intent/action | When manual condition specification becomes impractical |
| Adaptive thresholds | Learn optimal support/contradiction thresholds from data | When fixed thresholds prove too rigid |
| Cross-domain patterns | "fix bug" pattern transfers to "fix login issue" | When domain-specific patterns prove too narrow |

### 14.3 Deterministic Approach Failure Mode

The deterministic approach fails when:
- Experience conditions are TOO SPECIFIC (no two experiences share the same condition)
- Experience conditions are TOO BROKE (too many experiences share the same condition, pattern is meaningless)
- Semantic similarity is needed but keywords don't match

**Mitigation in v1**: Use (intent, action_type) as the grouping key. This is broad enough to capture meaningful groups but specific enough to avoid noise. If this proves insufficient, Phase 13+ can add richer condition matching.

---

## 15. Resource / Scaling Analysis

### 15.1 Storage

| Scale | Experiences | Patterns (est.) | Experience Store | Pattern Store |
|-------|------------|-----------------|-----------------|---------------|
| Small | 100 | ~20 (5 intents × 4 actions) | ~50 KB | ~10 KB |
| Medium | 1,000 | ~50 | ~500 KB | ~25 KB |
| Large | 10,000 | ~200 | ~5 MB | ~100 KB |
| Enterprise | 100,000 | ~2,000 | ~50 MB | ~1 MB |

Pattern storage is ~2% of experience storage. Negligible overhead.

### 15.2 Consolidation Cost

Consolidation scans all experiences once and groups by (intent, action_type).

| Scale | Operations | Estimated Time |
|-------|-----------|---------------|
| 100 | 100 scans + 20 groups | < 1 ms |
| 1,000 | 1,000 scans + 50 groups | < 10 ms |
| 10,000 | 10,000 scans + 200 groups | < 100 ms |
| 100,000 | 100,000 scans + 2,000 groups | < 1 second |

### 15.3 Retrieval Cost

Pattern retrieval is O(P) where P = number of patterns (~2% of N). Significantly faster than experience retrieval (O(N)) at scale.

### 15.4 Consolidation Strategy

**Recommended: Lazy consolidation (on-demand)**

- Do NOT consolidate during the 11-stage pipeline
- Consolidate when PatternRetriever is first called after a threshold of new experiences
- Threshold: consolidate when experience_count % 10 == 0 (every 10 new experiences)
- This avoids blocking the pipeline while keeping patterns reasonably fresh

**Alternative: Background consolidation**

- Run consolidation in a separate thread
- Periodic (every N seconds) or event-driven (after each experience save)
- More complex, not needed for v1

**Not recommended: Real-time consolidation**

- Every experience save triggers full re-consolidation
- O(N) per save — unacceptable at scale
- Blocks the learning pipeline

---

## 16. Hermes Integration

### 16.1 Current State

**No Hermes code exists in this repository.** The search for "hermes" returned zero results. The Phase 12 audit document mentions Hermes Memory (Episodic, Semantic, Hybrid Retriever, Experience JSONL, Evolution) but these do not exist in the current codebase.

### 16.2 Implications

Since Hermes is not part of this codebase, Phase 12 Pattern must be:
- **Self-contained within NeuroCortex**
- **Not dependent on external Hermes components**
- **Designed to be compatible with future Hermes integration**

### 16.3 Recommended Integration Model (Future)

If Hermes is later integrated, the cleanest model is:

```
NeuroCortex: Defines Pattern schema + consolidation logic
Hermes:     Provides storage + retrieval infrastructure
           (Experience JSONL, Semantic Memory, Evolution)
```

This means:
- NeuroCortex's PatternConsolidator writes to a `PatternStore`
- PatternStore can be backed by Hermes's storage layer in the future
- The Pattern dataclass and consolidation algorithm remain NeuroCortex-owned
- No duplication of Pattern logic between NeuroCortex and Hermes

### 16.4 Option Assessment

| Option | Fit | Recommendation |
|--------|-----|---------------|
| A. Pattern fully in NeuroCortex | Self-contained, clean boundary | ✓ RECOMMENDED for v1 |
| B. Pattern fully in Hermes | Not applicable (Hermes doesn't exist yet) | N/A |
| C. NeuroCortex defines, Hermes stores | Good separation, future-proof | ✓ RECOMMENDED for v2 |
| D. Shared Pattern abstraction | Risks circular dependency | ✗ AVOID |

---

## 17. Frozen Architecture Impact

### 17.1 What Is Frozen and Protected

| Layer | Commit | Status | Can Phase 12 Touch? |
|-------|--------|--------|-------------------|
| Phase 0-4 (skeleton, perception, representation, state, prediction) | Various | FROZEN | NO |
| Phase 5 (prediction) | 50656ca | FROZEN | NO |
| Phase 6 (feedback) | 078f8fc | FROZEN | NO |
| Phase 7 (decision) | 546b42e | FROZEN | NO |
| Phase 8 (action) | 00ac18f | FROZEN | NO |
| Phase 9 (learning loop) | 9e2e176 | FROZEN | NO |
| Phase 10 (adaptive behavior) | b3ab0c8 | FROZEN | NO |
| Phase 11 (experience) | 98dfcea | FROZEN | NO (except adding new imports) |

### 17.2 What Phase 12 CAN Modify

1. **Add new files** — `src/neurocortex/pattern/` directory (all new)
2. **Modify `src/neurocortex/prediction/experience_prediction.py`** — Add pattern signal blend (NOT replace, ADD to)
3. **Modify `src/neurocortex/prediction/__init__.py`** — Export new PatternPredictionModule
4. **Add new tests** — `tests/test_phase12.py`
5. **Add documentation** — `.monkeycode/specs/phase-12-pattern-consolidation/`

### 17.3 What Phase 12 MUST NOT Modify

1. **Any Phase 0-10 file** — Strictly frozen
2. **Experience dataclass** — Add fields? NO. Modify existing fields? NO.
3. **ExperienceStore** — Add methods? NO.
4. **ExperienceRetriever** — Modify scoring? NO.
5. **ExperienceLearningModule** — Modify capture logic? NO.
6. **CortexEvent stage progression** — Add stages? NO.
7. **Cortex pipeline order** — Add stages? NO.
8. **Any interface protocol** — Add new methods to existing protocols? NO.

### 17.4 ARCHITECTURAL BLOCKER Check

**Is there any Phase 11 design issue that blocks Phase 12?**

**Finding 1: ExperiencePredictionModule calls ExperienceRetriever directly, bypassing MemoryModule interface.**

This is an architectural inconsistency but NOT a blocker. The MemoryModule interface exists but is unused (MockMemory returns empty). ExperiencePredictionModule directly depends on ExperienceRetriever. Phase 12 should follow the same pattern — PatternPredictionModule directly depends on PatternRetriever.

**Finding 2: Experience dataclass stores `uncertainty` from InternalState.**

This mixes State and Experience domains slightly. However, it's useful context (the system's uncertainty at the time of the event). This is NOT a blocker — it's a design choice that aids pattern formation (patterns can weigh recent-vs-old experiences based on uncertainty).

**Finding 3: No consolidation trigger mechanism.**

ExperienceLearningModule saves experiences but never triggers consolidation. Phase 12 must add this. This is a GAP in Phase 11, not a blocker.

**Verdict**: No ARCHITECTURAL BLOCKER found. Phase 12 can proceed with the recommended approach.

---

## 18. Risks / Blockers

### 18.1 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pattern over-fitting to noise | Medium | Medium | Minimum support threshold (3), contradiction tracking |
| Pattern stagnation (never retires) | High | Low | Explicit retirement mechanism, manual override |
| Pattern contradicts experience signal | Medium | Medium | Bounded blend (pattern weight ≤ experience weight) |
| Consolidation blocks pipeline | Low | High | Lazy/on-demand consolidation, not in-pipeline |
| Pattern retrieval slower than experience retrieval | Low | Low | Patterns are ~2% of experiences; retrieval is faster |
| False pattern from correlated but not causal data | Medium | Medium | Patterns encode correlation only; no causal claim |

### 18.2 Blockers

**None identified.** Phase 12 can proceed with the recommended MVP scope.

### 18.3 Known Limitations Inherited from Phase 11

1. **No experience aging** — Old and new experiences weigh equally. Patterns formed from stale data may be inaccurate.
2. **Keyword-only retrieval** — Semantically similar but lexically different experiences won't group together.
3. **No experience limit** — Store grows unbounded. At 100K+ experiences, consolidation becomes slow.
4. **Fixed 30% experience weight** — Cannot adapt to different contexts.
5. **No cross-cortex sharing** — Each instance has isolated experience and (future) pattern stores.

---

## 19. Final Verdict

### 19.1 Answer to the 10 Most Important Questions

**Q1: What is the true boundary between Experience and Pattern?**
Experience is a single event record. Pattern is a generalized rule extracted from multiple events sharing the same condition (intent + action_type). Experience preserves detail; Pattern abstracts it away.

**Q2: When is an Experience sufficient to form a Pattern?**
Never alone. A single Experience can never form a Pattern. Minimum 3 experiences with the same condition and ≤ 33% contradiction rate.

**Q3: How does a Pattern prove its reliability?**
By surviving contradiction. A pattern's confidence is computed from `success_rate * sigmoid(support_count - threshold)`. High confidence requires both high success rate AND sufficient supporting evidence.

**Q4: How does the system avoid forming wrong Patterns from错误 experiences?**
Through the contradiction mechanism. If > 50% of supporting experiences fail, the pattern moves to WEAKENING → RETIRED. Patterns from predominantly wrong data are either not formed or quickly retired.

**Q5: How can a Pattern be overturned?**
By new contradictory experiences pushing the contradiction rate above 50%. The pattern transitions to WEAKENING, then RETIRED. Retired patterns are excluded from prediction.

**Q6: Does Pattern need independent persistence?**
Yes. Patterns must be stored separately from experiences so they can be loaded independently and so that pattern retirement doesn't delete the underlying experiences.

**Q7: Should Pattern influence Prediction?**
Yes, but as a BOUNDED supplement to Experience, not a replacement. Pattern signal should be blended alongside Experience signal with a weight ≤ the experience weight.

**Q8: Should Pattern directly influence Decision?**
No. Decision should remain based on Prediction output. Pattern influences Prediction, which influences Decision. Direct Pattern→Decision coupling breaks the clean pipeline separation.

**Q9: Should Pattern enter State?**
No. State is for CURRENT-MOMENT internal condition. Pattern is a derived abstraction from past experiences. Mixing them would make State depend on historical data, breaking the clean snapshot model.

**Q10: What is the Phase 12 MVP?**
A Pattern dataclass, a PatternConsolidator (experience→pattern grouping by intent+action_type), a PatternStore (JSONL), a PatternRetriever, and a modified ExperiencePredictionModule that blends pattern signal. ~300 lines of new code, ~15 new tests, zero modifications to frozen Phase 0-11 code.

### 19.2 Final Decision

**APPROVED FOR PHASE 12 IMPLEMENTATION**

**MVP Scope:**

1. **New files (5):**
   - `src/neurocortex/pattern/pattern.py` — Pattern dataclass
   - `src/neurocortex/pattern/consolidator.py` — PatternConsolidator
   - `src/neurocortex/pattern/store.py` — PatternStore
   - `src/neurocortex/pattern/retriever.py` — PatternRetriever
   - `tests/test_phase12.py` — 15+ tests

2. **Modified files (2):**
   - `src/neurocortex/prediction/experience_prediction.py` — Add pattern signal blend
   - `src/neurocortex/pattern/__init__.py` — Package exports

3. **Do NOT modify:**
   - Any Phase 0-10 file
   - Any Phase 11 file (except adding imports in __init__.py)
   - CortexEvent core schema
   - Pipeline stage order
   - Any interface protocol

4. **Do NOT introduce:**
   - ML, embeddings, clustering
   - Real-time consolidation during pipeline
   - Pattern→State or Pattern→Decision coupling
   - Cross-Cortex pattern sharing
   - Automatic pattern decay

5. **Test baseline:** 426 PASS (must remain 426 PASS + new Phase 12 tests)
6. **Expected final:** ~441 PASS / 0 FAIL

### 19.3 Out of Scope for Phase 12

- Semantic similarity (keyword-only for v1)
- Pattern aging/decay
- Cross-domain pattern transfer
- Pattern→Decision coupling
- Pattern→State coupling
- Hermes integration
- Experience eviction policy
- Adaptive consolidation triggers

---

**Audit Complete. Output: APPROVED FOR PHASE 12 IMPLEMENTATION.**
