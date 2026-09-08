# NeuroCortex Phase 13 — Knowledge Architecture Audit v1

**Document**: Architecture Audit — Knowledge Layer Feasibility  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: DRAFT — Under Review  
**Project**: neuro-cortex  
**Baseline**: Commit 3ce854e (Evidence Integrity frozen), 458 PASS / 0 FAIL  
**Frozen Base**: Phase 0-12 + Evidence Integrity all frozen

---

## 1. Executive Summary

**VERDICT: BLOCKED — Do NOT implement Knowledge in Phase 13.**

Three fundamental blockers prevent a viable Knowledge layer:

1. **Pattern is already the maximum abstraction achievable without semantic understanding.** Pattern = group-level statistics. Knowledge requires conditional propositions with boundaries and mechanisms. The gap between them is SEMANTIC, not statistical. Bridging it requires either (a) manual condition specification (brittle, non-scalable) or (b) semantic generalization (requires ML/embeddings, forbidden by constraints).

2. **The double-counting problem is structural, not just numerical.** Even with Scheme B (bounded adjustment), adding a third layer (Knowledge) on top of Pattern creates a deeper architectural issue: Pattern is derived from Experience, and any Knowledge derived from Pattern would inherit the same correlation problem. The fix requires a fundamental rethinking of how evidence flows, not just adding another layer.

3. **No clear boundary with future Hermes integration.** The Phase 12 audit assumed Hermes Semantic Memory would exist. It does not. Designing Knowledge now risks building a system that duplicates what Hermes will provide, or creates dependencies that block future integration.

**Recommendation**: Do NOT proceed to Phase 13 Implementation. Instead:
- Accept that Pattern is the current ceiling for statistical generalization
- Document the exact gap between Pattern and Knowledge (this report)
- Wait for Hermes architecture to be defined before attempting Knowledge
- Consider whether Knowledge is actually needed for the current use case

---

## 2. Current Architecture

### 2.1 Verified Module Map (as of 3ce854e)

```
neuro-cortex/src/neurocortex/
├── cortex.py                  ✓ NeuroCortex orchestration (11 stages)
├── event.py                   ✓ CortexEvent + 11 Data classes + Experience
├── interfaces.py              ✓ 10 module protocols
├── perception/perception.py   ✓ BasicPerception (Chinese+English keywords)
├── representation/representation.py ✓ BasicRepresentation
├── attention/                 ✗ empty (no-op)
├── state/cortex_state.py      ✓ CortexState (uncertainty, confidence, goal, inputs)
├── state/state_module.py      ✓ BasicStateModule
├── memory/experience_store.py ✓ ExperienceStore (JSONL)
├── memory/experience_retriever.py ✓ ExperienceRetriever (keyword+tag)
├── prediction/prediction.py   ✓ BasicPrediction (rule-based intent→prob)
├── prediction/experience_prediction.py ✓ ExperiencePredictionModule (Scheme B)
├── decision/decision.py       ✓ BasicDecision (intent→action mapping)
├── action/action.py           ✓ BasicAction
├── feedback/feedback.py       ✓ BasicFeedback (v2.1 evaluation)
├── learning/experience_learner.py ✓ ExperienceLearningModule
├── pattern/pattern.py         ✓ Pattern (support_score, 6 lifecycle states)
├── pattern/consolidator.py    ✓ PatternConsolidator (groupby intent+action)
├── pattern/store.py           ✓ PatternStore (JSONL)
├── pattern/retriever.py       ✓ PatternRetriever (condition match)
└── modules/__init__.py        ✓ Mock implementations
```

### 2.2 Pipeline (Frozen, 11 Stages)

```
INPUT → PERCEPTION → REPRESENTATION → ATTENTION → STATE
  → MEMORY → PREDICTION → DECISION → ACTION → OUTCOME → FEEDBACK → LEARNING
```

**Cannot be modified.** This is a frozen interface.

### 2.3 Current Evidence Flow (Post-Evidence-Integrity Fix)

