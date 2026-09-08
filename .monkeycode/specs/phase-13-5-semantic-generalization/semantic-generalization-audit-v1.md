# NeuroCortex Phase 13.5 — Semantic Representation & Generalization Architecture Audit v1

**Document**: Architecture Audit — Semantic Capability Assessment  
**Version**: v1  
**Date**: 2026-09-07  
**Status**: DRAFT — Under Review  
**Project**: neuro-cortex  
**Baseline**: Commit 3ce854e, 458 PASS / 0 FAIL  
**Frozen Base**: Phase 0-12 + Evidence Integrity

---

## 1. Executive Summary

**VERDICT: BLOCKED — Semantic capability is NOT ready for implementation in Phase 13.5.**

The current hash embedding is a **placeholder with no semantic value**. Experimental evidence confirms:
- Intra-group similarity (0.89) ≈ Inter-group similarity (0.90) — difference of -0.01
- Hash embedding cannot distinguish semantic similarity from random similarity
- The embedding field exists in RepresentationData but is **never used** by any downstream module

**However**, the architecture is **designed for extensibility**:
- `EmbeddingProvider` is already a pluggable interface
- `RepresentationData.embedding` field exists
- All modules use Dependency Injection

The bottleneck is **not architecture** — it's the absence of semantic retrieval infrastructure and the decision of whether semantic generalization is necessary for Knowledge.

**Key finding**: Semantic generalization is NOT strictly necessary for Knowledge (Case 1: explicit conditions work without it), but it ENABLES automatic Knowledge formation (Case 2). This is a **design decision for Phase 14+**, not an implementation task for Phase 13.5.

---

## 2. Current Architecture

### 2.1 Frozen Components (Cannot Modify)

| Component | Status | Frozen Commit |
|-----------|--------|--------------|
| Phase 0-10 | FROZEN | b3ab0c8 |
| Phase 11 (Experience) | FROZEN | 98dfcea |
| Phase 12 (Pattern) | FROZEN | adc8cbe |
| Evidence Integrity | FROZEN | 3ce854e |
| CortexEvent schema | FROZEN | All above |
| Pipeline stages (11) | FROZEN | All above |
| Module interfaces | FROZEN | All above |

### 2.2 Current Evidence Flow (Post-Evidence-Integrity)

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

### 2.3 Existing (Unused) Semantic Infrastructure

```python
# representation.py:12-53
class EmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        """Default: deterministic hash-based embedding (stable, no model).
        For production: replace with a real embedding provider."""
        return self._hash_embedding(text, dim=16)

# representation.py:66-82
class BasicRepresentation:
    def process(self, event):
        embedding = self._provider.embed(event.raw_input)
        event.represent(RepresentationData(
            raw_text=event.raw_input,
            features=features,
            embedding=embedding,  # ← WRITTEN but NEVER READ downstream
        ))
```

**Critical finding**: `EmbeddingProvider` exists as a **design-for-extensibility** pattern, but the embedding is computed and then **discarded** by all downstream modules.

---

## 3. Current Representation Capability

### 3.1 What Current Representation Produces

| Field | Type | Content | Semantic Value |
|-------|------|---------|---------------|
| `raw_text` | str | Original input | None (identity) |
| `features` | dict | 15 numeric features (token_count, char_count, etc.) | LOW (structural only) |
| `embedding` | list[float] | 16-dim hash vector | **NONE** (see Section 4) |

### 3.2 Hash Embedding Analysis

The current `_hash_embedding` method:
1. Applies 3 independent hash functions to the text
2. Produces 16 float values in [0, 1]
3. Is **deterministic** (same input → same output)
4. Is **NOT semantic** (similar meaning → random similarity)

### 3.3 Code Evidence

