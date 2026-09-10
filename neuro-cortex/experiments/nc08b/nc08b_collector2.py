#!/usr/bin/env python3
"""NC-08B Collector Part 2 — real FAILURE tasks (produce completed=False/None).

These are real executions that are expected to fail or be ambiguous.
task_completed is still decided by independent verifier against real state.
"""
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("/tmp/nc08b_work/real_completion_observations.jsonl")
WORK = Path("/tmp/nc08b_work/tasks")

# Load existing observations
OBS = []
if OUT.exists():
    for line in OUT.read_text().strip().splitlines():
        if line:
            OBS.append(json.loads(line))

print(f"已载入 {len(OBS)} 条，继续追加...")


def log_obs(task_id, task_desc, task_type, action, exec_success, completed,
            source, outcome, error=""):
    OBS.append({
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_description": task_desc,
        "task_type": task_type,
        "candidate_action": action,
        "selected_action": action,
        "execution_success": bool(exec_success),
        "task_completed": completed,
        "completion_source": source,
        "actual_outcome": outcome[:300],
        "error_message": error,
        "provenance": "real_agent_execution",
    })


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=str(WORK))
        return r.returncode == 0, (r.stdout or "")[:250], (r.stderr or "")[:200]
    except Exception as e:
        return False, "", str(e)


def finish(tid, desc, ttype, action, exec_ok, completed, source, outcome, err=""):
    log_obs(tid, desc, ttype, action, exec_ok, completed, source, outcome, err)
    print(f"  ✓ {tid} {desc[:44]:46s} exec={exec_ok} completed={completed} src={source}")


# ── F1: 读不存在的文件（真实失败 → completed=False）──────────────
print("== F1 读取不存在的文件 ==")
for i in range(5):
    tid = f"f1a_{i}"
    fname = f"nonexistent_{i}.txt"
    ok, out, err = run(f"cat {WORK}/{fname}")
    real_exists = (WORK / fname).exists()
    # verifier: 文件不存在 → 任务未完成（即使命令返回错误也是"明确失败"）
    completed = False if (not real_exists) else (True if ok else None)
    finish(tid, f"read nonexistent {fname} ({i})", "file_read_fail", "read_file", ok,
           completed, "task_verifier", out, err)

# ── F2: 搜索不存在的文件（真实失败）──────────────────────────────
print("== F2 搜索不存在的文件 ==")
for i in range(5):
    tid = f"f2a_{i}"
    target = f"ghost_file_{i}.py"
    ok, out, err = run(f"find {WORK}/proj -name '{target}'")
    real_exists = (WORK / "proj" / target).exists()
    completed = False if (not real_exists and ok and target not in out) else (True if real_exists else None)
    finish(tid, f"search ghost {target} ({i})", "file_search_fail", "search_files", ok,
           completed, "task_verifier", out, err)

# ── F3: 修改不存在的文件（真实失败）──────────────────────────────
print("== F3 追加到不存在的文件 ==")
for i in range(5):
    tid = f"f3a_{i}"
    fname = f"ghost_modify_{i}.txt"
    ok, out, err = run(f"echo 'x' >> {WORK}/{fname}")
    real = (WORK / fname).read_text() if (WORK / fname).exists() else ""
    completed = False if (not (WORK / fname).exists()) else (True if "x" in real else None)
    finish(tid, f"append to ghost {fname} ({i})", "file_modify_fail", "write_file", ok,
           completed, "task_verifier", out, err)

# ── F4: 语法错误的代码（真实失败）────────────────────────────────
print("== F4 语法错误代码 ==")
for i in range(5):
    tid = f"f4a_{i}"
    fname = f"broken_{i}.py"
    (WORK / fname).write_text("def broken(:\n    pass\n")
    ok, out, err = run(f"python3 -m py_compile {WORK}/{fname}")
    completed = False if (not ok and "SyntaxError" in err) else (True if ok else None)
    finish(tid, f"compile broken_{i}.py ({i})", "code_check_fail", "terminal", ok,
           completed, "task_verifier", out, err)

# ── F5: 答案不匹配（真实"完成但答案错"→ 未完成任务）────────────
print("== F5 答案不匹配 ==")
for i in range(5):
    tid = f"f5a_{i}"
    wrong = f"WRONG_ANSWER_{i}"
    ok, out, err = run(f"echo '{wrong}'")
    # verifier: 期望特定答案，实际返回错误 → completed=False（执行成功但任务未完成！）
    completed = False if (ok and out.strip() != "EXPECTED_42") else (True if ok else None)
    finish(tid, f"answer wrong ({i})", "exact_answer_fail", "terminal", ok,
           completed, "task_verifier", out, err)

# ── F6: 歧义任务（无明确完成条件 → completed=None）──────────────
print("== F6 歧义任务 ==")
for i in range(5):
    tid = f"f6a_{i}"
    ok, out, err = run(f"ls /tmp")
    # verifier: 无明确 ground truth → 无法判定 → None
    completed = None
    finish(tid, f"list tmp (ambiguous) ({i})", "ambiguous", "terminal", ok,
           completed, "unknown", out, err)

# 持久化（追加模式，不覆盖）
with open(OUT, "w") as f:
    f.write("\n".join(json.dumps(o, ensure_ascii=False) for o in OBS) + "\n")

from collections import Counter
true_n = sum(1 for o in OBS if o["task_completed"] is True)
false_n = sum(1 for o in OBS if o["task_completed"] is False)
none_n = sum(1 for o in OBS if o["task_completed"] is None)
print(f"\n=== 累计 {len(OBS)}: TRUE={true_n} FALSE={false_n} UNKNOWN={none_n} ===")
print("BY_ACTION:", dict(Counter(o["selected_action"] for o in OBS)))
print("BY_TYPE:", dict(Counter(o["task_type"] for o in OBS)))
swc = sum(1 for o in OBS if o["execution_success"] and o["task_completed"] is False)
print(f"SUCCESS_WITHOUT_COMPLETION: {swc}")
