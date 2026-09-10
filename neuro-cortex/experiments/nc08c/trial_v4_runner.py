"""NC-08C.5 — Capability Boundary & Failure Injection Experiment.

Tests where NC's experience actually changes decisions AND improves outcomes.
Uses failure injection to create discriminative scenarios.
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


# ── Evidence Levels for Analysis ─────────────────────────────────────
class EvidenceLevel:
    LEVEL_0 = "no_evidence"           # No evidence retrieved
    LEVEL_1 = "evidence_no_change"    # Evidence exists but doesn't change action
    LEVEL_2 = "evidence_changes_rank" # Evidence changes ranking but not final action
    LEVEL_3 = "evidence_changes_action" # Evidence changes final action
    LEVEL_4 = "action_improves_outcome" # Changed action improves completion


# ── Task Design: Failure Injection Scenarios ─────────────────────────
def _make_injection_tasks() -> list[dict[str, Any]]:
    """Generate 60 tasks with built-in failure modes."""
    tasks = []
    counter = [0]

    def next_id():
        counter[0] += 1
        return f"NC08C5-T{counter[0]:03d}"

    # ===== GROUP 1: Code Symbol Location (10 tasks) - HARD NEGATIVE =====
    # Evidence shows: search_files=100%, terminal=0% for search_code_symbol
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "code_symbol_location",
            "raw_input": f"定位函数 locate_symbol_{i} 在源码中的位置",
            "action": "search_files",  # Correct action per evidence
            "arguments": {"pattern": f"locate_symbol_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"source_inject_{i}"},
            "prepare": lambda p, n=i: (p / f"source_inject_{n}.py").write_text(
                f"def locate_symbol_{n}():\n    return True\n\ndef helper_{n}():\n    pass\n",
                encoding="utf-8",
            ),
            "injection_type": "hard_negative",
            "trap": "terminal_success_but_wrong_outcome",  # terminal executes but doesn't find symbol
        })

    # ===== GROUP 2: File Search with Hidden Failure (10 tasks) =====
    # Tasks where search might succeed but verifier is strict
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "file_search_strict",
            "raw_input": f"搜索包含 exact_keyword_{i} 的配置文件",
            "action": "search_files",
            "arguments": {"pattern": f"exact_keyword_{i}"},
            "verify": "file_content_contains",  # Strict: must contain exact string
            "verify_args": {"path": f"config_{i}.json", "needle": f'"exact_keyword_{i}": true'},
            "prepare": lambda p, n=i: (p / f"config_{n}.json").write_text(
                f'{{"exact_keyword_{n}": true, "other": "data"}}\n',
                encoding="utf-8"
            ),
            "injection_type": "verifier_strictness",
            "trap": None,
        })

    # ===== GROUP 3: Ambiguous Situations (10 tasks) =====
    # Tasks that could be classified differently
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "ambiguous_situation",
            "raw_input": f"检查一下 project_{i} 的代码质量并找出问题",
            "action": "search_files",
            "arguments": {"pattern": f"class Project{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"project_{i}.py"},
            "prepare": lambda p, n=i: (p / f"project_{n}.py").write_text(
                f"class Project{n}:\n    def __init__(self):\n        pass\n\ndef helper():\n    pass\n",
                encoding="utf-8"
            ),
            "injection_type": "classification_ambiguity",
            "trap": None,
        })

    # ===== GROUP 4: Evidence-Poor Situations (10 tasks) =====
    # Tasks where NO evidence exists - should ABSTAIN
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "evidence_poor",
            "raw_input": f"分析一个全新的架构模式 architecture_pattern_{i}",
            "action": "read_file",  # Will fail because file doesn't exist
            "arguments": {"path": f"nonexistent_{i}.txt"},
            "verify": "file_exists",
            "verify_args": {"path": f"nonexistent_{i}.txt"},
            "prepare": None,  # Intentionally no file
            "injection_type": "no_evidence",
            "trap": "file_not_found",
        })

    # ===== GROUP 5: Multi-Step Verification (10 tasks) =====
    # Tasks requiring both search and read
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "multi_step_verify",
            "raw_input": f"找到函数 multi_func_{i} 的定义并验证它存在",
            "action": "search_files",
            "arguments": {"pattern": f"def multi_func_{i}"},
            "verify": "search_hit",
            "verify_args": {"needle": f"multi_step_{i}.py"},
            "prepare": lambda p, n=i: (p / f"multi_step_{n}.py").write_text(
                f"def multi_func_{n}():\n    return {n}\n\nclass Helper{n}:\n    pass\n",
                encoding="utf-8"
            ),
            "injection_type": "multi_step",
            "trap": None,
        })

    # ===== GROUP 6: Misleading Terminal (10 tasks) =====
    # Tasks where terminal seems reasonable but fails verification
    for i in range(1, 11):
        tasks.append({
            "task_id": next_id(),
            "category": "misleading_terminal",
            "raw_input": f"使用命令行输出第 {i} 个测试数据",
            "action": "terminal",
            "arguments": {"command": f"python3 -c 'print(\"test_data_{i}\")'"},
            "verify": "output_contains",
            "verify_args": {"needle": f"test_data_{i}"},
            "prepare": None,
            "injection_type": "terminal_misleading",
            "trap": "output_format_mismatch",  # Terminal outputs with quotes, verifier expects exact
        })

    return tasks


# ── Per-task Record with Evidence Tracking ───────────────────────────
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
    evidence_level: str  # LEVEL_0 to LEVEL_4

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Evidence Level Analyzer ──────────────────────────────────────────
def analyze_evidence_level(
    situation: str,
    candidates: list[str],
    original_action: str,
    actual_action: str,
    nc_recommendation: str | None,
    nc_confidence: float | None,
    nc_evidence_strength: int | None,
    task_completed: bool | None,
    agg_dict: dict,
) -> str:
    """Determine evidence utilization level."""
    from experiments.nc08b.shadow.shadow_adapter import (
        _classify_to_task_type, _get_all_related_tts, rank_by_completion, _load_evidence
    )

    # Get ranking with evidence
    _, sit_map = _load_evidence()
    ranking = rank_by_completion(situation, candidates, agg_dict, sit_map)

    # Check if evidence was retrieved
    tt_match = _classify_to_task_type(situation)
    related_tts = _get_all_related_tts(situation, _classify_to_task_type) if tt_match else []

    has_evidence = nc_evidence_strength and nc_evidence_strength > 0

    if not has_evidence:
        return EvidenceLevel.LEVEL_0

    # Check if evidence changed the action
    if nc_recommendation != original_action:
        if task_completed:
            return EvidenceLevel.LEVEL_4  # Changed action AND improved outcome
        else:
            return EvidenceLevel.LEVEL_3  # Changed action but failed
    elif has_evidence:
        return EvidenceLevel.LEVEL_1  # Evidence exists but didn't change action

    return EvidenceLevel.LEVEL_0


# ── Core Trial Execution ────────────────────────────────────────────
def run_trial(
    trial_id: str,
    sandbox_root: Path,
    out_dir: Path,
    n_per_category: int = 10,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run failure injection A/B trial."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sandbox_root.mkdir(parents=True, exist_ok=True)

    assigner = ExperimentAssigner(trial_id, nc_ratio=FROZEN_NC_RATIO)
    selector = PolicySelector(config=FROZEN_CONFIG, assigner=assigner)
    ex = SandboxExecutor(sandbox_root)
    vf = TaskVerifier(sandbox_root)

    # Load evidence for analysis
    from experiments.nc08b.shadow.shadow_adapter import _load_evidence
    agg_dict, sit_map = _load_evidence()

    pool = _make_injection_tasks()
    seed_uuid = _uuid_lib.UUID(int=seed or hash(trial_id))
    pool.sort(key=lambda t: _uuid_lib.uuid5(_uuid_lib.NAMESPACE_DNS, f"{seed_uuid}:{t['task_id']}").hex)

    selected: list[dict] = []
    for cat in ("code_symbol_location", "file_search_strict", "ambiguous_situation",
                 "evidence_poor", "multi_step_verify", "misleading_terminal"):
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

        # Analyze evidence level
        ev_level = analyze_evidence_level(
            sit, cands, orig_action, actual,
            decision.nc_recommendation, decision.nc_confidence,
            decision.nc_evidence_strength, verified.task_completed, agg_dict
        )

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

    # Compute stats
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
        "nc_evidence_levels": nc.get("evidence_levels", {}),
        "errors": errors,
        "rows": rows,
    }
    (out_dir / f"{trial_id}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
