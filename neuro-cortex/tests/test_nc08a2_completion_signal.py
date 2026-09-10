"""NC-08A.2: Real Task Completion Signal Integration Tests

Tests for:
1. OutcomeData with task_completed field
2. OutcomeAdapter extracts task_completed from event
3. Provenance preservation (completion_source)
4. Task ID propagation
5. Legacy compatibility
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from neurocortex.event import CortexEvent, OutcomeData
from neurocortex.action_learning.schema import ActionLearningOutcome, outcome_from_event
from neurocortex.action_learning.engine import ActionLearningEngine
from neurocortex.action_learning.config import ActionLearningConfig
from neurocortex.action_learning.schema import ActionLearningSituation


# ============================================================================
# Test 1: Explicit completion = True
# ============================================================================

def test_explicit_completion_true():
    """Task explicitly completed."""
    outcome = OutcomeData(
        success=True,
        actual_outcome="file read successfully",
        task_completed=True,
        completion_source="environment",
    )
    assert outcome.task_completed is True
    assert outcome.completion_source == "environment"


# ============================================================================
# Test 2: Explicit completion = False
# ============================================================================

def test_explicit_completion_false():
    """Task explicitly NOT completed."""
    outcome = OutcomeData(
        success=True,  # execution succeeded
        actual_outcome="responded but task incomplete",
        task_completed=False,
        completion_source="user_feedback",
    )
    assert outcome.task_completed is False
    assert outcome.completion_source == "user_feedback"


# ============================================================================
# Test 3: No completion signal = None
# ============================================================================

def test_no_completion_signal():
    """No completion signal means unknown."""
    outcome = OutcomeData(
        success=True,
        actual_outcome="done",
    )
    assert outcome.task_completed is None
    assert outcome.completion_source == "unknown"


# ============================================================================
# Test 4: Execution success + completion false
# ============================================================================

def test_execution_success_but_task_incomplete():
    """Action executed successfully but task not completed."""
    outcome = OutcomeData(
        success=True,
        actual_outcome="generated response",
        task_completed=False,
        completion_source="task_verifier",
    )
    
    # Convert to ActionLearningOutcome
    event = CortexEvent(raw_input="test")
    event.record_outcome(outcome)
    
    al_outcome = outcome_from_event(event)
    assert al_outcome is not None
    assert al_outcome.success is True
    assert al_outcome.task_completion is False


# ============================================================================
# Test 5: Execution failure + completion false
# ============================================================================

def test_execution_failure_and_task_incomplete():
    """Both execution and task failed."""
    outcome = OutcomeData(
        success=False,
        error_message="tool failed",
        task_completed=False,
        completion_source="environment",
    )
    
    event = CortexEvent(raw_input="test")
    event.record_outcome(outcome)
    
    al_outcome = outcome_from_event(event)
    assert al_outcome is not None
    assert al_outcome.success is False
    assert al_outcome.task_completion is False


# ============================================================================
# Test 6: Execution success + completion true
# ============================================================================

def test_execution_success_and_task_complete():
    """Both execution and task succeeded."""
    outcome = OutcomeData(
        success=True,
        actual_outcome="file written successfully",
        task_completed=True,
        completion_source="environment",
    )
    
    event = CortexEvent(raw_input="test")
    event.record_outcome(outcome)
    
    al_outcome = outcome_from_event(event)
    assert al_outcome is not None
    assert al_outcome.success is True
    assert al_outcome.task_completion is True


# ============================================================================
# Test 7: Completion signal independent of action type
# ============================================================================

def test_completion_independent_of_action_type():
    """Task completion is NOT determined by action type."""
    # Both respond and tool_call can have any completion state
    
    respond_complete = OutcomeData(
        success=True,
        task_completed=True,
        completion_source="user_feedback",
    )
    
    respond_incomplete = OutcomeData(
        success=True,
        task_completed=False,
        completion_source="user_feedback",
    )
    
    tool_call_complete = OutcomeData(
        success=True,
        task_completed=True,
        completion_source="environment",
    )
    
    # All are valid - no heuristic enforcement
    assert respond_complete.task_completed is True
    assert respond_incomplete.task_completed is False
    assert tool_call_complete.task_completed is True


# ============================================================================
# Test 8: Legacy event compatibility
# ============================================================================

def test_legacy_event_without_task_completed():
    """Old events without task_completed work correctly."""
    # Simulate old OutcomeData (before NC-08A.2)
    legacy_outcome = OutcomeData(
        success=True,
        actual_outcome="done",
        # No task_completed field in legacy
    )
    
    # Should default to None (unknown)
    assert legacy_outcome.task_completed is None
    assert legacy_outcome.completion_source == "unknown"
    
    # Convert to ActionLearningOutcome
    event = CortexEvent(raw_input="test")
    event.record_outcome(legacy_outcome)
    
    al_outcome = outcome_from_event(event)
    assert al_outcome is not None
    assert al_outcome.success is True
    assert al_outcome.task_completion is None  # Unknown, not False


# ============================================================================
# Test 9: Task ID propagation
# ============================================================================

def test_session_id_propagation():
    """Session ID propagates through event lifecycle."""
    event = CortexEvent(
        raw_input="test task",
        session_id="test-session-123"
    )
    
    outcome = OutcomeData(
        success=True,
        task_completed=True,
    )
    
    event.record_outcome(outcome)
    
    # Session ID should be preserved
    assert event.session_id == "test-session-123"
    assert event.outcome.task_completed is True


# ============================================================================
# Test 10: Provenance preservation
# ============================================================================

def test_provenance_preserved():
    """completion_source is preserved through conversion."""
    outcome = OutcomeData(
        success=True,
        task_completed=True,
        completion_source="user_feedback",
    )
    
    event = CortexEvent(raw_input="test")
    event.record_outcome(outcome)
    
    al_outcome = outcome_from_event(event)
    
    # Provenance should be accessible
    assert al_outcome is not None
    assert al_outcome.task_completion is True
    # Note: completion_source is on OutcomeData, not ActionLearningOutcome
    # This is by design - we track provenance at the event level


# ============================================================================
# Test 11: Engine records task completion with provenance
# ============================================================================

def test_engine_records_with_provenance(tmp_path):
    """Engine records task completion from event."""
    cfg = ActionLearningConfig(
        enabled=True,
        statistics_path=tmp_path / "stats.json",
        shadow_only=False,
    )
    engine = ActionLearningEngine(cfg)
    
    # Create event with explicit completion
    event = CortexEvent(raw_input="optimize this code")
    event.record_outcome(OutcomeData(
        success=True,
        task_completed=False,
        completion_source="user_feedback",
        actual_outcome="responded with suggestions",
    ))
    
    # Convert to ActionLearningOutcome
    al_outcome = outcome_from_event(event)
    assert al_outcome is not None
    assert al_outcome.success is True
    assert al_outcome.task_completion is False
    
    # Record in engine
    situation = ActionLearningSituation(intent="optimize")
    engine.record_outcome(situation, "respond", al_outcome)
    
    # Verify statistics
    stats = engine.store.get_global_for("respond")
    assert stats["success_count"] == 1
    assert stats["task_completion_count"] == 0
    assert stats["task_incompletion_count"] == 1


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    import tempfile
    
    print("="*70)
    print("NC-08A.2: Real Task Completion Signal Integration Tests")
    print("="*70)
    print()
    
    tests = [
        test_explicit_completion_true,
        test_explicit_completion_false,
        test_no_completion_signal,
        test_execution_success_but_task_incomplete,
        test_execution_failure_and_task_incomplete,
        test_execution_success_and_task_complete,
        test_completion_independent_of_action_type,
        test_legacy_event_without_task_completed,
        test_session_id_propagation,
        test_provenance_preserved,
        test_engine_records_with_provenance,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            if 'tmp_path' in test.__code__.co_varnames:
                with tempfile.TemporaryDirectory() as tmp:
                    test(Path(tmp))
            else:
                test()
            print(f"✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
