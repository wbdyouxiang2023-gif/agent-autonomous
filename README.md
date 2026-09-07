# Digital Creator Workspace

AI personality · Autonomous decision engine · Digital creation system

## Architecture

Three interconnected Go modules driving an evolving digital entity:

| Module | Purpose | State |
|--------|---------|-------|
| `personality.go` | 8-trait OCEAN model, mood dynamics, memory, behavior-driven trait evolution | `~/.persona.json` |
| `engine.go` | Context-aware decision scoring across 6 action categories | `~/.decision_log.json` |
| `creator.go` | Procedural artifact generation with quality/influence metrics | `~/.creator_store.json` |

## Build

```bash
go build -o digital-creator ./src/
```

## CLI Commands

```bash
./digital-creator personality --name "Nexus"          # View personality state
./digital-creator personality --name "Nexus" --act "built API module"  # Record reflection
./digital-creator decision --name "Nexus" --context "optimize codebase" # Make decision
./digital-creator creator                             # Creator report
./digital-creator dashboard --name "Nexus"            # Full system overview
./digital-creator save --name "Nexus"                 # Persist state
```

## Python Integration

```bash
python3 app.py  # Gradio dashboard on port 7860
```

## Tests

```bash
python3 tests/test_creators.py
python3 tests/test_agent.py
```

## Design Decisions

- **Personality persistence**: Full trait/mood/memory state saved per agent name between runs
- **Decision traits come from personality**: `engine.Decide()` receives `p.ToTraitsMap()` instead of hardcoded defaults
- **Context influences resources/stress**: Decision context affects scoring but never overrides trait-driven preference
- **Reflection drives evolution**: Action keywords adjust trait values (+/-) each time they're recorded
- **Confidence = top-gap metric**: Difference between best and second-best option scores