```
CortexEvent.raw_input
    │
    ├─→ BasicPrediction → base_prob (70% weight)
    │
    ├─→ ExperienceRetriever → empirical_rate(E) (30% weight)
    │     │
    │     └─→ ExperienceStore.list_all() → keyword+tag scoring → top-3
    │
    └─→ [LAZY] PatternConsolidator → PatternStore
           │
           └─→ PatternRetriever → support_score → quality_factor
                                  clamp(support_score, 0.5, 1.0)
                                  ↓
                    adjusted_evidence = empirical_rate × quality_factor
                                  ↓
                    prediction = 0.70 × base + 0.30 × adjusted_evidence
```

**Key invariant**: Pattern.support_score is a QUALITY WEIGHT, not an independent signal. No double counting.

### 2.4 Frozen Interfaces (Cannot Modify)

| Interface | Methods | Can Add? |
|-----------|---------|----------|
| `PerceptionModule` | `process(event)` | NO |
| `RepresentationModule` | `process(event)` | NO |
| `AttentionModule` | `process(event)` | NO |
| `StateModule` | `process(event)` | NO |
| `MemoryModule` | `process(event)` | NO |
| `PredictionModule` | `process(event)` | NO |
| `DecisionModule` | `process(event)` | NO |
| `ActionModule` | `process(event)` | NO |
| `OutcomeProvider` | `provide(event)` | NO |
| `FeedbackModule` | `process(event)` | NO |
| `LearningModule` | `process(event)` | NO |

All interfaces are `ABC` with single `process(event)` method. Adding methods breaks all implementations.

### 2.5 Test Coverage

| Module | Has Tests | Test Count |
|--------|-----------|------------|
| perception | ✓ | 29 |
| representation | ✓ | 20 |
| attention | ✗ | 0 |
| state | ✓ | 25 |
| memory | ✗ | 0 (only tested via Phase 11/12) |
| prediction | ✓ | 27 |
| decision | ✓ | 38 |
| action | ✓ | 36 |
| feedback | ✓ | 38 |
| learning | ✗ | 0 (only tested via Phase 11/12) |
| pattern | ✗ | 0 (only tested via Phase 12) |

**Total: 458 tests across 16 test files.**

---

## 3. Experience Boundary

### 3.1 Current Structure

```python
@dataclass
class Experience:
    experience_id: str          # UUID
    timestamp: str              # ISO
    source_event_id: str        # Links to CortexEvent
    raw_input: str              # Original text
    intent: str                 # Perceived intent label
    action_type: str            # Action taken
    predicted_outcome: str      # What was predicted
    predicted_prob: float       # Predicted probability
    actual_outcome: str         # What happened
    success: bool               # Binary outcome
    prediction_error: float     # |predicted - actual|
    evaluation: str             # "correct" | "miss" | etc.
    confidence: float           # Prediction confidence
    uncertainty: float          # State uncertainty
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
| Influence | Direct | Counts in empirical_rate calculation |
| Conflict | Coexists | Multiple experiences with same condition coexist |

### 3.3 What Experience IS and IS NOT

- **IS**: A structured record of one past event
- **IS**: Append-only, immutable after creation
- **IS**: Retrieved by keyword/tag similarity
- **IS NOT**: A rule or generalization
- **IS NOT**: Summarized or aggregated
- **IS NOT**: Conditioned on context beyond tags
- **IS NOT**: Capable of expressing "when X, Y happens because Z"

---

## 4. Pattern Boundary

### 4.1 Current Structure

```python
@dataclass
class Pattern:
    pattern_id: str                       # UUID
    created_at: str                       # ISO
    source_experience_ids: list[str]      # Which experiences formed this
    
    condition_intent: str                 # When: intent match
    condition_action_type: str            # When: action match
    predicted_outcome: str                # What tends to happen
    success_rate: float                   # 0.0-1.0
    
    support_count: int                    # Total matching experiences
    contradiction_count: int              # Minority outcome count
    support_score: float                  # 0.0-1.0, quality weight (NOT probability)
    
    status: str                           # CANDIDATE|OBSERVED|SUPPORTED|STABLE|WEAKENING|RETIRED
    last_observed_at: str
    last_contradicted_at: str | None
