"""NC-08C.4 — Discriminative Policy Trial with Hard Negatives.

Uses NC-08B evidence patterns to design tasks where:
- Original might choose suboptimal action
- NC V2 should choose evidence-supported action
- Completion rates differ by action choice
"""
from __future__ import annotations

import json
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


# ── Frozen Policy V2 Config ──────────────────────────────────────────
FROZEN_CONFIG = PolicyConfig(
    nc_enable=True, kill_switch=False, policy_mode="trial_nc",
    nc_min_confidence=0.6, nc_min_evidence=3,
)
FROZEN_NC_RATIO = 0.5


# ── Task Pool: 60 tasks with discriminative potential ────────────────
def _make_v3_tasks() -> list[dict[str, Any]]:
    """Generate 60 tasks designed to discriminate policies."""
    tasks = []
    counter = [0]

    def next_id():
        counter[0] += 1
        return f"NC08C4-T{counter[0]:03d}"

    # Category 1: code_locator_hard (10 tasks) - KEY DISCRIMINATIVE
    # Evidence: search_code_symbol → search_files=100%, terminal=0%
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "code_locator_hard",
            "raw_input": f"定位函数 find_symbol_{i} 在源码中的位置",
            "action": "search_files",  # Original should also choose this
            "arguments": {"pattern": f"find_symbol_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"source_hard_{i}"},
            "prepare": lambda p, n=i: (p / f"source_hard_{n}.py").write_text(
                f"def find_symbol_{n}():\n    return True\n\ndef other_{n}():\n    pass\n",
                encoding="utf-8",
            ),
            "hard_negative": True,  # Mark as hard negative
        })

    # Category 2: code_inspect (10 tasks) - from C.2/C.3 lessons
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "code_inspect",
            "raw_input": f"检查代码文件 inspect_{i}.py 的所有函数定义",
            "action": "search_files",
            "arguments": {"pattern": f"def func_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"inspect_{i}"},
            "prepare": lambda p, n=i: (p / f"inspect_{n}.py").write_text(
                f"def func_{n}():\n    return {n}\n\ndef helper_{n}():\n    pass\n",
                encoding="utf-8",
            ),
            "hard_negative": False,
        })

    # Category 3: file_search (10 tasks) - control
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "file_search",
            "raw_input": f"搜索包含 keyword_{i} 的文件",
            "action": "search_files",
            "arguments": {"pattern": f"keyword_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"doc_{i}"},
            "prepare": lambda p, n=i: (p / f"doc_{n}.txt").write_text(
                f"contains keyword_{n} here\n", encoding="utf-8"
            ),
            "hard_negative": False,
        })

    # Category 4: file_read (10 tasks) - control
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "file_read",
            "raw_input": f"读取文件 data_read_{i}.txt 的内容",
            "action": "read_file",
            "arguments": {"path": f"data_read_{i}.txt"},
            "verify": "file_content_contains",
            "verify_args": {"path": f"data_read_{i}.txt", "needle": f"read-content-{i}"},
            "prepare": lambda p, n=i: (p / f"data_read_{n}.txt").write_text(
                f"read-content-{n}\n", encoding="utf-8"
            ),
            "hard_negative": False,
        })

    # Category 5: terminal_safe (10 tasks) - control
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "terminal_safe",
            "raw_input": f"执行命令输出数字 {i}",
            "action": "terminal",
            "arguments": {"command": f"python3 -c 'print({i})'"},
            "verify": "output_contains",
            "verify_args": {"needle": str(i)},
            "prepare": None,
            "hard_negative": False,
        })

    # Category 6: exact_answer (10 tasks) - potential hard negative
    # Evidence: exact_answer → terminal=100%, exact_answer_fail → terminal=0%
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "exact_answer",
            "raw_input": f"获取系统第 {i} 种信息",
            "action": "terminal",
            "arguments": {"command": "python3 -c 'import sys; print(sys.version.split()[0])'"},
            "verify": "output_contains",
            "verify_args": {"needle": "3."},
            "prepare": None,
            "hard_negative": i <= 3,  # First 3 are hard negatives
        })

    return tasks


# ── Per-task Record ──────────────────────────────────────────────────
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
    hard_negative: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Core Trial Execution ────────────────────────────────────────────
