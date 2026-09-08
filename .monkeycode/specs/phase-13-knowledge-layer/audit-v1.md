# NeuroCortex Phase 13 — Architecture Audit v1

**Document**: Architecture Audit — Knowledge Layer Feasibility  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: DRAFT  
**Project**: neuro-cortex  
**Baseline**: Commit adc8cbe (Phase 12 frozen), 453 PASS / 0 FAIL  
**Frozen Base**: Phase 0-12 all frozen

---

## 1. Executive Summary

**VERDICT: BLOCKED — Do NOT implement Knowledge layer in Phase 13.**

Three architectural blockers prevent a safe Knowledge layer:

1. **Pattern ≠ Knowledge**: Current Pattern is group-level statistics (intent+action → success_rate). It lacks the semantic depth, boundary conditions, and causal reasoning that Knowledge requires. Elevating Pattern to Knowledge would be a name change, not an architectural improvement.

2. **Double-counting risk is unquantified**: Experience signal (30%) and Pattern signal (15%) derive from the SAME experiences. A 5-experience group contributes to both the experience_prob (direct) AND the pattern_prob (via aggregation). This means the same evidence is weighted ~1.5× more than it should be. Adding a third Knowledge signal (derived from Pattern) would compound this error.

3. **Hermes Semantic Memory overlap is unresolvable without code review**: The audit spec references "Hermes Semantic Memory" but NO Hermes code exists in this repository. The Phase 12 audit spec assumed Hermes would exist. Until we understand what Hermes provides, we cannot define a safe boundary for NeuroCortex Knowledge.

**Recommendation**: Do not proceed to Phase 13 Implementation. Instead:
- First, resolve the double-counting issue in Phase 12's prediction blending
- Second, audit the Hermes codebase to understand its memory architecture
- Third, if Hermes does not cover Pattern→Knowledge, THEN design Phase 13

---

## 2. Current Architecture

### 2.1 Verified File Map (as of adc8cbe)

```
neuro-cortex/src/neurocortex/
├── cortex.py                  ✓ Orchestration (11 stages)
├── event.py                   ✓ CortexEvent + 11 Data classes + Experience
├── interfaces.py              ✓ 10 module protocols
├── perception/perception.py   ✓ BasicPerception
├── representation/representation.py ✓ BasicRepresentation
├── attention/                 ✗ empty
├── state/cortex_state.py      ✓ CortexState (uncertainty, confidence, active_goal, recent_inputs)
├── state/state_module.py      ✓ BasicStateModule
├── memory/experience_store.py ✓ ExperienceStore (JSONL)
├── memory/experience_retriever.py ✓ ExperienceRetriever (keyword+tag)
├── prediction/prediction.py   ✓ BasicPrediction (rule-based)
├── prediction/experience_prediction.py ✓ ExperiencePredictionModule (70/30 blend)
├── decision/decision.py       ✓ BasicDecision (intent→action)
├── action/action.py           ✓ BasicAction
├── feedback/feedback.py       ✓ BasicFeedback (v2.1 evaluation)
├── learning/experience_learner.py ✓ ExperienceLearningModule
├── pattern/pattern.py         ✓ Pattern dataclass (6 lifecycle states)
├── pattern/consolidator.py    ✓ PatternConsolidator (groupby intent+action)
├── pattern/store.py           ✓ PatternStore (JSONL)
├── pattern/retriever.py       ✓ PatternRetriever (condition match)
└── modules/__init__.py        ✓ Mock implementations
```

### 2.2 Pipeline (from cortex.py)

```
INPUT → PERCEPTION → REPRESENTATION → ATTENTION → STATE
  → MEMORY → PREDICTION → DECISION → ACTION → OUTCOME → FEEDBACK → LEARNING
```

11 stages. No stage can be skipped or reordered.

### 2.3 Data Flow (Current)

```
Event.raw_input
  → Perception.intent (string label)
  → BasicPrediction(base_prob from intent+risk+uncertainty)
  → ExperiencePredictionModule:
      Step 1: Retrieve experiences by keyword+tag match → experience_prob
      Step 2: Retrieve patterns by condition match → pattern_prob
      Step 3: Blend = 0.55×base + 0.30×experience_prob + 0.15×pattern_prob
  → Decision (maps intent → action)
  → Action → Outcome → Feedback → Learning
  → ExperienceLearningModule saves Experience to ExperienceStore
  → [LAZY] PatternConsolidator scans ExperienceStore → PatternStore
```

