"""NC-08C.5 Revised — Capability Boundary with True Discrimination.

Key insight: To show NC value, we need situations where:
- Original would choose Action A (naive/intuitive)
- NC evidence supports Action B (learned from history)
- Action B has better completion rate than Action A
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


# ── Evidence Levels ──────────────────────────────────────────────────
class EvidenceLevel:
    LEVEL_0 = "no_evidence"
    LEVEL_1 = "evidence_no_change"
    LEVEL_2 = "evidence_changes_rank"
    LEVEL_3 = "evidence_changes_action"
    LEVEL_4 = "action_improves_outcome"


# ── Task Design: True Discriminative Scenarios ────────────────────────
def _make_discriminative_tasks() -> list[dict[str, Any]]:
    """Generate tasks where Original and NC should choose differently."""
    tasks = []
    counter = [0]

    def next_id():
        counter[0] += 1
        return f"NC08C5-T{counter[0]:03d}"

    # ===== TYPE A: Code quality check (should use search_files, not terminal) =====
    # Situation: "检查代码质量" → code_check → terminal (WRONG per evidence)
    # But evidence shows search_files is better for code_locator
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "code_quality_search",
            "raw_input": f"检查代码质量并搜索func_{i}函数的实现",
            "action": "terminal",  # Original will likely choose terminal
            "arguments": {"command": f"python3 -c 'print(1)'"},
            "verify": "search_hit",  # Must find the function
            "verify_args": {"needle": f"func_{i}"},
            "prepare": lambda p, n=i: (p / f"code_q_{n}.py").write_text(
                f"def func_{n}():\n    return {n}\n\nclass Helper{n}:\n    pass\n",
                encoding="utf-8"
            ),
            "injection_type": "terminal_vs_search",
            "trap": "terminal_succeeds_but_doesnt_find_function",
            "expected_original": "terminal",  # Naive choice
            "expected_nc": "search_files",    # Evidence-based choice
        })

    # ===== TYPE B: Code location with misleading verb =====
    # Situation uses "检查" which triggers code_check → terminal
    # But task is actually about locating symbols → should use search_files
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "misleading_verb",
            "raw_input": f"检查函数 check_symbol_{i} 的定义位置",
            "action": "terminal",
            "arguments": {"command": f"python3 -c 'print({i})'"},
            "verify": "search_hit",
            "verify_args": {"needle": f"check_symbol_{i}"},
            "prepare": lambda p, n=i: (p / f"source_m_{n}.py").write_text(
                f"def check_symbol_{n}():\n    return True\n\ndef other_{n}():\n    pass\n",
                encoding="utf-8"
            ),
            "injection_type": "verb_misleading",
            "trap": "terminal_output_irrelevant",
            "expected_original": "terminal",
            "expected_nc": "search_files",
        })

    # ===== TYPE C: Clear search intent (control) =====
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "clear_search",
            "raw_input": f"搜索包含 keyword_control_{i} 的文件",
            "action": "search_files",
            "arguments": {"pattern": f"keyword_control_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"doc_ctrl_{i}"},
            "prepare": lambda p, n=i: (p / f"doc_ctrl_{n}.txt").write_text(
                f"contains keyword_control_{n} here\n", encoding="utf-8"
            ),
            "injection_type": "control",
            "trap": None,
            "expected_original": "search_files",
            "expected_nc": "search_files",
        })

    # ===== TYPE D: Evidence-poor (should ABSTAIN) =====
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "evidence_poor",
            "raw_input": f"分析一个全新的量子计算架构 quantum_arch_{i}",
            "action": "read_file",
            "arguments": {"path": f"nonexistent_arch_{i}.txt"},
            "verify": "file_exists",
            "verify_args": {"path": f"nonexistent_arch_{i}.txt"},
            "prepare": None,
            "injection_type": "no_evidence",
            "trap": "file_not_found",
            "expected_original": "read_file",
            "expected_nc": "ABSTAIN",
        })

    # ===== TYPE E: Terminal-successful but wrong outcome =====
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "terminal_success_wrong",
            "raw_input": f"执行命令输出系统版本信息",
            "action": "terminal",
            "arguments": {"command": "python3 --version"},
            "verify": "output_contains",
            "verify_args": {"needle": "Python"},
            "prepare": None,
            "injection_type": "terminal_success",
            "trap": None,
            "expected_original": "terminal",
            "expected_nc": "terminal",
        })

    # ===== TYPE F: File read with verification =====
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "file_read_verify",
            "raw_input": f"读取文件 data_read_{i}.txt 并验证内容",
            "action": "read_file",
            "arguments": {"path": f"data_read_{i}.txt"},
            "verify": "file_content_contains",
            "verify_args": {"path": f"data_read_{i}.txt", "needle": f"read-content-{i}"},
            "prepare": lambda p, n=i: (p / f"data_read_{n}.txt").write_text(
                f"read-content-{n}\n", encoding="utf-8"
            ),
            "injection_type": "control",
            "trap": None,
            "expected_original": "read_file",
            "expected_nc": "read_file",
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
    injection_type: str
    trap: str | None
    expected_original: str
    expected_nc: str
    evidence_level: str

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

    pool = _make_discriminative_tasks()
    seed_uuid = _uuid_lib.UUID(int=seed or hash(trial_id))
    pool.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, f"{seed_uuid}:{t['task_id']}").hex)

    selected: list[dict] = []
    for cat in ("code_quality_search", "misleading_verb", "clear_search",
                 "evidence_poor", "terminal_success_wrong", "file_read_verify"):
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

        # Use action-specific arguments
        args = spec.get("arguments") or {}
        if actual == "search_files" and "pattern" not in args:
            # Extract pattern from raw_input if not provided
            import re
            # Try to extract function name or keyword
            match = re.search(r'(func_\d+|check_symbol_\d+|\w+)', spec["raw_input"])
            if match:
                args = {"pattern": match.group(1)}
        elif actual == "read_file" and "path" not in args:
            import re
            match = re.search(r'(\w+\.txt|\w+\.py)', spec["raw_input"])
            if match:
                args = {"path": match.group(1)}
        elif actual == "terminal" and "command" not in args:
            args = {"command": "echo ok"}

        result = ex.execute(request_for_action(
            actual, args, request_id=f"{trial_id}-{tid}"
        ))

        verified = vf.verify(spec, result)
        latency = time.monotonic() - t0

        # Determine evidence level (will be updated after we know task_completed)
        if decision.nc_abstained:
            ev_level = EvidenceLevel.LEVEL_0 if not decision.nc_evidence_strength else EvidenceLevel.LEVEL_1
        elif decision.nc_recommendation != orig_action:
            ev_level = EvidenceLevel.LEVEL_3  # Changed action - will verify outcome later
        elif decision.nc_evidence_strength:
            ev_level = EvidenceLevel.LEVEL_1
        else:
            ev_level = EvidenceLevel.LEVEL_0

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
            injection_type=spec.get("injection_type", "none"),
            trap=spec.get("trap"),
            expected_original=spec.get("expected_original", "unknown"),
            expected_nc=spec.get("expected_nc", "unknown"),
            evidence_level=ev_level,
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
            "evidence_levels": {
                "LEVEL_0": sum(1 for r in xs if r["evidence_level"] == EvidenceLevel.LEVEL_0),
                "LEVEL_1": sum(1 for r in xs if r["evidence_level"] == EvidenceLevel.LEVEL_1),
                "LEVEL_2": sum(1 for r in xs if r["evidence_level"] == EvidenceLevel.LEVEL_2),
                "LEVEL_3": sum(1 for r in xs if r["evidence_level"] == EvidenceLevel.LEVEL_3),
                "LEVEL_4": sum(1 for r in xs if r["evidence_level"] == EvidenceLevel.LEVEL_4),
            },
        }

    orig = _stats("original")
    nc = _stats("nc")

    # Action difference analysis
    action_diffs = sum(1 for r in rows if r["original_action"] != r["actual_action"] and r["policy_source"] == "neurocortex")

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
        "action_differences": action_diffs,
        "nc_evidence_levels": nc.get("evidence_levels", {}),
        "errors": errors,
        "rows": rows,
    }
    (out_dir / f"{trial_id}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