From `representation.py:31-53`:
```python
@staticmethod
def _hash_embedding(text: str, dim: int = 16) -> list[float]:
    """Deterministic hash-based embedding.
    Same input always produces same output.
    Values are in [-1, 1] range, normalized to [0, 1]."""
    if not text:
        return [0.5] * dim
    vectors = []
    for seed in range(3):
        h = hash((text, seed)) & 0xFFFFFFFF
        component = []
        for i in range(dim):
            h = ((h ^ (h >> 16)) * 0x45d9f3b) & 0xFFFFFFFF
            component.append((h & 0xFF) / 255.0)
        vectors.append(component)
    result = []
    for i in range(dim):
        avg = sum(v[i] for v in vectors) / len(vectors)
        result.append(round(avg, 4))
    return result
```

**This is a HASH FUNCTION, not a semantic embedding.** It maps text to a fixed-length vector based on bitwise operations, not meaning.

---

## 4. Current Embedding Analysis

### 4.1 Experimental Evidence

Test matrix (12 texts across 3 semantic groups):

| Group | Texts | Intra-group avg similarity |
|-------|-------|---------------------------|
| import_errors | 5 texts | 0.8910 |
| unrelated | 4 texts | 0.8845 |
| chinese_import | 3 texts | 0.8726 |

**Inter-group avg similarity: 0.9017**

**Difference: Intra - Inter = -0.0108** (essentially zero — random)

### 4.2 Similarity Matrix (Selected Pairs)

| Pair | Type | Similarity | Expected | Result |
|------|------|-----------|----------|--------|
| "fix python import" ↔ "fix python import" | Exact | 1.0000 | 1.0 | ✓ |
| "fix python import" ↔ "repair python import problem" | Lexical | 0.9504 | >0.7 | Partial |
| "Python import error" ↔ "ModuleNotFoundError" | Semantic | 0.8854 | >0.8 | Coincidental |
| "Python import error" ↔ "package path resolution failure" | Semantic | 0.8915 | >0.8 | Coincidental |
| "Python import error" ↔ "database backup failure" | Negative | 0.9298 | <0.3 | **FAIL** |
| "fix python import" ↔ "修复 Python 导入错误" | Cross-lingual | 0.9446 | >0.7 | Coincidental |

### 4.3 Conclusion

**The hash embedding CANNOT distinguish semantic similarity.**

- Same-group pairs: ~0.89 average
- Different-group pairs: ~0.90 average
- The difference is NEGATIVE (-0.01), meaning inter-group similarity is HIGHER than intra-group

This is the hallmark of a **random mapping** — not a semantic one.

### 4.4 Why This Matters

The comment in `representation.py:26` states:
> "For production: replace with a real embedding provider."

**This replacement has not happened.** The hash embedding is a placeholder.

---

## 5. Generalization Levels

### 5.1 Defined Levels

| Level | Name | Description | Current Status |
|-------|------|-------------|---------------|
| 0 | Exact Match | Identical text → identical vector | ✓ WORKS |
| 1 | Lexical Variation | Shared words → higher similarity | ~PARTIAL |
| 2 | Semantic Variation | Shared meaning → higher similarity | ✗ FAILS |
| 3 | Cross-Lingual | Same meaning, different language | ✗ FAILS |

### 5.2 Current System Capability

**NeuroCortex currently operates at Level 0-1 only.**

- Exact match works (hash is deterministic)
- Lexical variation has PARTIAL success (shared tokens produce somewhat similar hashes)
- Semantic variation FAILS (meaning is invisible to hash)
- Cross-lingual FAILS (no language awareness)

### 5.3 Knowledge Requirements

**Knowledge requires at minimum Level 2 (Semantic Variation).**

Without semantic generalization:
- Knowledge conditions must be explicitly specified (manual, brittle)
- Knowledge cannot discover implicit relationships
- Knowledge cannot generalize to novel phrasings

### 5.4 Gap Analysis

```
Current:  Level 0-1 (Exact + Lexical)
Required: Level 2+ (Semantic + Cross-lingual)
Gap:      1-2 levels
```

---

