#!/usr/bin/env python3
"""NeuroCortex neuron CLI — status / record / rank / decide (shadow mode).

All operations are SHADOW-ONLY: they read Action Learning statistics and
produce rankings/decisions, but NEVER change the actual decision behavior
of Hermes. Recording requires an explicit success=true|false flag; unknown
is never accepted as learning input.

Usage:
  neuron.py status
  neuron.py record --situation "..." --action read_file --success true [--intent inspect]
  neuron.py rank --situation "..." [--intent inspect]
  neuron.py decide --situation "..." --actions read_file,search [--intent inspect]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(os.environ.get(
    "NEUROCORTEX_REPO",
    "/home/user/workspace/agent-autonomous/neuro-cortex",
)).resolve()
sys.path.insert(0, str(REPO / "src"))


def _engine(stats_path: Path):
    from neurocortex.action_learning import (
        ActionLearningConfig, ActionLearningEngine,
    )
    cfg = ActionLearningConfig(enabled=True, shadow_only=True, statistics_path=str(stats_path))
    return ActionLearningEngine(cfg)


def _sit(situation: str, intent: str):
    from neurocortex.action_learning import ActionLearningSituation
    return ActionLearningSituation(intent=intent or "unknown", raw_input=situation, situation_completeness="partial")


def cmd_status(stats_path: Path) -> int:
    eng = _engine(stats_path)
    snap = eng.store.snapshot()
    print(json.dumps({
        "statistics_keys": len(snap),
        "semantic_transfer_enabled": eng.config.semantic_transfer_enabled,
        "action_learning_enabled": eng.config.enabled,
        "shadow_only": eng.config.shadow_only,
        "statistics_path": str(stats_path),
        "entries": snap,
    }, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_record(stats_path: Path, situation: str, action: str, success: str, intent: str) -> int:
    eng = _engine(stats_path)
    from neurocortex.action_learning import ActionLearningOutcome
    if success not in ("true", "false"):
        print(f"error: success must be 'true' or 'false', got '{success}' (UNKNOWN never updates)", file=sys.stderr)
        return 2
    ok = eng.record_outcome(_sit(situation, intent), action, ActionLearningOutcome(success=(success == "true")))
    if not ok:
        print("error: record rejected (engine disabled or invalid input)", file=sys.stderr)
        return 1
    print(json.dumps({"recorded": True, "situation": situation, "intent": intent or "unknown",
                      "action": action, "success": success}))
    return 0


def cmd_rank(stats_path: Path, situation: str, intent: str) -> int:
    eng = _engine(stats_path)
    ranked = eng.rank_actions(_sit(situation, intent), ["read_file", "search", "respond", "code_edit"])
    out = []
    for r in ranked:
        out.append({
            "action": r["action_key"],
            "score": r["score"],
            "estimated_success": r["estimated_success"],
            "support": r["support_count"],
            "success": r["success_count"],
            "failure": r["failure_count"],
            "match_level": r["match_level"],
            "evidence_status": r["evidence_status"],
            "borrowed_from": r["borrowed_from"],
        })
    print(json.dumps({"situation": situation, "intent": intent or "unknown", "ranking": out},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_decide(stats_path: Path, situation: str, actions: str, intent: str) -> int:
    eng = _engine(stats_path)
    from neurocortex.policy import PolicyConfig, PolicyEngine
    pol = PolicyEngine(PolicyConfig(enabled=True, shadow_only=True, log_path=str(stats_path.parent / "policy_shadow.jsonl")))
    action_list = [a.strip() for a in actions.split(",") if a.strip()]
    decision = pol.choose_action(_sit(situation, intent), action_list, engine=eng)
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="NeuroCortex neuron CLI (shadow mode)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status")
    p_status.set_defaults(fn=cmd_status)

    p_rec = sub.add_parser("record")
    p_rec.add_argument("--situation", required=True)
    p_rec.add_argument("--action", required=True)
    p_rec.add_argument("--success", required=True, choices=["true", "false"])
    p_rec.add_argument("--intent", default="")
    p_rec.set_defaults(fn=cmd_record)

    p_rank = sub.add_parser("rank")
    p_rank.add_argument("--situation", required=True)
    p_rank.add_argument("--intent", default="")
    p_rank.set_defaults(fn=cmd_rank)

    p_dec = sub.add_parser("decide")
    p_dec.add_argument("--situation", required=True)
    p_dec.add_argument("--actions", required=True)
    p_dec.add_argument("--intent", default="")
    p_dec.set_defaults(fn=cmd_decide)

    args = ap.parse_args()

    stats_path = Path(os.environ.get("NEUROCORTEX_STATS", str(Path.home() / ".neurocortex_action_statistics.json")))
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    if args.cmd == "status":
        return cmd_status(stats_path)
    if args.cmd == "record":
        return cmd_record(stats_path, args.situation, args.action, args.success, args.intent)
    if args.cmd == "rank":
        return cmd_rank(stats_path, args.situation, args.intent)
    if args.cmd == "decide":
        return cmd_decide(stats_path, args.situation, args.actions, args.intent)
    return 2


if __name__ == "__main__":
    sys.exit(main())
