#!/usr/bin/env python3
"""
Extended Experiment Runner — Phase 2
Continues data collection to reach 100+ total records.
"""
import json
import os
import sys
import time
import urllib.request

SERVER_URL = "http://localhost:9100"
OBS_LOG = os.path.expanduser("~/.neurocortex_observation_log.jsonl")

# Extended task suite - more diversity
EXTENDED_TASKS = [
    # More file_read variations
    ("file_read_specific", "读取 /root/.openclaw/workspace/MEMORY.md 的完整内容"),
    ("file_read_config", "查看 /root/.openclaw/workspace/AGENTS.md 的前100行"),
    ("file_read_binary", "检查 /root/.openclaw/workspace/excel_demo.xlsx 是否存在"),
    
    # File search variations
    ("search_markdown", "搜索 workspace 中所有 .md 文件"),
    ("search_python", "查找包含 'import' 关键字的所有 Python 文件"),
    ("search_empty", "搜索不存在的文件名 'xxx_no_such_file'"),
    
    # Code analysis
    ("analyze_class", "分析 cortex.py 中的 NeuroCortex 类结构"),
    ("find_function", "查找 server.py 中处理 POST 请求的函数"),
    ("check_imports", "查看 neuro-cortex/src 目录的模块导入结构"),
    
    # System operations
    ("env_check", "查看当前进程的内存使用情况"),
    ("file_list", "列出 /root/.openclaw/workspace/neuro-cortex/src 下的所有 .py 文件"),
    ("text_search", "在 neuro-cortex 目录搜索 'Experience' 关键字"),
    
    # Explain tasks
    ("explain_arch", "解释 NeuroCortex 的决策流程"),
    ("explain_schema", "说明 CortexEvent 的各个字段用途"),
    
    # Create tasks
    ("create_code", "帮我写一个简单的 HTTP 服务器"),
    ("create_doc", "创建一份 README 文档说明项目结构"),
    
    # Fix tasks
    ("fix_error", "修复这段代码的语法错误: def foo() print('bar')"),
    ("debug_issue", "调试一个常见的 Python 缩进错误"),
    
    # Review tasks
    ("review_code", "审查这段代码的质量: def add(a,b): return a+b"),
    ("optimize_code", "优化这段循环的性能"),
    
    # Deploy tasks
    ("deploy_plan", "制定一个部署计划"),
    ("test_system", "测试系统连通性"),
    
    # Additional diversity
    ("analyze_performance", "分析当前系统的 CPU 负载"),
    ("check_logs", "查看最近 10 行的日志文件"),
    ("list_processes", "列出所有 Python 相关进程"),
    ("check_disk", "检查根分区磁盘使用率"),
    ("search_docs", "在文档目录搜索 'NeuroCortex'"),
    ("read_policy", "读取 server.py 中的配置部分"),
    ("analyze_deps", "分析项目的依赖关系"),
    ("check_time", "查看系统当前时间"),
    ("list_users", "查看当前系统用户信息"),
    ("network_check", "检查网络连接状态"),
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


def run_extended_experiment():
    """Run extended tasks and collect observations."""
    print("=" * 60)
    print("NEUROCORTEX EXPERIMENT - PHASE 2")
    print("=" * 60)
    
    # Count existing
    existing = 0
    if os.path.exists(OBS_LOG):
        with open(OBS_LOG) as f:
            existing = sum(1 for _ in f)
    print(f"Existing records: {existing}")
    print(f"Tasks to run: {len(EXTENDED_TASKS)}")
    print()
    
    results = []
    successes = 0
    failures = 0
    
    for i, (situation_type, task_text) in enumerate(EXTENDED_TASKS):
        target = 110 - existing  # Target ~110 to have buffer
        if existing + len(results) >= target:
            break
            
        print(f"[{existing + len(results) + 1}] {situation_type}: {task_text[:40]}...")
        resp = send_task(situation_type, task_text)
        
        if "error" in resp:
            print(f"  ❌ Error: {resp['error']}")
            failures += 1
            continue
        
        print(f"  ✅ intent={resp.get('intent','?')} action={resp.get('action','?')} success={resp.get('success','?')}")
        successes += 1
        results.append({
            "index": existing + len(results) + 1,
            "situation": situation_type,
            "input": task_text,
            "response": resp,
        })
        time.sleep(0.3)  # Rate limiting
    
    print()
    print("=" * 60)
    print(f"Phase 2 complete: {successes} succeeded, {failures} failed")
    print(f"Total observations: {existing + len(results)}")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    run_extended_experiment()
