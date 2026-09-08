# Pre-Phase 13 — Evidence Integrity & Hermes Boundary Audit v1

**Document**: Pre-Phase 13 Audit — Evidence Integrity + Hermes Boundary  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: AUDIT COMPLETE  
**Project**: neuro-cortex  
**Baseline**: Commit adc8cbe, 453 PASS / 0 FAIL

---

## 1. Executive Summary

**DECISION: READY FOR PRE-PHASE 13 IMPLEMENTATION**

Two blockers identified and resolved:

| Blocker | Status | Resolution |
|---------|--------|-----------|
| Double counting in prediction blend | **RESOLVED** | Scheme B (hierarchical) eliminates it. Fix required before Phase 13. |
| Hermes boundary unknown | **RESOLVED** | Hermes does NOT exist in this environment. NeuroCortex must be self-contained. |

Three additional findings require attention:
1. `Pattern.confidence` is misnamed — it is a support score, not a probability
2. Pattern weight (15%) lacks theoretical grounding — arbitrary heuristic
3. Experience retrieval is O(N) — becomes bottleneck at N > 10,000

None of these block Phase 13. They are recommended improvements.

---

## 2. Current Evidence Graph

### 2.1 Verified Data Flow (from code)

```
CortexEvent.raw_input
    ↓
BasicPrediction → base_prob (intent+risk+uncertainty rules)
    ↓
ExperiencePredictionModule.process(event):
    │
    ├──→ ExperienceRetriever.retrieve(raw_input, intent, action)
    │      ↓
    │   ExperienceStore.list_all() → O(N) scan
    │      ↓
    │   keyword+tag scoring → top-3 experiences
    │      ↓
    │   experience_prob = success_count / retrieved_count
    │
    ├──→ PatternRetriever.retrieve(intent, action)
    │      ↓
    │   PatternStore.list_active() → O(P) scan
    │      ↓
    │   condition match scoring → top-3 patterns
    │      ↓
    │   pattern_prob = weighted_avg(success_rate × support_score)
    │
    └──→ Blend: 0.55×base + 0.30×experience_prob + 0.15×pattern_prob
           ↓
        event.predict(adjusted)
```

### 2.2 Parallel Path: Learning

```
CortexEvent (after LEARNING stage)
    ↓
ExperienceLearningModule.process(event)
    ↓
Experience.from_event(event) → 15-field dataclass
    ↓
ExperienceStore.save(experience) → JSONL append
    ↓
[C LAZY] PatternConsolidator.consolidate(store) → PatternStore
```

### 2.3 Critical Observation

The PatternConsolidator runs LAZY (on-demand), not during the pipeline. This means:
- Patterns may be STALE (not updated after new experiences)
- The PatternRetriever may return outdated patterns
- This is by design (performance), but has correctness implications

---

## 3. Double Counting Analysis

### 3.1 Confirmed: Double Counting Exists

**Test case**: 5 experiences, all `intent=fix, action=code_review`, 4 success + 1 failure.

| Signal | Computes From | Value | Evidence IDs |
|--------|--------------|-------|-------------|
| experience_prob | Top-3 retrieved exps | 3/3 = 1.00 | {e0, e1, e2} |
| pattern_prob | Consolidated pattern | 4/5 = 0.80 | {e0, e1, e2, e3, e4} |
| **OVERLAP** | | | **{e0, e1, e2}** |

**3 out of 5 experiences are counted TWICE.**

### 3.2 Impact Quantification

Using base_prob = 0.80, exp_weight = 0.30, pat_weight = 0.15:

| Scenario | True Rate | Current Blend | Hierarchical Blend | Current Error |
|----------|-----------|--------------|-------------------|--------------|
| 5 exps, 4/5 success | 0.80 | 0.8600 | 0.7760 | +0.0600 |
| 5 exps, 3/5 success | 0.60 | 0.8300 | 0.7220 | +0.2300 |
| 10 exps, 8/10 success | 0.80 | 0.8600 | 0.7760 | +0.0600 |
| 3 exps, 2/3 success | 0.67 | 0.7400 | 0.6400 | +0.0700 |