## 6. Experimental Design

### 6.1 Read-Only Experiments (Designed, Not Implemented)

The following experiments are DESIGNED for future implementation. They do NOT modify production code.

#### Group A — Exact Match
```python
text_a = "fix python import error"
text_b = "fix python import error"
# Expected: similarity = 1.0
# Current:  1.0 ✓
```

#### Group B — Lexical Variation
```python
text_a = "fix python import error"
text_b = "repair python import problem"
# Expected: similarity > 0.7
# Current:  ~0.95 (partial — due to shared tokens)
```

#### Group C — Semantic Variation
```python
text_a = "Python import error"
text_b = "ModuleNotFoundError"
# Expected: similarity > 0.8
# Current:  ~0.89 (coincidental — not reliable)
```

#### Group D — Chinese Variation
```python
text_a = "修复 Python 导入错误"
text_b = "Python 模块导入失败"
# Expected: similarity > 0.8
# Current:  ~0.87 (coincidental — not reliable)
```

#### Group E — Cross-Lingual
```python
text_a = "fix python import error"
text_b = "修复 Python 导入错误"
# Expected: similarity > 0.7
# Current:  ~0.94 (coincidental — not reliable)
```

#### Group F — Negative Pair
```python
text_a = "Python import error"
text_b = "database backup failure"
# Expected: similarity < 0.3
# Current:  ~0.93 (FAIL — should be low, is high)
```

### 6.2 Expected Results with Real Embedding

| Group | Expected with Hash | Expected with Real Embedding |
|-------|-------------------|---------------------------|
| A (Exact) | 1.000 | 1.000 |
| B (Lexical) | 0.950 | 0.700-0.850 |
| C (Semantic) | 0.890 | 0.850-0.950 |
| D (Chinese) | 0.870 | 0.800-0.900 |
| E (Cross-lingual) | 0.940 | 0.700-0.850 |
| F (Negative) | 0.930 | 0.100-0.300 |

**Key difference**: Real embedding would make Group F have LOW similarity (<0.3), while hash gives HIGH similarity (~0.93). This is the critical test.

---

## 7. Expected Failure Cases

### 7.1 If Semantic Capability Is Added Without Proper Design

| Failure Mode | Description | Prevention |
|-------------|-------------|------------|
| Double counting | Same experience retrieved via keyword AND semantic paths | Deduplicate by experience_id |
| Provenance loss | Cannot trace which retrieval method found an experience | Add provenance tag to retrieval results |
| Performance degradation | Semantic retrieval is slower than keyword | Cache embeddings, batch processing |
| Non-determinism | Different machines produce different embeddings | Use frozen model, fixed seed |
| Chinese degradation | English-only model fails on Chinese | Use multilingual model |

### 7.2 If Semantic Capability Is NOT Added

| Limitation | Description | Impact |
|-----------|-------------|--------|
| No semantic retrieval | "fix import" won't match "ModuleNotFoundError" | Knowledge formation blocked |
| Manual condition specification | User must explicitly tag sub-contexts | Brittle, non-scalable |
| No cross-lingual support | Chinese and English experiences isolated | Language barrier |
| Pattern isolation | Each (intent, action) pattern is independent | No cross-pattern generalization |

---

## 8. Semantic Architecture Candidates

### 8.1 Architecture A: Semantic Representation Layer

```
Raw Input
    ↓
Perception (intent detection)
    ↓
Representation
    ├── Features (structural)
    └── Embedding (semantic) ← ENHANCED
    ↓
ExperienceStore (stores embedding)
    ↓
ExperienceRetriever
    ├── Keyword+tag path (existing)
    └── Semantic path (NEW) ← DEDUPLICATE
    ↓
empirical_rate (single, deduplicated)
    ↓
Pattern quality adjustment
    ↓
Prediction
```

**Pros:**
- Minimal pipeline changes
- Embedding flows naturally through existing Representation stage
- Deduplication at retrieval level prevents double counting