```

### 4.2 Pattern Formation

```python
# Consolidator groups ALL experiences by (intent, action_type)
groups = defaultdict(list)
for exp in store.list_all():
    groups[(exp.intent, exp.action_type)].append(exp)

# One Pattern per group
for (intent, action), exps in groups.items():
    success_rate = sum(e.success for e in exps) / len(exps)
    contradiction = min(success_count, failure_count)
    support_score = success_rate * evidence_weight(support_count)
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
| Influence | Bounded | support_score used as quality_factor in [0.5, 1.0] |
| Persistence | JSONL file | PatternStore |

### 4.4 What Pattern IS and IS NOT

- **IS**: A statistical summary of experiences sharing (intent, action)
- **IS**: A quality weight for experience evidence
- **IS**: Deterministic and reversible
- **IS NOT**: A causal rule ("X causes Y")
- **IS NOT**: A generalization beyond exact condition match
- **IS NOT**: Capable of expressing boundary conditions
- **IS NOT**: Falsifiable (can only weaken, not be proven wrong)
- **IS NOT**: Knowledge (see Section 5)

### 4.5 Critical Gap: Pattern = Table Lookup

A Pattern is effectively: `map[(intent, action_type)] → {success_rate, support_count, ...}`

It is a **statistical summary table**, not a **generalized rule**. It cannot:
- Express conditions beyond intent+action
- Capture "when X AND Y, then Z with probability P"
- Handle edge cases or boundary conditions
- Transfer across domains

---

## 5. Knowledge Boundary

### 5.1 What Knowledge WOULD Need to Be

Based on the audit requirements, Knowledge should be:

> A verified, conditional proposition that can be applied across contexts with explicit boundaries.

This requires:
1. **Condition granularity beyond (intent, action)** — e.g., "import error in auth module"
2. **Boundary conditions** — e.g., "ONLY for Python import errors, not logic errors"
3. **Causal mechanism** — WHY the success occurred
4. **Falsifiability** — How do we know when it's wrong?
5. **Cross-condition generalization** — "import fixes" and "package fixes" are related

### 5.2 Does Current Pattern Satisfy These?

| Requirement | Pattern Capability | Gap |
|-------------|-------------------|-----|
| Condition granularity | (intent, action) only | **CRITICAL**: Cannot express sub-conditions |
| Boundary conditions | None | **CRITICAL**: No knowledge of when rule doesn't apply |
| Causal mechanism | None | **CRITICAL**: Only correlation, not causation |
| Falsifiability | Reactive (WEAKENING) | **CRITICAL**: No proactive hypothesis testing |
| Cross-condition generalization | None | **CRITICAL**: Patterns are isolated per (intent, action) |

### 5.3 The Minimal Difference

```
Pattern:  "In 4 fix+code_review tasks, 3 succeeded (75%)"
          → A statistic about a GROUP

Knowledge: "For Python import-error fixing tasks, code_review action succeeds
            with ~90% probability, but ONLY when the error is in import/path
            resolution (not in logic errors or type mismatches)."
          → A GENERALIZED RULE with CONDITIONS, BOUNDARIES, and MECHANISM
```

The difference is **CONDITIONALITY** and **BOUNDARY SPECIFICATION**. Knowledge answers "when does this apply?" and "why does it work?" Pattern only answers "how often did this happen?"

### 5.4 Why Renaming Pattern to Knowledge Is Not Enough

If we simply rename `Pattern` → `Knowledge` and add a `condition` field:
- We still can't EXPRESS the condition (no schema for sub-conditions)
- We still can't ENFORCE boundaries (no mechanism to check them)
- We still can't capture CAUSAL MECHANISMS (no field for explanation)
- We still can't do CROSS-CONDITION GENERALIZATION (no linking mechanism)

This would be **nominal change only** — renaming without adding capability.

---

## 6. Pattern → Knowledge 晋升模型

### 6.1 Required Dimensions