def run_trial(
    trial_id: str,
    sandbox_root: Path,
    out_dir: Path,
    n_per_category: int = 10,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run discriminative A/B trial."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sandbox_root.mkdir(parents=True, exist_ok=True)

    assigner = ExperimentAssigner(trial_id, nc_ratio=FROZEN_NC_RATIO)
    selector = PolicySelector(config=FROZEN_CONFIG, assigner=assigner)
    ex = SandboxExecutor(sandbox_root)
    vf = TaskVerifier(sandbox_root)

    pool = _make_v3_tasks()
    seed_uuid = _uuid_lib.UUID(int=seed or hash(trial_id))
    pool.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, f"{seed_uuid}:{t['task_id']}").hex)

    selected: list[dict] = []
    for cat in ("code_locator_hard", "code_inspect", "file_search", "file_read", "terminal_safe", "exact_answer"):
        cat_tasks = [t for t in pool if t["category"] == cat]
        selected.extend(cat_tasks[:n_per_category])
    selected.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, f"{seed_uuid}:{t['task_id']}").hex)

    rows: list[dict] = []
    start_ts = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    for spec in selected:
        tid = spec["task_id"]
        if spec.get("prepare"):
            try:
                spec["prepare"](sandbox_root)
            except Exception as e:
                errors.append(f"prepare {tid}: {e}")

        assignment = assigner.assign(tid)
        orig_action = spec["action"]
        cands = ["read_file", "write_file", "search_files", "terminal"]
        sit = spec["raw_input"]

        ts = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()

        decision = selector.select(sit, cands, orig_action, task_id=tid)
        actual = decision.actual_action

        result = ex.execute(request_for_action(
            actual, spec.get("arguments") or {}, request_id=f"{trial_id}-{tid}"
        ))

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
            hard_negative=spec.get("hard_negative", False),
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

    rec_log = out_dir / f"{trial_id}_records.jsonl"
    for r in rows:
        with open(rec_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _stats(group):
        xs = [r for r in rows if r["experiment_assignment"] == group]
        if not xs:
            return {"n": 0}
        n = len(xs)
        tc = [r["task_completed"] for r in xs if r["task_completed"] is not None]
        es = [r["execution_success"] for r in xs if r["execution_success"] is not None]
        return {
            "n": n,
            "tc_rate": sum(1 for v in tc if v) / len(tc) if tc else None,
            "es_rate": sum(1 for v in es if v) / len(es) if es else None,
            "abstain": sum(1 for r in xs if r["nc_abstained"]),
            "fallback": sum(1 for r in xs if r["fallback_reason"]),
            "nc_direct": sum(1 for r in xs if r["policy_source"] == "neurocortex"),
            "error": sum(1 for r in xs if r["error_message"]),
            "hard_negative_n": sum(1 for r in xs if r.get("hard_negative")),
            "hard_negative_tc": sum(1 for r in xs if r.get("hard_negative") and r["task_completed"] is True),
        }

    orig = _stats("original")
    nc = _stats("nc")

    summary = {
        "trial_id": trial_id,
        "policy_version": POLICY_VERSION,
        "policy_variant": "V2",
        "start_timestamp": start_ts,
        "total_tasks": len(rows),
        "n_original": orig["n"],
        "n_nc": nc["n"],
        "original_task_completion": orig["tc_rate"],
        "nc_task_completion": nc["tc_rate"],
        "original_execution_success": orig["es_rate"],
        "nc_execution_success": nc["es_rate"],
        "abstain_total": orig["abstain"] + nc["abstain"],
        "nc_direct": nc["nc_direct"],
        "nc_fallback": nc["fallback"],
        "hard_negative_n": orig.get("hard_negative_n", 0) + nc.get("hard_negative_n", 0),
        "hard_negative_orig_tc": sum(1 for r in rows if r["experiment_assignment"]=="original" and r.get("hard_negative") and r["task_completed"]) if orig.get("hard_negative_n") else None,
        "hard_negative_nc_tc": sum(1 for r in rows if r["experiment_assignment"]=="nc" and r.get("hard_negative") and r["task_completed"]) if nc.get("hard_negative_n") else None,
        "errors": errors,
        "rows": rows,
    }
    (out_dir / f"{trial_id}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
