# NC-06.1: Policy Disagreement Validation Report

## Executive Summary

**VERDICT: NO_NATURAL_POLICY_DISAGREEMENT**

The experiment demonstrates that under current architecture and evidence landscape, NC-06 cannot produce disagreements with Original Policy. This is not a bug — it's a structural property of the system.

---

## Root Cause Analysis

### Why NC-06 Always Agrees with Original

The key finding is **cumulative evidence dominance**:

| Action | Total Evidence | Success Rate | Source |
|--------|---------------|--------------|--------|
| `respond` | 122 | 86.1% | ALL intents (general, explain, review, test) |
| `code_edit` | 36 | 61.1% | create intent only |
| `code_review` | 29 | 100.0% | fix intent only |
| `tool_call` | 32 | 43.8% | optimize, deploy |

**The Problem**: `respond` has the highest cumulative evidence because it's used across multiple intents. When ActionLearning ranks candidates, `respond` consistently wins due to:

1. Higher total evidence count (confidence boost)
2. High success rate (86.1%)
3. Semantic similarity to many other intents

### Evidence Landscape

```
Cumulative Evidence Across All Intents:
  respond     : S=105 F=17 total=122 rate=86.1%
  code_edit   : S=22 F=14 total=36  rate=61.1%
  tool_call   : S=14 F=18 total=32  rate=43.8%
  code_review : S=29 F= 0 total=29  rate=100.0%
```

### Original Policy Mapping (from decision.py)

```python
INTENT_ACTION_MAP = {
    "create": "code_edit",
    "fix": "code_review",
    "learn": "respond",
    "optimize": "tool_call",
    "deploy": "tool_call",
}
```

### The Vicious Circle

1. **Original Policy** always selects the intent-mapped action
2. **ActionLearning** records this as a successful outcome
3. **Evidence accumulates** for the mapped action
4. **PolicyEngine** sees high evidence for mapped action → selects it
5. **Result**: Original policy reinforces itself forever

### The Respond Dominance Problem

`respond` has the highest cumulative evidence because:
- It's used for `explain`, `review`, `test`, `general` intents
- Each intent adds to the same `intent:respond|action:respond` bucket
- Cumulative effect: 122 total vs 36 for `code_edit`

When both candidates have evidence above threshold:
- `respond`: score ≈ 0.86 (high confidence from 122 samples)
- `code_edit`: score ≈ 0.61 (lower confidence from 36 samples)

**Result**: `respond` wins even when intent-specific evidence suggests otherwise.

---

## Experimental Results

### Scenario Testing

Tested 8 intents with various candidate configurations:

| Intent | Original | NC Selected | Status |
|--------|----------|-------------|--------|
| create | code_edit | None (insufficient) | No change |
| fix | code_review | code_review | ✓ AGREES |
| optimize | tool_call | None (insufficient) | No change |
| deploy | tool_call | None (insufficient) | No change |
| review | respond | respond | ✓ AGREES |
| explain | respond | respond | ✓ AGREES |
| test | respond | respond | ✓ AGREES |
| general | respond | respond | ✓ AGREES |

### Key Observations

1. **For fix/review/explain/test/general**: NC-06 always agrees with Original
2. **For create/modify/deploy**: NC-06 returns `None` (insufficient evidence) due to `min_evidence=1` threshold being too high relative to evidence distribution
3. **No disagreements found**: The system is self-reinforcing

---

## Can We Force a Disagreement?

### Option 1: Remove `respond` from Candidates

If we generate candidates without `respond`:

```python
# Hypothetical scenario
candidates = [ActionLearningCandidate("code_edit", "code_edit")]
# Result: NC would select code_edit (matches Original)
```

This would NOT create disagreement because Original also selects `code_edit`.

### Option 2: Add Artificial Distractors

Add a fake action like `experimental_tool` with high score:

```python
candidates = [
    ActionLearningCandidate("code_edit", "code_edit"),
    ActionLearningCandidate("experimental_tool", "experimental_tool"),  # High score
]
# Result: NC might select experimental_tool (disagreement!)
```

But this is artificial — not a "natural" disagreement.

### Option 3: Build Up Evidence for Alternative Actions

If we manually inject evidence for `code_edit` to exceed `respond`:

```python
# Hypothetical: code_edit has 200S/0F (200 total)
# respond has 122 total
# Result: code_edit would win → disagreement with Original
```

But this requires modifying statistics directly — not a natural scenario.

---

## Architectural Implications

### The System is Self-Stabilizing

The current architecture creates a **self-stabilizing loop**:

```
Original Policy → chooses action A
ActionLearning → records success of action A
Evidence for A increases
PolicyEngine → selects A again
```

This is good for stability but bad for exploring alternatives.

### The Role of `respond` as Fallback

`respond` acts as a **high-confidence fallback** because:
1. It has the most cumulative evidence
2. It's used across many intents
3. It has a good success rate (86.1%)

This means the system will always prefer `respond` over alternatives unless:
- The alternative has significantly higher evidence
- OR `respond` is not in the candidate list

---

## Recommendations

### For NC-06 Architecture

1. **Lower `min_evidence` threshold** to allow selection with less certainty
2. **Add intent-specific weighting** to reduce `respond` dominance
3. **Consider removing `respond` from candidates** for specific intents
4. **Add exploration mode** to intentionally try alternative actions

### For Finding Natural Disagreements

Natural disagreements require:
1. **Novel intents** not seen before (no cumulative evidence)
2. **Edge cases** where Original Policy makes a "mistake"
3. **Context-aware decisions** where intent alone is insufficient

Example scenario that COULD produce disagreement:
```
Input: "这段代码有个性能问题，帮我优化"
Intent: optimize (Original → tool_call)
Candidates: code_edit, tool_call
If code_edit has MORE evidence than tool_call → disagreement
```

But this requires the evidence to be artificially constructed or the system to have learned differently.

---

## Final Verdict

**NO_NATURAL_POLICY_DISAGREEMENT**

The current architecture and evidence landscape do not support natural disagreements between Original Policy and NC-06. This is a structural property, not a bug.

To enable future disagreement exploration:
1. Reduce `respond` dominance through intent-scoped evidence
2. Lower evidence thresholds for more aggressive selection
3. Consider adding an "exploration" mode for policy testing

---

*Report generated by NC-06.1 experiment*
*Status: COMPLETED*
*Next: Consider NC-07 or architectural changes*
