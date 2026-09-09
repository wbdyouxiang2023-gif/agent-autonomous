#!/usr/bin/env python3
"""NC-08B.2 — Situation-level Ranking Validation (OFFLINE).

Compares per comparable-group:
  MODEL A: execution_success rate ranking
  MODEL B: task_completion rate ranking (True/(True+False), None excluded)

No action-name penalty, no manual weights, no G4 special-casing.
Ties allowed and reported. No production code touched.
"""
import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent
OLD = BASE / "real_completion_observations.jsonl"
NEW = BASE / "situation_observations.jsonl"

old_obs = [json.loads(l) for l in OLD.read_text().strip().splitlines() if l]
new_obs = [json.loads(l) for l in NEW.read_text().strip().splitlines() if l]
assert len(old_obs) == 80
assert len(new_obs) == 50
all_obs = old_obs + new_obs

# ── STEP 1: data audit ────────────────────────────────────────────────
print("=" * 66)
print("STEP 1 — DATA AUDIT")
print("=" * 66)
print(f"OLD={len(old_obs)} NEW={len(new_obs)} TOTAL={len(all_obs)}")
assert all(o.get("provenance") == "real_agent_execution" for o in new_obs), "provenance!"
assert all(o.get("experimental_action_control") is True for o in new_obs), "control flag!"
assert all(o["task_completed"] in (True, False, None) for o in all_obs)
print("provenance ✓  experimental_action_control ✓  task_completed 3-state ✓")

# ── STEP 2: per-group stats ───────────────────────────────────────────
g = defaultdict(lambda: defaultdict(lambda: {"n": 0, "ok": 0, "t": 0, "f": 0}))
for o in all_obs:
    s = g[o["task_type"]][o["selected_action"]]
    s["n"] += 1
    if o["execution_success"]:
        s["ok"] += 1
    if o["task_completed"] is True:
        s["t"] += 1
    elif o["task_completed"] is False:
        s["f"] += 1

# comparable groups: ≥2 actions, each ≥5 valid labels
groups = {}
for tt, acts in g.items():
    if len(acts) >= 2 and all((s["t"] + s["f"]) >= 5 for s in acts.values()):
        rows = []
        for a, s in acts.items():
            exec_rate = s["ok"] / s["n"]
            tc_total = s["t"] + s["f"]
            comp_rate = s["t"] / tc_total if tc_total > 0 else None
            rows.append({"action": a, "exec_rate": exec_rate, "comp_rate": comp_rate,
                         "n": s["n"], "t": s["t"], "f": s["f"]})
        groups[tt] = rows

print(f"\nCOMPARABLE_GROUPS: {len(groups)}")

# ── STEP 3-5: rankings per group ──────────────────────────────────────
print("\n" + "=" * 66)
print("STEP 4/5 — PER-GROUP RANKING (ties preserved)")
print("=" * 66)

ranking_changed = 0
ranking_unchanged = 0
exec_ties = 0
comp_ties = 0
exec_alignment = 0
comp_alignment = 0

for tt in sorted(groups):
    rows = groups[tt]
    # deterministic tie-breaker: action name (lexicographic) — documented, NOT completion
    def key_exec(r):
        return (-r["exec_rate"], -r["n"], r["action"])
    def key_comp(r):
        return (-r["comp_rate"], -r["n"], r["action"]) if r["comp_rate"] is not None else (1, 0, r["action"])

    rows_a = sorted(rows, key=key_exec)
    rows_b = sorted(rows, key=key_comp)

    # top actions
    top_a = rows_a[0]
    top_b = rows_b[0]

    # actual best completion action (real evidence)
    max_comp = max(r["comp_rate"] for r in rows)
    best_comp_actions = sorted([r["action"] for r in rows if r["comp_rate"] == max_comp])
    actual_best = best_comp_actions if len(best_comp_actions) > 1 else best_comp_actions[0]

    # ties
    exec_tie = len([r for r in rows if r["exec_rate"] == top_a["exec_rate"]]) > 1
    comp_tie = len([r for r in rows if r["comp_rate"] == top_b["comp_rate"]]) > 1
    if exec_tie:
        exec_ties += 1
    if comp_tie:
        comp_ties += 1

    # ranking change: top-1 differs
    changed = top_a["action"] != top_b["action"]
    if changed:
        ranking_changed += 1
    else:
        ranking_unchanged += 1

    # alignment: top-1 is (one of) best completion actions
    a_aligned = top_a["action"] in (actual_best if isinstance(actual_best, list) else [actual_best])
    b_aligned = top_b["action"] in (actual_best if isinstance(actual_best, list) else [actual_best])
    if a_aligned:
        exec_alignment += 1
    if b_aligned:
        comp_alignment += 1

    print(f"\nGROUP: {tt}")
    print(f"  {'action':14s} {'n':>3s} {'exec_rate':>9s} {'comp_rate':>9s} {'exec_rank':>9s} {'comp_rank':>9s}")
    for r in sorted(rows, key=lambda x: x["action"]):
        er = f"{r['exec_rate']:.3f}"
        cr = f"{r['comp_rate']:.3f}" if r["comp_rate"] is not None else "N/A"
        ra = rows_a.index(r) + 1
        rb = rows_b.index(r) + 1
        print(f"  {r['action']:14s} {r['n']:3d} {er:>9s} {cr:>9s} {ra:9d} {rb:9d}")
    print(f"  EXECUTION_TOP: {top_a['action']}  COMPLETION_TOP: {top_b['action']}")
    print(f"  ACTUAL_BEST_COMPLETION: {actual_best}  {'CHANGED' if changed else 'SAME'}")

# ── STEP 5 summary ────────────────────────────────────────────────────
print("\n" + "=" * 66)
print("STEP 5 — SUMMARY")
print("=" * 66)
print(f"TOTAL_COMPARABLE_GROUPS: {len(groups)}")
print(f"RANKING_CHANGED_GROUPS: {ranking_changed}")
print(f"RANKING_UNCHANGED_GROUPS: {ranking_unchanged}")
print(f"EXECUTION_TIES: {exec_ties}")
print(f"COMPLETION_TIES: {comp_ties}")
print(f"EXECUTION_ALIGNMENT: {exec_alignment}/{len(groups)}")
print(f"COMPLETION_ALIGNMENT: {comp_alignment}/{len(groups)}")

# ── STEP 7: G4 explicit check ─────────────────────────────────────────
print("\n" + "=" * 66)
print("STEP 7 — G4 VERIFICATION (search_code_symbol)")
print("=" * 66)
g4 = groups.get("search_code_symbol")
if not g4:
    print("STOP: G4 not found!")
else:
    for r in g4:
        print(f"  {r['action']:14s} exec={r['exec_rate']:.3f} comp={r['comp_rate']:.3f}")
    sf = next(r for r in g4 if r["action"] == "search_files")
    term = next(r for r in g4 if r["action"] == "terminal")
    assert sf["exec_rate"] == 1.0 and term["exec_rate"] == 1.0, "exec both 1.0"
    assert sf["comp_rate"] == 1.0 and term["comp_rate"] == 0.0, "comp 1.0 vs 0.0"
    top_b = min(g4, key=lambda r: (-r["comp_rate"], -r["n"], r["action"]))
    assert top_b["action"] == "search_files", f"completion top must be search_files, got {top_b['action']}"
    print("  ✅ G4: exec model cannot distinguish (1.0=1.0); completion model selects search_files (1.0 vs 0.0)")
