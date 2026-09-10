"""NC-08C.5 — Capability Boundary Trial (Revised).

Key insight: To show NC value, we need situations where:
1. Evidence supports a DIFFERENT action than the naive choice
2. Or evidence is insufficient → NC should ABSTAIN
3. Or evidence changes ranking significantly
"""
from __future__ import annotations

import json
import re
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


FROZEN_CONFIG = PolicyConfig(
    nc_enable=True, kill_switch=False, policy_mode="trial_nc",
    nc_min_confidence=0.6, nc_min_evidence=3,
)
FROZEN_NC_RATIO = 0.5


class EvidenceLevel:
    LEVEL_0 = "no_evidence"
    LEVEL_1 = "evidence_no_change"
    LEVEL_2 = "evidence_changes_rank"
    LEVEL_3 = "evidence_changes_action"
    LEVEL_4 = "action_improves_outcome"


def _make_tasks() -> list[dict]:
    """Generate tasks with clear evidence patterns."""
    tasks = []
    counter = [0]

    def next_id():
        counter[0] += 1
        return f"NC08C5-T{counter[0]:03d}"

    # Group 1: Code symbol search (10) - Evidence supports search_files
    # Situation triggers code_locator → search_files (correct)
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "code_symbol",
            "raw_input": f"搜索代码中 find_func_{i} 的定义位置",
            "expected_action": "search_files",
            "arguments": {"pattern": f"find_func_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"src_code_{i}"},
            "prepare": lambda p, n=i: (p / f"src_code_{n}.py").write_text(
                f"def find_func_{n}():\n    return {n}\n", encoding="utf-8"
            ),
            "injection": "evidence_correct",
        })

    # Group 2: File read (10) - Control
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "file_read",
            "raw_input": f"读取文件 readme_{i}.md 的内容",
            "expected_action": "read_file",
            "arguments": {"path": f"readme_{i}.md"},
            "verify": "file_content_contains",
            "verify_args": {"path": f"readme_{i}.md", "needle": f"content-{i}"},
            "prepare": lambda p, n=i: (p / f"readme_{n}.md").write_text(
                f"content-{n}\n", encoding="utf-8"
            ),
            "injection": "control",
        })

    # Group 3: Terminal info (10) - Control
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "terminal_info",
            "raw_input": f"获取第 {i} 个系统信息",
            "expected_action": "terminal",
            "arguments": {"command": f"python3 -c 'print({i})'"},
            "verify": "output_contains",
            "verify_args": {"needle": str(i)},
            "prepare": None,
            "injection": "control",
        })

    # Group 4: Evidence-poor (10) - Should ABSTAIN
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "evidence_poor",
            "raw_input": f"分析量子计算架构 quantum_impl_{i} 的实现",
            "expected_action": "read_file",
            "arguments": {"path": f"quantum_{i}.txt"},
            "verify": "file_exists",
            "verify_args": {"path": f"quantum_{i}.txt"},
            "prepare": None,  # File doesn't exist
            "injection": "no_evidence",
        })

    # Group 5: File search (10) - Control
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "file_search",
            "raw_input": f"搜索包含 pattern_{i} 的配置文件",
            "expected_action": "search_files",
            "arguments": {"pattern": f"pattern_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"config_{i}"},
            "prepare": lambda p, n=i: (p / f"config_{n}.json").write_text(
                f'{{"pattern_{n}": true}}\n', encoding="utf-8"
            ),
            "injection": "control",
        })

    # Group 6: Ambiguous situation (10) - Mix of evidence and no evidence
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "ambiguous",
            "raw_input": f"查看 project_{i} 的代码结构",
            "expected_action": "search_files",
            "arguments": {"pattern": f"class Project{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"project_{i}.py"},
            "prepare": lambda p, n=i: (p / f"project_{n}.py").write_text(
                f"class Project{n}:\n    pass\n\ndef helper():\n    pass\n",
                encoding="utf-8"
            ),
            "injection": "ambiguous",
        })

    return tasks


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
    injection: str
    evidence_level: str

    def to_dict(self):
        return asdict(self)


def run_trial(trial_id: str, sandbox_root: Path, out_dir: Path,
              n_per_category: int = 10, seed: int | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    sandbox_root.mkdir(parents=True, exist_ok=True)

    assigner = ExperimentAssigner(trial_id, nc_ratio=FROZEN_NC_RATIO)
    selector = PolicySelector(config=FROZEN_CONFIG, assigner=assigner)
    ex = SandboxExecutor(sandbox_root)
    vf = TaskVerifier(sandbox_root)

    pool = _make_tasks()
    seed_uuid = _uuid_lib.UUID(int=seed or hash(trial_id))
    pool.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS,
                                              f"{seed_uuid}:{t['task_id']}").hex)

    selected: list[dict] = []
    for cat in ("code_symbol", "file_read", "terminal_info", "evidence_poor",
                 "file_search", "ambiguous"):
        cat_tasks = [t for t in pool if t["category"] == cat]
        selected.extend(cat_tasks[:n_per_category])
    selected.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS,
                                                  f"{seed_uuid}:{t['task_id']}").hex)

    rows: list[dict] = []
    errors: list[str] = []

    for spec in selected:
        tid = spec["task_id"]
        if spec.get("prepare"):
            try:
                spec["prepare"](sandbox_root)
            except Exception as e:
                errors.append(f"prepare {tid}: {e}")

        assignment = assigner.assign(tid)
        orig_action = spec["expected_action"]
        cands = ["read_file", "write_file", "search_files", "terminal"]
        sit = spec["raw_input"]

        ts = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()

        decision = selector.select(sit, cands, orig_action, task_id=tid)
        actual = decision.actual_action

        # Get arguments
        args = spec.get("arguments") or {}
        if actual == "search_files" and "pattern" not in args:
            match = re.search(r'(find_func_\d+|pattern_\d+|class Project\d+)', sit)
            if match:
                args = {"pattern": match.group(1)}
        elif actual == "read_file" and "path" not in args:
            match = re.search(r'(readme_\d+\.md|quantum_\d+\.txt|project_\d+\.py)', sit)
            if match:
                args = {"path": match.group(1)}

        result = ex.execute(request_for_action(
            actual, args, request_id=f"{trial_id}-{tid}"
        ))

        verified = vf.verify(spec, result)
        latency = time.monotonic() - t0

        # Determine evidence level
        if decision.nc_abstained:
            ev_level = "LEVEL_0"
        elif decision.nc_recommendation != orig_action:
            ev_level = "LEVEL_3"
        elif decision.nc_evidence_strength:
            ev_level = "LEVEL_1"
        else:
            ev_level = "LEVEL_0"

        rec = TaskRecord(
            trial_id=trial_id, task_id=tid, category=spec["category"],
            raw_input=sit, timestamp=ts,
            experiment_assignment=assignment,
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
            injection=spec.get("injection", "none"),
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

    action_diffs = sum(1 for r in rows
                       if r["original_action"] != r["actual_action"]
                       and r["policy_source"] == "neurocortex")

    summary = {
        "trial_id": trial_id,
        "policy_version": POLICY_VERSION,
        "policy_variant": "V2",
        "start_timestamp": datetime.now(timezone.utc).isoformat(),
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