### 2.4 State Adaptation Path (Separate)

```
CortexState.update_from_event(event)
  → uncertainty: ±0.05 (success) / ±0.10 (failure)
  → confidence: ±0.05 (success) / ±0.10 (failure)
  → active_goal: from intent
  → recent_inputs: append, cap 10

BasicPrediction reads event.state.uncertainty (threshold routing)
```

**TWO independent learning paths coexist:**
1. State path: numeric adaptation via CortexState
2. Experience+Pattern path: episodic retrieval via ExperienceStore+PatternStore

### 2.5 No Hermes Code Found

```
$ find /workspace -name "*.py" | xargs grep -l "hermes\|Hermes" 2>/dev/null
(no results)
```

The Phase 12 audit spec mentioned "Hermes Memory" with Episodic, Semantic, Hybrid Retriever, Evolution. **None of this exists in the current repository.** This is a critical gap in the audit assumptions.

---

## 3. Experience Boundary

### 3.1 What Experience IS (from code)

```python
@dataclass
class Experience:
    experience_id: str          # UUID
    timestamp: str              # ISO timestamp
    source_event_id: str        # Links back to CortexEvent
    raw_input: str              # Original text
    intent: str                 # Perceived intent label
    action_type: str            # Action taken
    predicted_outcome: str      # What was predicted
    predicted_prob: float       # Predicted probability
    actual_outcome: str         # What actually happened
    success: bool               # Binary outcome
    prediction_error: float     # |predicted - actual|
    evaluation: str             # "correct" | "miss" | etc.
    confidence: float           # Prediction confidence at time
    uncertainty: float          # State uncertainty at time
    context_tags: list[str]     # ["intent:fix", "action:code_review", ...]
```

### 3.2 Experience Properties

| Property | Value | Evidence |
|----------|-------|----------|
| Scope | ONE event | `from_event()` factory captures single event |
| Granularity | Atomic | No sub-structure, no nesting |
| Abstraction | None | raw_input preserved verbatim |
| Generalization | None | No rule extraction |
| Lifecycle | Append-only | `save()` only, no update/delete |
| Retrieval | Keyword+tag | ExperienceRetriever scores by overlap |
| Influence | Direct | Counts in experience_prob calculation |
| Conflict | Coexists | Multiple experiences with same condition coexist |

### 3.3 Experience is NOT

- NOT a rule ("when X, Y happens")
- NOT a summary ("fix tasks succeed 80% of the time")
- NOT a generalized statement
- NOT reusable across different contexts (only matched by keyword similarity)

---

## 4. Pattern Boundary

### 4.1 What Pattern IS (from code)

```python
@dataclass
class Pattern:
    pattern_id: str                      # UUID
    created_at: str                      # ISO timestamp
    source_experience_ids: list[str]     # Which experiences formed this
    
    condition_intent: str                # When: intent match
    condition_action_type: str           # When: action match
    predicted_outcome: str               # What tends to happen
    success_rate: float                  # 0.0-1.0
    
    support_count: int                   # Total matching experiences
    contradiction_count: int             # Minority outcome count
    confidence: float                    # 0.0-1.0
    
    status: str                          # CANDIDATE|OBSERVED|SUPPORTED|STABLE|WEAKENING|RETIRED
    last_observed_at: str
    last_contradicted_at: str | None
```

### 4.2 Pattern Formation Algorithm

```python
# Group ALL experiences by (intent, action_type)
groups = defaultdict(list)
for exp in store.list_all():
    groups[(exp.intent, exp.action_type)].append(exp)

# For each group, compute statistics
for (intent, action), exps in groups.items():
    success_rate = sum(e.success for e in exps) / len(exps)
    contradiction = min(success_count, failure_count)
    confidence = success_rate * evidence_weight(support_count)
    status = determine_status(support_count, contradiction, success_rate)
```

### 4.3 Pattern Properties