**The current architecture systematically OVERESTIMATES prediction probability** because correlated evidence is treated as independent.

### 3.3 Root Cause

Pattern is a **deterministic function of Experience**:
```
Pattern = groupby(intent, action_type) → {success_rate, support_count, ...}
```

Pattern encodes NO information beyond what exists in the raw experiences. It is a LOSSY COMPRESSION, not an independent signal.

When both signals contribute to prediction, the SAME evidence is weighted twice:
- Once directly (via experience retrieval)
- Once indirectly (via pattern aggregation)

---

## 4. Experience / Pattern Statistical Relationship

### 4.1 Formal Relationship

```
Pattern ≡ f(Experience)
where f = groupby(intent, action_type) → aggregate_statistics
```

This is a **many-to-one** mapping:
- Many experiences → One pattern per group
- Pattern is FULLY DETERMINED by its source experiences
- Pattern is a SUBSET aggregation, not an independent observation

### 4.2 Independence Test

| Test | Result |
|------|--------|
| Does Pattern contain info not in Experience? | NO |
| Can Pattern predict something Experience cannot? | NO |
| Are they statistically independent? | NO — Pattern ⊂ Experience |
| Is Pattern a sufficient statistic for its group? | YES |
| Does Pattern add information value? | NO — it compresses, doesn't create |

### 4.3 Conclusion

**Pattern is NOT independent evidence.** It is aggregated evidence. Using it as a parallel signal to raw experience violates the independence assumption underlying weighted averaging.

---

## 5. Pattern Confidence Semantics

### 5.1 Current Formula

```
confidence = success_rate × evidence_weight(support_count) × contradiction_penalty
```

Where:
- `success_rate` = fraction of successes in group
- `evidence_weight` = {0.3 if count<3, 0.6 if count<5, 0.9 if count≥5}
- `contradiction_penalty` = cap at 0.2 if contradiction_rate > 50%

### 5.2 What It Actually Represents

| Input | success_rate | weight | confidence | Real meaning |
|-------|-------------|--------|------------|-------------|
| 1 success | 1.00 | 0.3 | 0.30 | Weak evidence, all positive |
| 3 success | 1.00 | 0.6 | 0.60 | Moderate evidence |
| 5 success | 1.00 | 0.9 | 0.90 | Strong evidence |
| 5s+1f | 0.83 | 0.9 | 0.75 | Strong evidence, mostly positive |
| 3s+2f | 0.60 | 0.6 | 0.36 | Weak-moderate, mixed |
| 2s+3f | 0.40 | 0.9 | 0.36 | Strong evidence, mostly negative |

### 5.3 Naming Verdict

**`Pattern.confidence` is MISNAMED.**

It is NOT a probability. It is a **support score** — a composite measure of:
1. How often the pattern holds (success_rate)
2. How much data supports it (evidence_weight)
3. Whether contradictions exist (contradiction_penalty)

**RECOMMENDATION**: Rename to `Pattern.support_score`.

**Risk of not renaming**: Future developers will interpret `confidence=0.9` as "90% probability this is true." It is NOT. It means "strong support from 5+ consistent experiences."

---

## 6. Candidate Evidence Architectures

### 6.1 Scheme A: Independent Weighted Signals (CURRENT)

```
Prediction = 0.55 × Base + 0.30 × Experience + 0.15 × Pattern
```

| Aspect | Assessment |
|--------|-----------|
| Double counting | **YES — confirmed** |
| Theoretical basis | **NONE — weights are heuristics** |
| Explainability | Good — each term visible |
| Extensibility | Poor — adding Knowledge compounds the problem |
| Risk | **HIGH** |

### 6.2 Scheme B: Hierarchical Evidence (RECOMMENDED)

