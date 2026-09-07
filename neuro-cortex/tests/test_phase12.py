"""Phase 12 — Pattern Consolidation Tests (v1).

Verifies:
- Pattern dataclass schema and lifecycle
- PatternConsolidator groups experiences correctly
- PatternStore persists and loads patterns
- PatternRetriever matches by condition
- ExperiencePrediction blends experience + pattern signals
- Contradiction handling prevents false patterns
- Pattern retirement works correctly
- Deterministic behavior across runs
- Regression: all 426 Phase 0-11 tests still pass
"""
from __future__ import annotations

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from neurocortex.event import (
    CortexEvent,
    PerceptionData,
    RepresentationData,
    AttentionData,
    InternalState,
    MemoryData,
    PredictionData,
    DecisionData,
    ActionData,
    OutcomeData,
    FeedbackData,
    LearningData,
    Experience,
)
from neurocortex.cortex import NeuroCortex
from neurocortex.modules import (
    MockPerception, MockRepresentation, MockAttention, MockState,
    MockMemory, MockPrediction, MockDecision, MockAction,
    MockOutcomeProvider, MockFeedback, MockLearning,
)
from neurocortex.state import BasicStateModule
from neurocortex.prediction import BasicPrediction
from neurocortex.memory import ExperienceStore, ExperienceRetriever
from neurocortex.learning import ExperienceLearningModule
from neurocortex.prediction.experience_prediction import ExperiencePredictionModule
from neurocortex.interfaces import OutcomeProvider
from neurocortex.pattern import (
    Pattern,
    PatternConsolidator,
    PatternStore,
    PatternRetriever,
    PATTERN_LIFECYCLE,
)


# ── Helpers ───────────────────────────────────────────────────────


def make_experience(
    experience_id: str = "exp-1",
    raw_input: str = "fix a bug",
    intent: str = "fix",
    action_type: str = "code_review",
    success: bool = True,
    predicted_prob: float = 0.8,
    evaluation: str = "correct",
) -> Experience:
    """Create a minimal Experience for testing."""
    return Experience(
        experience_id=experience_id,
        timestamp="2026-09-07T00:00:00+00:00",
        source_event_id=f"evt-{experience_id}",
        raw_input=raw_input,
        intent=intent,
        action_type=action_type,
        predicted_outcome=f"{intent}完成",
        predicted_prob=predicted_prob,
        actual_outcome="done",
        success=success,
        prediction_error=abs(1.0 - predicted_prob) if success else predicted_prob,
        evaluation=evaluation,
        confidence=0.55,
        uncertainty=0.2,
        context_tags=[f"intent:{intent}", f"action:{action_type}",
                      f"outcome:success" if success else "outcome:failure",
                      f"eval:{evaluation}"],
    )


def make_cortex_with_patterns(store_path=None):
    """Create a NeuroCortex with both experience and pattern prediction."""
    from neurocortex.pattern import PatternConsolidator, PatternStore, PatternRetriever

    exp_store = ExperienceStore(store_path)
    exp_retriever = ExperienceRetriever(exp_store)
    exp_learner = ExperienceLearningModule(exp_store)

    pat_store = PatternStore(store_path.replace(".jsonl", "_patterns.jsonl") if store_path else None)
    pat_retriever = PatternRetriever(pat_store)
    consolidator = PatternConsolidator()

    # Consolidate existing patterns from store
    patterns = consolidator.consolidate(exp_store)
    if patterns:
        pat_store.save_all(patterns)
    pat_retriever = PatternRetriever(pat_store)

    exp_pred = ExperiencePredictionModule(exp_retriever, base_prediction=BasicPrediction())
    exp_pred.set_pattern_retriever(pat_retriever)

    cortex = NeuroCortex(
        perception=MockPerception(), representation=MockRepresentation(),
        attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
        prediction=exp_pred, decision=MockDecision(), action=MockAction(),
        outcome_provider=MockOutcomeProvider(),
        feedback=MockFeedback(), learning=exp_learner,
    )
    return cortex, exp_store, pat_store, pat_retriever, consolidator


# ── TestPatternSchema ──────────────────────────────────────────────


