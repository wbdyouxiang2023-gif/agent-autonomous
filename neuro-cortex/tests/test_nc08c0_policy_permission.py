"""NC-08C.0 — Policy Permission Architecture safety tests.

Run: python3 -m pytest tests/test_nc08c0_policy_permission.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "experiments"))
sys.path.insert(0, str(REPO / "experiments" / "nc08b" / "shadow"))

from experiments.nc08c.policy_selector import (  # noqa: E402
    PolicySelector, PolicyConfig, ExperimentAssigner, NCRecommender,
    NCRecommenderFailure, TwoPhaseLogger, POLICY_VERSION,
)

# ── helpers ─────────────────────────────────────────────────────────
_TMP = Path(tempfile.mkdtemp(prefix="nc08c0-test-"))


def make_selector(mode="trial_nc", nc_enable=True, kill=False,
                  min_conf=0.6, min_ev=2, nc_ratio=1.0):
    """nc_ratio=1.0 → all tasks assigned to 'nc' group for testability."""
    cfg = PolicyConfig(
        nc_enable=nc_enable, kill_switch=kill, policy_mode=mode,
        nc_min_confidence=min_conf, nc_min_evidence=min_ev,
        decision_log=str(_TMP / "decision.jsonl"),
        outcome_log=str(_TMP / "outcome.jsonl"),
    )
    assigner = ExperimentAssigner("test-exp", nc_ratio=nc_ratio)
    return PolicySelector(config=cfg, assigner=assigner)


def decision_of(sel, sit="search_code_symbol",
                cands=("search_files", "terminal", "read_file"),
                orig="terminal", **kw):
    if "task_id" not in kw:
        kw["task_id"] = "t1"
    return sel.select(sit, list(cands), orig, **kw)


# TEST-01: NC_ENABLE=false → 100% Original
def test_01_nc_enable_false_original():
    sel = make_selector(nc_enable=False)
    d = decision_of(sel)
    assert d.actual_action == "terminal"
    assert d.policy_source == "original"
    assert d.fallback_reason == "nc_enable_false"


# TEST-02: shadow mode → Original + NC only recorded
def test_02_shadow_mode_original():
    sel = make_selector(mode="shadow")
    d = decision_of(sel)
    assert d.actual_action == "terminal"
    assert d.policy_source == "original"
    assert d.fallback_reason == "mode_shadow"


# TEST-03: trial_original → Original
def test_03_trial_original():
    sel = make_selector(mode="trial_original")
    d = decision_of(sel)
    assert d.actual_action == "terminal"
    assert d.policy_source == "original"


# TEST-04: trial_nc + valid NC rec → NC action
def test_04_trial_nc_valid():
    sel = make_selector()
    d = decision_of(sel, sit="search_code_symbol")
    # search_files has comp 1.0, evidence 5 >= 2 → NC acts
    assert d.nc_abstained is False
    assert d.policy_source == "neurocortex"
    assert d.actual_action == "search_files"
    assert d.nc_recommendation == "search_files"


# TEST-05: trial_nc + ABSTAIN → Original fallback
def test_05_trial_nc_abstain():
    sel = make_selector(min_ev=999)  # evidence gate forces abstain
    d = decision_of(sel)
    assert d.nc_abstained is True
    assert d.nc_abstain_reason and "insufficient_evidence" in d.nc_abstain_reason
    assert d.actual_action == "terminal"
    assert d.policy_source == "original"
    assert d.fallback_reason == "nc_abstain"


# TEST-06: trial_nc + low confidence → Original fallback
def test_06_low_confidence():
    # disk_check has no completion evidence → confidence=None → low_confidence
    sel = make_selector(min_conf=0.5)
    d = decision_of(sel, sit="disk_check", cands=("terminal", "read_file"))
    assert d.nc_abstained is True
    assert "low_confidence" in d.nc_abstain_reason
    assert d.actual_action == "terminal"


# TEST-07: trial_nc + insufficient evidence → Original fallback
def test_07_insufficient_evidence():
    sel = make_selector(min_ev=999)
    d = decision_of(sel, sit="search_code_symbol")
    assert d.nc_abstained is True
    assert "insufficient_evidence" in d.nc_abstain_reason
    assert d.actual_action == "terminal"


# TEST-08: trial_nc + NC exception → Original fallback
def test_08_nc_exception():
    sel = make_selector()
    d = decision_of(sel, _inject_failure={"type": "exception", "reason": "boom"})
    assert d.nc_failure is True
    assert d.nc_failure_type == "exception"
    assert d.actual_action == "terminal"
    assert d.fallback_reason == "nc_exception"


# TEST-09: trial_nc + NC timeout → Original fallback
def test_09_nc_timeout():
    sel = make_selector()
    d = decision_of(sel, _inject_failure={"type": "timeout", "reason": "slow"})
    assert d.nc_failure is True
    assert d.nc_failure_type == "timeout"
    assert d.actual_action == "terminal"


# TEST-10: Kill Switch=true → Original unconditionally
def test_10_kill_switch():
    sel = make_selector(kill=True)
    d = decision_of(sel)
    assert d.actual_action == "terminal"
    assert d.fallback_reason == "kill_switch"


# TEST-11: invalid candidate → Original fallback
def test_11_invalid_candidate():
    class BadRec:
        def recommend(self, *a, **k):
            return {"recommendation": "ghost_tool", "confidence": 0.9,
                    "evidence_strength": 5}
    sel = make_selector()
    sel.recommender = BadRec()
    d = decision_of(sel)
    assert d.nc_abstained is True
    assert "invalid_candidate" in d.nc_abstain_reason
    assert d.actual_action == "terminal"


# TEST-12: NC recommendation cannot auto-override actual_action
def test_12_no_implicit_override():
    # shadow mode: NC recommends search_files but actual stays terminal
    sel = make_selector(mode="shadow")
    d = decision_of(sel, sit="search_code_symbol")
    assert d.actual_action == "terminal"  # never auto-equals recommendation
    # trial_original: same
    sel2 = make_selector(mode="trial_original")
    d2 = decision_of(sel2, sit="search_code_symbol")
    assert d2.actual_action == "terminal"


# TEST-13: shadow mode cannot execute NC action
def test_13_shadow_no_nc_exec():
    sel = make_selector(mode="shadow")
    d = decision_of(sel, sit="search_code_symbol")
    assert d.policy_source == "original"
    assert d.actual_action != "search_files"


# TEST-14: assignment determined before outcome
def test_14_assignment_before_outcome():
    sel = make_selector()
    d = decision_of(sel)
    assert d.experiment_assignment in ("original", "nc")
    assert d.experiment_assignment == "nc"  # nc_ratio=1.0
    # outcome written after; must not change assignment
    sel.record_outcome(d, True, True, "task_verifier", "ok")
    recs = [json.loads(l) for l in Path(d.timestamp and sel.config.outcome_log).read_text().splitlines()]
    assert recs[-1]["experiment_assignment"] == "nc"


# TEST-15: task_completed=None not inferred as success
def test_15_none_not_success():
    sel = make_selector()
    d = decision_of(sel)
    sel.record_outcome(d, execution_success=True, task_completed=None,
                       completion_source="unknown", actual_outcome="ran ok")
    recs = [json.loads(l) for l in Path(sel.config.outcome_log).read_text().splitlines()]
    last = recs[-1]
    assert last["execution_success"] is True
    assert last["task_completed"] is None  # NOT inferred True


# TEST-16: outcome cannot mutate assignment
def test_16_outcome_no_reassignment():
    sel = make_selector()
    d = decision_of(sel)
    a1 = d.experiment_assignment
    sel.record_outcome(d, False, False, "task_verifier", "failed")
    d2 = decision_of(sel, task_id=d.task_id)  # same task
    assert d2.experiment_assignment == a1  # stable, not flipped by outcome


# TEST-17: policy version constant within trial task
def test_17_version_stable():
    sel = make_selector()
    d1 = decision_of(sel, task_id="same-task")
    d2 = decision_of(sel, task_id="same-task")
    assert d1.policy_version == d2.policy_version == POLICY_VERSION
    assert d1.experiment_assignment == d2.experiment_assignment


# TEST-18: NC failure never blocks executor (fail-open)
def test_18_nc_failure_does_not_block():
    sel = make_selector()
    d = decision_of(sel, _inject_failure={"type": "exception", "reason": "x"})
    assert d.actual_action == "terminal"  # executor still gets an action
    assert d.fallback_reason == "nc_exception"
    # even Kill Switch + failure → still original
    sel2 = make_selector(kill=True)
    d2 = decision_of(sel2, _inject_failure={"type": "exception", "reason": "x"})
    assert d2.actual_action == "terminal"


# ── extra: experiment assignment distribution sanity ────────────────
def test_assignment_deterministic():
    a = ExperimentAssigner("exp1", nc_ratio=0.5)
    r1 = a.assign("taskA")
    r2 = a.assign("taskA")
    assert r1 == r2  # deterministic per task
    assert r1 in ("original", "nc")


def test_abstain_not_counted_as_success():
    sel = make_selector(min_ev=999)
    d = decision_of(sel)
    assert d.nc_abstained is True
    assert d.actual_action == "terminal"
    # abstain must NOT look like NC success
    assert d.policy_source == "original"