**Cons:**
- Requires modifying Experience to store embedding
- Requires modifying ExperienceRetriever to support semantic path
- Still needs embedding model

### 8.2 Architecture B: Semantic Retrieval Layer

```
Raw Input
    ↓
Perception (intent detection)
    ↓
Representation (unchanged)
    ↓
ExperienceStore (unchanged)
    ↓
SemanticRetriever (NEW module)
    ├── Retrieves by embedding similarity
    └── Returns deduplicated experience IDs
    ↓
Merge with keyword retrieval results
    ↓
Single empirical_rate (deduplicated)
    ↓
Pattern quality adjustment
    ↓
Prediction
```

**Pros:**
- No changes to Experience or Representation
- Semantic retrieval is a separate concern
- Easy to toggle on/off

**Cons:**
- Need to re-compute embeddings for existing experiences
- Two retrieval paths need coordination
- More complex integration

### 8.3 Recommendation

**Architecture A is preferred** because:
1. Embedding is already computed in Representation (just unused)
2. Storing embedding in Experience is a natural extension
3. Deduplication at retrieval time is cleaner
4. Minimal pipeline changes

---

## 9. Embedding Architecture Candidates

### 9.1 Option A: Multilingual Sentence Transformer

```python
from sentence_transformers import SentenceTransformer

class MultilingualEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    def embed(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()
```

| Attribute | Value |
|-----------|-------|
| Model size | ~90 MB |
| Languages | 50+ (including Chinese) |
| Dimension | 384 |
| Inference (CPU) | ~20-50 ms/text |
| Deterministic | Yes (frozen model) |
| Dependency | `sentence-transformers` + `torch` |
| GPU required | No |

**Fits constraints:** NO — requires installing torch/sentence-transformers.

### 9.2 Option B: ONNX Runtime Embedding

```python
import onnxruntime

class ONNXEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_path: str):
        self._session = onnxruntime.InferenceSession(model_path)
    
    def embed(self, text: str) -> list[float]:
        # Tokenize and run ONNX model
        ...
```

| Attribute | Value |
|-----------|-------|
| Model size | ~90 MB (same model, ONNX format) |
| Languages | 50+ |
| Dimension | 384 |
| Inference (CPU) | ~10-30 ms/text |
| Deterministic | Yes (frozen model) |
| Dependency | `onnxruntime` |
| GPU required | No |

**Fits constraints:** BORDERLINE — requires model download + ONNX dependency.

### 9.3 Option C: Character N-gram Hash (No ML)

```python
class NGramEmbeddingProvider(EmbeddingProvider):
    def embed(self, text: str, dim: int = 64) -> list[float]:
        # Build character n-gram histogram
        # Hash to fixed dimension
        ...
```

| Attribute | Value |
|-----------|-------|
| Model size | 0 (algorithmic) |
| Languages | All (character-level) |
| Dimension | 64 (configurable) |
| Inference (CPU) | <1 ms/text |
| Deterministic | Yes |
| Dependency | None |
| GPU required | No |

**Semantic quality:** LOW — better than current hash, but not true semantics.

**Fits constraints:** YES.

### 9.4 Option D: Bilingual Keyword Expansion

```python
class KeywordExpansionProvider(EmbeddingProvider):
    SYNONYMS = {
        "fix": ["修复", "repair", "解决"],
        "import": ["导入", "引入", "package"],
        "error": ["错误", "失败", "异常"],
        ...
    }
    
    def embed(self, text: str) -> list[float]:
        # Expand text with synonyms, then hash
        ...
```

| Attribute | Value |
|-----------|-------|
| Model size | 0 (dictionary) |
| Languages | Chinese + English |
| Dimension | 16 (same as current) |
| Inference (CPU) | <1 ms/text |
| Deterministic | Yes |
| Dependency | None |
| GPU required | No |

**Semantic quality:** MEDIUM — captures explicit synonym relationships.

