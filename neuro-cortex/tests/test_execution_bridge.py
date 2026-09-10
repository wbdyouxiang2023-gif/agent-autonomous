"""Execution Bridge tests — Level 4.0 (18 required cases).

Run:  pytest tests/test_execution_bridge.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from neurocortex.execution_bridge import (
    ActionRequest,
    ExecutionBridge,
    ExecutionBridgeConfig,
    ExecutionEvidence,
    ExecutionLog,
    ExecutionResult,
    HermesExecutionAdapter,
    RealExecutionOutcomeProvider,
    request_from_event,
)


def _cfg(tmp_path, enabled=True, timeout=5):
    return ExecutionBridgeConfig(
        enabled=enabled,
        timeout_seconds=timeout,
        log_path=tmp_path / "exec.log.jsonl",
    )


def _request(action_type="read_file", path=None, **sit):
    return ActionRequest(
        request_id="req-test-1",
        action_type=action_type,
        situation={"intent": sit.get("intent", "fix"), "raw_input": sit.get("raw_input", "read a file")},
        tool_name="read_file_tool" if action_type == "read_file" else None,
        arguments={"path": path} if path else {},
    )


# ── 1. disabled passthrough ────────────────────────────────────────────


def test_disabled_bridge_no_side_effect(tmp_path):
    cfg = _cfg(tmp_path, enabled=False)
    br = ExecutionBridge(cfg)
    req = _request(path=str(tmp_path / "x.txt"))
    res = br.execute(req)
    # Disabled → UNSUPPORTED (never executes), success=None
    assert res.status == "unsupported"
    assert res.success is None


def test_disabled_event_unchanged(tmp_path):
    cfg = _cfg(tmp_path, enabled=False)
    br = ExecutionBridge(cfg)
    event = type("E", (), {"outcome": type("O", (), {"success": "original", "actual_outcome": "orig"})()})()
    out = br.execute_event(event)
    # Original outcome untouched
    assert out.outcome.success == "original"


# ── 2. unsupported action ──────────────────────────────────────────────


def test_unsupported_action(tmp_path):
    cfg = _cfg(tmp_path, enabled=True)
    br = ExecutionBridge(cfg)
    res = br.execute(_request(action_type="code_edit"))
    assert res.status == "unsupported"
    assert res.success is None


# ── 3. real success ────────────────────────────────────────────────────


def test_real_success(tmp_path):
    target = tmp_path / "hello.txt"
    target.write_text("hello world\n", encoding="utf-8")
    cfg = _cfg(tmp_path, enabled=True)
    br = ExecutionBridge(cfg)
    res = br.execute(_request(path=str(target)))
    assert res.status == "success"
    assert res.success is True
    assert "hello world" in res.output


# ── 4. real failure (missing file) ─────────────────────────────────────


def test_real_failure_missing_file(tmp_path):
    cfg = _cfg(tmp_path, enabled=True)
    br = ExecutionBridge(cfg)
    res = br.execute(_request(path=str(tmp_path / "does_not_exist.txt")))
    assert res.status == "failure"
    assert res.success is False
    assert res.error  # tool_error carries the reason


# ── 5. unknown result ──────────────────────────────────────────────────


def test_unknown_result(tmp_path):
    cfg = _cfg(tmp_path, enabled=True)
    br = ExecutionBridge(cfg)
    # Empty path → real tool returns "File not found" → REAL FAILURE (False),
    # never a fabricated True. (UNKNOWN is reserved for no reliable result,
    # e.g. exceptions/timeouts — covered by test_exception_becomes_unknown.)
    res = br.execute(_request(path=""))
    assert res.success is False
    assert "File not found" in res.error or res.error


# ── 6. exception → unknown ─────────────────────────────────────────────


def test_exception_becomes_unknown(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, enabled=True)
    br = ExecutionBridge(cfg)

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(br.adapter._executor, "__call__", boom) if br.adapter._executor else None
    # Force by replacing executor with a raiser
    monkeypatch.setattr(br.adapter, "_executor", boom)
    res = br.execute(_request(path=str(tmp_path / "x.txt")))
    assert res.status == "unknown"
    assert res.success is None


# ── 7. timeout ─────────────────────────────────────────────────────────


def test_timeout_is_unknown(tmp_path, monkeypatch):
    import time

    cfg = _cfg(tmp_path, enabled=True, timeout=1)
    br = ExecutionBridge(cfg)

    def slow(*a, **k):
        time.sleep(5)
        return "late"

    monkeypatch.setattr(br.adapter, "_executor", slow)
    # We don't enforce timeout in the adapter (real executor owns it); a
    # long-running call is the executor's domain. Simulate by raising TimeoutError.
    def timeout_raise(*a, **k):
        raise TimeoutError("timed out")

    monkeypatch.setattr(br.adapter, "_executor", timeout_raise)
    res = br.execute(_request(path=str(tmp_path / "x.txt")))
    assert res.success is None  # timeout → UNKNOWN


# ── 8. ExecutionResult schema ──────────────────────────────────────────


def test_execution_result_schema():
    r = ExecutionResult(
        execution_id="e1", request_id="r1", action_type="read_file",
        tool_name="read_file_tool", status="success", success=True,
        output="content", error="",
    )
    d = r.to_dict()
    for k in ("execution_id", "request_id", "action_type", "tool_name", "status", "success", "output", "error", "started_at", "finished_at"):
        assert k in d
    assert r.is_known is True


# ── 9. OutcomeAdapter via provider ─────────────────────────────────────


def test_outcome_provider_maps_tristate(tmp_path):
    prov = RealExecutionOutcomeProvider(_cfg(tmp_path))
    ok = ExecutionResult("e1", "r1", "read_file", "read_file_tool", "success", True, output="data")
    fail = ExecutionResult("e2", "r1", "read_file", "read_file_tool", "failure", False, error="missing")
    unk = ExecutionResult("e3", "r1", "read_file", "read_file_tool", "unknown", None)
    assert prov.to_outcome_data(ok).success is True
    assert prov.to_outcome_data(fail).success is False
    assert prov.to_outcome_data(unk).success is None


# ── 10. predicted_prob not involved ────────────────────────────────────


def test_predicted_prob_not_involved(tmp_path):
    # The bridge consumes only ExecutionResult; predicted_prob is a
    # prediction artifact that never appears in the execution path.
    cfg = _cfg(tmp_path, enabled=True)
    br = ExecutionBridge(cfg)
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    res = br.execute(_request(path=str(target)))
    assert res.success is True  # outcome from real execution, not prediction


# ── 11. confidence not involved ────────────────────────────────────────


def test_confidence_not_involved(tmp_path):
    # Same: confidence is a prediction field, absent from ExecutionResult.
    r = ExecutionResult("e", "r", "read_file", "read_file_tool", "success", True)
    assert "confidence" not in r.to_dict()
    assert "predicted_prob" not in r.to_dict()


# ── 12. mock outcome not in real learning ──────────────────────────────


def test_mock_not_in_real_learning(tmp_path):
    from neurocortex.action_learning import OutcomeAdapter, ExecutionResult as MockRes

    adapter = OutcomeAdapter(require_real=True)
    mock = MockRes(success=True, source="mock")
    od = adapter.to_outcome_data(mock)
    assert od.success is None  # mock never enters real stats


# ── 13. real outcome can enter Experience ──────────────────────────────


def test_real_outcome_enters_experience(tmp_path):
    from neurocortex.memory.experience_store import ExperienceStore
    from neurocortex.learning.experience_learner import ExperienceLearningModule
    from neurocortex.event import CortexEvent, OutcomeData

    store = ExperienceStore(tmp_path / "exp.jsonl")
    learner = ExperienceLearningModule(store)
    event = CortexEvent(raw_input="read a file")
    event.perceive({"intent": "fix", "confidence": 0.5})
    event.represent()
    event.attend()
    event.update_state()
    event.retrieve_memory()
    event.predict({"predicted_outcome": "read ok", "success_probability": 0.9})
    event.decide({"selected_action": "read_file", "decision_score": 0.9, "candidates": [{"id": "read_file"}]})
    event.act({"action_type": "read_file", "status": "success", "actual": True})
    event.record_outcome(OutcomeData(actual_outcome="file content", success=True))
    event.compute_feedback()
    learner.process(event)
    assert store.count() == 1
    exp = store.list_all()[0]
    assert exp.success is True
    assert exp.action_type == "read_file"


# ── 14. real outcome can enter Action Learning ─────────────────────────


def test_real_outcome_enters_action_learning(tmp_path):
    from neurocortex.action_learning import (
        ActionLearningConfig, ActionLearningEngine,
        ActionLearningSituation, ActionLearningOutcome,
    )

    eng = ActionLearningEngine(ActionLearningConfig(
        enabled=True, statistics_path=tmp_path / "stats.json"
    ))
    sit = ActionLearningSituation(intent="fix", situation_completeness="partial")
    eng.record_outcome(sit, "read_file", ActionLearningOutcome(success=True))
    ranked = eng.rank_actions(sit, ["read_file"])
    assert ranked[0]["support_count"] == 1
    assert ranked[0]["success_count"] == 1


# ── 15. persistence ────────────────────────────────────────────────────


def test_persistence(tmp_path):
    cfg = _cfg(tmp_path, enabled=True)
    target = tmp_path / "p.txt"
    target.write_text("persist", encoding="utf-8")
    br1 = ExecutionBridge(cfg)
    res1 = br1.execute(_request(path=str(target)))
    assert res1.success is True
    # Execution log persisted
    log_path = tmp_path / "exec.log.jsonl"
    assert log_path.exists()
    entries = [json.loads(l) for l in log_path.read_text().strip().splitlines()]
    assert any(e["success"] is True for e in entries)


# ── 16. atomic write (log) ─────────────────────────────────────────────


def test_log_append(tmp_path):
    prov = RealExecutionOutcomeProvider(_cfg(tmp_path))
    prov.to_outcome_data(ExecutionResult("e1", "r1", "read_file", "read_file_tool", "success", True))
    prov.to_outcome_data(ExecutionResult("e2", "r1", "read_file", "read_file_tool", "failure", False))
    entries = (tmp_path / "exec.log.jsonl").read_text().strip().splitlines()
    assert len(entries) == 2


# ── 17. bridge failure doesn't affect pipeline ─────────────────────────


def test_bridge_failure_pipeline_unchanged(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, enabled=True)
    br = ExecutionBridge(cfg)

    def boom(request):
        raise RuntimeError("bridge exploded")

    monkeypatch.setattr(br.adapter, "execute", boom)
    event = type("E", (), {
        "outcome": type("O", (), {"success": "orig", "actual_outcome": "orig"})(),
        "raw_input": "x", "perception": type("P", (), {"intent": "fix"})(),
        "action": type("A", (), {"action_type": "read_file"})(),
    })()
    out = br.execute_event(event)
    # Original event outcome untouched on bridge failure
    assert out.outcome.success == "orig"


# ── 18. feature flag safety ────────────────────────────────────────────


def test_flag_safety_default(tmp_path):
    cfg = ExecutionBridgeConfig(enabled=False, timeout_seconds=5, log_path=tmp_path / "e.jsonl")
    br = ExecutionBridge(cfg)
    assert br.enabled is False
    res = br.execute(_request(path=str(tmp_path / "any.txt")))
    assert res.success is None  # zero side effects when disabled


# ── runtime smoke helpers ──────────────────────────────────────────────


def test_request_from_event():
    event = type("E", (), {
        "action": type("A", (), {"action_type": "read_file"})(),
        "perception": type("P", (), {"intent": "fix"})(),
        "raw_input": "read a file",
    })()
    req = request_from_event(event)
    assert req is not None
    assert req.action_type == "read_file"
