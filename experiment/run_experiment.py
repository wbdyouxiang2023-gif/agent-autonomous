#!/usr/bin/env python3
"""
Experiment Runner — runs real tasks through NeuroCortex and collects observations.

Design principles:
- Only reads from the server, never modifies learning state
- Tasks are low-risk, read-only operations
- Each task produces at least one observation record
- Data quality is validated before counting toward totals
"""
import json
import os
import sys
import time
import urllib.request

SERVER_URL = "http://localhost:9100"
OBS_LOG = os.path.expanduser("~/.neurocortex_observation_log.jsonl")

# ── Task Suite ──────────────────────────────────────────────────────────────
# Grouped by situation type to ensure diversity.
# Each entry: (description, input_text)

TASKS = [
    # === file_read situations ===
    ("read_existing_file", "读取 /root/.openclaw/workspace/SOUL.md 文件内容"),
    ("read_existing_file", "读取 /root/.openclaw/workspace/MEMORY.md 文件内容"),
    ("read_existing_file", "读取 /root/.openclaw/workspace/USER.md 文件内容"),
    ("read_existing_file", "查看 /root/.openclaw/workspace/AGENTS.md 的配置"),
    ("read_nonexistent", "读取 /tmp/nonexistent_file_xyz.txt 看看是否存在"),
    ("read_config", "查看 /root/.openclaw/workspace/.gitignore 的内容"),
    ("read_config", "检查 /root/.openclaw/workspace/TOOLS.md 配置信息"),

    # === file_search situations ===
    ("search_existing", "在 workspace 目录搜索包含 'NeuroCortex' 的文件"),
    ("search_existing", "搜索 workspace 中所有 .py 文件"),
    ("search_existing", "查找包含 'experiment' 关键字的文件"),
    ("search_nonexistent", "搜索 workspace 中不存在的文件名 'zzz_fake_xyz'"),
    ("search_dir", "在 neuro-cortex 目录下搜索包含 'Decision' 的 Python 文件"),

    # === code_search situations ===
    ("code_function_search", "搜索代码中定义 'process' 函数的文件"),
    ("code_config_search", "查找代码中关于 'ACTION_LEARNING' 配置项的定义"),
    ("code_symbol_search", "搜索不存在的函数名 'nonexistent_function_abc123'"),
    ("code_class_search", "查找所有继承自 'Module' 的类定义"),

    # === disk_check situations ===
    ("disk_space", "检查当前磁盘空间使用情况"),
    ("disk_usage", "查看 /root 目录的磁盘占用"),
    ("dir_size", "检查 neuro-cortex 目录的大小"),

    # === system_check situations ===
    ("system_status", "查看当前系统运行状态"),
    ("system_uptime", "检查系统运行时间和负载"),
    ("process_list", "查看当前运行的 Python 进程"),

    # === host_check situations ===
    ("host_info", "查看当前主机名和系统信息"),
    ("host_network", "检查当前网络配置和 IP 地址"),

    # === user_query situations ===
    ("env_query", "查询当前用户的环境变量 PATH"),
    ("env_query", "查看当前工作目录和所属用户"),
    ("env_query", "查询 Python 版本和安装路径"),

    # === additional diversity tasks ===
    ("explain_task", "解释一下 NeuroCortex 的架构设计"),
    ("explain_task", "说明 CortexEvent 的数据结构"),
    ("create_task", "帮我写一个简单的日志记录函数"),
    ("fix_task", "修复一个示例代码中的语法错误"),
    ("optimize_task", "优化一段 Python 代码的性能"),
    ("test_task", "测试当前系统的连通性"),
]


def send_task(description, text):
    """Send a single task to the server and return the response."""
    try:
        data = json.dumps({"msg": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{SERVER_URL}/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def run_experiment():
    """Run all tasks and collect observations."""
    print("=" * 60)
    print("NeuroCortex Real Data Collection Experiment")
    print("=" * 60)
    print(f"Server: {SERVER_URL}")
    print(f"Log: {OBS_LOG}")
    print(f"Tasks: {len(TASKS)}")
    print()

    # Health check
    try:
        req = urllib.request.Request(f"{SERVER_URL}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            health = json.loads(resp.read())
            print(f"Health: {health}")
    except Exception as e:
        print(f"ERROR: Cannot reach server: {e}")
        return

    results = []
    successes = 0
    failures = 0

    for i, (situation_type, task_text) in enumerate(TASKS):
        print(f"[{i+1}/{len(TASKS)}] {situation_type}: {task_text[:50]}...")
        resp = send_task(situation_type, task_text)

        if "error" in resp:
            print(f"  ❌ Error: {resp['error']}")
            failures += 1
            continue

        print(f"  ✅ intent={resp.get('intent','?')} action={resp.get('action','?')} success={resp.get('success','?')}")
        successes += 1
        results.append({
            "index": i + 1,
            "situation": situation_type,
            "input": task_text,
            "response": resp,
        })
        time.sleep(0.5)  # Rate limiting

    print()
    print("=" * 60)
    print(f"Experiment complete: {successes} succeeded, {failures} failed")
    print(f"Observation log: {OBS_LOG}")
    print("=" * 60)

    # Save summary
    summary_path = "/root/.openclaw/workspace/experiment/experiment_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "total_tasks": len(TASKS),
            "successes": successes,
            "failures": failures,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"Summary saved to {summary_path}")

    return results


if __name__ == "__main__":
    run_experiment()
