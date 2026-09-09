"""NC-08A: Outcome Schema Upgrade Tests

Tests for:
1. New task_completion field in ActionLearningOutcome
2. Statistics store records task completion
3. Backward compatibility with legacy data
4. No heuristic-based task_completion
"""
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from neurocortex.action_learning.schema import (
    ActionLearningOutcome,
    ActionLearningSituation,
    ActionLearningCandidate,
    outcome_from_event,
)
from neurocortex.action_learning.engine import ActionLearningEngine, StatisticsStore
from neurocortex.action_learning.config import ActionLearningConfig


# ============================================================================
# Test 1: Schema with task_completion
# ============================================================================

def test_outcome_with_task_completion():
    """New: outcome can have task_completion field."""
    outcome = ActionLearningOutcome(
        success=True,
        task_completion=True,
        actual_outcome="completed",
    )
    assert outcome.success is True
    assert outcome.is_complete is True
    assert outcome.is_incomplete is False
    assert outcome.task_completion_unknown is False


def test_outcome_without_task_completion():
    """Legacy: outcome without task_completion defaults to None."""
    outcome = ActionLearningOutcome(
        success=True,
        actual_outcome="done",
    )
    assert outcome.success is True
    assert outcome.task_completion is None
    assert outcome.task_completion_unknown is True


def test_outcome_incomplete():
    """Execution success but task not completed."""
    outcome = ActionLearningOutcome(
        success=True,
        task_completion=False,
        actual_outcome="responded but task incomplete",
    )
    assert outcome.is_incomplete is True
    assert outcome.task_completion_unknown is False


# ============================================================================
# Test 2: Statistics store with task_completion
# ============================================================================

def test_statistics_record_with_task_completion(tmp_path):
    """Stats store records task completion counts."""
    store = StatisticsStore(tmp_path / "stats.json")
    
    # Record with task completion
    store.record("intent:optimize", "respond", True, "2026-09-09T00:00:00Z", task_completion=False)
    store.record("intent:optimize", "respond", True, "2026-09-09T00:00:01Z", task_completion=False)
    store.record("intent:optimize", "respond", True, "2026-09-09T00:00:02Z", task_completion=True)
    
    stats = store.get_global_for("respond")
    assert stats["success_count"] == 3
    assert stats["task_completion_count"] == 1
    assert stats["task_incompletion_count"] == 2


def test_statistics_record_without_task_completion():
    """Legacy: stats without task_completion work normally."""
    store = StatisticsStore(None)  # In-memory
    
    store.record("intent:optimize", "tool_call", True, "2026-09-09T00:00:00Z")
    store.record("intent:optimize", "tool_call", False, "2026-09-09T00:00:01Z")
    
    stats = store.get_global_for("tool_call")
    assert stats["success_count"] == 1
    assert stats["failure_count"] == 1
    assert stats.get("task_completion_count", 0) == 0  # Default to 0


# ============================================================================
# Test 3: Engine records task_completion
# ============================================================================

def test_engine_records_task_completion(tmp_path):
    """Engine passes task_completion to store."""
    cfg = ActionLearningConfig(
        enabled=True,
        statistics_path=tmp_path / "stats.json",
        shadow_only=False,
    )
    engine = ActionLearningEngine(cfg)
    
    situation = ActionLearningSituation(intent="optimize")
    outcome = ActionLearningOutcome(success=True, task_completion=False)
    
    engine.record_outcome(situation, "respond", outcome)
    
    stats = engine.store.get_global_for("respond")
    assert stats["success_count"] == 1
    assert stats["task_completion_count"] == 0
    assert stats["task_incompletion_count"] == 1


def test_engine_ignores_unknown_task_completion(tmp_path):
    """Engine handles None task_completion correctly."""
    cfg = ActionLearningConfig(enabled=True, statistics_path=tmp_path / "stats.json")
    engine = ActionLearningEngine(cfg)
    
    situation = ActionLearningSituation(intent="optimize")
    outcome = ActionLearningOutcome(success=True, task_completion=None)
    
    engine.record_outcome(situation, "respond", outcome)
    
    stats = engine.store.get_global_for("respond")
    assert stats["success_count"] == 1
    assert stats.get("task_completion_count", 0) == 0  # Not counted


