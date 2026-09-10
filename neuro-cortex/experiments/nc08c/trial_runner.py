"""NC-08C.1 — Controlled Policy Trial runner.

Frozen policy: NC-08C.0
No online learning. No threshold modification. No evidence mutation.
Outcomes recorded to trial/<trial_id>/ only.
"""
from __future__ import annotations

import json
import math
import time
import uuid as _uuid_lib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.nc08c.policy_selector import (
    POLICY_VERSION, ExperimentAssigner, PolicyConfig, PolicySelector,
)
from neurocortex.execution_bridge.sandbox import SandboxExecutor, request_for_action
from neurocortex.execution_bridge.verifier import TaskVerifier
from neurocortex.perception.intent_router import detect_coarse_intent


# ── Frozen policy config (must not change during trial) ──────────────
FROZEN_CONFIG = PolicyConfig(
    nc_enable=True, kill_switch=False, policy_mode="trial_nc",
    nc_min_confidence=0.6, nc_min_evidence=3,
)
FROZEN_NC_RATIO = 0.5


# ── Task pool: 60 unique tasks, 6 categories × 10 ────────────────────
def _make_tasks() -> list[dict[str, Any]]:
    """Generate diverse, repeatable sandbox tasks."""
    tasks = []
    # Category 1: file_read (10 variants)
    for i in range(10):
        tasks.append({
            "task_id": f"T-R{i+1:02d}",
            "category": "file_read",
            "raw_input": f"读取文件 data_{i+1}.txt 并返回第一行内容",
            "action": "read_file",
            "arguments": {"path": f"data_{i+1}.txt"},
            "verify": "first_line_equals",
            "verify_args": {"path": f"data_{i+1}.txt", "expected": f"line-{i+1}-header"},
            "prepare": lambda p, n=i+1: (p / f"data_{n}.txt").write_text(f"line-{n}-header\nextra\n", encoding="utf-8"),
        })
    # Category 2: file_write (10 variants)
    for i in range(10):
        tasks.append({
            "task_id": f"T-W{i+1:02d}",
            "category": "file_write",
            "raw_input": f"创建一个文件 report_{i+1}.txt，内容为 line_{i+1}_content",
            "action": "write_file",
            "arguments": {"path": f"report_{i+1}.txt", "content": f"line_{i+1}_content\n"},
            "verify": "file_content_contains",
            "verify_args": {"path": f"report_{i+1}.txt", "needle": "line_1"},
            "prepare": None,
        })
    # Category 3: search_files (10 variants)
    for i in range(10):
        tasks.append({
            "task_id": f"T-S{i+1:02d}",
            "category": "search_files",
            "raw_input": f"搜索包含 keyword_{i+1} 的文件",
            "action": "search_files",
            "arguments": {"pattern": f"keyword_{i+1}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"doc_{i+1}"},
            "prepare": lambda p, n=i+1: (p / f"doc_{n}.txt").write_text(f"contains keyword_{n} here\n", encoding="utf-8"),
        })
    # Category 4: terminal-safe (10 variants)
    for i in range(10):
        tasks.append({
            "task_id": f"T-T{i+1:02d}",
            "category": "terminal_safe",
            "raw_input": f"执行命令获取第 {i+1} 种信息",
            "action": "terminal",
            "arguments": {"command": f"python3 -c 'print({i+1})'"},
            "verify": "output_contains",
            "verify_args": {"needle": str(i+1)},
            "prepare": None,
        })
    # Category 5: code_inspect (10 variants)
    for i in range(10):
        tasks.append({
            "task_id": f"T-C{i+1:02d}",
            "category": "code_inspect",
            "raw_input": f"检查代码文件 code_{i+1}.py 的函数定义",
            "action": "search_files",
            "arguments": {"pattern": f"def func_{i+1}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"code_{i+1}"},
            "prepare": lambda p, n=i+1: (p / f"code_{n}.py").write_text(
                f"def func_{n}():\n    return {n}\n\ndef helper():\n    pass\n",
                encoding="utf-8",
            ),
        })
    # Category 6: file_verify (10 variants)
    for i in range(10):
        tasks.append({
            "task_id": f"T-V{i+1:02d}",
            "category": "file_verify",
            "raw_input": f"验证文件 check_{i+1}.txt 存在且非空",
            "action": "read_file",
            "arguments": {"path": f"check_{i+1}.txt"},
            "verify": "file_exists",
            "verify_args": {"path": f"check_{i+1}.txt"},
            "prepare": lambda p, n=i+1: (p / f"check_{n}.txt").write_text(
                f"verification content {n}\n" * 5, encoding="utf-8"
            ),
        })
    return tasks


# ── Per-task record ──────────────────────────────────────────────────
@dataclass
class TaskRecord:
    trial_id: str
    task_id: str
    category: str
    raw_input: str
    timestamp: str
    experiment_assignment: str
    original_action: str
    actual_action: str
    policy_source: str
    policy_version: str
    nc_recommendation: str | None
    nc_confidence: float | None
    nc_evidence_strength: int | None
    nc_abstained: bool
    nc_abstain_reason: str | None
    fallback_reason: str | None
    execution_success: bool | None
    task_completed: bool | None
    completion_source: str
    actual_outcome: str
    error_message: str
    latency_s: float

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ── Core trial execution ────────────────────────────────────────────
def run_trial(
    trial_id: str,
    sandbox_root: Path,
    out_dir: Path,
    n_per_category: int = 5,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run one controlled trial. Returns summary dict."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sandbox_root.mkdir(parents=True, exist_ok=True)

    # Frozen assigner
    assigner = ExperimentAssigner(trial_id, nc_ratio=FROZEN_NC_RATIO)
    selector = PolicySelector(config=FROZEN_CONFIG, assigner=assigner)
    ex = SandboxExecutor(sandbox_root)
    vf = TaskVerifier(sandbox_root)

    # Build task pool
    pool = _make_tasks()
    # Deterministic shuffle
    seed_uuid = _uuid_lib.UUID(int=seed or hash(trial_id))
    pool.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, f"{seed_uuid}:{t['task_id']}").hex)
    # Take balanced samples per category
    selected: list[dict] = []
    for cat in ("file_read", "file_write", "search_files", "terminal_safe",
                 "code_inspect", "file_verify"):
        cat_tasks = [t for t in pool if t["category"] == cat]
        selected.extend(cat_tasks[:n_per_category])
    # Ensure even split via re-shuffle
    selected.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, f"{seed_uuid}:{t['task_id']}").hex)

    rows: list[dict] = []
    start_ts = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    for spec in selected:
        tid = f"{trial_id}-{spec['task_id']}"
        # Prepare sandbox files
        if spec.get("prepare"):
            try:
                spec["prepare"](sandbox_root)
            except Exception as e:
                errors.append(f"prepare {tid}: {e}")

        # Assignment (BEFORE execution)
        assignment = assigner.assign(tid)
        orig_action = spec["action"]
        cands = ["read_file", "write_file", "search_files", "terminal"]
        sit = spec["raw_input"]

        ts = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()

        # Policy selection
        decision = selector.select(sit, cands, orig_action, task_id=tid)
        actual = decision.actual_action

        # Real execution
        exec_spec = dict(spec)
        exec_spec["action"] = actual
        result = ex.execute(request_for_action(
            actual, spec.get("arguments") or {}, request_id=f"{trial_id}-{tid}"
        ))

        # Verify
        verified = vf.verify(spec, result)

        latency = time.monotonic() - t0

        rec = TaskRecord(
            trial_id=trial_id, task_id=tid, category=spec["category"],
            raw_input=sit, timestamp=ts,
            experiment_assignment=decision.experiment_assignment,
            original_action=orig_action, actual_action=actual,
            policy_source=decision.policy_source,
            policy_version=decision.policy_version,
            nc_recommendation=decision.nc_recommendation,
            nc_confidence=decision.nc_confidence,
            nc_evidence_strength=decision.nc_evidence_strength,
            nc_abstained=decision.nc_abstained,
            nc_abstain_reason=decision.nc_abstain_reason,
            fallback_reason=decision.fallback_reason,
            execution_success=result.success,
            task_completed=verified.task_completed,
            completion_source=verified.completion_source,
            actual_outcome=(result.output or result.error or result.status)[:300],
            error_message=result.error,
            latency_s=round(latency, 4),
        )
        selector.record_outcome(
            decision,
            execution_success=bool(result.success) if result.success is not None else False,
            task_completed=verified.task_completed,
            completion_source=verified.completion_source,
            actual_outcome=rec.actual_outcome,
            error_message=rec.error_message,
        )
        rows.append(rec.to_dict())

    # Write outputs (append-only, never overwrite existing trial)
    dec_log = out_dir / "decisions.jsonl"
    out_log = out_dir / "outcomes.jsonl"
    run_log = out_dir / f"{trial_id}_records.jsonl"
    for r in rows:
        with open(dec_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(out_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(run_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Compute stats
    def _stats(group):
        xs = [r for r in rows if r["experiment_assignment"] == group]
        if not xs:
            return {"n": 0, "tc": None, "es": None, "abstain": 0, "fallback": 0,
                    "nc_direct": 0, "error": 0, "timeout": 0, "latency_avg": 0}
        n = len(xs)
        tc_known = [r["task_completed"] for r in xs if r["task_completed"] is not None]
        es_known = [r["execution_success"] for r in xs if r["execution_success"] is not None]
        tc_rate = sum(1 for v in tc_known if v) / len(tc_known) if tc_known else None
        es_rate = sum(1 for v in es_known if v) / len(es_known) if es_known else None
        return {
            "n": n,
            "task_completion_rate": tc_rate,
            "execution_success_rate": es_rate,
            "abstain": sum(1 for r in xs if r["nc_abstained"]),
            "fallback": sum(1 for r in xs if r["fallback_reason"]),
            "nc_direct": sum(1 for r in xs if r["policy_source"] == "neurocortex"),
            "error": sum(1 for r in xs if r["error_message"]),
            "timeout": sum(1 for r in xs if "timeout" in (r["error_message"] or "").lower()),
            "latency_avg": round(sum(r["latency_s"] for r in xs) / n, 4),
        }

    orig = _stats("original")
    nc = _stats("nc")

    summary = {
        "trial_id": trial_id,
        "policy_version": POLICY_VERSION,
        "start_timestamp": start_ts,
        "total_tasks": len(rows),
        "n_original": orig["n"],
        "n_nc": nc["n"],
        "original_task_completion": orig["task_completion_rate"],
        "nc_task_completion": nc["task_completion_rate"],
        "original_execution_success": orig["execution_success_rate"],
        "nc_execution_success": nc["execution_success_rate"],
        "original_error_rate": orig["error"] / orig["n"] if orig["n"] else None,
        "nc_error_rate": nc["error"] / nc["n"] if nc["n"] else None,
        "abstain_total": orig["abstain"] + nc["abstain"],
        "nc_direct": nc["nc_direct"],
        "nc_fallback": nc["fallback"],
        "original_abstain": orig["abstain"],
        "latency_orig_avg": orig["latency_avg"],
        "latency_nc_avg": nc["latency_avg"],
        "errors": errors,
        "rows": rows,
    }
    (out_dir / f"{trial_id}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
