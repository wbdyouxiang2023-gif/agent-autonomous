"""Pattern module package for Phase 12."""
from .pattern import Pattern, PATTERN_LIFECYCLE
from .consolidator import PatternConsolidator
from .store import PatternStore
from .retriever import PatternRetriever

__all__ = [
    "Pattern",
    "PATTERN_LIFECYCLE",
    "PatternConsolidator",
    "PatternStore",
    "PatternRetriever",
]