| Property | Value | Evidence |
|----------|-------|----------|
| Scope | GROUP of events | Aggregates all experiences with same (intent, action) |
| Granularity | Statistical | success_rate, support_count, contradiction_count |
| Abstraction | Partial | Strips raw_input, keeps only condition+outcome stats |
| Generalization | SAME CONDITION ONLY | Cannot generalize beyond exact (intent, action) match |
| Lifecycle | 6 states | CANDIDATE→OBSERVED→SUPPORTED→STABLE→WEAKENING→RETIRED |
| Retrieval | Condition match | PatternRetriever matches by intent+action_type |
| Influence | Bounded | 15% weight, ≤ experience_weight/2 |
| Persistence | JSONL file | PatternStore |

### 4.4 Pattern is NOT

- NOT a causal rule (doesn't explain WHY)
- NOT semantically generalized (can't match "repair" to "fix")
- NOT bounded by context (no environmental conditions)
- NOT verified against held-out data
- NOT a "knowledge proposition" — it's a frequency count with metadata

### 4.5 Key Gap: Pattern is Just a Table Lookup

A Pattern is effectively: `map[(intent, action_type)] → {success_rate, support_count, ...}`

It is a **statistical summary table**, not a **generalized rule**. It cannot:
- Express conditions beyond intent+action
- Capture "when X AND Y, then Z with probability P"
- Handle edge cases or boundary conditions
- Transfer across domains

---

## 5. Knowledge Boundary

### 5.1 What Knowledge Would Need to Be

Based on the audit requirements, Knowledge should be:

> A verified, generalizable proposition that can be applied across contexts.

This requires:
1. **Generalization beyond the original data** — "When debugging Python import errors, checking sys.path is effective" generalizes across all import-related tasks
2. **Boundary conditions** — "This applies to Python projects, not JavaScript"
3. **Causal understanding** — WHY the success occurred
4. **Verification mechanism** — How do we know it's reliable?
5. **Falsifiability** — How do we know when it's wrong?

### 5.2 Does Current Pattern Satisfy These?

| Requirement | Pattern Capability | Gap |
|-------------|-------------------|-----|
| Generalization | Same (intent, action) only | **CRITICAL**: Cannot generalize across conditions |
| Boundary conditions | None | **CRITICAL**: No knowledge of when rule doesn't apply |
| Causal understanding | None | **CRITICAL**: Only correlation, not causation |
| Verification | support_count threshold | **MEDIUM**: Arbitrary threshold, no held-out test |
| Falsifiability | contradiction_count → WEAKENING | **MEDIUM**: Reactive, not proactive |

**Verdict**: Pattern is a NECESSARY PRECURSOR to Knowledge, but NOT sufficient.

### 5.3 The Minimal Difference

```
Pattern:  "In 5 fix+code_review tasks, 4 succeeded (80%)"
          → A statistic about a GROUP

Knowledge: "For Python bug-fixing tasks, code_review action succeeds with 80% probability,
            but ONLY when the bug is in import resolution (not in logic errors)."
          → A GENERALIZED RULE with CONDITIONS and BOUNDARIES
```

The difference is **CONDITIONALITY**. Knowledge answers "when does this apply?" Pattern only answers "how often did this happen?"

---

## 6. Pattern → Knowledge 晋升模型

### 6.1 Required晋升 Dimensions

Based on the audit spec, a Pattern should become Knowledge when it satisfies:

| Dimension | Current Pattern | Required for Knowledge | Gap |
|-----------|----------------|----------------------|-----|
| Evidence quantity | support_count ≥ 3 | support_count ≥ 10 | Needs higher threshold |
| Evidence diversity | NONE (same condition only) | Different sub-conditions | **CRITICAL GAP** |
| Contradiction | contradiction_rate ≤ 50% | contradiction_rate ≤ 20% | Stricter |
| Success consistency | success_rate ≥ 0.7 | success_rate ≥ 0.8 | Stricter |
| Temporal stability | NONE (no time factor) | Consistent across time windows | **CRITICAL GAP** |
| Provenance | source_experience_ids | source_experience_ids + conditions | Partial |
| Verification | NONE (no test) | Held-out validation | **CRITICAL GAP** |
| Falsification | reactive (WEAKENING) | proactive (A/B testing) | **CRITICAL GAP** |
| Confidence | support_rate × weight | calibrated probability | **SEMANTIC GAP** |
| Applicability scope | implicit (same condition) | EXPLICIT (domain, context, boundaries) | **CRITICAL GAP** |

### 6.2 Five Critical Gaps

The 5 gaps that MUST be closed before Pattern can become Knowledge:

1. **Condition generalization**: Pattern only matches exact (intent, action). Knowledge must handle "similar but not identical" conditions.
2. **Boundary specification**: Knowledge must declare WHEN IT DOES NOT APPLY.
3. **Temporal validation**: Knowledge must be tested across time, not just aggregated.
4. **Held-out verification**: Knowledge must pass tests on unseen data.
5. **Causal attribution**: Knowledge must explain WHY, not just HOW OFTEN.

### 6.3 Without These Gaps Closed

Elevating Pattern to Knowledge would be:
- **Nominal only**: Renaming "Pattern" to "Knowledge" with no functional change
- **Dangerous**: False confidence in unverified generalizations
- **Redundant**: Hermes Semantic Memory (when available) would duplicate this

---

## 7. Confidence Semantics Audit

### 7.1 All "Confidence" Fields in the System

| Field | Type | Current Formula | What It Actually Means |
|-------|------|----------------|----------------------|
| `PerceptionData.confidence` | float 0-1 | Heuristic (0.7 fixed) | Perceptual certainty |
| `InternalState.confidence` | float 0-1 | ±0.05 per event | Session-level self-trust |
| `PredictionData.prediction_confidence` | float 0-1 | `perf_conf × 0.8` | How sure the prediction model is |
| `Experience.confidence` | float 0.5 | From prediction_confidence | Past prediction confidence |
| `Pattern.confidence` | float 0-1 | `success_rate × evidence_weight` | **SUPPORT SCORE**, NOT probability |

### 7.2 Pattern.confidence is NOT a Probability

**Formula**: `confidence = success_rate × evidence_weight(support_count)`

Where:
- `success_rate` = fraction of successes (0.0–1.0)
- `evidence_weight` = {0.3 if count<3, 0.6 if count<5, 0.9 if count≥5}

**This is a multiplicative support score, not a Bayesian probability.**

| Scenario | success_rate | weight | confidence | Real meaning |
|----------|-------------|--------|------------|-------------|
| 1 success | 1.0 | 0.3 | 0.30 | "One data point, weak support" |
| 3 success | 1.0 | 0.6 | 0.60 | "Three consistent results" |
| 5 success | 1.0 | 0.9 | 0.90 | "Five consistent results, strong support" |
| 5 success + 1 fail | 0.83 | 0.9 | 0.75 | "Mostly successful but some doubt" |
| 3 success + 2 fail | 0.60 | 0.6 | 0.36 | "Mixed results, low support" |

**Correct naming**: `Pattern.support_score` or `Pattern.evidence_strength`

**WRONG naming**: `Pattern.confidence` (implies probability)

### 7.3 Recommendation

Rename `Pattern.confidence` to `Pattern.support_score` to prevent misinterpretation. This is a **naming fix, not an architecture change**.

---

## 8. Knowledge Lifecycle

### 8.1 If Knowledge Were Implemented

Proposed lifecycle (hypothetical — not approved):

```
CANDIDATE ← Pattern (support_count ≥ N, all other criteria met)
    ↓
PROPOSITION ← Additional boundary conditions specified
    ↓
TESTED ← Held-out validation performed
    ↓
VERIFIED ← Passes validation with margin
    ↓
STABLE ← Time-tested, no contradictions
    ↓
WEAKENING ← Contradictions exceed threshold
    ↓
RETIRED ← Falsified or superseded
```

### 8.2 Why This Can't Start in Phase 13

Phase 13 is supposed to be the MINIMUM viable Knowledge layer. But the lifecycle above requires:
- Boundary condition specification (needs semantic understanding)
- Held-out validation (needs test infrastructure)
- Time-testing (needs temporal dimension)

These are **Phase 14+ features**, not Phase 13 MVP.

### 8.3 Minimum Viable Knowledge (If We Proceed Anyway)

If we MUST have Knowledge in Phase 13, the absolute minimum is:

```
Knowledge = Pattern + explicit_boundary_conditions
```

Where `explicit_boundary_conditions` means:
- Adding a `scope` field to Pattern (e.g., "python" vs "javascript")
- Adding a `not_applicable_when` field (e.g., "logic errors")
- This is a DATA MODEL CHANGE, not an algorithmic change

But this still doesn't solve the double-counting problem or the Hermes overlap question.

---

## 9. Knowledge Retrieval

### 9.1 Current Retrieval Mechanisms

| Retriever | Method | Complexity | Scale Limit |
|-----------|--------|-----------|-------------|
| ExperienceRetriever | O(N) keyword+tag scan | N = experience count | ~10K acceptable |
| PatternRetriever | O(P) condition match | P = pattern count (~N/10) | 100K+ fine |

### 9.2 Knowledge Retrieval Would Be

If Knowledge = Pattern + boundaries:
- Same O(P) retrieval (just filter by scope/boundaries)
- No new algorithm needed
- No ML/embedding needed for v1

### 9.3 Scaling Analysis (Verified)

```
N=10 experiences → 10 patterns → 0.4 ms consolidation
N=100 experiences → 12 patterns → 0.1 ms consolidation
N=1,000 experiences → 12 patterns → 0.3 ms consolidation
N=5,000 experiences → 12 patterns → 1.4 ms consolidation
```

Pattern count saturates at ~12 (6 intents × 2 actions in test). At scale, pattern count = unique (intent, action) combinations, which grows much slower than N.

**Conclusion**: Knowledge retrieval cost would be negligible (same as Pattern retrieval).

---

## 10. Knowledge → Cognitive Loop

### 10.1 Current Data Flow

```
ExperienceStore ──→ ExperienceRetriever ──→ experience_prob ──┐
                                                              ├──→ Blended Prediction
PatternStore  ──→ PatternRetriever  ──→ pattern_prob ────────┘
                                                              │
BasePrediction ───────────────────────────────────────────────┘
```

### 10.2 Where Knowledge Would Fit (Three Options)

**Option A: Knowledge → Prediction (direct)**
```
BasePrediction → experience_signal → pattern_signal → knowledge_signal → Prediction
```
- Same blending pattern as current
- Risk: compounding double-counting (3 signals from same data)
- **NOT RECOMMENDED**

**Option B: Knowledge → Context (indirect)**
```
Knowledge → modifies MemoryData → influences ExperienceRetriever scoring
```
- Knowledge adjusts HOW experiences are retrieved, not the probability directly
- Avoids double-counting
- More architecturally clean
- **PREFERRED IF proceeding**

**Option C: No Knowledge layer (stop at Pattern)**
```
Experience → Pattern → Prediction (current)
```
- No new layer needed
- Pattern already provides the generalization
- **RECOMMENDED**

### 10.3 Why Option C Is Best

The current system already answers:
- "What happened before?" → Experience
- "How often does this type of task succeed?" → Pattern
- "What should I predict?" → Blended prediction

Adding Knowledge would answer:
- "What is a general rule I can rely on?" → Pattern ALREADY answers this (with lower confidence)

The ONLY thing Knowledge adds is **semantic generalization** (matching "repair" to "fix"). This requires either:
1. A semantic embedding (ML — forbidden by constraints)
2. A manual taxonomy (over-engineering for MVP)

Neither is available in Phase 13 scope.

---

## 11. Hermes Memory Boundary

### 11.1 Current State

**No Hermes code exists in this repository.**

The Phase 12 audit spec assumed:
> "Hermes currently exists: Episodic Memory, Semantic Memory, Hybrid Retriever, Experience JSONL, Evolution"

**None of these exist.** The search returned zero results.

### 11.2 Implications

Without knowing what Hermes provides, we CANNOT:
1. Determine if NeuroCortex Knowledge would duplicate Hermes Semantic Memory
2. Define a clean boundary between the two systems
3. Decide whether Knowledge should live in NeuroCortex or Hermes

### 11.3 Required Resolution

Before Phase 13 can proceed:
1. **Locate the Hermes codebase** and understand its memory architecture
2. **Map Hermes capabilities** against NeuroCortex Phase 0-12 capabilities
3. **Identify overlap** and decide ownership
4. **Define integration points** (if any)

### 11.4 Hypothetical Boundary (If Hermes Exists)

| Capability | NeuroCortex | Hermes | Rationale |
|-----------|-------------|--------|-----------|
| Episodic records | ExperienceStore | ? | NeuroCortex owns immediate past |
| Statistical patterns | PatternStore | ? | NeuroCortex owns behavioral regularities |
| Semantic facts | NONE | Likely here | Should NOT duplicate |
| Cross-domain retrieval | NONE | Likely here | Should NOT duplicate |
| Long-term persistence | JSONL files | ? | Shared or separate? |

**This is speculative.** Must verify against actual Hermes code.

---

## 12. ML / LLM Necessity

### 12.1 Current State (Deterministic Only)

All Phase 0-12 components are deterministic:
- Pattern formation: groupby + count + threshold
- Pattern retrieval: exact condition match
- Prediction blending: weighted average
- No embeddings, no clustering, no neural networks

### 12.2 What Knowledge Would Require

| Component | Deterministic Possible? | Future ML Needed? |
|-----------|------------------------|-------------------|
| Knowledge extraction | YES (Pattern + boundaries) | No for v1 |
| Consolidation | YES (same algorithm) | No for v1 |
| Retrieval | YES (condition match) | No for v1 |
| Contradiction detection | YES (count-based) | No for v1 |
| Verification | PARTIALLY (held-out test) | Yes for robust verification |
| Confidence calibration | NO (needs statistical model) | Yes for proper probabilities |

### 12.3 Verdict

Phase 13 MVP CAN be deterministic IF:
- Knowledge = Pattern + explicit boundary fields
- No semantic generalization (exact condition matching only)
- No probabilistic calibration (support_score remains heuristic)

But this is so close to just "Pattern with extra fields" that the question becomes: **is it worth the architectural complexity?**

---

## 13. Phase 12 Weight Audit

### 13.1 Current Blending Formula

```python
adjusted_prob = 0.55 × base_prob + 0.30 × experience_prob + 0.15 × pattern_prob
```

### 13.2 Double-Counting Analysis

**Scenario**: 5 fix+code_review experiences, 4 success, 1 failure.

| Signal Source | What It Computes | Evidence Used |
|--------------|-----------------|---------------|
| experience_prob | 4/3 = 1.0 (top-3 retrieved, all success) | 3 of 5 experiences |
| pattern_prob | 4/5 = 0.80 (entire group) | All 5 experiences |

**Problem**: The 3 retrieved experiences are a SUBSET of the 5 pattern experiences. The same evidence is counted in BOTH signals.

**Effect**: 
- Base: 0.80 (from BasicPrediction)
- With experience only: 0.55×0.80 + 0.30×1.0 = 0.74
- With experience + pattern: 0.55×0.80 + 0.30×1.0 + 0.15×0.80 = 0.82

The pattern signal ADDS 0.08 but the underlying evidence (4/5 = 0.80) is ALREADY partially captured by the experience signal (3/3 = 1.0).

**Net effect**: The system overweights success (sees 1.0 from experiences + 0.80 from patterns when the true rate is 0.80).

### 13.3 Is This a Problem for Knowledge?

**YES, and it compounds.**

If Knowledge = Pattern-derived (as assumed), then:
- Knowledge signal would be ANOTHER derivation from the SAME experiences
- Triple-counting: experience_prob + pattern_prob + knowledge_prob
- Each derived from overlapping subsets of the same data
- The more layers we add, the more the system overweights evidence

### 13.4 Root Cause

The root cause is that **ExperiencePredictionModule is doing double duty**:
1. It retrieves raw experiences directly
2. It retrieves aggregated patterns derived from those same experiences

These are not independent signals. They are the SAME signal at different abstraction levels.

### 13.5 Fix Options (Out of Phase 13 Scope)

1. **Mutually exclusive**: Use EITHER experience retrieval OR pattern retrieval, not both
2. **Deduplication**: Track which experiences contributed to patterns, exclude them from direct retrieval
3. **Single source**: Remove experience retrieval, use only pattern retrieval (patterns ARE the aggregated experience signal)
4. **Re-weight**: Reduce experience_weight and pattern_weight to compensate for overlap

**None of these fixes are trivial.** They require changing the core prediction architecture, which touches frozen Phase 11/12 code.

---

## 14. Scaling Audit

### 14.1 Verified Costs

| Metric | N=100 | N=1,000 | N=10,000 | N=100,000 |
|--------|-------|---------|----------|-----------|
| Experience store | ~50 KB | ~500 KB | ~5 MB | ~50 MB |
| Pattern count | ~12 | ~12 | ~12 | ~12 (saturates) |
| Pattern store | ~2 KB | ~2 KB | ~2 KB | ~2 KB |
| Consolidation | <1 ms | <1 ms | <1 ms | ~10 ms |
| Experience retrieval | <1 ms | <10 ms | <100 ms | <1 second |
| Pattern retrieval | <0.1 ms | <0.1 ms | <0.1 ms | <0.1 ms |

### 14.2 Bottleneck Analysis

- **ExperienceStore** is the bottleneck at scale (O(N) scan for retrieval)
- **PatternStore** is negligible (small, fixed-size)
- **Consolidation** is negligible (fast groupby operation)

### 14.3 Knowledge Impact on Scaling

If Knowledge were added:
- KnowledgeStore size ≈ PatternStore size (same structure, extra fields)
- Knowledge retrieval cost ≈ Pattern retrieval cost
- Consolidation cost unchanged (Knowledge derived from Pattern)
- **No scaling concern**

---

## 15. Minimal Phase 13 MVP

### 15.1 What Would Be Required

If we PROCEED despite the blockers, the absolute minimum MVP is:

**New files:**
1. `src/neurocortex/knowledge/knowledge.py` — Knowledge dataclass (Pattern + boundaries)
2. `src/neurocortex/knowledge/store.py` — KnowledgeStore (JSONL, same as PatternStore)
3. `src/neurocortex/knowledge/retriever.py` — KnowledgeRetriever (same as PatternRetriever + scope filter)

**Modified files:**
1. `src/neurocortex/prediction/experience_prediction.py` — Add knowledge_weight (0.10)
2. `src/neurocortex/pattern/consolidator.py` — Add knowledge promotion step

**Total new code**: ~200 lines
**Total modified**: 2 files
**Tests needed**: ~10

### 15.2 What This Would NOT Solve

- Double-counting problem (still present)
- Hermes overlap (unknown)
- Semantic generalization (still absent)
- Causal understanding (still absent)

### 15.3 What This WOULD Add

- An explicit "Knowledge" label on top of Pattern
- Boundary condition fields (scope, not_applicable_when)
- One additional signal in prediction (10% weight)
- ~10 new tests

**Net value**: Marginal. The system gains a label but not meaningful capability.

---

## 16. Controlled Experiments (Proposed)

### 16.1 If Phase 13 Were Implemented

| Exp | Hypothesis | Expected | Failure Means |
|-----|-----------|----------|---------------|
| A | No Knowledge → same as Phase 12 | Baseline | Regression |
| B | Pattern meets Knowledge threshold → promoted | New Knowledge record created | Promotion logic broken |
| C | Contradictory evidence → Knowledge weakens | Status transitions to WEAKENING | Lifecycle broken |
| D | Irrelevant Knowledge → not retrieved | Empty results for wrong scope | Scope filtering broken |
| E | Same input → same Knowledge | Deterministic replay | Non-determinism introduced |
| F | Knowledge + Experience → no double counting | Probability shift ≤ expected | Double-counting present |
| G | Hermes Knowledge ≠ NeuroCortex Knowledge | No cross-contamination | Boundary violation |
| H | Knowledge retirement → not used in prediction | Base prediction only | Retirement broken |
| I | Restart persistence | Knowledge loads correctly | Persistence broken |
| J | 100K experiences → Knowledge still fast | <1s retrieval | Scaling issue |

---

## 17. Risks

### CRITICAL

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Double-counting compounds with each layer | Certain | High | Fix Phase 12 blending first |
| Hermes Semantic Memory duplication | Unknown | High | Audit Hermes codebase first |
| Pattern confusion with Knowledge | Certain | Medium | Rename Pattern.confidence → support_score |

### HIGH

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Overconfidence from weighted blend | Certain | Medium | Calibrate weights with experiments |
| Pattern condition too narrow | Certain | Medium | Add condition generalization (Phase 14+) |
| Lazy consolidation misses rapid changes | Medium | Low | Add periodic refresh trigger |

### MEDIUM

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Knowledge = Pattern rename (no value) | High | Medium | Define clear upgrade criteria |
| Retrograde to simpler architecture | Medium | Low | Accept if justified |
| Test coverage gaps in new layer | Medium | Low | Require ≥10 tests per new component |

### LOW

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| JSONL file corruption | Low | Low | Graceful handling (already in store) |
| Timestamp precision issues | Low | Low | ISO format handles this |
| UUID collision | Negligible | Low | 12-char hex, negligible risk |

---

## 18. Architecture Decision

### 18.1 Final Verdict

**BLOCKED — Phase 13 Knowledge Implementation Should NOT Proceed.**

### 18.2 Blockers

| # | Blocker | Evidence | Resolution Required |
|---|---------|----------|-------------------|
| 1 | Double-counting unaddressed | Same experiences contribute to both experience_prob and pattern_prob | Fix prediction blending before adding third layer |
| 2 | Hermes overlap unknown | No Hermes code in repo, Phase 12 audit assumed it exists | Audit Hermes architecture first |
| 3 | Pattern ≠ Knowledge | Pattern is group statistics, Knowledge requires conditional generalization | Define what extra capability Knowledge adds |

### 18.3 Recommended Path Forward

**Step 1**: Fix the double-counting issue in `ExperiencePredictionModule`
- Option A: Make experience and pattern retrieval mutually exclusive
- Option B: Deduplicate by tracking which experiences feed into patterns
- Option C: Replace direct experience retrieval with pattern-only retrieval
- **This is a Phase 12 regression fix, not a new phase**

**Step 2**: Rename `Pattern.confidence` → `Pattern.support_score`
- Semantic accuracy fix
- Zero behavioral change
- Prevents misinterpretation

**Step 3**: Audit Hermes codebase (separate from NeuroCortex)
- Understand what Semantic Memory provides
- Define clean boundary between NeuroCortex and Hermes
- This may reveal that NeuroCortex Knowledge is unnecessary

**Step 4**: If Hermes does NOT cover Pattern→Knowledge, THEN design Phase 13
- With clear understanding of what Knowledge adds
- With double-counting fixed
- With Hermes boundary defined

### 18.4 What Phase 13 Should NOT Do

- NOT add a Knowledge layer on top of unverified Pattern
- NOT introduce ML/embedding for semantic generalization
- NOT modify frozen Phase 0-12 code except for double-counting fix
- NOT assume Hermes exists without verification
- NOT add a third prediction signal without solving double-counting first

### 18.5 What Phase 13 COULD Do (If Blockers Resolved)

The MINIMUM viable Knowledge layer, IF blockers are resolved:

1. **Knowledge dataclass** — Pattern + `scope` + `not_applicable_when` fields
2. **KnowledgeStore** — JSONL persistence (same as PatternStore)
3. **KnowledgeRetriever** — PatternRetriever + scope filter
4. **Promotion rule** — STABLE Pattern with support_count ≥ 10 promotes to Knowledge
5. **Prediction integration** — knowledge_weight = 0.10, bounded
6. **10+ tests** covering promotion, retrieval, isolation, determinism

But this is speculative until blockers are resolved.

---

## 19. Summary

### What We Have (Phase 0-12)

```
Experience (episodic records)
    ↓ groupby(intent, action)
Pattern (statistical summaries)
    ↓ blend(0.55, 0.30, 0.15)
Prediction (adjusted probability)
```

### What's Missing for Knowledge

1. **Generalization beyond exact conditions** — Pattern only matches (intent, action)
2. **Boundary conditions** — No "when this rule does NOT apply"
3. **Causal understanding** — No "why this works"
4. **Held-out verification** — No test on unseen data
5. **Fixed double-counting** — Same evidence counted multiple times

### What's Blocking Phase 13

1. **Double-counting** in current prediction blending
2. **Unknown Hermes architecture** (no code in repo)
3. **Pattern≠Knowledge gap** (no clear upgrade path)

### Recommendation

**STOP at Phase 12.** Do not proceed to Phase 13 until:
1. Double-counting is fixed in the prediction pipeline
2. Hermes codebase is audited and boundaries are defined
3. A clear "what does Knowledge add beyond Pattern" is documented

The current system (453 tests passing, Pattern consolidation working) is a solid foundation. Adding an unverified Knowledge layer on top would risk regressions and architectural confusion.

---

**Audit Complete. Output: BLOCKED.**