# ============================================================================
# Test 4: No heuristic-based task_completion
# ============================================================================

def test_no_heuristic_for_respond():
    """Critical: respond does NOT automatically get task_completion=False."""
    # If someone creates outcome without specifying task_completion,
    # it should be None (unknown), not False
    outcome = ActionLearningOutcome(success=True)
    assert outcome.task_completion is None
    assert outcome.task_completion_unknown is True


def test_no_heuristic_for_tool_call():
    """Critical: tool_call does NOT automatically get task_completion=True."""
    outcome = ActionLearningOutcome(success=True)
    assert outcome.task_completion is None


# ============================================================================
# Test 5: Legacy data compatibility
# ============================================================================

def test_legacy_data_compatibility(tmp_path):
    """Legacy stats files work with new code."""
    # Create legacy-style stats
    legacy_data = {
        "intent:optimize|action:respond": {
            "success_count": 122,
            "failure_count": 5,
            "total_count": 127,
            "last_seen": "2026-09-09T00:00:00Z",
            "updated_at": "2026-09-09T00:00:00Z",
        }
    }
    stats_file = tmp_path / "stats.json"
    stats_file.write_text(str(legacy_data).replace("'", "\""))
    
    store = StatisticsStore(stats_file)
    stats = store.get_global_for("respond")
    
    # Should read legacy counts
    assert stats["success_count"] == 122
    assert stats["failure_count"] == 5
    
    # Task completion defaults to 0
    assert stats.get("task_completion_count", 0) == 0
    assert stats.get("task_incompletion_count", 0) == 0


# ============================================================================
# Test 6: Outcome adapter extracts task_completion from event
# ============================================================================

def test_outcome_from_event_with_task_completed():
    """Adapter extracts task_completed from event."""
    class MockOutcome:
        success = True
        actual_outcome = "done"
        task_completed = True
    
    class MockEvent:
        outcome = MockOutcome()
    
    outcome = outcome_from_event(MockEvent())
    assert outcome is not None
    assert outcome.success is True
    assert outcome.task_completion is True


def test_outcome_from_event_without_task_completed():
    """Adapter handles missing task_completed."""
    class MockOutcome:
        success = True
        actual_outcome = "done"
        # No task_completed field
    
    class MockEvent:
        outcome = MockOutcome()
    
    outcome = outcome_from_event(MockEvent())
    assert outcome is not None
    assert outcome.success is True
    assert outcome.task_completion is None  # Unknown, not False


def test_outcome_from_event_unknown_success():
    """Adapter returns None for unknown success."""
    class MockOutcome:
        success = None
    
    class MockEvent:
        outcome = MockOutcome()
    
    outcome = outcome_from_event(MockEvent())
    assert outcome is None


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        from pathlib import Path
        tmp_path = Path(tmp)
        
        print("="*70)
        print("NC-08A: Outcome Schema Upgrade Tests")
        print("="*70)
        print()
        
        tests = [
            test_outcome_with_task_completion,
            test_outcome_without_task_completion,
            test_outcome_incomplete,
            test_statistics_record_with_task_completion,
            test_statistics_record_without_task_completion,
            test_engine_records_task_completion,
            test_engine_ignores_unknown_task_completion,
            test_no_heuristic_for_respond,
            test_no_heuristic_for_tool_call,
            test_legacy_data_compatibility,
            test_outcome_from_event_with_task_completed,
            test_outcome_from_event_without_task_completed,
            test_outcome_from_event_unknown_success,
        ]
        
        passed = 0
        failed = 0
        for test in tests:
            try:
                test(tmp_path)
                print(f"✓ {test.__name__}")
                passed += 1
            except Exception as e:
                print(f"✗ {test.__name__}: {e}")
                failed += 1
        
        print()
        print(f"Results: {passed} passed, {failed} failed")
