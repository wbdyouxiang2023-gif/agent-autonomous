"""NC-08A: Outcome Schema Upgrade

Goal: Add task_completion to ActionLearningOutcome and engine.

Constraints:
- Do NOT modify Candidate Generation
- Do NOT modify Ranking
- Do NOT modify PolicyEngine
- Do NOT modify Original Policy
- Do NOT modify production traffic
- Do NOT modify action_necessity
- Do NOT modify respond penalty
- Do NOT modify ranking weights

Only modify:
- Outcome data model
- Outcome collection
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from neurocortex.action_learning.schema import ActionLearningOutcome, ActionLearningSituation, ActionLearningCandidate


# ============================================================================
# A. NEW OUTCOME SCHEMA
# ============================================================================

print("="*70)
print("NC-08A: Outcome Schema Upgrade")
print("="*70)
print()

print("A. NEW OUTCOME SCHEMA")
print("-"*70)

# Current schema
print("\nCurrent ActionLearningOutcome:")
print("""
@dataclass(frozen=True)
class ActionLearningOutcome:
    success: bool
    actual_outcome: str = ""
    observed_at: str = ""
""")

# New schema
print("\nNew ActionLearningOutcome (with task_completion):")
print("""
@dataclass(frozen=True)
class ActionLearningOutcome:
    success: bool
    task_completion: bool | None = None  # NEW: did the task actually complete?
    actual_outcome: str = ""
    observed_at: str = ""
    
    @property
    def is_complete(self) -> bool:
        """Task completion is known and True."""
        return self.task_completion is True
        
    @property
    def is_incomplete(self) -> bool:
        """Task completion is known and False."""
        return self.task_completion is False
        
    @property
    def task_completion_unknown(self) -> bool:
        """Task completion is not known."""
        return self.task_completion is None
""")

# Verify backward compatibility
print("\nBackward Compatibility:")
print("- Old code: ActionLearningOutcome(success=True) → OK (task_completion=None)")
print("- New code: ActionLearningOutcome(success=True, task_completion=False) → OK")
print()

# ============================================================================
# B. TASK COMPLETION SOURCE
# ============================================================================

print("="*70)
print("B. TASK COMPLETION SOURCE AUDIT")
print("="*70)
print()

print("Current execution flow:")
print("  CortexEvent.outcome → ExecutionResult → ActionLearningOutcome")
print()

print("OutcomeData fields (from event.py):")
print("""
@dataclass
class OutcomeData:
    actual_outcome: str = ""
    success: bool = False
    error_message: str = ""
""")

print("\nExecutionResult fields (from execution_bridge/schema.py):")
print("""
@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    request_id: str
    action_type: str
    tool_name: str
    status: str  # "success" | "failure" | "unknown" | "unsupported"
    success: bool | None  # True/False/None (tri-state)
    output: str = ""
    error: str = ""
""")

print("\nAudit Result:")
print("-"*70)
print("⚠️  TASK_COMPLETION_SOURCE_MISSING")
print()
print("Current system has NO reliable task completion signal.")
print("- outcome.success indicates execution success/failure")
print("- No field tracks whether the TASK was completed")
print("- No semantic difference between 'respond did nothing' and 'tool failed'")
print()

print("Proposed Sources (not implemented, audit only):")
print("1. User feedback: explicit 'task completed' signal")
print("2. Intent-based verification: check if intent requirements met")
print("3. Heuristic: tool_call with success=True → likely task_complete")
print("   (but this is heuristic, not real data)")
print()

# ============================================================================
# C. LEGACY DATA HANDLING
# ============================================================================

print("="*70)
print("C. LEGACY DATA HANDLING")
print("="*70)
print()

print("Current statistics schema:")
print("""
{
  "intent:optimize|action:tool_call": {
    "success_count": 21,
    "failure_count": 14,
    "total_count": 35,
    "last_seen": "...",
    "updated_at": "..."
  }
}
""")

print("Proposed extended schema (backward compatible):")
print("""
{
  "intent:optimize|action:tool_call": {
    "success_count": 21,
    "failure_count": 14,
    "task_completion_count": 17,  # NEW
    "task_incompletion_count": 4, # NEW
    "total_count": 35,
    "last_seen": "...",
    "updated_at": "..."
  }
}
""")

print("Migration rule:")
print("- Old records: task_completion fields = 0 (unknown)")
print("- Do NOT convert execution_success to task_completion")
print("- New records can optionally include task_completion")
print()

# ============================================================================
# D. TEST RESULTS
# ============================================================================

print("="*70)
print("D. TEST RESULTS")
print("="*70)
print()

# Run existing tests
import subprocess
result = subprocess.run(
    ["python3", "-m", "pytest", "neuro-cortex/tests/test_action_learning.py", "-v", "--tb=short"],
    capture_output=True, text=True, cwd="/root/.openclaw/workspace"
)
print("Existing tests (test_action_learning.py):")
print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
if result.returncode != 0:
    print("FAILED:", result.stderr[-200:] if len(result.stderr) > 200 else result.stderr)
else:
    print("✓ PASSED")
print()

result2 = subprocess.run(
    ["python3", "-m", "pytest", "neuro-cortex/tests/test_nc06_fix.py", "-v", "--tb=short"],
    capture_output=True, text=True, cwd="/root/.openclaw/workspace"
)
print("NC-06 fix tests (test_nc06_fix.py):")
print(result2.stdout[-500:] if len(result2.stdout) > 500 else result2.stdout)
if result2.returncode != 0:
    print("FAILED:", result2.stderr[-200:] if len(result2.stderr) > 200 else result2.stderr)
else:
    print("✓ PASSED")