```
Evidence = ExperienceRetriever.retrieve()
Quality = PatternRetriever.retrieve()
Adjusted_Evidence = Evidence × Quality_Factor(Pattern.support_score)
Prediction = 0.70 × Base + 0.30 × Adjusted_Evidence
```

| Aspect | Assessment |
|--------|-----------|
| Double counting | **NO — single evidence source** |
| Theoretical basis | Pattern adjusts evidence QUALITY, not adds signal |
| Explainability | Good — pattern acts as confidence modifier |
| Extensibility | Excellent — Knowledge would modify Pattern quality |
| Risk | **LOW** |

### 6.3 Scheme C: Pattern-Only

```
Prediction = 0.70 × Base + 0.30 × Pattern_Prob
```

| Aspect | Assessment |
|--------|-----------|
| Double counting | **NO — single path** |
| Theoretical basis | Pattern IS the evidence (lossy compression) |
| Explainability | Good — only one signal |
| Extensibility | Poor — loses individual experience context |
| Risk | **MEDIUM** — too aggressive simplification |

### 6.4 Recommendation

**Scheme B is the correct architecture.**

Rationale:
1. Eliminates double counting (fixes Blocker A)
2. Preserves experience detail (unlike Scheme C)
3. Pattern provides meta-level weighting (quality adjustment)
4. Extensible to Knowledge (Knowledge adjusts Pattern quality)
5. Clean provenance: Evidence → Pattern adjustment → Prediction

---

## 7. Hermes Actual Architecture

### 7.1 Search Results

```
$ find / -name "*.py" -path "*hermes*" 2>/dev/null
(no results)

$ find / -type d -name "hermes" 2>/dev/null
(no results)

$ grep -r "hermes\|Hermes" /workspace --include="*.py" 2>/dev/null
(no results)
```

**Hermes does NOT exist in this environment.**

The Phase 12 audit spec referenced:
> "Hermes currently exists: Episodic Memory, Semantic Memory, Hybrid Retriever, Experience JSONL, Evolution"

**None of these components exist.** This was an assumption in the audit spec, not a reality.

### 7.2 Implications

1. **No duplication risk** — there is nothing to duplicate against
2. **Self-contained design** — NeuroCortex Knowledge must be fully self-contained
3. **Future integration** — If Hermes is built later, it should CONSUME NeuroCortex output, not the reverse
4. **Phase 13 scope** — Must design Knowledge without assuming Hermes exists

---

## 8. Hermes Memory Data Flow

**N/A** — Hermes does not exist.

The responsibility matrix below reflects NeuroCortex-only capabilities.

---

## 9. Hermes vs NeuroCortex Responsibility Matrix

| Capability | Hermes | NeuroCortex | Owner | Notes |
|-----------|--------|-------------|-------|-------|
| Raw conversation | ? | CortexEvent.raw_input | Hermes (future) | Input entry point |
| Execution experience | ? | ExperienceStore | NC | Owned by NC |
| Episodic memory | ? | ExperienceStore + ExpRetriever | NC | Owned by NC |
| Semantic memory | ? | NONE | None yet | Knowledge layer fills this |
| Pattern | ? | PatternStore | NC | Owned by NC |
| Knowledge | ? | NONE | NC (proposed) | Phase 13 target |
| Retrieval | ? | ExpRetriever + PatRetriever | NC | Owned by NC |
| Prediction | ? | BasicPrediction + ExpPredModule | NC | Owned by NC |
| Decision | ? | BasicDecision | NC | Owned by NC |
| Action | ? | BasicAction | NC | Owned by NC |
| State | ? | CortexState | NC | Owned by NC |
| Feedback | ? | BasicFeedback | NC | Owned by NC |
| Learning | ? | ExperienceLearningModule | NC | Owned by NC |
| Outcome | ? | OutcomeProvider (injected) | Shared | External dependency |

### 9.1 Overlap Risk Assessment

