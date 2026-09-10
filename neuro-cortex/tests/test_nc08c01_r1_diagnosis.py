"""NC-08C.1-R1 — Eligibility diagnosis and validation tests."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))

from experiments.nc08b.shadow.shadow_adapter import (
    _load_evidence, _classify_to_task_type, rank_by_completion, ShadowAdapter,
)
from experiments.nc08c.policy_selector import PolicySelector, PolicyConfig, ExperimentAssigner

REPO = Path(__file__).parent.parent


def _make_sel(mode="trial_nc", nc_ratio=1.0, nc_min_confidence=0.6, nc_min_evidence=3, **kw):
    cfg = PolicyConfig(nc_enable=True, kill_switch=False, policy_mode=mode,
                       nc_min_confidence=nc_min_confidence, nc_min_evidence=nc_min_evidence,
                       decision_log=str(REPO / "tests/_tmp_decision.jsonl"),
                       outcome_log=str(REPO / "tests/_tmp_outcome.jsonl"),
                       **kw)
    assigner = ExperimentAssigner("r1-test", nc_ratio=nc_ratio)
    return PolicySelector(config=cfg, assigner=assigner)


# R1-01: 已有有效 evidence → 应能够产生 recommendation
def test_r1_01_valid_evidence_produces_recommendation():
    sel = _make_sel()
    d = sel.select("读取 test.txt 并告诉我第一行内容",
                   ["read_file", "write_file", "search_files", "terminal"],
                   "read_file", task_id="r1-01")
    assert d.nc_abstained is False
    assert d.nc_confidence is not None
    assert d.nc_confidence >= 0.6
    assert d.nc_evidence_strength >= 3
    assert d.actual_action == "read_file"
    assert d.policy_source == "neurocortex"


# R1-02: 无 evidence → ABSTAIN
def test_r1_02_no_evidence_abstains():
    sel = _make_sel(nc_min_confidence=0.0, nc_min_evidence=0)
    # Use a completely unknown situation that won't match any classifier
    d = sel.select("xyz_qqq_unknown_situation_12345",
                   ["ghost_action_xyz"],
                   "ghost_action_xyz", task_id="r1-02")
    assert d.nc_abstained is True


# R1-03: 低 confidence → ABSTAIN
def test_r1_03_low_confidence_abstains():
    # confidence=1.0 always when evidence exists; inject failure to simulate low conf
    sel = _make_sel()
    d = sel.select("读取 test.txt 并告诉我第一行内容",
                   ["read_file", "terminal"],
                   "read_file", task_id="r1-03",
                   _inject_failure={"type": "low_confidence", "reason": "sim"})
    assert d.nc_abstained is True
    assert d.actual_action == "read_file"  # Original fallback


# R1-04: 低 evidence → ABSTAIN
def test_r1_04_low_evidence_abstains():
    sel = _make_sel(nc_min_evidence=999)
    d = sel.select("读取 test.txt 并告诉我第一行内容",
                   ["read_file", "terminal"],
                   "read_file", task_id="r1-04")
    assert d.nc_abstained is True
    assert "insufficient_evidence" in d.nc_abstain_reason


# R1-05: valid recommendation → trial_nc 可以产生 NC actual_action
def test_r1_05_nc_action_in_trial():
    sel = _make_sel()
    d = sel.select("搜索指定文件",
                   ["read_file", "write_file", "search_files", "terminal"],
                   "search_files", task_id="r1-05")
    assert d.nc_abstained is False
    assert d.policy_source == "neurocortex"
    assert d.actual_action == "search_files"


# R1-06: ABSTAIN → Original fallback
def test_r1_06_abstain_falls_back():
    sel = _make_sel(nc_min_evidence=999)
    d = sel.select("读取 test.txt 并告诉我第一行内容",
                   ["read_file", "terminal"],
                   "read_file", task_id="r1-06")
    assert d.nc_abstained is True
    assert d.actual_action == "read_file"
    assert d.policy_source == "original"
    assert d.fallback_reason == "nc_abstain"


# R1-07: NC exception → Original fallback
def test_r1_07_nc_exception_fallback():
    sel = _make_sel()
    d = sel.select("读取 test.txt",
                   ["read_file", "terminal"],
                   "read_file", task_id="r1-07",
                   _inject_failure={"type": "exception", "reason": "boom"})
    assert d.nc_failure is True
    assert d.actual_action == "read_file"
    assert d.policy_source == "original"


# R1-08: NC timeout → Original fallback
def test_r1_08_nc_timeout_fallback():
    sel = _make_sel()
    d = sel.select("读取 test.txt",
                   ["read_file", "terminal"],
                   "read_file", task_id="r1-08",
                   _inject_failure={"type": "timeout", "reason": "slow"})
    assert d.nc_failure is True
    assert d.nc_failure_type == "timeout"
    assert d.actual_action == "read_file"


# R1-09: shadow/trial_original 不得被 NC 覆盖
def test_r1_09_shadow_no_override():
    for mode in ("shadow", "trial_original"):
        sel = _make_sel(mode=mode)
        d = sel.select("读取 test.txt",
                       ["read_file", "terminal"],
                       "read_file", task_id=f"r1-09-{mode}")
        assert d.actual_action == "read_file"
        assert d.policy_source == "original"
        assert d.fallback_reason == f"mode_{mode}"


# R1-10: NC direct action must enter Executor (verified via record_outcome)
def test_r1_10_nc_action_leads_to_outcome():
    sel = _make_sel()
    d = sel.select("搜索指定文件",
                   ["read_file", "write_file", "search_files", "terminal"],
                   "search_files", task_id="r1-10")
    assert d.policy_source == "neurocortex"
    assert d.actual_action == "search_files"
    # Record outcome (simulating execution)
    sel.record_outcome(d, execution_success=True, task_completed=True,
                       completion_source="task_verifier", actual_outcome="hello.txt")
    out_log = Path(sel.config.outcome_log).read_text(encoding="utf-8")
    last = json.loads(out_log.strip().splitlines()[-1])
    assert last["policy_source"] == "neurocortex"
    assert last["actual_action"] == "search_files"
    assert last["task_completed"] is True
