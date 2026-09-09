#!/usr/bin/env python3
"""
Observation Logger for NeuroCortex — append-only, zero behavioral change.

Patches server.py to:
1. Log candidate_actions and hermes_original_selected_action per request
2. Output to ~/.neurocortex_observation_log.jsonl (separate from experience store)

DOES NOT modify:
- Decision logic
- Action selection
- Outcome computation
- Learning algorithms
"""
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

OBS_LOG_PATH = os.path.expanduser("~/.neurocortex_observation_log.jsonl")


def log_observation(event, raw_input, response_extra=None):
    """Append a single observation record. Never reads or modifies event state."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment_run_id": str(uuid.uuid4())[:8],
        "event_id": getattr(getattr(event, "id", None), "hex", str(uuid.uuid4())) if hasattr(event, 'id') else str(uuid.uuid4()),
        "raw_input": raw_input,
        "situation": raw_input[:200],
        "intent": event.perception.intent if hasattr(event, 'perception') else "",
        "candidate_actions": [
            c["id"] for c in (event.decision.candidates if hasattr(event, 'decision') and event.decision.candidates else [])
        ],
        "hermes_original_selected_action": (
            event.decision.selected_action if hasattr(event, 'decision') and event.decision else ""
        ),
        "decision_score": (
            event.decision.decision_score if hasattr(event, 'decision') and event.decision else None
        ),
        "execution_id": str(uuid.uuid4())[:8],
        "action": (
            event.action.action_type if hasattr(event, 'action') and event.action else ""
        ),
        "success": (
            event.outcome.success if hasattr(event, 'outcome') and event.outcome else None
        ),
        "outcome_source": "real",
        "observation_only": True,
    }
    if response_extra:
        record.update(response_extra)

    with open(OBS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def count():
    if not os.path.exists(OBS_LOG_PATH):
        return 0
    with open(OBS_LOG_PATH) as f:
        return sum(1 for _ in f)


if __name__ == "__main__":
    # Self-test
    print(f"Observation logger ready. Log path: {OBS_LOG_PATH}")
    print(f"Current records: {count()}")
