"""NC-08C.0.1 real end-to-end tasks. No mocks."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "experiments"))

from nc08c.real_loop import default_tasks, run_task
from neurocortex.perception.intent_router import detect_coarse_intent


def test_real_e2e_six_tasks(tmp_path):
    (tmp_path / "sample.py").write_text("def quality():\n    return True\n", encoding="utf-8")
    log = tmp_path / "loop.jsonl"
    recs = [run_task(spec, tmp_path, log) for spec in default_tasks()]
    assert len(recs) == 6
    assert all(r.execution_success is True for r in recs)
    assert all(r.task_completed is True for r in recs)
    assert recs[0].action_type == "write_file"
    assert recs[1].action_type == "read_file"
    assert recs[3].action_type == "terminal"
    text = log.read_text(encoding="utf-8")
    assert "TASK-01" in text


def test_task05_intent_is_review():
    assert detect_coarse_intent("检查代码质量") == "review"