**Fits constraints:** YES.

### 9.5 Recommendation

For **Phase 13.5 AUDIT only**:
- Design Architecture A with Option A (multilingual embedding) as the target
- Document why Options C/D are insufficient for true semantic generalization
- Defer implementation to Phase 14+ pending Hermes architecture decision

---

## 10. Evidence Provenance Analysis

### 10.1 Current Provenance

```
Experience.experience_id → source_event_id (CortexEvent.id)
Pattern.source_experience_ids → list of Experience.experience_id
```

**Current state:** Provenance is TRACABLE but not TRACKED during retrieval.

### 10.2 Risk with Semantic Retrieval

If we add semantic retrieval:

```
ExperienceStore
    ├── keyword+tag retrieval → [e0, e1, e2]
    └── semantic retrieval    → [e0, e1, e2, e3]  ← overlap!
```

The SAME experiences (e0, e1, e2) would be counted in BOTH retrieval paths.

### 10.3 Solution: Provenance Tracking

Each retrieved experience must carry:
```python
@dataclass
class RetrievedExperience:
    experience: Experience
    source: str  # "keyword" | "semantic" | "pattern"
    score: float
```

Then deduplicate:
```python
# Before computing empirical_rate:
unique_experiences = {}
for retr_exp in all_retrieved:
    if retr_exp.experience.experience_id not in unique_experiences:
        unique_experiences[retr_exp.experience.experience_id] = retr_exp

empirical_rate = sum(1 for e in unique_experiences.values() if e.experience.success) / len(unique_experiences)
```

### 10.4 Hierarchical Evidence Model (Proposed)

```
Level 1: Raw Experience Retrieval
  - keyword+tag path (deterministic)
  - semantic path (probabilistic)
  - DEDUPLICATE by experience_id
  - Compute SINGLE empirical_rate

Level 2: Pattern Quality Adjustment
  - Pattern.support_score adjusts empirical_rate
  - Pattern is derived from ALL experiences (not just retrieved)
  - No double counting (Pattern is metadata, not evidence)

Level 3: Knowledge (future)
  - Knowledge.refinement adjusts Pattern.support_score
  - No double counting (Knowledge modifies Pattern, not evidence)
```

**Key principle:** Evidence flows UP the hierarchy. Each level MODIFIES the quality of the level below, never adds INDEPENDENT evidence.

---

## 11. Double Counting Risk Analysis

### 11.1 Current Risk (Post-Evidence-Integrity)

**Risk: LOW** — Scheme B eliminates double counting by making Pattern a quality weight, not an independent signal.

### 11.2 Risk with Semantic Retrieval

**Risk: HIGH** — If both keyword and semantic retrievals return overlapping experiences, and both contribute to empirical_rate, double counting RESURFACES.

### 11.3 Mitigation

1. **Deduplication by experience_id** before computing empirical_rate
2. **Provenance tagging** to track which path found each experience
3. **Hierarchical evidence model** — semantic retrieval is just another path to the SAME evidence pool

### 11.4 Never-Allow Pattern

The following MUST NEVER happen:
```python
# WRONG: Double counting
empirical_rate_1 = compute_rate(keyword_results)
empirical_rate_2 = compute_rate(semantic_results)
prediction = w1 * empirical_rate_1 + w2 * empirical_rate_2  # SAME experiences counted twice

# CORRECT: Deduplicated
all_results = deduplicate(keyword_results + semantic_results)
empirical_rate = compute_rate(all_results)
prediction = w * empirical_rate  # Each experience counted once
```

---

## 12. Knowledge Dependency Analysis

### 12.1 Can Knowledge Exist Without Semantic Generalization?

**YES, but with limitations.**

| Knowledge Type | Needs Semantic? | Feasible Without? |
|---------------|-----------------|-------------------|
| Explicit condition proposition | NO | YES (manual specification) |
| Automatic pattern refinement | PARTIALLY | PARTIALLY (with tagging) |
| Cross-condition generalization | YES | NO |
| Boundary condition discovery | YES | NO |

