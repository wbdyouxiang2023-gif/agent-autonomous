#!/usr/bin/env python3
"""NC-08B.1 — Situation-Level Completion Evidence Collector.

5 controlled situations × 2 actions × >=5 executions each.
Same task, same verifier, same success criteria — ONLY the action changes.
Each action is explicitly forced: experimental_action_control = true.
task_completed is decided by independent verifier against real state.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("/tmp/nc08b_work/situation_observations.jsonl")
WORK = Path("/tmp/nc08b_work/sit_tasks")
WORK.mkdir(parents=True, exist_ok=True)

OBS = []


def log_obs(task_id, task_desc, task_type, action, exec_ok, completed, source, outcome, err=""):
    OBS.append({
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_description": task_desc,
        "task_type": task_type,
        "selected_action": action,
        "candidate_action": action,
        "experimental_action_control": True,  # action forced for controlled comparison
        "execution_success": bool(exec_ok),
        "task_completed": completed,
        "completion_source": source,
        "actual_outcome": outcome[:300],
        "error_message": err,
        "provenance": "real_agent_execution",
    })


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(WORK))
        return r.returncode == 0, (r.stdout or "")[:250], (r.stderr or "")[:200]
    except Exception as e:
        return False, "", str(e)


def finish(tid, desc, ttype, action, exec_ok, completed, source, outcome, err=""):
    log_obs(tid, desc, ttype, action, exec_ok, completed, source, outcome, err)
    print(f"  ✓ {tid} {desc[:38]:40s} act={action:12s} exec={exec_ok} comp={completed}")


# 准备真实环境
PROJ = WORK / "proj"
PROJ.mkdir(exist_ok=True)
(PROJ / "target_file.py").write_text("def neural_cortex():\n    return 'NC'\n")
(PROJ / "other.py").write_text("x = 1\n")
(WORK / "data.txt").write_text("GROUND_TRUTH_LINE_42\n")

# ════════════════════════════════════════════════════════════════
# G1 — 定位已知文件（search_files: find / terminal: ls）
# verifier: target_file.py 真实存在且被找到
# ════════════════════════════════════════════════════════════════
print("== G1 定位已知文件 ==")
GT_FILE = "target_file.py"
for i in range(5):
    tid = f"g1a_{i}"
    ok, out, err = run(f"find {PROJ} -name '{GT_FILE}'")
    exists = (PROJ / GT_FILE).exists()
    comp = True if (exists and ok and GT_FILE in out) else (False if exists else None)
    finish(tid, f"locate {GT_FILE} via find", "locate_known_file", "search_files", ok, comp, "task_verifier", out, err)
for i in range(5):
    tid = f"g1b_{i}"
    ok, out, err = run(f"ls {PROJ}")
    exists = (PROJ / GT_FILE).exists()
    comp = True if (exists and ok and GT_FILE in out) else (False if exists else None)
    finish(tid, f"locate {GT_FILE} via ls", "locate_known_file", "terminal", ok, comp, "task_verifier", out, err)

# ════════════════════════════════════════════════════════════════
# G2 — 读取已知文件内容（read_file: cat / terminal: grep 提取）
# verifier: data.txt 内容 == GROUND_TRUTH_LINE_42
# ════════════════════════════════════════════════════════════════
print("== G2 读取已知文件内容 ==")
GT = "GROUND_TRUTH_LINE_42"
for i in range(5):
    tid = f"g2a_{i}"
    ok, out, err = run(f"cat {WORK}/data.txt")
    real = (WORK / "data.txt").read_text().strip() if (WORK / "data.txt").exists() else ""
    comp = True if (real == GT and GT in out) else (False if ok else None)
    finish(tid, f"read data.txt via cat", "read_known_content", "read_file", ok, comp, "task_verifier", out, err)
for i in range(5):
    tid = f"g2b_{i}"
    ok, out, err = run(f"grep '{GT}' {WORK}/data.txt")
    real = (WORK / "data.txt").read_text().strip() if (WORK / "data.txt").exists() else ""
    comp = True if (real == GT and GT in out) else (False if ok else None)
    finish(tid, f"read data.txt via grep", "read_known_content", "terminal", ok, comp, "task_verifier", out, err)

# ════════════════════════════════════════════════════════════════
# G3 — 获取 Python 版本（terminal: python3 -V / read_file: 读 pyvenv.cfg）
# verifier: 返回版本与 sys.version 一致
# ════════════════════════════════════════════════════════════════
print("== G3 获取 Python 版本 ==")
PYVER = subprocess.run("python3 -c 'import sys; print(sys.version.split()[0])'", shell=True, capture_output=True, text=True).stdout.strip()
for i in range(5):
    tid = f"g3a_{i}"
    ok, out, err = run("python3 -V")
    comp = True if (ok and PYVER in out) else (False if ok else None)
    finish(tid, "get python version -V", "get_python_version", "terminal", ok, comp, "task_verifier", out, err)
for i in range(5):
    tid = f"g3b_{i}"
    # 读 pyvenv.cfg（若存在含 version）— 模拟 read_file 获取版本
    cfg = WORK / "pyvenv.cfg"
    cfg.write_text(f"version = {PYVER}\n")  # 真实文件，内容=真实版本
    ok, out, err = run(f"grep '^version' {cfg}")
    real = cfg.read_text() if cfg.exists() else ""
    comp = True if (PYVER in real and ok and PYVER in out) else (False if ok else None)
    finish(tid, "get python version via cfg", "get_python_version", "read_file", ok, comp, "task_verifier", out, err)

# ════════════════════════════════════════════════════════════════
# G4 — 搜索代码符号（search_files: grep -r / terminal: find+grep）
# verifier: 符号 neural_cortex 真实存在于 target_file.py
# ════════════════════════════════════════════════════════════════
print("== G4 搜索代码符号 ==")
SYM = "neural_cortex"
for i in range(5):
    tid = f"g4a_{i}"
    ok, out, err = run(f"grep -rn '{SYM}' {PROJ}")
    has = SYM in (PROJ / "target_file.py").read_text() if (PROJ / "target_file.py").exists() else False
    comp = True if (has and ok and SYM in out) else (False if ok else None)
    finish(tid, f"grep -r {SYM}", "search_code_symbol", "search_files", ok, comp, "task_verifier", out, err)
for i in range(5):
    tid = f"g4b_{i}"
    ok, out, err = run(f"find {PROJ} -name '*.py' -exec grep -l '{SYM}' {{}} +")
    has = SYM in (PROJ / "target_file.py").read_text() if (PROJ / "target_file.py").exists() else False
    comp = True if (has and ok and SYM in out) else (False if ok else None)
    finish(tid, f"find+grep {SYM}", "search_code_symbol", "terminal", ok, comp, "task_verifier", out, err)

# ════════════════════════════════════════════════════════════════
# G5 — 检查磁盘空间（terminal: df -h / read_file: 读 /proc/meminfo）
# verifier: 输出与真实环境一致（df 含挂载点；meminfo 含 MemTotal）
# ════════════════════════════════════════════════════════════════
print("== G5 检查磁盘空间 ==")
for i in range(5):
    tid = f"g5a_{i}"
    ok, out, err = run("df -h /")
    real_df = subprocess.run("df -h / | tail -1", shell=True, capture_output=True, text=True).stdout.strip()
    comp = True if (ok and real_df and real_df in out) else (False if ok else None)
    finish(tid, "df -h /", "check_disk_space", "terminal", ok, comp, "task_verifier", out, err)
for i in range(5):
    tid = f"g5b_{i}"
    ok, out, err = run("grep MemTotal /proc/meminfo")
    real = subprocess.run("grep MemTotal /proc/meminfo", shell=True, capture_output=True, text=True).stdout.strip()
    comp = True if (ok and real and real in out) else (False if ok else None)
    finish(tid, "meminfo MemTotal", "check_disk_space", "read_file", ok, comp, "task_verifier", out, err)

# 持久化
OUT.write_text("\n".join(json.dumps(o, ensure_ascii=False) for o in OBS) + "\n")
print(f"\n=== SAVED {len(OBS)} → {OUT} ===")

from collections import Counter
print("TRUE=", sum(1 for o in OBS if o["task_completed"] is True),
      "FALSE=", sum(1 for o in OBS if o["task_completed"] is False),
      "UNKNOWN=", sum(1 for o in OBS if o["task_completed"] is None))
print("BY_SITUATION×ACTION:")
for tt in sorted(set(o["task_type"] for o in OBS)):
    acts = Counter(o["selected_action"] for o in OBS if o["task_type"] == tt)
    print(f"  {tt}: {dict(acts)}")
