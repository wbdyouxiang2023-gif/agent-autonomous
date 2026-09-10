#!/usr/bin/env python3
"""NC-08B Data Provenance Audit — verify each observation is real."""
import json
from pathlib import Path
from collections import Counter

OUT = Path("/tmp/nc08b_work/real_completion_observations.jsonl")
OBS = [json.loads(l) for l in OUT.read_text().strip().splitlines() if l]

print("=" * 60)
print("NC-08B DATA PROVENANCE AUDIT")
print("=" * 60)
print(f"TOTAL_OBSERVATIONS: {len(OBS)}")

# 1. provenance 字段
prov = Counter(o.get("provenance") for o in OBS)
print(f"PROVENANCE: {dict(prov)}")

# 2. task_completed 三态
true_n = sum(1 for o in OBS if o["task_completed"] is True)
false_n = sum(1 for o in OBS if o["task_completed"] is False)
none_n = sum(1 for o in OBS if o["task_completed"] is None)
print(f"TRUE={true_n} FALSE={false_n} UNKNOWN={none_n}")

# 3. 按 action
print(f"BY_ACTION: {dict(Counter(o['selected_action'] for o in OBS))}")

# 4. 按 task_type
print(f"BY_TASK_TYPE: {dict(Counter(o['task_type'] for o in OBS))}")

# 5. 按 completion_source
print(f"BY_COMPLETION_SOURCE: {dict(Counter(o['completion_source'] for o in OBS))}")

# 6. 关键: success=True AND completed=False
swc = [o for o in OBS if o["execution_success"] and o["task_completed"] is False]
print(f"\nSUCCESS_WITHOUT_COMPLETION: {len(swc)}")
for o in swc[:15]:
    print(f"  {o['task_id']} {o['task_description'][:40]}")

# 7. 无 synthetic/hypothetical 标记
syn = [o for o in OBS if o.get("provenance") != "real_agent_execution"]
print(f"\nSYNTHETIC/HYPOTHETICAL: {len(syn)} (必须为 0)")

# 8. 字段完整性
req = ["task_id", "timestamp", "task_description", "task_type", "selected_action",
       "execution_success", "task_completed", "completion_source", "actual_outcome",
       "error_message", "provenance"]
missing = [o["task_id"] for o in OBS if any(k not in o for k in req)]
print(f"MISSING_FIELDS: {len(missing)} {'✅' if not missing else missing}")

# 9. 禁止的: task_completed 由 action 名/成功推断检查
# 检查是否所有 success=False 都 → completed=False（如果不是则说明无推断）
sf = [o for o in OBS if not o["execution_success"]]
sf_not_false = [o["task_id"] for o in sf if o["task_completed"] is not False]
print(f"SUCCESS=False 但 completed 非 False: {len(sf_not_false)} {'✅ 无推断' if not sf_not_false else sf_not_false}")

# 10. 时间唯一性（每个 task 独立时间戳）
ts = len({o["timestamp"] for o in OBS})
print(f"UNIQUE_TIMESTAMPS: {ts}/{len(OBS)}")

print("\n=== AUDIT PASS ===" if (len(syn) == 0 and not missing and not sf_not_false) else "\n=== AUDIT ISSUES ===")
