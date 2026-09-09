#!/usr/bin/env python3
"""NC-08B — Completion-based Action Learning (OFFLINE experiment).

Reads only the 80 real observations. Does NOT touch production engine,
NC-07A ranking, or policy. Produces two independent rankings:

  MODEL A — execution_success baseline
  MODEL B — task_completion based

Reports per-action and per task_type×action stats, ranking comparison,
safe-but-ineffective detection, and observational replay.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).parent / "real_completion_observations.jsonl"
OBS = [json.loads(l) for l in DATA.read_text().strip().splitlines() if l]

# ════════════════════════════════════════════════════════════════
# STEP 1 — Schema / provenance audit
# ════════════════════════════════════════════════════════════════
print("=" * 66)
print("STEP 1 — DATA SCHEMA / PROVENANCE AUDIT")
print("=" * 66)
req = ["task_id", "timestamp", "task_description", "selected_action",
       "execution_success", "task_completed", "completion_source",
       "actual_outcome", "provenance"]
missing = [o["task_id"] for o in OBS if any(k not in o for k in req)]
prov_ok = all(o.get("provenance") == "real_agent_execution" for o in OBS)
tc_ok = all(o["task_completed"] in (True, False, None) for o in OBS)
print(f"MISSING_FIELDS: {len(missing)}")
print(f"PROVENANCE_ALL_REAL: {prov_ok}")
print(f"TASK_COMPLETED_VALID: {tc_ok}")

# success→completion 推断检查
sf = [o for o in OBS if not o["execution_success"]]
sf_not_false = [o["task_id"] for o in sf if o["task_completed"] is not False]
print(f"SUCCESS=False 但 completed 非 False: {len(sf_not_false)} {'✅ 无推断' if not sf_not_false else sf_not_false}")

# action_name → completion 硬编码检查（同一 action 应有混合的 completion）
by_action_tc = defaultdict(set)
for o in OBS:
    by_action_tc[o["selected_action"]].add(o["task_completed"])
hardcoded = {a: v for a, v in by_action_tc.items() if len(v) == 1 and None not in v and len([o for o in OBS if o['selected_action']==a]) >= 3}
print(f"ACTION_COMPLETION_VARIETY: { {a: sorted(str(x) for x in v) for a, v in by_action_tc.items()} }")
print(f"POTENTIAL_HARDCODED: {hardcoded if hardcoded else '无（所有 action 有混合完成状态）'}")

swc = [o for o in OBS if o["execution_success"] and o["task_completed"] is False]
print(f"SUCCESS_WITHOUT_COMPLETION: {len(swc)}")

# ════════════════════════════════════════════════════════════════
# STEP 2 — Action 分布 + 双指标
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print("STEP 2 — ACTION STATISTICS (execution vs completion)")
print("=" * 66)
acts = defaultdict(lambda: {"n": 0, "exec_ok": 0, "tc_true": 0, "tc_false": 0, "tc_none": 0})
for o in OBS:
    a = acts[o["selected_action"]]
    a["n"] += 1
    if o["execution_success"]:
        a["exec_ok"] += 1
    if o["task_completed"] is True:
        a["tc_true"] += 1
    elif o["task_completed"] is False:
        a["tc_false"] += 1
    else:
        a["tc_none"] += 1

print(f"{'action':14s} {'n':>3s} {'exec_ok':>7s} {'exec_rate':>9s} {'tc_T':>4s} {'tc_F':>4s} {'tc_N':>4s} {'completion_rate':>15s}")
action_stats = {}
for a in sorted(acts):
    s = acts[a]
    exec_rate = s["exec_ok"] / s["n"]
    tc_total = s["tc_true"] + s["tc_false"]
    comp_rate = s["tc_true"] / tc_total if tc_total > 0 else None
    action_stats[a] = {"n": s["n"], "exec_rate": exec_rate, "comp_rate": comp_rate,
                        "tc_true": s["tc_true"], "tc_false": s["tc_false"]}
    comp_s = f"{comp_rate:.3f}" if comp_rate is not None else "   N/A"
    print(f"{a:14s} {s['n']:3d} {s['exec_ok']:7d} {exec_rate:9.3f} {s['tc_true']:4d} {s['tc_false']:4d} {s['tc_none']:4d} {comp_s:>15s}")

# ════════════════════════════════════════════════════════════════
# STEP 3 — 两个 Ranking
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print("STEP 3 — MODEL A (execution) vs MODEL B (completion) RANKING")
print("=" * 66)
# Model A: 按 execution_success_rate 排序
model_a = sorted(action_stats.items(), key=lambda kv: (kv[1]["exec_rate"], kv[1]["n"]), reverse=True)
# Model B: 按 completion_rate 排序（None 排除）
model_b = sorted(
    [(a, s) for a, s in action_stats.items() if s["comp_rate"] is not None],
    key=lambda kv: (kv[1]["comp_rate"], kv[1]["n"]), reverse=True)
print("MODEL A (execution_success):")
for a, s in model_a:
    print(f"  {a:14s} exec_rate={s['exec_rate']:.3f} (n={s['n']})")
print("MODEL B (task_completion):")
for a, s in model_b:
    print(f"  {a:14s} comp_rate={s['comp_rate']:.3f} (n={s['n']}, tc={s['tc_true']}/{s['tc_false']})")

# ════════════════════════════════════════════════════════════════
# STEP 4 — Task Type × Action 分组
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print("STEP 4 — TASK_TYPE × ACTION GROUPS")
print("=" * 66)
groups = defaultdict(lambda: defaultdict(lambda: {"n": 0, "exec_ok": 0, "tc_t": 0, "tc_f": 0}))
for o in OBS:
    g = groups[o["task_type"]][o["selected_action"]]
    g["n"] += 1
    if o["execution_success"]:
        g["exec_ok"] += 1
    if o["task_completed"] is True:
        g["tc_t"] += 1
    elif o["task_completed"] is False:
        g["tc_f"] += 1

comparable = []  # 同 task_type 有 ≥2 个不同 action 且总 evidence ≥ 4
for tt in sorted(groups):
    acts_in = groups[tt]
    if len(acts_in) >= 2:
        total_n = sum(g["n"] for g in acts_in.values())
        if total_n >= 4:
            comparable.append(tt)
            desc = {}
            for a, g in acts_in.items():
                tc_total = g["tc_t"] + g["tc_f"]
                cr = (g["tc_t"] / tc_total) if tc_total > 0 else None
                desc[a] = "n=%d exec=%.2f comp=%s" % (g["n"], g["exec_ok"]/g["n"],
                                                      "%.2f" % cr if cr is not None else "None")
            print("  %s: %s" % (tt, desc))
print(f"COMPARABLE_GROUPS: {len(comparable)}")

# ════════════════════════════════════════════════════════════════
# STEP 5 — Ranking 对比
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print("STEP 5 — RANKING COMPARISON (within comparable groups)")
print("=" * 66)
changed = 0
unchanged = 0
for tt in comparable:
    acts_in = groups[tt]
    items = []
    for a, g in acts_in.items():
        tc_total = g["tc_t"] + g["tc_f"]
        exec_rate = g["exec_ok"] / g["n"]
        comp_rate = g["tc_t"] / tc_total if tc_total > 0 else None
        items.append({"a": a, "exec_rate": exec_rate, "comp_rate": comp_rate, "n": g["n"]})
    # Model A rank
    sorted_a = sorted(items, key=lambda x: (-x["exec_rate"], -x["n"]))
    # Model B rank (only where comp_rate known)
    items_b = [x for x in items if x["comp_rate"] is not None]
    sorted_b = sorted(items_b, key=lambda x: (-x["comp_rate"], -x["n"]))
    if len(sorted_b) >= 2:
        top_a = sorted_a[0]["a"]
        top_b = sorted_b[0]["a"]
        print(f"  {tt}: ModelA_top={top_a}(exec={sorted_a[0]['exec_rate']:.2f})  ModelB_top={top_b}(comp={sorted_b[0]['comp_rate']:.2f})")
        if top_a != top_b:
            changed += 1
            print(f"      ⚠️ RANKING CHANGED: {top_a} → {top_b}")
        else:
            unchanged += 1
print(f"\nRANKING_CHANGED: {changed} | RANKING_UNCHANGED: {unchanged}")

# ════════════════════════════════════════════════════════════════
# STEP 6 — Safe but Ineffective
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print("STEP 6 — HIGH_EXECUTION_LOW_COMPLETION ACTIONS (data-driven)")
print("=" * 66)
sbi = []
for a, s in action_stats.items():
    if s["comp_rate"] is not None and s["n"] >= 3:
        gap = s["exec_rate"] - s["comp_rate"]
        if gap >= 0.2:  # 执行成功率显著高于完成率
            sbi.append((a, s["exec_rate"], s["comp_rate"], s["n"], gap))
print("HIGH_EXECUTION_LOW_COMPLETION_ACTIONS:")
if sbi:
    for a, er, cr, n, gap in sorted(sbi, key=lambda x: -x[4]):
        print(f"  {a:14s} exec={er:.3f} comp={cr:.3f} gap={gap:.3f} n={n}")
else:
    print("  无（没有 action 满足 exec - comp >= 0.2）")

# ════════════════════════════════════════════════════════════════
# STEP 7 — Observational replay
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print("STEP 7 — OBSERVATIONAL REPLAY (non-causal)")
print("=" * 66)
# 对每个 observation，模拟两个 policy 的选择：
# Policy A: 选全局 exec_rate 最高的 action
# Policy B: 选全局 comp_rate 最高的 action
top_a = model_a[0][0]
top_b = model_b[0][0]
# 统计如果全局 policy 选择该 action，实际完成率如何
print(f"Policy A top action: {top_a} (exec={model_a[0][1]['exec_rate']:.3f})")
print(f"Policy B top action: {top_b} (comp={model_b[0][1]['comp_rate']:.3f})")
# 观测性 replay：数据中每个 action 的真实完成情况
print("\nObservational replay — 若按完成率选择 action，各 action 的期望完成率：")
for a, s in model_b:
    print(f"  {a:14s} comp_rate={s['comp_rate']:.3f}")
print("\nCOUNTERFACTUAL_LIMITATION: 当前数据无同一 situation 下不同 action 的交叉执行，"
      "无法做严格 counterfactual 因果评估。replay 为 observational，非 causal。")

# ════════════════════════════════════════════════════════════════
# STEP 9 — 统计质量
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print("STEP 9 — STATISTICAL QUALITY")
print("=" * 66)
print(f"TOTAL_OBSERVATIONS: {len(OBS)}")
print(f"VALID_LABELS: {sum(1 for o in OBS if o['task_completed'] is not None)}")
print(f"UNKNOWN: {sum(1 for o in OBS if o['task_completed'] is None)}")
for a, s in action_stats.items():
    flag = "  ⚠️ INSUFFICIENT_SAMPLE_SIZE" if s["n"] < 10 else ""
    print(f"  {a:14s} n={s['n']}{flag}")