| Dimension | Current Pattern | Required for Knowledge | Gap |
|-----------|----------------|----------------------|-----|
| Evidence quantity | support_count ≥ 3 | support_count ≥ 10 | Needs higher threshold |
| Evidence diversity | NONE | Different sub-conditions | **CRITICAL GAP** |
| Contradiction | contradiction_rate ≤ 50% | contradiction_rate ≤ 20% | Stricter |
| Success consistency | success_rate ≥ 0.7 | success_rate ≥ 0.8 | Stricter |
| Temporal stability | NONE | Consistent across time windows | **CRITICAL GAP** |
| Provenance | source_experience_ids | source_ids + conditions + mechanisms | Partial |
| Verification | NONE (no test) | Held-out validation | **CRITICAL GAP** |
| Falsification | reactive (WEAKENING) | proactive (hypothesis testing) | **CRITICAL GAP** |
| Support score | success_rate × weight | calibrated measure | **SEMANTIC GAP** |
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
- **Redundant**: Would duplicate what a future Hermes Semantic Memory would provide

---

## 7. Confidence Semantics Audit

### 7.1 All "Confidence" Fields in the System

| Field | Type | Current Formula | What It Actually Means |
|-------|------|----------------|----------------------|
| `PerceptionData.confidence` | float 0-1 | Heuristic (0.7 fixed) | Perceptual certainty |
| `InternalState.confidence` | float 0-1 | ±0.05 per event | Session-level self-trust |
| `PredictionData.prediction_confidence` | float 0-1 | `perf_conf × 0.8` | How sure the prediction model is |
| `Experience.confidence` | float 0.5 | From prediction_confidence | Past prediction confidence |
| `Pattern.support_score` | float 0-1 | `success_rate × evidence_weight` | **SUPPORT SCORE**, NOT probability |

### 7.2 Pattern.support_score is NOT a Probability

**Formula**: `support_score = success_rate × evidence_weight(support_count)`

Where:
- `success_rate` = fraction of successes (0.0–1.0)
- `evidence_weight` = {0.3 if count<3, 0.6 if count<5, 0.9 if count≥5}

**This is a multiplicative support score, not a Bayesian probability.**

### 7.3 Recommendation (Already Implemented)

`Pattern.confidence` has been renamed to `Pattern.support_score`. The semantics are now correctly documented as a quality weight, not a probability.

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

But this still doesn't solve the double-counting problem or the semantic generalization gap.

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
N=100 experiences → 8 patterns → 0.2 ms consolidation
N=1,000 experiences → 8 patterns → 0.3 ms consolidation
N=10,000 experiences → 8 patterns → 3.4 ms consolidation
N=100,000 experiences → 8 patterns → 42.3 ms consolidation
```

Pattern count saturates at ~48 (unique intent×action combinations). At scale, pattern count = unique (intent, action) combinations, which grows much slower than N.

**Conclusion**: Knowledge retrieval cost would be negligible (same as Pattern retrieval).

---

## 10. Knowledge → Cognitive Loop

### 10.1 Current Data Flow

```
ExperienceStore ──→ ExperienceRetriever ──→ empirical_rate ──┐
                                                              ├──→ Bounded Adjustment → Prediction
PatternStore  ──→ PatternRetriever  ──→ support_score ──────┘
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

**Option B: Knowledge → Pattern (modify Pattern quality)**
```
Knowledge → adjusts Pattern.support_score → Pattern quality affects evidence
```
- Knowledge modifies Pattern, which modifies evidence weight
- Avoids direct double-counting
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
- "What should I predict?" → Bounded adjustment

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

The Phase 12 audit spec referenced:
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

| Capability | NeuroCortex | Hermes (future) | Rationale |
|-----------|-------------|-----------------|-----------|
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
- Prediction blending: bounded adjustment
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

## 13. Phase 12 Weight Audit (Already Fixed)

### 13.1 Current Blending Formula (Scheme B)

```python
quality_factor = clamp(avg_support_score, 0.5, 1.0)
adjusted_evidence = empirical_rate × quality_factor
prediction = 0.70 × base + 0.30 × adjusted_evidence
```

### 13.2 Double-Counting Status

**FIXED.** Pattern is no longer an independent signal. It is a quality weight for the experience signal.

Verification (4/5 success scenario):
- Old Scheme A: prediction = 0.86 (error +0.06)
- New Scheme B: prediction = 0.776 (error -0.024)
- True rate: 0.80

### 13.3 If Knowledge Were Added

