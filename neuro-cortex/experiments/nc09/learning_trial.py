"""NC-09 — Learning → Adaptation Trial.

Minimal controlled experiment to verify:
  REAL OUTCOME → EXPERIENCE → RANKING CHANGE → ACTION ADAPTATION → BETTER OUTCOME
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid as _uuid_lib
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from neurocortex.action_learning.bridge import ActionLearningBridge
from neurocortex.action_learning.config import ActionLearningConfig
from neurocortex.action_learning.engine import ActionLearningEngine, StatisticsStore
from neurocortex.action_learning.schema import (
    ActionLearningCandidate,
    ActionLearningOutcome,
    ActionLearningSituation,
)
from neurocortex.execution_bridge.sandbox import SandboxExecutor, request_for_action
from neurocortex.execution_bridge.verifier import TaskVerifier


# ── Experiment Configuration ─────────────────────────────────────────
EXPERIMENT_ID = "NC09-Learning-Adaptation"
STATS_PATH = Path("/tmp/nc09_action_statistics.json")
MEMORY_PATH = Path("/tmp/nc09_memory.jsonl")
OUT_DIR = Path(__file__).parent.parent / "nc09" / "trial"


# ── Task Design ──────────────────────────────────────────────────────
# Each task family has:
# - Situation S (varies slightly per round)
# - Action A (fails in Round 1, should be avoided in Round 2)
# - Action B (succeeds, should be preferred in Round 2)

TASK_FAMILIES = [
    {
        "family_id": "code_symbol",
        "round1_situation": "查找函数 find_symbol_1 在源代码中的位置",
        "round2_situation": "定位符号 find_symbol_2 在源码里的位置",
        "action_a": "terminal",  # Wrong: empty command
        "action_b": "search_files",  # Correct: finds the symbol
        "args_a": {"command": ""},  # Empty = failure
        "args_b": {"pattern": "find_symbol"},
        "verify": "search_hit",
        "verify_args": {"needle": "source_sym"},
        "prepare": lambda p: (p / "source_sym.py").write_text(
            "def find_symbol():\n    return True\n", encoding="utf-8"
        ),
    },
    {
        "family_id": "file_content",
        "round1_situation": "读取配置文件 config_data_1.json 的内容",
        "round2_situation": "打开并查看 config_data_2.json 文件",
        "action_a": "terminal",  # Wrong: can't read file content directly
        "action_b": "read_file",  # Correct: reads file
        "args_a": {"command": "echo test"},
        "args_b": {"path": "config_data_1.json"},
        "verify": "file_content_contains",
        "verify_args": {"path": "config_data_1.json", "needle": "config-data"},
        "prepare": lambda p: (p / "config_data_1.json").write_text(
            '{"config-data": "test"}\n', encoding="utf-8"
        ),
    },
    {
        "family_id": "search_keyword",
        "round1_situation": "搜索包含 keyword_search_1 的代码文件",
        "round2_situation": "在源码中查找 keyword_search_2",
        "action_a": "read_file",  # Wrong: reads single file
        "action_b": "search_files",  # Correct: searches all files
        "args_a": {"path": "dummy.txt"},
        "args_b": {"pattern": "keyword_search"},
        "verify": "search_hit",
        "verify_args": {"needle": "doc_search"},
        "prepare": lambda p: (p / "doc_search.py").write_text(
            "# contains keyword_search here\n", encoding="utf-8"
        ),
    },
]


@dataclass
class TrialRecord:
    trial_id: str
    round: int
    task_id: str
    family_id: str
    situation: str
    selected_action: str
    action_score: float | None
    evidence_strength: int | None
    execution_success: bool | None
    task_completed: bool | None
    outcome: str
    timestamp: str
    before_ranking: str
    after_ranking: str

    def to_dict(self):
        return asdict(self)


def run_round(
    round_num: int,
    sandbox: Path,
    engine: ActionLearningEngine,
    bridge: ActionLearningBridge,
) -> list[TrialRecord]:
    """Run one round of experiments."""
    records = []
    seed_uuid = _uuid_lib.UUID(int=round_num * 1000000 + abs(hash(EXPERIMENT_ID)) % (1 << 128))

    for family in TASK_FAMILIES:
        # Round-specific situation
        if round_num == 1:
            situation = family["round1_situation"]
        else:
            situation = family["round2_situation"]

        task_id = f"NC09-R{round_num}-{family['family_id']}-{uuid.uuid4().hex[:4]}"

        # Prepare sandbox
        family["prepare"](sandbox)

        # Create candidates
        candidates = [
            ActionLearningCandidate(action_type=family["action_a"], strategy=family["action_a"]),
            ActionLearningCandidate(action_type=family["action_b"], strategy=family["action_b"]),
        ]

        # Get situation using V4 classifier
        from neurocortex.perception.classifier_v4 import classify_v4
        classification = classify_v4(situation)
        
        sit = ActionLearningSituation(
            intent=classification.task_type or "general",
            task_type=classification.task_type,
            raw_input=situation,
            situation_completeness="full",
        )

        # Record before ranking
        before_ranking = bridge.engine.rank_actions(sit, candidates, [])
        before_str = ", ".join(f"{r['action_key']}:{r.get('score') or 0:.3f}" for r in before_ranking)

        # Rank with bridge (uses learned statistics)
        ranked = bridge.rank_candidates(candidates, situation=sit, raw_input=situation)
        ranked_keys = [c.action_key if hasattr(c, 'action_key') else c for c in ranked]

        # Select top action
        selected_action = ranked_keys[0] if ranked_keys else family["action_a"]

        # Execute
        executor = SandboxExecutor(sandbox)
        verifier = TaskVerifier(sandbox)

        args = family["args_a"] if selected_action == family["action_a"] else family["args_b"]
        result = executor.execute(request_for_action(
            selected_action, args, request_id=task_id
        ))

        verified = verifier.verify(family, result)

        # Record after ranking
        after_ranking = bridge.engine.rank_actions(sit, candidates, [])
        after_str = ", ".join(f"{r['action_key']}:{r.get('score') or 0:.3f}" for r in after_ranking)

        rec = TrialRecord(
            trial_id=EXPERIMENT_ID,
            round=round_num,
            task_id=task_id,
            family_id=family["family_id"],
            situation=situation,
            selected_action=selected_action,
            action_score=before_ranking[0].get("score") if before_ranking else None,
            evidence_strength=sum(1 for r in before_ranking if r.get("support_count", 0) > 0),
            execution_success=result.success,
            task_completed=verified.task_completed,
            outcome=result.output or result.error or result.status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            before_ranking=before_str,
            after_ranking=after_str,
        )
        records.append(rec)

        # Record outcome to learning bridge
        if result.success is not None:
            outcome = ActionLearningOutcome(
                success=bool(result.success),
                task_completion=verified.task_completed,
                actual_outcome=rec.outcome[:200],
            )
            engine.record_outcome(sit, ActionLearningCandidate(action_type=selected_action, strategy=selected_action), outcome)

    return records


def main():
    """Run the NC-09 learning experiment."""
    print(f"=== NC-09 LEARNING → ADAPTATION TRIAL ===\n")
    print(f"Experiment ID: {EXPERIMENT_ID}")
    print(f"Stats path: {STATS_PATH}")
    print()

    # Clean slate
    if STATS_PATH.exists():
        STATS_PATH.unlink()
    if MEMORY_PATH.exists():
        MEMORY_PATH.unlink()
    (OUT_DIR).mkdir(parents=True, exist_ok=True)
    sandbox = OUT_DIR / "sandbox"
    sandbox.mkdir(exist_ok=True)

    # Initialize learning components
    config = ActionLearningConfig(
        enabled=True,
        shadow_only=False,  # Enable actual ranking changes
        statistics_path=STATS_PATH,
    )
    engine = ActionLearningEngine(config)
    bridge = ActionLearningBridge(config, engine)

    print("ROUND 1 — COLD START (no prior experience)")
    print("-" * 50)
    round1_records = run_round(1, sandbox, engine, bridge)
    for r in round1_records:
        status = "✅" if r.task_completed else "❌"
        print(f"{status} {r.family_id:15s} action={r.selected_action:12s} completed={r.task_completed}")

    print("\nROUND 2 — AFTER LEARNING (experience from Round 1)")
    print("-" * 50)
    round2_records = run_round(2, sandbox, engine, bridge)
    for r in round2_records:
        status = "✅" if r.task_completed else "❌"
        print(f"{status} {r.family_id:15s} action={r.selected_action:12s} completed={r.task_completed}")

    # Save records
    all_records = round1_records + round2_records
    rec_file = OUT_DIR / "NC09_records.jsonl"
    with open(rec_file, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")

    # Compute metrics
    print("\n" + "=" * 50)
    print("RESULTS ANALYSIS")
    print("=" * 50)

    # Group by family
    by_family = {}
    for r in all_records:
        by_family.setdefault(r.family_id, []).append(r)

    adaptation_count = 0
    correct_adaptation = 0
    negative_transfer = 0

    for family_id, recs in by_family.items():
        r1 = recs[0]
        r2 = recs[1]

        print(f"\n{family_id}:")
        print(f"  Round 1: action={r1.selected_action} completed={r1.task_completed}")
        print(f"  Round 2: action={r2.selected_action} completed={r2.task_completed}")

        # Check adaptation
        if r1.selected_action != r2.selected_action:
            adaptation_count += 1
            print(f"  → ACTION CHANGED: {r1.selected_action} → {r2.selected_action}")

            # Check if correct
            if r2.selected_action == TASK_FAMILIES[[f["family_id"] for f in TASK_FAMILIES].index(family_id)]["action_b"]:
                correct_adaptation += 1
                print(f"  → CORRECT ADAPTATION ✅")
            else:
                negative_transfer += 1
                print(f"  → WRONG ADAPTATION ❌")
        else:
            print(f"  → No change (same action)")

    # Summary
    print(f"\n" + "=" * 50)
    print(f"SUMMARY")
    print("=" * 50)
    print(f"Total tasks: {len(all_records)}")
    print(f"Adaptations: {adaptation_count}/{len(TASK_FAMILIES)}")
    print(f"Correct adaptations: {correct_adaptation}/{adaptation_count}" if adaptation_count else "Correct adaptations: 0/0")
    print(f"Negative transfer: {negative_transfer}")
    print(f"\nRound 1 completion: {sum(1 for r in round1_records if r.task_completed)}/{len(round1_records)}")
    print(f"Round 2 completion: {sum(1 for r in round2_records if r.task_completed)}/{len(round2_records)}")

    # Check statistics file
    if STATS_PATH.exists():
        stats = json.loads(STATS_PATH.read_text())
        print(f"\nStatistics entries: {len(stats)}")
        for key, val in list(stats.items())[:5]:
            print(f"  {key}: success={val.get('success_count')} fail={val.get('failure_count')}")

    return all_records


if __name__ == "__main__":
    main()