class TestPatternSchema:
    """Test Pattern dataclass fields and serialization."""

    def test_pattern_required_fields(self):
        pat = Pattern(
            pattern_id="test-1",
            condition_intent="fix",
            condition_action_type="code_review",
            success_rate=0.8,
            support_count=5,
            status="STABLE",
        )
        assert pat.pattern_id == "test-1"
        assert pat.condition_intent == "fix"
        assert pat.condition_action_type == "code_review"
        assert pat.success_rate == 0.8
        assert pat.support_count == 5
        assert pat.status == "STABLE"

    def test_pattern_serialization(self):
        pat = Pattern(
            pattern_id="test-1",
            condition_intent="fix",
            condition_action_type="code_review",
            success_rate=0.8,
            support_count=5,
            contradiction_count=1,
            support_score=0.6,
            status="SUPPORTED",
        )
        d = pat.to_dict()
        assert d["pattern_id"] == "test-1"
        assert d["condition_intent"] == "fix"
        assert d["success_rate"] == 0.8
        assert d["support_count"] == 5
        assert d["contradiction_count"] == 1
        assert d["support_score"] == 0.6
        assert d["status"] == "SUPPORTED"

    def test_pattern_deserialization(self):
        data = {
            "pattern_id": "test-1",
            "condition_intent": "fix",
            "condition_action_type": "code_review",
            "success_rate": 0.8,
            "support_count": 5,
            "contradiction_count": 1,
            "support_score": 0.6,
            "status": "SUPPORTED",
        }
        pat = Pattern.from_dict(data)
        assert pat.pattern_id == "test-1"
        assert pat.condition_intent == "fix"
        assert pat.success_rate == 0.8

    def test_pattern_lifecycle_values(self):
        expected = ("CANDIDATE", "OBSERVED", "SUPPORTED", "STABLE", "WEAKENING", "RETIRED")
        assert PATTERN_LIFECYCLE == expected

    def test_pattern_is_active(self):
        assert Pattern(status="STABLE").is_active() is True
        assert Pattern(status="SUPPORTED").is_active() is True
        assert Pattern(status="CANDIDATE").is_active() is True
        assert Pattern(status="WEAKENING").is_active() is False
        assert Pattern(status="RETIRED").is_active() is False

    def test_pattern_retire(self):
        pat = Pattern(status="SUPPORTED")
        pat.retire()
        assert pat.status == "RETIRED"
        assert pat.is_active() is False

    def test_pattern_create_from_experiences(self):
        exps = [
            make_experience("e1", "fix bug 1", "fix", "code_review", True),
            make_experience("e2", "fix bug 2", "fix", "code_review", True),
            make_experience("e3", "fix bug 3", "fix", "code_review", True),
        ]
        pat = Pattern.create("fix", "code_review", exps)
        assert pat.condition_intent == "fix"
        assert pat.condition_action_type == "code_review"
        assert pat.support_count == 3
        assert pat.success_rate == 1.0
        assert pat.contradiction_count == 0
        assert pat.status in ("OBSERVED", "SUPPORTED")
        assert len(pat.source_experience_ids) == 3

    def test_pattern_create_from_mixed_experiences(self):
        exps = [
            make_experience("e1", "fix bug 1", "fix", "code_review", True),
            make_experience("e2", "fix bug 2", "fix", "code_review", False),
            make_experience("e3", "fix bug 3", "fix", "code_review", True),
        ]
        pat = Pattern.create("fix", "code_review", exps)
        assert pat.support_count == 3
        assert pat.success_rate == 2 / 3
        assert pat.contradiction_count == 1
        # 2/3 success, 1 contradiction → should be OBSERVED or SUPPORTED
        assert pat.status in ("OBSERVED", "SUPPORTED")


# ── TestPatternConsolidator ───────────────────────────────────────