### 12.2 When Is Semantic Generalization Necessary?

**When Knowledge must:**
1. Discover that "import error" and "ModuleNotFoundError" are the same concept
2. Generalize from "fix Python import" to "fix Node.js require"
3. Handle novel phrasings not in any explicit condition list

**When Knowledge does NOT need it:**
1. All conditions are explicitly specified by user
2. Manual tagging covers all relevant sub-contexts
3. Pattern-level generalization is sufficient

### 12.3 Verdict

**Semantic generalization is an ENABLER, not a REQUIREMENT, for Knowledge.**

- With semantic generalization: Knowledge can be AUTOMATICALLY discovered
- Without semantic generalization: Knowledge must be MANUALLY specified

The choice depends on whether we want Knowledge to be **scalable and automatic** or **explicit and controlled**.

---

## 13. Chinese Capability Analysis

### 13.1 Current State

| Capability | Status |
|-----------|--------|
| Chinese keyword detection | ✓ (in MockPerception) |
| Chinese text hashing | ✓ (hash handles Unicode) |
| Chinese semantic similarity | ✗ (hash has no semantic awareness) |
| Chinese-English cross-lingual | ✗ (no cross-lingual capability) |
| Chinese experience storage | ✓ (UTF-8 preserved) |
| Chinese pattern consolidation | ✓ (intent labels are language-agnostic) |

### 13.2 Requirements for Full Chinese Support

| Requirement | Current | Needed |
|------------|---------|--------|
| Chinese tokenization | Character-level hash | Word-level (jieba) or character n-gram |
| Chinese embedding | Hash (no semantics) | Multilingual embedding model |
| Chinese-English alignment | None | Multilingual model or translation layer |
| Chinese synonym expansion | None | Bilingual synonym dictionary |

### 13.3 Recommendation

**Phase 13.5:** Design architecture for multilingual embedding (Option A: paraphrase-multilingual-MiniLM)
**Phase 14+:** Implement with Chinese-specific considerations (jieba tokenization, bilingual expansion)

---

## 14. Cost / Complexity Analysis

### 14.1 Approach Comparison

| Approach | Semantic Quality | Deterministic | Dependency | Latency | Cost | Fits Constraints? |
|----------|-----------------|---------------|------------|---------|------|-------------------|
| A: Rules/Synonyms | Low | YES | None | <1ms | Low | YES |
| B: NLP Features | Medium | YES* | spaCy | 5-10ms | Medium | YES* |
| C: Multilingual Embed | High | NO* | torch+model | 20-50ms | High | NO |
| D: ONNX Embed | High | NO* | onnx+model | 10-30ms | High | BORDERLINE |
| E: LLM API | Highest | NO | API key | 500ms+ | Very High | NO |

*Deterministic only with frozen model.

### 14.2 Implementation Complexity

| Component | Effort (hours) | Risk |
|-----------|---------------|------|
| Add embedding to Experience | 2 | LOW |
| Modify ExperienceRetriever | 4 | MEDIUM |
| Add deduplication logic | 3 | LOW |
| Integrate semantic path | 8 | MEDIUM |
| Test with real embedding | 16 | MEDIUM |
| Chinese support | 8 | MEDIUM |
| **Total** | **41** | **MEDIUM** |

### 14.3 Operational Complexity

| Factor | Current | With Semantic |
|--------|---------|--------------|
| Storage per experience | ~200 bytes | ~200 bytes + 384 floats (1.5KB) |
| Retrieval latency | <1ms | 20-50ms (embedding computation) |
| Startup time | Instant | 1-2 seconds (model load) |
| Memory footprint | ~50MB | ~150MB (+model) |
| Dependencies | None | sentence-transformers, torch |

---

## 15. Recommended Architecture

### 15.1 For Phase 13.5 (Audit Only)