If Knowledge modifies Pattern.support_score:
- Knowledge → Pattern.support_score adjustment → Pattern quality_factor → evidence adjustment → prediction
- This is ONE level of indirection, NOT a parallel signal
- No double counting IF Knowledge only modifies Pattern, not evidence directly

But this adds complexity without clear benefit over just improving Pattern conditions.

---

## 14. Scaling Audit

### 14.1 Verified Costs

| N (experiences) | Pattern Count | Consolidation | Experience Retrieval |
|-----------------|--------------|--------------|---------------------|
| 100 | 8 | 0.2 ms | < 1 ms |
| 1,000 | 8 | 0.3 ms | < 1 ms |
| 10,000 | 8 | 3.4 ms | ~5 ms |
| 100,000 | 8 | 42.3 ms | ~50 ms |

### 14.2 Bottleneck Analysis

- **ExperienceStore retrieval** is O(N) — becomes slow at N > 10,000
- **PatternStore retrieval** is O(P) where P ≈ constant (~48 max) — always fast
- **Consolidation** is O(N) — acceptable at all scales (< 50ms at 100K)

### 14.3 Knowledge Impact on Scaling

If Knowledge were added:
- KnowledgeStore size ≈ PatternStore size (same structure, extra fields)
- Knowledge retrieval cost ≈ Pattern retrieval cost
- Consolidation cost unchanged (Knowledge derived from Pattern)
- **No scaling concern**

---

## 15. Minimal Phase 13 MVP (Design Only — Not Implemented)

### 15.1 What Would Be Required (If Approved)

**New files:**
1. `src/neurocortex/knowledge/knowledge.py` — Knowledge dataclass
2. `src/neurocortex/knowledge/store.py` — KnowledgeStore (JSONL)
3. `src/neurocortex/knowledge/retriever.py` — KnowledgeRetriever

**Modified files:**
1. `src/neurocortex/pattern/pattern.py` — Add `parent_knowledge_id` link
2. `src/neurocortex/pattern/consolidator.py` — Add knowledge promotion step

**Total new code**: ~300 lines
**Total modified**: 2 files
**Tests needed**: ~15

### 15.2 What This Would NOT Solve

- Semantic generalization (still absent)
- Boundary condition specification (still manual)
- Causal understanding (still absent)
- Hermes overlap (still unknown)

### 15.3 What This WOULD Add

- An explicit "Knowledge" label on top of Pattern
- Boundary condition fields
- One additional retrieval path
- ~15 new tests

**Net value**: Marginal. The system gains a label but not meaningful capability.

---

## 16. Controlled Experiments (Proposed — Not Run)

| Exp | Hypothesis | Expected | Failure Means |
|-----|-----------|----------|---------------|
| A | No Knowledge → same as Phase 12 | Baseline | Regression |
| B | Pattern meets Knowledge threshold → promoted | New Knowledge record | Promotion logic broken |
| C | Contradictory evidence → Knowledge weakens | Status transitions | Lifecycle broken |
| D | Irrelevant Knowledge → not retrieved | Empty results for wrong scope | Scope filtering broken |
| E | Same input → same Knowledge | Deterministic replay | Non-determinism |
| F | Knowledge + Experience → no double counting | Probability shift ≤ expected | Double-counting present |
| G | Hermes Knowledge ≠ NeuroCortex Knowledge | No cross-contamination | Boundary violation |
| H | Knowledge retirement → not used | Base prediction only | Retirement broken |
| I | Restart persistence | Knowledge loads correctly | Persistence broken |
| J | 100K experiences → Knowledge still fast | <1s retrieval | Scaling issue |

---

## 17. Risks

### CRITICAL

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pattern ≠ Knowledge (just rename) | Certain | High | Define clear upgrade criteria |
| Hermes duplication risk | Unknown | High | Audit Hermes first |
| Over-engineering for marginal gain | High | Medium | Strict MVP scope |

### HIGH

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Double counting compounds | Medium | Medium | Hierarchical evidence model |
| Pattern condition too narrow | Certain | Medium | Add condition generalization (Phase 14+) |
| Lazy consolidation misses rapid changes | Medium | Low | Add periodic refresh trigger |