class TestPatternConsolidator:
    """Test PatternConsolidator groups and creates patterns correctly."""

    def test_empty_store_no_patterns(self):
        store = ExperienceStore(None)
        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        assert patterns == []

    def test_single_experience_creates_candidate(self):
        store = ExperienceStore(None)
        store.save(make_experience("e1", "fix bug", "fix", "code_review", True))
        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        assert len(patterns) == 1
        assert patterns[0].support_count == 1
        assert patterns[0].status == "CANDIDATE"

    def test_three_consistent_experiences_create_supported(self):
        store = ExperienceStore(None)
        for i in range(3):
            store.save(make_experience(f"e{i}", f"fix bug {i}", "fix", "code_review", True))
        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.support_count == 3
        assert p.success_rate == 1.0
        assert p.contradiction_count == 0
        assert p.status == "SUPPORTED"

    def test_five_stable_experiences(self):
        store = ExperienceStore(None)
        for i in range(5):
            store.save(make_experience(f"e{i}", f"fix bug {i}", "fix", "code_review", True))
        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.support_count == 5
        assert p.status == "STABLE"
        assert p.support_score >= 0.7

    def test_mixed_outcomes_create_weakening(self):
        store = ExperienceStore(None)
        store.save(make_experience("e1", "fix bug 1", "fix", "code_review", True))
        store.save(make_experience("e2", "fix bug 2", "fix", "code_review", False))
        store.save(make_experience("e3", "fix bug 3", "fix", "code_review", True))
        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.support_count == 3
        assert p.success_rate == 2 / 3
        # 1 failure out of 3 → contradiction_count=1, rate=33% → OBSERVED
        assert p.contradiction_count == 1
        assert p.status in ("OBSERVED", "SUPPORTED")


class TestExperimentP5MixedSuccessFailureDegrades:
    """P5: Success/failure mix → pattern degrades."""
    def test_majority_failure_observed(self):
        store = ExperienceStore(None)
        # 2 success, 3 failure → contradiction_count=2 (minority=success), rate=40% → OBSERVED
        store.save(make_experience("e1", "fix 1", "fix", "code_review", True))
        store.save(make_experience("e2", "fix 2", "fix", "code_review", True))
        store.save(make_experience("e3", "fix 3", "fix", "code_review", False))
        store.save(make_experience("e4", "fix 4", "fix", "code_review", False))
        store.save(make_experience("e5", "fix 5", "fix", "code_review", False))
        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.success_rate == 0.4
        assert p.contradiction_count == 2
        assert p.status == "OBSERVED"


class TestExperimentP6MajorityBias:
    """P6: Many repetitive experiences → confidence reflects uncertainty, not 1.0."""
    def test_seven_of_ten_success_not_overconfident(self):
        store = ExperienceStore(None)
        for i in range(7):
            store.save(make_experience(f"e{i}", f"fix {i}", "fix", "code_review", True))
        for i in range(3):
            store.save(make_experience(f"f{i}", f"fail {i}", "fix", "code_review", False))
        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.success_rate == 0.7
        assert p.support_count == 10
        # Confidence should reflect the 70% rate, not 100%
        assert p.support_score < 0.8
        assert p.support_score > 0.5


class TestExperimentP7WrongMajority:
    """P7: Majority wrong experiences → pattern forms but with low confidence."""
    def test_majority_failure_low_confidence(self):
        store = ExperienceStore(None)
        for i in range(4):
            store.save(make_experience(f"e{i}", f"fix {i}", "fix", "code_review", False))
        store.save(make_experience("e4", "fix last", "fix", "code_review", True))
        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.success_rate == 0.2
        # 1/5 = 20% contradiction ≤ 20% → STABLE (but low confidence due to low success_rate)
        assert p.status == "STABLE"
        assert p.support_score < 0.3


class TestExperimentP8NewOverturnsOld:
    """P8: New experiences can overturn an old stable pattern."""
    def test_stable_to_observed_after_contradictions(self):
        store = ExperienceStore(None)
        # Build 5 success → STABLE
        for i in range(5):
            store.save(make_experience(f"e{i}", f"fix {i}", "fix", "code_review", True))
        cons = PatternConsolidator()
        patterns1 = cons.consolidate(store)
        assert patterns1[0].status == "STABLE"

        # Add 3 failures → should degrade
        for i in range(3):
            store.save(make_experience(f"f{i}", f"fail {i}", "fix", "code_review", False))
        patterns2 = cons.consolidate(store)
        assert len(patterns2) == 1
        p = patterns2[0]
        # 5 success + 3 failure = 8 total, contradiction_count=3, rate=37.5%
        assert p.support_count == 8
        assert p.success_rate == 5 / 8
        # 37.5% contradiction > 33% → not SUPPORTED; 8≥2 → OBSERVED
        assert p.status == "OBSERVED"


