"""NC-08C.1 frozen-policy controlled trial on REAL sandbox actions.

Does not mutate ranking / candidate generation / thresholds.
Outcomes go to experiments/nc08c/trial/ only.
"""
from __future__ import annotations

import json
from pathlib import Path

from experiments.nc08c.policy_selector import (
    POLICY_VERSION, ExperimentAssigner, PolicyConfig, PolicySelector,
)
from experiments.nc08c.real_loop import default_tasks, run_task


def run_trial(sandbox: Path, out_dir: Path, experiment_id: str = "nc08c1-sandbox") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = PolicyConfig(
        nc_enable=True, kill_switch=False, policy_mode="trial_nc",
        nc_min_confidence=0.6, nc_min_evidence=5,
        decision_log=str(out_dir / "decision.jsonl"),
        outcome_log=str(out_dir / "outcome.jsonl"),
    )
    assigner = ExperimentAssigner(experiment_id, nc_ratio=0.5)
    selector = PolicySelector(config=cfg, assigner=assigner)
    (sandbox / "sample.py").write_text("def quality():\n    return True\n", encoding="utf-8")

    rows = []
    for spec in default_tasks():
        original = spec["action"]
        cands = ["read_file", "write_file", "search_files", "terminal"]
        if original not in cands:
            cands.append(original)
        sit = spec.get("raw_input") or spec["task_id"]
        decision = selector.select(sit, cands, original, task_id=spec["task_id"])
        exec_spec = dict(spec)
        exec_spec["action"] = decision.actual_action
        if decision.actual_action != original:
            exec_spec.setdefault("arguments", {})
        rec = run_task(exec_spec, sandbox, out_dir / "real_loop.jsonl")
        selector.record_outcome(
            decision,
            execution_success=bool(rec.execution_success),
            task_completed=rec.task_completed,
            completion_source=rec.completion_source,
            actual_outcome=rec.actual_outcome,
            error_message=rec.error_message,
        )
        rows.append({
            "task_id": spec["task_id"],
            "assignment": decision.experiment_assignment,
            "policy_source": decision.policy_source,
            "policy_version": decision.policy_version,
            "original_action": original,
            "actual_action": decision.actual_action,
            "nc_recommendation": decision.nc_recommendation,
            "nc_abstained": decision.nc_abstained,
            "fallback_reason": decision.fallback_reason,
            "execution_success": rec.execution_success,
            "task_completed": rec.task_completed,
        })

    def _rate(group, field):
        xs = [r for r in rows if r["assignment"] == group]
        if not xs:
            return None, 0
        known = [r[field] for r in xs if r[field] is not None]
        if not known:
            return None, len(xs)
        return sum(1 for v in known if v) / len(known), len(xs)

    orig_tc, n_orig = _rate("original", "task_completed")
    nc_tc, n_nc = _rate("nc", "task_completed")
    summary = {
        "policy_version": POLICY_VERSION,
        "experiment_id": experiment_id,
        "n": len(rows),
        "n_original": n_orig,
        "n_nc": n_nc,
        "original_task_completion": orig_tc,
        "nc_task_completion": nc_tc,
        "abstain": sum(1 for r in rows if r["nc_abstained"]),
        "nc_direct": sum(1 for r in rows if r["policy_source"] == "neurocortex"),
        "fallback": sum(1 for r in rows if r["fallback_reason"]),
        "rows": rows,
    }
    (out_dir / "trial_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
