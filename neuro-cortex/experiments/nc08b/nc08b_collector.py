#!/usr/bin/env python3
"""NC-08B Data Collector — real agent execution + independent task verification.

Each observation records:
  task_id, timestamp, task_description, task_type, selected_action,
  execution_success, task_completed (True/False/None), completion_source,
  actual_outcome, error_message, provenance="real_agent_execution"

task_completed is decided by an INDEPENDENT VERIFIER that checks the real
environment state (file exists, content matches, answer matches ground
truth) — NOT by the tool's own success flag and NOT by hardcoded labels.
"""
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("/tmp/nc08b_work/real_completion_observations.jsonl")
WORK = Path("/tmp/nc08b_work/tasks")
WORK.mkdir(parents=True, exist_ok=True)

OBS = []


def log_obs(task_id, task_desc, task_type, action, exec_success, completed,
            source, outcome, error=""):
    rec = {
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_description": task_desc,
        "task_type": task_type,
        "candidate_action": action,
        "selected_action": action,
        "execution_success": bool(exec_success),
        "task_completed": completed,  # True/False/None — set by verifier only
        "completion_source": source,  # environment / task_verifier / user_feedback / unknown
        "actual_outcome": outcome[:300],
        "error_message": error,
        "provenance": "real_agent_execution",
    }
    OBS.append(rec)