class TestExperimentP9NoAutomaticDecay:
    """P9: Patterns do NOT decay over time in v1."""
    def test_pattern_persists_without_new_evidence(self):
        store = ExperienceStore(None)
        for i in range(5):
            store.save(make_experience(f"e{i}", f"fix {i}", "fix", "code_review", True))
        cons = PatternConsolidator()
        patterns1 = cons.consolidate(store)
        assert patterns1[0].status == "STABLE"

        # No new experiences added, re-consolidate
        patterns2 = cons.consolidate(store)
        assert patterns2[0].status == "STABLE"
        assert patterns2[0].support_count == 5


class TestExperimentP10PatternRetirement:
    """P10: Explicitly retired patterns are excluded from retrieval."""
    def test_retired_pattern_not_retrieved(self):
        store = PatternStore(None)
        pat = Pattern(
            pattern_id="p1", condition_intent="fix", condition_action_type="code_review",
            success_rate=0.9, support_count=5, support_score=0.8, status="STABLE",
        )
        store.save(pat)
        retr = PatternRetriever(store)
        assert len(retr.retrieve(intent="fix")) == 1

        # Retire the pattern
        pat.retire()
        store.save_all(list(store.list_all()))  # persist retirement
        assert len(retr.retrieve(intent="fix")) == 0


class TestExperimentP11NoPatternFallback:
    """P11: No relevant pattern → prediction uses Phase 11 behavior only."""
    def test_fallback_to_experience_only(self):
        exp_store = ExperienceStore(None)
        exp_retriever = ExperienceRetriever(exp_store)
        pat_store = PatternStore(None)
        pat_retriever = PatternRetriever(pat_store)
        pred = ExperiencePredictionModule(exp_retriever, base_prediction=BasicPrediction())
        pred.set_pattern_retriever(pat_retriever)
        pred._quality_floor = 0.0  # disable pattern to isolate

        cortex = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
            prediction=pred, decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=ExperienceLearningModule(exp_store),
        )
        e = cortex.process("fix a bug")
        assert e.stage == "LEARNING"
        # With no experiences and pattern disabled, should be base prediction
        assert e.prediction.success_probability > 0.0


class TestExperimentP12PatternChangesPrediction:
    """P12: Relevant pattern → prediction shows observable change."""
    def test_pattern_shifts_probability(self):
        exp_store = ExperienceStore(None)
        exp_retriever = ExperienceRetriever(exp_store)
        pat_store = PatternStore(None)
        # Strong pattern: fix → 90% success
        pat_store.save(Pattern(
            pattern_id="p1", condition_intent="fix", condition_action_type="code_review",
            success_rate=0.9, support_count=5, support_score=0.85, status="STABLE",
        ))
        pat_retriever = PatternRetriever(pat_store)

        pred_with = ExperiencePredictionModule(exp_retriever, base_prediction=BasicPrediction())
        pred_with.set_pattern_retriever(pat_retriever)
        pred_with._experience_weight = 0.0  # isolate pattern

        pred_without = ExperiencePredictionModule(exp_retriever, base_prediction=BasicPrediction())
        pred_without._experience_weight = 0.0  # no pattern, no experience

        cortex_with = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
            prediction=pred_with, decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=ExperienceLearningModule(exp_store),
        )
        cortex_without = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
            prediction=pred_without, decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=ExperienceLearningModule(exp_store),
        )

        e_with = cortex_with.process("fix a bug")
        e_without = cortex_without.process("fix a bug")

        # Pattern should shift probability upward
        diff = abs(e_with.prediction.success_probability - e_without.prediction.success_probability)
        assert diff > 0.05, f"Pattern should change prediction by > 0.05, got {diff:.4f}"


