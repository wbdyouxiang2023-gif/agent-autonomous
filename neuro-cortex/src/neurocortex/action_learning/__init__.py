"""Action Learning — Experience → Action Value learning (Level 3.5-C/D).

Evidence comes ONLY from REAL OUTCOMES. Feature flag:
NEUROCORTEX_ACTION_LEARNING=false by default (production behavior unchanged).
"""
from .config import ActionLearningConfig
from .engine import ActionLearningEngine, StatisticsStore
from .schema import (
    ActionLearningCandidate,
    ActionLearningOutcome,
    ActionLearningSituation,
)
from .bridge import ActionLearningBridge
from .outcome_adapter import OutcomeAdapter, ExecutionResult
from .similarity import similarity, SimilarityResult
from .semantic_transfer import (
    BorrowedEvidence, transfer_gate, compute_transfer_weight, build_borrowed_evidence,
)

__all__ = [
    "ActionLearningConfig",
    "ActionLearningEngine",
    "StatisticsStore",
    "ActionLearningCandidate",
    "ActionLearningOutcome",
    "ActionLearningSituation",
    "ActionLearningBridge",
    "OutcomeAdapter",
    "ExecutionResult",
    "similarity",
    "SimilarityResult",
    "BorrowedEvidence",
    "transfer_gate",
    "compute_transfer_weight",
    "build_borrowed_evidence",
]
