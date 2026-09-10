"""NC-08C.3 — Policy V2 Independent Validation Trial.

New task set (no C.1 task_ids), frozen Policy V2, strict A/B assignment.
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


# ── New Task Pool (40 tasks, no C.1 IDs) ─────────────────────────────
def _make_v2_tasks() -> list[dict[str, Any]]:
    """Generate 40 unique tasks across 8 categories."""
    tasks = []
    task_id_counter = [0]

    def next_id():
        task_id_counter[0] += 1
        return f"NC08C3-T{task_id_counter[0]:03d}"

    # Category 1: file_read (5 tasks)
    for i in range(1, 6):
        tasks.append({
            "task_id": next_id(),
            "category": "file_read",
            "raw_input": f"读取文件 data_read_{i}.txt 并返回第一行内容",
            "action": "read_file",
            "arguments": {"path": f"data_read_{i}.txt"},
            "verify": "first_line_equals",
            "verify_args": {"path": f"data_read_{i}.txt", "expected": f"read-line-{i}-header"},
            "prepare": lambda p, n=i: (p / f"data_read_{n}.txt").write_text(
                f"read-line-{n}-header\nextra-{n}\n", encoding="utf-8"
            ),
        })

    # Category 2: file_write (5 tasks) - fixed verifier
    for i in range(1, 6):
        tasks.append({
            "task_id": next_id(),
            "category": "file_write",
            "raw_input": f"创建一个文件 report_write_{i}.txt，内容为 write-content-{i}",
            "action": "write_file",
            "arguments": {"path": f"report_write_{i}.txt", "content": f"write-content-{i}\n"},
            "verify": "file_content_contains",
            "verify_args": {"path": f"report_write_{i}.txt", "needle": f"write-content-{i}"},
            "prepare": None,
        })

    # Category 3: search_files (5 tasks)
    for i in range(1, 6):
        tasks.append({
            "task_id": next_id(),
            "category": "search_files",
            "raw_input": f"搜索包含 keyword_search_{i} 的文件",
            "action": "search_files",
            "arguments": {"pattern": f"keyword_search_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"doc_search_{i}"},
            "prepare": lambda p, n=i: (p / f"doc_search_{n}.txt").write_text(
                f"contains keyword_search_{n} here\n", encoding="utf-8"
            ),
        })

    # Category 4: terminal_safe (5 tasks)
    for i in range(1, 6):
        tasks.append({
            "task_id": next_id(),
            "category": "terminal_safe",
            "raw_input": f"执行命令获取第 {i} 种信息",
            "action": "terminal",
            "arguments": {"command": f"python3 -c 'print({i})'"},
            "verify": "output_contains",
            "verify_args": {"needle": str(i)},
            "prepare": None,
        })

    # Category 5: code_inspect (5 tasks) - KEY CATEGORY
    for i in range(1, 6):
        tasks.append({
            "task_id": next_id(),
            "category": "code_inspect",
            "raw_input": f"检查代码文件 code_v2_{i}.py 的函数定义",
            "action": "search_files",
            "arguments": {"pattern": f"def func_v2_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"code_v2_{i}"},
            "prepare": lambda p, n=i: (p / f"code_v2_{n}.py").write_text(
                f"def func_v2_{n}():\n    return {n}\n\ndef helper_{n}():\n    pass\n",
                encoding="utf-8",
            ),
        })

    # Category 6: file_verify (5 tasks)
    for i in range(1, 6):
        tasks.append({
            "task_id": next_id(),
            "category": "file_verify",
            "raw_input": f"验证文件 check_v2_{i}.txt 存在且非空",
            "action": "read_file",
            "arguments": {"path": f"check_v2_{i}.txt"},
            "verify": "file_exists",
            "verify_args": {"path": f"check_v2_{i}.txt"},
            "prepare": lambda p, n=i: (p / f"check_v2_{n}.txt").write_text(
                f"verification content {n}\n" * 5, encoding="utf-8"
            ),
        })

    # Category 7: code_locator (5 tasks)
    for i in range(1, 6):
        tasks.append({
            "task_id": next_id(),
            "category": "code_locator",
            "raw_input": f"定位符号 find_symbol_v2_{i} 在源码中的位置",
            "action": "search_files",
            "arguments": {"pattern": f"find_symbol_v2_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"source_v2_{i}"},
            "prepare": lambda p, n=i: (p / f"source_v2_{n}.py").write_text(
                f"def find_symbol_v2_{n}():\n    return True\n",
                encoding="utf-8",
            ),
        })

    # Category 8: mixed (5 tasks)
    for i in range(1, 6):
        tasks.append({
            "task_id": next_id(),
            "category": "mixed",
            "raw_input": f"混合任务 {i}: 创建一个临时文件并读取它",
            "action": "write_file" if i % 2 == 0 else "read_file",
            "arguments": {"path": f"mixed_{i}.txt", "content": f"mixed-content-{i}\n"} if i % 2 == 0 else {"path": f"mixed_{i}.txt"},
            "verify": "file_content_contains" if i % 2 == 0 else "file_exists",
            "verify_args": {"path": f"mixed_{i}.txt", "needle": f"mixed-content-{i}"} if i % 2 == 0 else {"path": f"mixed_{i}.txt"},
            "prepare": lambda p, n=i: (p / f"mixed_{n}.txt").write_text(
                f"mixed-content-{n}\n", encoding="utf-8"
            ) if i % 2 == 1 else None,
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Core Trial Execution ────────────────────────────────────────────
def run_trial(
    trial_id: str,
    sandbox_root: Path,
    out_dir: Path,
    n_per_category: int = 5,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run one controlled trial with Policy V2."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sandbox_root.mkdir(parents=True, exist_ok=True)

    # Frozen assigner and selector
    assigner = ExperimentAssigner(trial_id, nc_ratio=FROZEN_NC_RATIO)
    selector = PolicySelector(config=FROZEN_CONFIG, assigner=assigner)
    ex = SandboxExecutor(sandbox_root)
    vf = TaskVerifier(sandbox_root)

    # Build task pool
    pool = _make_v2_tasks()
    # Deterministic shuffle
    seed_uuid = _uuid_lib.UUID(int=seed or hash(trial_id))
    pool.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, f"{seed_uuid}:{t['task_id']}").hex)
    # Take balanced samples per category
    selected: list[dict] = []
    for cat in ("file_read", "file_write", "search_files", "terminal_safe",
                 "code_inspect", "file_verify", "code_locator", "mixed"):
        cat_tasks = [t for t in pool if t["category"] == cat]
        selected.extend(cat_tasks[:n_per_category])
    selected.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, f"{seed_uuid}:{t['task_id']}").hex)

    rows: list[dict] = []
    start_ts = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    for spec in selected:
        tid = spec["task_id"]
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

        # Policy selection (V2 with multi-key evidence retrieval)
        decision = selector.select(sit, cands, orig_action, task_id=tid)
        actual = decision.actual_action

        # Real execution
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

    # Write outputs
    rec_log = out_dir / f"{trial_id}_records.jsonl"
    for r in rows:
        with open(rec_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Compute stats
    def _stats(group):
        xs = [r for r in rows if r["experiment_assignment"] == group]
        if not xs:
            return {"n": 0, "tc_rate": None, "es_rate": None, "abstain": 0, "fallback": 0,
                    "nc_direct": 0, "error": 0}
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
        "original_task_completion": orig["task_completion_rate"],
        "nc_task_completion": nc["task_completion_rate"],
        "original_execution_success": orig["execution_success_rate"],
        "nc_execution_success": nc["execution_success_rate"],
        "abstain_total": orig["abstain"] + nc["abstain"],
        "nc_direct": nc["nc_direct"],
        "nc_fallback": nc["fallback"],
        "errors": errors,
        "rows": rows,
    }
    (out_dir / f"{trial_id}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