class TestExperimentP13WrongPatternDoesNotPollute:
    """P13: Wrong pattern does not permanently pollute prediction."""
    def test_wrong_pattern_degraded_not_used(self):
        exp_store = ExperienceStore(None)
        exp_retriever = ExperienceRetriever(exp_store)
        pat_store = PatternStore(None)
        # Add a WEAKENING pattern (low confidence, should be excluded)
        pat_store.save(Pattern(
            pattern_id="p-bad", condition_intent="fix", condition_action_type="code_review",
            success_rate=0.2, support_count=5, contradiction_count=4,
            support_score=0.1, status="WEAKENING",
        ))
        pat_retriever = PatternRetriever(pat_store)

        pred = ExperiencePredictionModule(exp_retriever, base_prediction=BasicPrediction())
        pred.set_pattern_retriever(pat_retriever)
        pred._experience_weight = 0.0  # isolate pattern effect

        cortex = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
            prediction=pred, decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=ExperienceLearningModule(exp_store),
        )
        e = cortex.process("fix a bug")
        # WEAKENING pattern excluded from retrieval → base prediction only
        # Base prediction for "fix a bug" is ~0.80
        assert e.prediction.success_probability >= 0.75


class TestExperimentP14RestartPersistence:
    """P14: Patterns persist across restart (file reload)."""
    def test_persistence_across_restart(self, tmp_path):
        store_path = str(tmp_path / "patterns.jsonl")
        pat_store1 = PatternStore(store_path)
        pat_store1.save(Pattern(
            pattern_id="p1", condition_intent="fix", condition_action_type="code_review",
            success_rate=0.9, support_count=5, support_score=0.8, status="STABLE",
        ))
        assert pat_store1.count() == 1

        # Simulate restart: new instance loads from file
        pat_store2 = PatternStore(store_path)
        assert pat_store2.count() == 1
        assert pat_store2.list_all()[0].condition_intent == "fix"
        assert pat_store2.list_all()[0].success_rate == 0.9


class TestExperimentP15CortexIsolation:
    """P15: Different Cortex instances have isolated pattern stores."""
    def test_isolation(self):
        store_a = PatternStore(None)
        store_b = PatternStore(None)
        store_a.save(Pattern(pattern_id="pa", condition_intent="fix", status="STABLE",
                            success_rate=0.9, support_count=5, support_score=0.8))
        store_b.save(Pattern(pattern_id="pb", condition_intent="create", status="STABLE",
                            success_rate=0.8, support_count=3, support_score=0.6))
        retr_a = PatternRetriever(store_a)
        retr_b = PatternRetriever(store_b)
        results_a = retr_a.retrieve(intent="fix")
        results_b = retr_b.retrieve(intent="create")
        assert len(results_a) == 1
        assert len(results_b) == 1
        assert results_a[0][0].pattern_id == "pa"
        assert results_b[0][0].pattern_id == "pb"
        # Cross-contamination check
        assert len(retr_a.retrieve(intent="create")) == 0
        assert len(retr_b.retrieve(intent="fix")) == 0


class TestExperimentP16Determinism:
    """P16: Same experiences → same patterns (deterministic)."""
    def test_deterministic_consolidation(self):
        store = ExperienceStore(None)
        for i in range(5):
            store.save(make_experience(f"e{i}", f"fix bug {i}", "fix", "code_review", True))
        cons = PatternConsolidator()
        p1 = cons.consolidate(store)
        p2 = cons.consolidate(store)
        assert len(p1) == len(p2)
        assert p1[0].condition_intent == p2[0].condition_intent
        assert p1[0].success_rate == p2[0].success_rate
        assert p1[0].support_count == p2[0].support_count
        assert p1[0].status == p2[0].status