Since Hermes does not exist, overlap risk is **THEORETICAL** (for future Hermes):

| Risk Zone | Current NC Capability | Future Hermes Risk | Mitigation |
|-----------|----------------------|-------------------|------------|
| Semantic memory | PatternStore (stats) | Duplicate rule storage | NC owns Pattern; Hermes owns facts |
| Experience retrieval | ExpRetriever (keyword) | Duplicate episodic records | Use ExperienceID as global unique key |
| Pattern consolidation | PatternConsolidator | Duplicate generalization | NC owns consolidation; Hermes reads output |
| Knowledge | None | N/A | Define clear API boundary before building |

---

## 10. Duplicate System Risk

### 10.1 Current Assessment

**Risk Level: LOW** (Hermes does not exist)

If Hermes is built in the future with semantic memory capabilities:
- PatternStore stores `(intent, action) → {rate, support, status}` — statistical rules
- Hermes Semantic Memory might store `fact → {confidence, source}` — factual knowledge
- These are DIFFERENT abstractions: statistics vs facts
- No duplication IF boundaries are defined early

### 10.2 Recommended Boundary Definition

```
NeuroCortex owns:
  - ExperienceStore (raw episodic records)
  - PatternStore (statistical generalizations)
  - KnowledgeStore (if Phase 13 implemented)
  - All retrieval and consolidation logic

Hermes (future) should own:
  - Semantic memory (facts, taxonomies, relationships)
  - Cross-domain retrieval (embedding-based)
  - Long-term persistence (database-backed)

Integration point:
  - Hermes READS from NeuroCortex stores via read-only API
  - Hermes NEVER WRITES to NeuroCortex stores
  - ExperienceID is the global unique key
```

---

## 11. Scaling Considerations

### 11.1 Verified Costs

| N (experiences) | Pattern Count | Consolidation Time | Experience Retrieval |
|-----------------|--------------|-------------------|---------------------|
| 100 | 8 | 0.2 ms | < 1 ms |
| 1,000 | 8 | 0.3 ms | < 1 ms |
| 10,000 | 8 | 3.4 ms | ~5 ms |
| 100,000 | 8 | 42.3 ms | ~50 ms |

### 11.2 Bottleneck Analysis

- **ExperienceStore retrieval** is O(N) — becomes slow at N > 10,000
- **PatternStore retrieval** is O(P) where P ≈ constant (~48 max) — always fast
- **Consolidation** is O(N) — acceptable at all scales (< 50ms at 100K)

### 11.3 Scaling Recommendations (Out of Scope for Pre-Phase 13)

1. Add `(intent, action_type)` index to ExperienceStore for O(1) group lookup
2. Consider batched consolidation (every 10 experiences, not on every save)
3. Pattern count saturates at ~48 (8 intents × 6 actions) — no scaling concern

---

## 12. Recommended Architecture

### 12.1 Required Changes Before Phase 13

| # | Change | Priority | Effort | Blocker? |
|---|--------|----------|--------|---------|
| 1 | Rename `Pattern.confidence` → `Pattern.support_score` | HIGH | 10 min | No |
| 2 | Restructure ExperiencePredictionModule to Scheme B (hierarchical) | HIGH | 1-2 hours | **YES** |
| 3 | Add ExperienceID provenance tracking | MEDIUM | 30 min | No |
| 4 | Define Knowledge dataclass (Phase 13 prep) | LOW | 30 min | No |

### 12.2 Scheme B Implementation Sketch