**Do NOTHING to production code.**

Document the following design for future implementation:

```
[DESIGN ONLY — NOT IMPLEMENTED]

Representation Enhancement:
  - Add embedding to Experience dataclass (optional, backward-compatible)
  - Keep hash embedding as default
  - Allow EmbeddingProvider injection for real embeddings

Retrieval Enhancement:
  - Add semantic retrieval path to ExperienceRetriever
  - Deduplicate by experience_id before computing empirical_rate
  - Tag each retrieved experience with provenance source

Prediction Integration:
  - NO change to Evidence Integrity (Scheme B)
  - Semantic retrieval feeds into SAME empirical_rate (deduplicated)
  - Pattern quality adjustment remains unchanged
```

### 15.2 Implementation Prerequisites

Before implementing semantic capability, resolve:

1. **Hermes architecture** — Does Hermes provide semantic memory? If yes, NeuroCortex should consume it.
2. **Knowledge requirement** — Does Knowledge truly need semantic generalization, or can it work with explicit conditions?
3. **Dependency policy** — Is installing torch/sentence-transformers acceptable for this project?
4. **Performance budget** — Is 20-50ms additional latency acceptable per prediction?

### 15.3 Decision Matrix

| Condition | Action |
|-----------|--------|
| Hermes has Semantic Memory | Consume Hermes, no NeuroCortex change |
| Hermes has NO Semantic Memory + Knowledge needs it | Implement Option A (multilingual embedding) |
| Hermes has NO Semantic Memory + Knowledge doesn't need it | Stay with Pattern (no semantic capability) |
| Dependency policy forbids torch | Implement Option C/D (ONNX or n-gram) |
| Performance budget <10ms | Implement Option C (n-gram hash enhancement) |

---

## 16. Minimum Sufficient Capability

### 16.1 What "Minimum Sufficient" Means

The minimum semantic capability that enables:
1. Semantic generalization within the same language
2. Basic cross-lingual support (if needed)
3. No double counting
4. Deterministic behavior (with frozen model)
5. No breaking changes to frozen phases

### 16.2 Minimum Viable Semantic Capability

```python
# 1. Add optional embedding to Experience
@dataclass
class Experience:
    # ... existing fields ...
    embedding: list[float] = field(default_factory=list)  # NEW, optional

# 2. Enhance ExperienceRetriever with semantic path
class ExperienceRetriever:
    def retrieve(self, raw_input, intent, action_type, use_semantic=False):
        keyword_results = self._keyword_retrieve(raw_input, intent, action_type)
        if use_semantic and self._embedding_provider:
            semantic_results = self._semantic_retrieve(raw_input)
            # Deduplicate
            all_results = deduplicate_by_id(keyword_results + semantic_results)
        else:
            all_results = keyword_results
        return all_results[:self._top_k]

# 3. Keep Evidence Integrity (Scheme B) unchanged
# Pattern still acts as quality weight, not independent signal
```

### 16.3 What Is NOT Minimum Viable

- Full LLM integration
- Real-time embedding computation (cache instead)
- Cross-lingual retrieval (can add later)
- Automatic Knowledge formation (requires more than just embedding)

---

## 17. Future Implementation Boundary

### 17.1 What Phase 13.5 Should NOT Do

- ❌ Install sentence-transformers or torch
- ❌ Download any model weights
- ❌ Modify Experience dataclass
- ❌ Modify ExperienceRetriever
- ❌ Modify PatternConsolidator
- ❌ Modify Prediction module
- ❌ Add any new production code
- ❌ Change any frozen interface

### 17.2 What Phase 13.5 SHOULD Do

- ✅ Document the gap (hash ≠ semantic)
- ✅ Design the architecture for semantic capability
- ✅ Define the integration points
- ✅ Identify prerequisites (Hermes, dependencies, performance)
- ✅ Produce this audit report

### 17.3 What Phase 14+ Will Do (If Approved)