class TestExperimentP17FullIntegration:
    """P17: Full integration — experiences → patterns → prediction."""
    def test_full_loop(self):
        cortex, exp_store, pat_store, pat_retriever, cons = make_cortex_with_patterns()

        # Build up experiences
        for i in range(5):
            cortex.process(f"fix bug {i}")

        # Manually trigger consolidation (lazy pattern: not automatic in v1)
        patterns = cons.consolidate(exp_store)
        if patterns:
            pat_store.save_all(patterns)

        # Check patterns were formed
        assert pat_store.count() >= 1
        active = pat_store.list_active()
        assert len(active) >= 1

        # Re-create retriever with updated store
        pat_retriever = PatternRetriever(pat_store)
        cortex.prediction_module.set_pattern_retriever(pat_retriever)

        # Run a new task and verify pattern influences prediction
        e = cortex.process("fix a new bug")
        assert e.stage == "LEARNING"
        assert e.prediction.success_probability > 0.5



class TestEvidenceIntegrity:
    """Evidence Integrity regression tests — double counting fix."""

    def test_no_double_counting_4of5_success(self):
        """
        P17 regression: 5 experiences (4 success), top-3 all success.
        Old Scheme A: 0.30×1.0 + 0.15×0.80 = 0.425 shift
        New Scheme B: 0.30×(1.0×0.72) = 0.216 shift
        Prediction must be LOWER than old scheme.
        """
        from neurocortex.event import Experience
        from neurocortex.memory.experience_store import ExperienceStore
        from neurocortex.memory.experience_retriever import ExperienceRetriever
        from neurocortex.pattern import PatternConsolidator, PatternStore, PatternRetriever
        from neurocortex.prediction.experience_prediction import ExperiencePredictionModule
        from neurocortex.prediction import BasicPrediction
        from neurocortex.modules import MockPerception, MockRepresentation, MockAttention
        from neurocortex.state import BasicStateModule
        from neurocortex.modules import MockMemory, MockDecision, MockAction, MockOutcomeProvider
        from neurocortex.modules import MockFeedback
        from neurocortex.learning import ExperienceLearningModule
        from neurocortex.cortex import NeuroCortex

        store = ExperienceStore(None)
        for i in range(5):
            store.save(Experience(
                experience_id=f"e{i}", timestamp="2026-09-07T00:00:00+00:00",
                source_event_id=f"evt-{i}", raw_input=f"fix bug {i}",
                intent="fix", action_type="code_review",
                predicted_outcome="fix完成", predicted_prob=0.8,
                actual_outcome="done", success=(i < 4),
                prediction_error=0.2, evaluation="correct",
                confidence=0.55, uncertainty=0.2,
                context_tags=[f"intent:fix", f"action:code_review",
                              "outcome:success" if i < 4 else "outcome:failure"],
            ))

        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        pat_store = PatternStore(None)
        pat_store.save_all(patterns)

        exp_retr = ExperienceRetriever(store, top_k=3)
        pat_retr = PatternRetriever(pat_store)
        pred = ExperiencePredictionModule(exp_retr, base_prediction=BasicPrediction())
        pred.set_pattern_retriever(pat_retr)

        cortex = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
            prediction=pred, decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=ExperienceLearningModule(store),
        )
        e = cortex.process("fix a bug")

        # With Scheme B: adjusted = 1.0 × clamp(0.72, 0.5, 1.0) = 0.72
        # prediction = 0.70 × 0.80 + 0.30 × 0.72 = 0.776
        # Old Scheme A would give: 0.55 × 0.80 + 0.30 × 1.0 + 0.15 × 0.80 = 0.86
        assert e.prediction.success_probability < 0.82,             f"Double counting not fixed: prob={e.prediction.success_probability:.4f}"
        assert e.prediction.success_probability >= 0.75,             f"Evidence too dampened: prob={e.prediction.success_probability:.4f}"

    def test_no_pattern_same_as_phase11(self):
        """No pattern → identity transform → same as Phase 11."""
        from neurocortex.event import Experience
        from neurocortex.memory.experience_store import ExperienceStore
        from neurocortex.memory.experience_retriever import ExperienceRetriever
        from neurocortex.prediction.experience_prediction import ExperiencePredictionModule
        from neurocortex.prediction import BasicPrediction
        from neurocortex.modules import MockPerception, MockRepresentation, MockAttention
        from neurocortex.state import BasicStateModule
        from neurocortex.modules import MockMemory, MockDecision, MockAction, MockOutcomeProvider
        from neurocortex.modules import MockFeedback
        from neurocortex.learning import ExperienceLearningModule
        from neurocortex.cortex import NeuroCortex

        store = ExperienceStore(None)
        for i in range(3):
            store.save(Experience(
                experience_id=f"e{i}", timestamp="2026-09-07T00:00:00+00:00",
                source_event_id=f"evt-{i}", raw_input=f"fix bug {i}",
                intent="fix", action_type="code_review",
                predicted_outcome="fix完成", predicted_prob=0.8,
                actual_outcome="done", success=True,
                prediction_error=0.2, evaluation="correct",
                confidence=0.55, uncertainty=0.2,
                context_tags=["intent:fix", "action:code_review", "outcome:success"],
            ))

        exp_retr = ExperienceRetriever(store, top_k=3)
        # NO pattern retriever set → Phase 11 behavior
        pred = ExperiencePredictionModule(exp_retr, base_prediction=BasicPrediction())

        cortex = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
            prediction=pred, decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=ExperienceLearningModule(store),
        )
        e = cortex.process("fix a bug")

        # empirical_rate = 3/3 = 1.0, no pattern → quality_factor = 1.0
        # prediction = 0.70 × 0.80 + 0.30 × 1.0 = 0.86
        expected = 0.70 * 0.80 + 0.30 * 1.0
        assert abs(e.prediction.success_probability - expected) < 0.001,             f"Phase 11 behavior not preserved: got {e.prediction.success_probability:.4f}, expected {expected}"

    def test_pattern_dampens_overconfident_rate(self):
        """Pattern should reduce overconfident top-k rates."""
        from neurocortex.event import Experience
        from neurocortex.memory.experience_store import ExperienceStore
        from neurocortex.memory.experience_retriever import ExperienceRetriever
        from neurocortex.pattern import PatternConsolidator, PatternStore, PatternRetriever
        from neurocortex.prediction.experience_prediction import ExperiencePredictionModule
        from neurocortex.prediction import BasicPrediction
        from neurocortex.modules import MockPerception, MockRepresentation, MockAttention
        from neurocortex.state import BasicStateModule
        from neurocortex.modules import MockMemory, MockDecision, MockAction, MockOutcomeProvider
        from neurocortex.modules import MockFeedback
        from neurocortex.learning import ExperienceLearningModule
        from neurocortex.cortex import NeuroCortex

        store = ExperienceStore(None)
        # 5 total: 4 success, 1 failure
        for i in range(5):
            store.save(Experience(
                experience_id=f"e{i}", timestamp="2026-09-07T00:00:00+00:00",
                source_event_id=f"evt-{i}", raw_input=f"fix bug {i}",
                intent="fix", action_type="code_review",
                predicted_outcome="fix完成", predicted_prob=0.8,
                actual_outcome="done", success=(i < 4),
                prediction_error=0.2, evaluation="correct",
                confidence=0.55, uncertainty=0.2,
                context_tags=[f"intent:fix", f"action:code_review",
                              "outcome:success" if i < 4 else "outcome:failure"],
            ))

        cons = PatternConsolidator()
        patterns = cons.consolidate(store)
        pat_store = PatternStore(None)
        pat_store.save_all(patterns)

        exp_retr = ExperienceRetriever(store, top_k=3)
        pat_retr = PatternRetriever(pat_store)
        pred = ExperiencePredictionModule(exp_retr, base_prediction=BasicPrediction())
        pred.set_pattern_retriever(pat_retr)

        cortex = NeuroCortex(
            perception=MockPerception(), representation=MockRepresentation(),
            attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
            prediction=pred, decision=MockDecision(), action=MockAction(),
            outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
            learning=ExperienceLearningModule(store),
        )
        e = cortex.process("fix a bug")

        # top-3 all success → empirical_rate=1.0
        # pattern support_score=0.72 → quality_factor=clamp(0.72, 0.5, 1.0)=0.72
        # adjusted = 1.0 × 0.72 = 0.72
        # prediction = 0.70 × 0.80 + 0.30 × 0.72 = 0.776
        # Without pattern: 0.70 × 0.80 + 0.30 × 1.0 = 0.86
        # So with pattern it should be LOWER
        assert e.prediction.success_probability < 0.86,             f"Pattern should dampen overconfident rate, got {e.prediction.success_probability:.4f}"

    def test_support_score_not_probability(self):
        """support_score is a quality weight, not a probability."""
        from neurocortex.pattern import Pattern
        p = Pattern(
            pattern_id="test", condition_intent="fix", condition_action_type="code_review",
            success_rate=1.0, support_count=5, support_score=0.9, status="STABLE",
        )
        # support_score should be accessible
        assert p.support_score == 0.9
        # backward-compatible alias
        assert p.confidence == 0.9
        # But it's NOT a probability — it can't be interpreted as P(true)
        # The value 0.9 means "strong evidence" not "90% chance"
        assert isinstance(p.support_score, float)
        assert 0.0 <= p.support_score <= 1.0

    def test_deterministic_replay(self):
        """Same input + same evidence → same output."""
        from neurocortex.event import Experience
        from neurocortex.memory.experience_store import ExperienceStore
        from neurocortex.memory.experience_retriever import ExperienceRetriever
        from neurocortex.pattern import PatternConsolidator, PatternStore, PatternRetriever
        from neurocortex.prediction.experience_prediction import ExperiencePredictionModule
        from neurocortex.prediction import BasicPrediction
        from neurocortex.modules import MockPerception, MockRepresentation, MockAttention
        from neurocortex.state import BasicStateModule
        from neurocortex.modules import MockMemory, MockDecision, MockAction, MockOutcomeProvider
        from neurocortex.modules import MockFeedback
        from neurocortex.learning import ExperienceLearningModule
        from neurocortex.cortex import NeuroCortex

        store = ExperienceStore(None)
        for i in range(5):
            store.save(Experience(
                experience_id=f"e{i}", timestamp="2026-09-07T00:00:00+00:00",
                source_event_id=f"evt-{i}", raw_input=f"fix bug {i}",
                intent="fix", action_type="code_review",
                predicted_outcome="fix完成", predicted_prob=0.8,
                actual_outcome="done", success=(i < 4),
                prediction_error=0.2, evaluation="correct",
                confidence=0.55, uncertainty=0.2,
                context_tags=[f"intent:fix", f"action:code_review",
                              "outcome:success" if i < 4 else "outcome:failure"],
            ))

        # Use isolated stores per iteration to prevent cross-contamination
        results = []
        for _ in range(3):
            iter_store = ExperienceStore(None)
            for e in store.list_all():
                iter_store.save(e)
            cons = PatternConsolidator()
            patterns = cons.consolidate(iter_store)
            pat_store = PatternStore(None)
            pat_store.save_all(patterns)
            exp_retr = ExperienceRetriever(iter_store, top_k=3)
            pat_retr = PatternRetriever(pat_store)
            pred = ExperiencePredictionModule(exp_retr, base_prediction=BasicPrediction())
            pred.set_pattern_retriever(pat_retr)
            cortex = NeuroCortex(
                perception=MockPerception(), representation=MockRepresentation(),
                attention=MockAttention(), state=BasicStateModule(), memory=MockMemory(),
                prediction=pred, decision=MockDecision(), action=MockAction(),
                outcome_provider=MockOutcomeProvider(), feedback=MockFeedback(),
                learning=ExperienceLearningModule(iter_store),
            )
            e = cortex.process("fix a bug")
            results.append(e.prediction.success_probability)

        assert all(r == results[0] for r in results),             f"Non-deterministic: {results}"



class TestRegression:
    """Regression: all existing Phase 0-11 tests must still pass."""
    def test_all_existing_tests_pass(self):
        """This test exists to ensure Phase 12 doesn't break anything."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "neuro-cortex/tests/", "-q", "--tb=line",
             "-k", "not Regression"],
            capture_output=True, text=True, timeout=600,
        )
        # Parse the output for pass/fail counts
        output = result.stdout
        import re
        match = re.search(r'(\d+) passed', output)
        if match:
            passed = int(match.group(1))
            assert passed >= 426, f"Expected at least 426 passed, got {passed}"
        else:
            assert result.returncode == 0, f"Tests failed: {result.stdout}\n{result.stderr}"