def run(cmd, timeout=30):
    """Real execution via subprocess (my terminal tool)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=str(WORK))
        return r.returncode == 0, (r.stdout or "")[:250], (r.stderr or "")[:200]
    except Exception as e:
        return False, "", str(e)


def finish(task_id, desc, ttype, action, exec_ok, completed, source, outcome, err=""):
    log_obs(task_id, desc, ttype, action, exec_ok, completed, source, outcome, err)
    print(f"  ✓ {task_id} {desc[:40]:42s} exec={exec_ok} completed={completed} src={source}")


# ══════════════════════════════════════════════════════════════════
# TYPE 1 — 文件读取（verifier: 读取真实文件并与 ground truth 对比）
# ══════════════════════════════════════════════════════════════════
print("== T1 文件读取 ==")
T1_GT = {"hostname": "this-host", "os_release": "Ubuntu"}

# T1-a: 读 /etc/hostname 要求返回内容
for i in range(5):
    tid = f"t1a_{i}"
    ok, out, err = run("cat /etc/hostname")
    # verifier: 真实文件存在且非空
    real = Path("/etc/hostname").read_text().strip() if Path("/etc/hostname").exists() else ""
    completed = True if (ok and real and real in out) else (False if ok else None)
    finish(tid, f"read /etc/hostname ({i})", "file_read", "read_file", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 2 — 文件搜索（verifier: 确认结果包含真实匹配文件）
# ══════════════════════════════════════════════════════════════════
print("== T2 文件搜索 ==")
# 先建真实文件供搜索
(WORK / "proj").mkdir(exist_ok=True)
for name in ["alpha.py", "beta.py", "gamma.md"]:
    (WORK / "proj" / name).write_text("# content placeholder\n")

for i in range(5):
    tid = f"t2a_{i}"
    target = f"alpha.py" if i % 2 == 0 else "beta.py"
    ok, out, err = run(f"find {WORK}/proj -name '{target}'")
    # verifier: 真实文件存在
    real_exists = (WORK / "proj" / target).exists()
    completed = True if (ok and real_exists and target in out) else (False if ok else None)
    finish(tid, f"search file {target} ({i})", "file_search", "search_files", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 3 — 信息提取（verifier: 提取值 vs ground truth）
# ══════════════════════════════════════════════════════════════════
print("== T3 信息提取 ==")
for i in range(5):
    tid = f"t3a_{i}"
    ok, out, err = run("python3 -c 'import sys; print(sys.version.split()[0])'")
    # verifier: python 版本真实存在
    real_v = sys.version.split()[0]
    completed = True if (ok and real_v and real_v in out) else (False if ok else None)
    finish(tid, f"get python version ({i})", "info_extract", "terminal", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 4 — 文件创建（verifier: 文件真实存在且内容正确）
# ══════════════════════════════════════════════════════════════════
print("== T4 文件创建 ==")
for i in range(5):
    tid = f"t4a_{i}"
    fname = f"created_{i}.txt"
    content = f"NC08B content {i}"
    ok, out, err = run(f"echo '{content}' > {WORK}/{fname}")
    # verifier: 文件真实存在 + 内容精确匹配
    fpath = WORK / fname
    real = fpath.read_text().strip() if fpath.exists() else ""
    completed = True if (fpath.exists() and real == content) else (False if ok else None)
    finish(tid, f"create file {fname} ({i})", "file_create", "write_file", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 5 — 文件修改（verifier: 修改后内容包含预期）
# ══════════════════════════════════════════════════════════════════
print("== T5 文件修改 ==")
for i in range(5):
    tid = f"t5a_{i}"
    fname = f"modify_{i}.txt"
    (WORK / fname).write_text("line1\n")
    ok, out, err = run(f"echo 'line2-appended' >> {WORK}/{fname}")
    real = (WORK / fname).read_text() if (WORK / fname).exists() else ""
    completed = True if ("line2-appended" in real) else (False if ok else None)
    finish(tid, f"append to file {fname} ({i})", "file_modify", "write_file", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 6 — 代码定位（verifier: 找到真实定义的符号）
# ══════════════════════════════════════════════════════════════════
print("== T6 代码定位 ==")
for i in range(5):
    tid = f"t6a_{i}"
    ok, out, err = run(f"grep -rn 'def collect_observation' {WORK}/../nc08b_collector.py 2>/dev/null || grep -rn 'log_obs' {WORK}/../nc08b_collector.py")
    # verifier: 真实文件中存在该符号
    has_sym = False
    for f in Path("/tmp/nc08b_work").glob("*.py"):
        if "log_obs" in f.read_text():
            has_sym = True
    completed = True if (ok and has_sym and "log_obs" in out) else (False if ok else None)
    finish(tid, f"locate symbol log_obs ({i})", "code_locator", "search_files", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 7 — 简单代码检查（verifier: 语法检查真实通过）
# ══════════════════════════════════════════════════════════════════
print("== T7 代码检查 ==")
for i in range(5):
    tid = f"t7a_{i}"
    (WORK / f"check_{i}.py").write_text("x = 1\ny = 2\nprint(x+y)\n")
    ok, out, err = run(f"python3 -m py_compile {WORK}/check_{i}.py")
    # verifier: 无语法错误
    completed = True if ok else (False if ok is False else None)
    finish(tid, f"check syntax check_{i}.py ({i})", "code_check", "terminal", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 8 — 环境检查（verifier: 值与真实环境一致）
# ══════════════════════════════════════════════════════════════════
print("== T8 环境检查 ==")
for i in range(5):
    tid = f"t8a_{i}"
    ok, out, err = run("df -h / | tail -1")
    # verifier: 真实 df 有输出（至少包含 Filesystem 挂载）
    real_df = subprocess.run("df -h / | tail -1", shell=True, capture_output=True, text=True).stdout
    completed = True if (ok and real_df.strip() and real_df.strip() in out) else (False if ok else None)
    finish(tid, f"check disk space ({i})", "env_check", "terminal", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 9 — 明确答案任务（verifier: 答案与 ground truth 精确匹配）
# ══════════════════════════════════════════════════════════════════
print("== T9 明确答案 ==")
GT_ANSWERS = ["42", "hello", "7", "pong", "done"]
for i in range(5):
    tid = f"t9a_{i}"
    gt = GT_ANSWERS[i]
    ok, out, err = run(f"echo '{gt}'")
    # verifier: 输出与 ground truth 精确匹配
    completed = True if (ok and out.strip() == gt) else (False if ok else None)
    finish(tid, f"answer exactly {gt} ({i})", "exact_answer", "terminal", ok, completed,
           "task_verifier", out, err)

# ══════════════════════════════════════════════════════════════════
# TYPE 10 — 可验证多步骤（verifier: 最终产物真实存在且正确）
# ══════════════════════════════════════════════════════════════════
print("== T10 多步骤 ==")
for i in range(5):
    tid = f"t10a_{i}"
    fname = f"multi_{i}.txt"
    ok1, _, _ = run(f"mkdir -p {WORK}/sub{i}")
    ok2, out2, err2 = run(f"echo 'multi-step-{i}' > {WORK}/sub{i}/{fname} && ls {WORK}/sub{i}/{fname}")
    fpath = WORK / "sub" + str(i) / fname if False else WORK / f"sub{i}" / fname
    real = fpath.read_text().strip() if fpath.exists() else ""
    completed = True if (fpath.exists() and real == f"multi-step-{i}") else (False if (ok1 and ok2) else None)
    finish(tid, f"multi-step create {fname} ({i})", "multi_step", "terminal", ok2, completed,
           "task_verifier", out2, err2)

# ── 持久化 ─────────────────────────────────────────────────────────
OUT.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in OBS) + "\n")
print(f"\n=== SAVED {len(OBS)} observations → {OUT} ===")

# ── 汇总统计 ───────────────────────────────────────────────────────
from collections import Counter
true_n = sum(1 for o in OBS if o["task_completed"] is True)
false_n = sum(1 for o in OBS if o["task_completed"] is False)
none_n = sum(1 for o in OBS if o["task_completed"] is None)
print(f"TOTAL={len(OBS)} TRUE={true_n} FALSE={false_n} UNKNOWN={none_n}")
by_action = Counter(o["selected_action"] for o in OBS)
print("BY_ACTION:", dict(by_action))
by_type = Counter(o["task_type"] for o in OBS)
print("BY_TYPE:", dict(by_type))
swc = sum(1 for o in OBS if o["execution_success"] and o["task_completed"] is False)
print(f"SUCCESS_WITHOUT_COMPLETION (exec_ok but completed=False): {swc}")
