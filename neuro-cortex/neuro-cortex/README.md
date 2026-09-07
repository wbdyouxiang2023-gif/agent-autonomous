# Neuro Cortex 2.0

A clean-slate cognitive/learning closed-loop core.

## Philosophy

**Not** a stack of classifiers + memory + personality.

A closed loop:

```
Input → Perception → Representation → Attention
  → Internal State + Memory → Prediction → Decision → Action
  → Outcome → Feedback → Learning → Update
  → Next behavior changes
```

Core criterion: after one experience, does the system behave differently next time?

## Architecture

```
src/neurocortex/
├── cortex.py          # NeuroCortex orchestration
├── event.py           # CortexEvent data class
├── perception/        # Raw input → structured perception
├── representation/    # Perception → features/embedding
├── attention/         # Relevance/novelty/risk scoring
├── state/             # Dynamic internal state (curiosity, caution, ...)
├── memory/            # Episodic + semantic memory + retrieval
├── prediction/        # Expected outcome + confidence
├── decision/          # Action selection with reasoning
├── action/            # NOOP | RESPOND | TOOL_CALL | CODE_REVIEW | CODE_EDIT
├── feedback/          # Prediction vs outcome → reward/error
└── learning/          # Experience-based adaptation (no weight updates)
```

## Key Distinction

| Concept | What it is |
|---------|-----------|
| Logging | Writing to file — no behavioral effect |
| Memory | Persisted experiences that can be retrieved |
| Retrieval | Finding relevant past experiences |
| Adaptation | Changing behavior based on retrieved memory |
| Learning | Modifying parameters so future behavior improves |

## Development Phases

Phase 0–10: Build core modules with tests
Phase 11: Closed-loop experiments
Phase 12: Hermes adapter
Phase 13: GitHub integration

## Quick Start

```bash
cd /workspace/neuro-cortex
python -m pytest tests/ -v
```

## Design Principles

- Every module has a single responsibility
- Data flows through `CortexEvent` — no parallel incompatible data structures
- All state changes are observable and testable
- No external dependencies in Phase 0–10
- DRY RUN by default for all actions
- Clear separation between logging, memory, retrieval, and learning
