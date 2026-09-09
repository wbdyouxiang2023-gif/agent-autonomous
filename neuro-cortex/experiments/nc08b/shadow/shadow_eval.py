#!/usr/bin/env python3
"""NC-08B.3 — Shadow Evaluation Runner (limited, offline).

Replays REAL historical observations through the Shadow Adapter:
  - original_action = the action that was actually taken (from data)
  - task_completion = the real completion label from the same record
  - NC recommendation = completion-based ranking from OTHER evidence

This is OBSERVATIONAL. NC never changes actual_action. The runner
verifies the shadow safety invariant on every record and produces
disagreement stats.

NOT causal. NOT policy trial. NC's recommended action is never executed.
"""
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent  # experiments/nc08b
sys.path.insert(0, str(Path(__file__).parent))  # shadow/ for adapter

from shadow_adapter import ShadowAdapter, FLAG, SHADOW_LOG, MODEL_VERSION  # noqa: E402

# ════════════════════════════════════════════════════════════════
# Shadow mode control — runner forces ON only for this offline eval
# ════════════════════════════════════════════════════════════════
os.environ["NC_SHADOW_MODE"] = "on"
adapter = ShadowAdapter(enabled=True)

# Load real observations (read-only)
obs = []
for p in (BASE / "real_completion_observations.jsonl", BASE / "situation_observations.jsonl"):
    for line in p.read_text().strip().splitlines():
        if line:
            obs.append(json.loads(line))

print(f"Loaded {len(obs)} real observations")
print(f"Shadow mode: {adapter.is_enabled} | model: {MODEL_VERSION}")

# Clear any pre-existing shadow log for a clean eval? NO — append-only,
# but we record eval window. Use a fresh log for this run.
if SHADOW_LOG.exists():
    SHADOW_LOG.unlink()  # fresh eval window (shadow log is experimental artifact)

import random
random.seed(42)
RUN_LIMIT = 30

# candidate actions per task_type (all actions seen in that situation)
sit_actions = defaultdict(set)
for o in obs:
    sit_actions[o["task_type"]].add(o["selected_action"])
multi_situations = {tt for tt, acts in sit_actions.items() if len(acts) >= 2}
print(f"Multi-action situations: {sorted(multi_situations)}")

# Re-sample from MULTI-ACTION situations only (candidate>=2 guaranteed)
multi_obs = [o for o in obs if o["task_type"] in multi_situations]
by_type = defaultdict(list)
for o in multi_obs:
    by_type[o["task_completed"] is True, o["task_completed"] is False, o["task_completed"] is None].append(o)
per = 10
sample = (random.sample(by_type.get((True, False, False), []), min(per, len(by_type.get((True, False, False), [])))) +
          random.sample(by_type.get((False, True, False), []), min(per, len(by_type.get((False, True, False), [])))) +
          random.sample(by_type.get((False, False, True), []), min(per, len(by_type.get((False, False, True), [])))))
if len(sample) < RUN_LIMIT:
    rest = [o for o in multi_obs if o not in sample]
    sample += random.sample(rest, RUN_LIMIT - len(sample))
sample = sample[:RUN_LIMIT]
print(f"Multi-sampled {len(sample)} (T={sum(1 for o in sample if o['task_completed'] is True)}, "
      f"F={sum(1 for o in sample if o['task_completed'] is False)}, "
      f"N={sum(1 for o in sample if o['task_completed'] is None)})")

stats = {
    "total": 0, "rec_available": 0, "disagreement": 0,
    "both_same": 0, "both_different": 0, "unknown_completion": 0,
    "original_completion": {"T": 0, "F": 0, "N": 0},
}

ran = 0
for o in sample:
    if ran >= RUN_LIMIT:
        break
    tt = o["task_type"]
    candidates = sorted(sit_actions.get(tt, {o["selected_action"]}))
    if len(candidates) < 2:
        continue  # only situations with ≥2 candidate actions are meaningful
    orig = o["selected_action"]
    completion = o["task_completed"]

    rec = adapter.recommend(tt, candidates, orig)
    if rec is None:
        continue
    ran += 1
    stats["total"] += 1

    nc_top = rec["nc_recommended_action"]
    # NC recommendation available (has score != None)
    if nc_top is not None and rec["nc_scores"].get(nc_top) is not None:
        stats["rec_available"] += 1

    # safety: actual action must remain original
    assert rec["original_action"] == orig, "SHADOW VIOLATED actual action!"

    disagree = nc_top != orig
    if disagree:
        stats["disagreement"] += 1
        stats["both_different"] += 1
    else:
        stats["both_same"] += 1

    if completion is True:
        stats["original_completion"]["T"] += 1
    elif completion is False:
        stats["original_completion"]["F"] += 1
    else:
        stats["unknown_completion"] += 1
        stats["original_completion"]["N"] += 1

print(f"\n=== SHADOW EVAL (limit={RUN_LIMIT}, ran={ran}) ===")
print(f"TOTAL_SHADOW_TASKS: {stats['total']}")
print(f"NC_RECOMMENDATION_AVAILABLE: {stats['rec_available']}")
print(f"NC_VS_ORIGINAL_DISAGREEMENT: {stats['disagreement']}")
print(f"BOTH_SAME: {stats['both_same']}")
print(f"BOTH_DIFFERENT: {stats['both_different']}")
print(f"UNKNOWN_COMPLETION: {stats['unknown_completion']}")
oc = stats["original_completion"]
oc_total = oc["T"] + oc["F"]
print(f"ORIGINAL_ACTION_COMPLETION: T={oc['T']} F={oc['F']} rate={oc['T']/oc_total:.3f}" if oc_total else "ORIGINAL_ACTION_COMPLETION: N/A")
print(f"NC_SHADOW_ALIGNMENT: computed in detail below")

# Disagreement detail — observational shadow indication only
print(f"\n=== DISAGREEMENT CASES (NC != original) ===")
disagreements = []
with open(SHADOW_LOG) as f:
    for line in f:
        r = json.loads(line)
        if r["nc_recommended_action"] != r["original_action"]:
            disagreements.append(r)
for r in disagreements[:10]:
    print(f"  sit={r['situation'][:20]:22s} orig={r['original_action']:12s} "
          f"nc_top={r['nc_recommended_action']:12s} "
          f"orig_rate={r.get('original_completion_rate')} "
          f"nc_scores={ {k: (round(v,3) if v is not None else None) for k,v in r['nc_scores'].items()} }")

print(f"\nDISAGREEMENT_COUNT: {len(disagreements)}")
print("COUNTERFACTUAL_LIMITATION: NC-recommended action NOT executed; "
      "observational shadow indication only, not causal improvement.")
print(f"\nShadow log: {SHADOW_LOG}")