### MEDIUM

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Knowledge = Pattern rename (no value) | High | Medium | Define clear upgrade criteria |
| Retrograde to simpler architecture | Medium | Low | Accept if justified |
| Test coverage gaps in new layer | Medium | Low | Require ≥15 tests per component |

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
| 1 | Pattern ≠ Knowledge (semantic gap) | Pattern is (intent,action) statistics. Knowledge requires conditional propositions with boundaries. | Define what EXTRA capability Knowledge adds beyond Pattern |
| 2 | Hermes does not exist | No Hermes code found anywhere on system. Cannot assess duplication risk. | Audit Hermes architecture before designing Knowledge |
| 3 | No clear upgrade path | No deterministic algorithm to promote Pattern → Knowledge. Requires semantic understanding. | Define explicit promotion criteria with experimental validation |

### 18.3 Recommended Path Forward

**Step 1**: Accept Pattern as the current ceiling for statistical generalization.
- Pattern successfully captures group-level regularities
- Pattern correctly modulates evidence quality (Scheme B)
- Pattern has clear boundaries and lifecycle

**Step 2**: If Hermes is built later:
- Audit Hermes memory architecture
- Determine if Hermes Semantic Memory covers Pattern's role
- If yes: NeuroCortex consumes Hermes patterns (read-only)
- If no: NeuroCortex retains Pattern ownership

**Step 3**: If Knowledge is truly needed:
- Define explicit boundary conditions (when does Pattern NOT apply?)
- Define causal mechanisms (WHY does the pattern hold?)
- Design held-out validation (how do we know it's reliable?)
- These require SEMANTIC understanding beyond statistics

### 18.4 What Phase 13 Should NOT Do

- NOT add a Knowledge layer on top of unverified Pattern
- NOT introduce ML/embedding for semantic generalization
- NOT modify frozen Phase 0-12 code except for documented fixes
- NOT assume Hermes exists without verification
- NOT add a third prediction signal without solving double-counting first

### 18.5 What Phase 13 COULD Do (If Blockers Resolved)

The MINIMUM viable Knowledge layer, IF blockers are resolved:

1. **Knowledge dataclass** — Pattern + `scope` + `not_applicable_when` + `causal_mechanism`
2. **KnowledgeStore** — JSONL persistence (same as PatternStore)
3. **KnowledgeRetriever** — PatternRetriever + scope filter
4. **Promotion rule** — STABLE Pattern with support_count ≥ 10 promotes to Knowledge
5. **Prediction integration** — Knowledge adjusts Pattern.support_score (hierarchical, not parallel)
6. **15+ tests** covering promotion, retrieval, isolation, determinism

But this is speculative until blockers are resolved.

---

## 19. Summary

### What We Have (Phase 0-12 + Evidence Integrity)

```
Experience (episodic records, 15 fields)
    ↓ groupby(intent, action)
Pattern (statistical summaries, 13 fields, support_score as quality weight)
    ↓ clamp(support_score, 0.5, 1.0)
Evidence adjustment (Scheme B, bounded)
    ↓
Prediction (70% base + 30% adjusted evidence)
```

### What's Missing for Knowledge

1. **Condition generalization** — Pattern only matches exact (intent, action)
2. **Boundary specification** — No "when this rule does NOT apply"
3. **Causal understanding** — No "why this works"
4. **Held-out verification** — No test on unseen data
5. **Hermes boundary** — Unknown overlap risk

### What's Blocking Phase 13

1. **Pattern ≠ Knowledge** — No clear upgrade path from statistics to propositions
2. **Hermes unknown** — Cannot assess duplication risk
3. **Semantic gap** — No deterministic algorithm for condition generalization

### Recommendation

**STOP at Phase 12 + Evidence Integrity.** Do not proceed to Phase 13 until:
1. Hermes architecture is understood
2. Clear "what does Knowledge add beyond Pattern" is documented
3. Explicit promotion criteria are defined and tested

The current system (458 tests passing, Pattern consolidation working, double counting fixed) is a solid foundation. Adding an unverified Knowledge layer on top would risk regressions and architectural confusion.

---

**Audit Complete. Output: BLOCKED.**