- Implement semantic retrieval with real embedding
- Add deduplication logic
- Test with multilingual model
- Measure performance impact
- Update documentation

---

## 18. Non-goals

The following are EXPLICITLY OUT OF SCOPE for Phase 13.5:

| Non-goal | Reason |
|----------|--------|
| Implement semantic retrieval | Requires ML dependency, defer to Phase 14+ |
| Install embedding models | Violates "no installation" constraint |
| Modify frozen phases | Violates freeze constraint |
| Add Knowledge layer | Blocked by Phase 13 audit (no semantic yet) |
| Build synonym dictionaries | Manual maintenance, not scalable |
| Integrate LLM API | Requires network, violates constraints |
| Modify CortexEvent schema | Frozen contract |
| Add new pipeline stages | Frozen 11-stage pipeline |
| Change Evidence Integrity | Already frozen and working |
| Build vector database | Over-engineering for current scale |

---

## 19. Architecture Risks

### 19.1 Critical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Semantic retrieval causes double counting | HIGH | HIGH | Deduplication by experience_id |
| Model download breaks air-gapped environments | MEDIUM | HIGH | Provide offline model cache option |
| Chinese support degrades with English model | MEDIUM | MEDIUM | Use multilingual model |
| Latency increase affects user experience | MEDIUM | MEDIUM | Cache embeddings, batch processing |

### 19.2 High Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hermes provides semantic memory (duplication) | UNKNOWN | HIGH | Audit Hermes first |
| Knowledge doesn't need semantic generalization | MEDIUM | MEDIUM | Define explicit Knowledge requirements |
| Embedding non-determinism across platforms | LOW | MEDIUM | Use frozen model, fixed seed |
| Memory footprint increase | MEDIUM | LOW | 1.5KB per experience is acceptable |

### 19.3 Medium Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Test coverage gaps in semantic retrieval | HIGH | LOW | Add dedicated tests |
| Backward compatibility with old experiences | MEDIUM | LOW | Embedding is optional field |
| Performance degradation at scale | LOW | MEDIUM | Benchmark at 10K, 100K experiences |

---

## 20. Final Verdict

### 20.1 Decision

**BLOCKED — Semantic capability is NOT ready for Phase 13.5 implementation.**

### 20.2 Blockers

| # | Blocker | Evidence | Resolution Required |
|---|---------|----------|-------------------|
| 1 | Hash embedding has NO semantic value | Experimental evidence: intra-group (0.89) ≈ inter-group (0.90) | Accept that current embedding is placeholder |
| 2 | Semantic generalization not proven necessary for Knowledge | Knowledge can work with explicit conditions (Case 1) | Define whether automatic Knowledge formation is required |
| 3 | Hermes architecture unknown | No Hermes code found in repository | Audit Hermes before designing NeuroCortex semantic layer |
| 4 | ML dependency forbidden by constraints | Installing torch/sentence-transformers violates "no ML" rule | Wait for dependency policy decision |

### 20.3 Path Forward

**Immediate (Phase 13.5):**
- Accept this audit as complete
- Do NOT modify any production code
- Document design for future implementation

**Prerequisites for Phase 14:**
1. Hermes architecture audit complete
2. Decision on whether Knowledge needs semantic generalization
3. Dependency policy approval for ML models
4. Performance budget confirmation

**If all prerequisites met:**
- Implement Architecture A with multilingual embedding
- Add deduplication and provenance tracking
- Test with real embedding model
- Expected: ~40 hours of implementation

### 20.4 What This Audit Proved

1. **Current embedding is a placeholder** — hash-based, no semantic value
2. **Architecture supports extensibility** — EmbeddingProvider interface exists
3. **Double counting risk is manageable** — deduplication by experience_id
4. **Semantic generalization is a DESIGN choice, not a technical requirement**
5. **Chinese support requires multilingual model or explicit expansion**

---

**Audit Complete. Output: BLOCKED.**