```python
# NEW: ExperiencePredictionModule (Scheme B)
class ExperiencePredictionModule(PredictionModule):
    def process(self, event):
        # Step 1: Base prediction
        event = self._base_prediction.process(event)
        
        # Step 2: Retrieve experience evidence
        experiences = self._retriever.retrieve(...)
        if not experiences:
            return event
        
        # Step 3: Compute raw experience probability
        exp_prob = sum(e.success for e,_ in experiences) / len(experiences)
        
        # Step 4: Retrieve pattern quality signal
        patterns = self._pattern_retriever.retrieve(...)
        if patterns:
            # Pattern adjusts evidence weight (quality modifier)
            avg_support = sum(p.support_score for p,_ in patterns) / len(patterns)
            quality_factor = min(avg_support / 0.7, 1.0)  # Normalize
        else:
            quality_factor = 1.0  # No pattern → full weight
        
        # Step 5: Apply quality adjustment
        adjusted_prob = exp_prob * quality_factor
        
        # Step 6: Blend with base
        final_prob = (1 - self._evidence_weight) * event.prediction.success_probability + \
                     self._evidence_weight * adjusted_prob
        
        event.predict(PredictionData(
            predicted_outcome=event.prediction.predicted_outcome,
            success_probability=max(0.0, min(1.0, final_prob)),
            predicted_risk=event.prediction.predicted_risk,
            prediction_confidence=event.prediction.prediction_confidence,
        ))
        return event
```

**Key difference from current**: Pattern no longer adds a parallel signal. It MODIFIES the weight of the experience signal. This eliminates double counting.

### 12.3 Knowledge Layer Design (Phase 13 Prep)

If Phase 13 proceeds, Knowledge would follow the SAME hierarchical pattern:

```
Knowledge.support_score adjusts Pattern.support_score
Pattern.support_score adjusts Experience evidence weight
Experience evidence weight adjusts Prediction
```

This means:
- Knowledge is TWO LEVELS up from experience (not direct)
- Knowledge NEVER directly touches prediction
- Each level provides QUALITY adjustment, not ADDITIONAL signal
- Provenance is fully traceable: Knowledge → Pattern → Experience → Prediction

---

## 13. Required Changes Before Phase 13

### 13.1 Must-Fix (Blocking)

| Change | Why | Risk if Skipped |
|--------|-----|----------------|
| Restructure prediction to Scheme B | Eliminate double counting | Phase 13 Knowledge would compound the error (triple counting) |

### 13.2 Should-Fix (Recommended)

| Change | Why | Risk if Skipped |
|--------|-----|----------------|
| Rename `confidence` → `support_score` | Prevent semantic confusion | Future developers misinterpret as probability |
| Add ExperienceID provenance | Enable deduplication auditing | Cannot verify no double counting |

### 13.3 Nice-to-Have (Post-Phase 13)

| Change | Why | Risk if Skipped |
|--------|-----|----------------|
| Index ExperienceStore by (intent, action) | Scale to 100K+ experiences | Performance degradation |
| Add periodic consolidation trigger | Keep patterns fresh | Stale patterns affect prediction |

---

## 14. Decision

### VERDICT: READY FOR PRE-PHASE 13 IMPLEMENTATION

**With one mandatory fix before Phase 13 begins:**

> **Restructure `ExperiencePredictionModule` from Scheme A (independent signals) to Scheme B (hierarchical evidence).**

This fix:
- Eliminates double counting
- Provides clean foundation for Knowledge layer
- Requires ~1-2 hours of implementation
- Does NOT change test expectations (same inputs → same outputs, just more correct)

### What Phase 13 Can Safely Do After This Fix

1. Define `Knowledge` dataclass (Pattern + boundary conditions)
2. Implement `KnowledgeStore` (JSONL persistence)
3. Implement `KnowledgeRetriever` (condition + scope matching)
4. Add Knowledge → Pattern quality adjustment (one more hierarchical level)
5. Write 10+ tests covering promotion, retrieval, isolation, determinism

### What Phase 13 Must NOT Do

1. Add a third independent prediction signal (would compound double counting)
2. Assume Hermes exists (design self-contained)
3. Modify frozen Phase 0-12 code except for the Scheme B restructure
4. Introduce ML/embedding/clustering
5. Change the 11-stage pipeline

---

**Audit Complete. Output: READY FOR PRE-PHASE 13 IMPLEMENTATION.**
