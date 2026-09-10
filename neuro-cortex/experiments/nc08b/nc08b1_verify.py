#!/usr/bin/env python3
"""NC-08B.1 — verify comparable groups across 80 (old) + 50 (new) obs."""
import json
from collections import defaultdict, Counter
from pathlib import Path

OLD = Path("/tmp/agent-autonomous/neuro-cortex/experiments/nc08b/real_completion_observations.jsonl")
NEW = Path("/tmp/nc08b_work/situation_observations.jsonl")

old_obs = [json.loads(l) for l in OLD.read_text().strip().splitlines() if l]
new_obs = [json.loads(l) for l in NEW.read_text().strip().splitlines() if l]

print(f"OLD: {len(old_obs)} | NEW: {len(new_obs)} | TOTAL: {len(old_obs) + len(new_obs)}")

# 新增数据审计
print("\n=== NEW DATA AUDIT ===")
prov_ok = all(o.get("provenance") == "real_agent_execution" for o in new_obs)
ctrl = all(o.get("experimental_action_control") is True for o in new_obs)
tc_ok = all(o["task_completed"] in (True, False, None) for o in new_obs)
print(f"PROVENANCE_ALL_REAL: {prov_ok}")
print(f"ALL_EXPERIMENTAL_CONTROL: {ctrl}")
print(f"TASK_COMPLETED_VALID: {tc_ok}")
print(f"TRUE={sum(1 for o in new_obs if o['task_completed'] is True)} "
      f"FALSE={sum(1 for o in new_obs if o['task_completed'] is False)} "
      f"UNKNOWN={sum(1 for o in new_obs if o['task_completed'] is None)}")

# 合并后按 task_type（situation）× action 统计
print("\n=== SITUATION × ACTION (merged) ===")
g = defaultdict(lambda: defaultdict(lambda: {"n": 0, "t": 0, "f": 0}))
for o in old_obs + new_obs:
    s = g[o["task_type"]][o["selected_action"]]
    s["n"] += 1
    if o["task_completed"] is True:
        s["t"] += 1
    elif o["task_completed"] is False:
        s["f"] += 1

comparable_groups = 0
for tt in sorted(g):
    acts = g[tt]
    valid_ok = all((s["t"] + s["f"]) >= 5 for s in acts.values())
    multi = len(acts) >= 2
    if multi and valid_ok:
        comparable_groups += 1
    for a, s in sorted(acts.items()):
        tc = s["t"] + s["f"]
        cr = s["t"] / tc if tc > 0 else None
        cr_s = f"{cr:.3f}" if cr is not None else "N/A"
        print(f"  {tt:24s} {a:14s} n={s['n']:3d} T={s['t']:3d} F={s['f']:3d} comp={cr_s}")

print(f"\nCOMPARABLE_GROUPS (≥2 actions, each ≥5 valid): {comparable_groups}")
