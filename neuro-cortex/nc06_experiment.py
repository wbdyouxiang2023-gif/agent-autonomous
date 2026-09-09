#!/usr/bin/env python3
"""
NC-06 Experiment Script: Controlled Policy Trial v0.1
Tests Original Policy vs NeuroCortex Policy in real conditions.
"""
import json
import urllib.request
import time
import sys
from pathlib import Path

SERVER = "http://localhost:9100"
NC06_LOG = Path("/root/.neurocortex_nc06_log.jsonl")


def http_post(msg):
    """Send POST request and return parsed response."""
    data = json.dumps({"msg": msg}).encode()
    req = urllib.request.Request(
        f"{SERVER}/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    # 1. Verify server is healthy
    try:
        health = http_post("health check")
        print(f"Server status: {health.get('status', 'unknown')}")
        if health.get('status') != 'ok':
            print("ERROR: Server not healthy!")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot connect to server: {e}")
        sys.exit(1)
    
    # 2. Clear old log for clean experiment
    if NC06_LOG.exists():
        NC06_LOG.unlink()
    
    # 3. 30 diverse real tasks (varying intents and situations)
    TASKS = [
        # Search tasks
        ("搜索 workspace 中包含 NeuroCortex 的文件", "search"),
        ("查找所有 .py 文件的位置", "search"),
        ("检查配置文件的内容", "read"),
        ("列出当前目录结构", "general"),
        
        # Review tasks
        ("查看当前系统的配置", "review"),
        ("分析这段代码的质量", "review"),
        ("审查项目架构设计", "review"),
        ("评估这段代码的安全性", "review"),
        ("分析代码复杂度", "review"),
        ("检查依赖关系", "review"),
        
        # Create tasks
        ("帮我创建一个测试函数", "create"),
        ("生成一个简单的 Python 脚本", "create"),
        ("写一个 HTTP 请求示例", "create"),
        ("创建新的模块文件", "create"),
        ("编写一个日志记录函数", "create"),
        
        # Fix tasks
        ("修复这段代码的语法错误", "fix"),
        ("调试一个常见的 ImportError", "fix"),
        ("解决代码中的类型错误", "fix"),
        ("排查一个内存泄漏问题", "fix"),
        ("调试认证模块的 bug", "fix"),
        
        # Optimize tasks
        ("优化这段循环的性能", "optimize"),
        ("提升代码的执行效率", "optimize"),
        ("加速数据处理流程", "optimize"),
        ("优化查询性能", "optimize"),
        
        # Test tasks
        ("测试系统的连通性", "test"),
        ("验证服务的响应速度", "test"),
        ("运行测试套件", "test"),
        ("检查数据库连接状态", "test"),
        
        # Explain tasks
        ("解释 NeuroCortex 的架构", "explain"),
        ("说明 CortexEvent 的结构", "explain"),
        ("讲解 action learning 原理", "explain"),
    ]
    
    # 4. Execute tasks and collect results
    print(f"\n{'='*70}")
    print("NC-06 CONTROLLED POLICY TRIAL v0.1")
    print(f"{'='*70}")
    print(f"Total tasks: {len(TASKS)}")
    print()
    
    results = []
    for i, (task, expected_intent) in enumerate(TASKS):
        try:
            resp = http_post(task)
            intent = resp.get('intent', '?')
            action = resp.get('action', '?')
            success = resp.get('success', '?')
            
            results.append({
                "index": i+1,
                "task": task[:50],
                "expected_intent": expected_intent,
                "actual_intent": intent,
                "action": action,
                "success": success,
            })
            print(f"[{i+1:2d}/30] intent={intent:10s} action={action:12s} success={success}")
            
        except Exception as e:
            print(f"[{i+1:2d}/30] ERROR: {e}")
            results.append({
                "index": i+1,
                "task": task[:50],
                "error": str(e),
                "success": "error",
            })
        
        time.sleep(0.1)  # Small delay between requests
    
    print()
    print("="*70)
    print("EXPERIMENT COMPLETE")
    print("="*70)
    
    # 5. Read NC-06 log
    print(f"\nNC-06 log file: {NC06_LOG}")
    if NC06_LOG.exists():
        records = []
        with open(NC06_LOG) as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except:
                        pass
        
        print(f"NC-06 decisions logged: {len(records)}")
        print()
        
        # Analyze
        original_count = sum(1 for r in records if r.get('policy_used') == 'original')
        nc_count = sum(1 for r in records if r.get('policy_used') == 'nc06')
        fallback_count = sum(1 for r in records if r.get('fallback_used'))
        safety_incidents = sum(1 for r in records if r.get('safety_incident'))
        
        # Disagreement analysis
        disagreements = []
        for r in records:
            orig = r.get('original_action')
            nc = r.get('nc_action')
            final = r.get('final_action')
            if orig != nc and nc is not None:
                disagreements.append({
                    'task': r.get('raw_input', '')[:40],
                    'original': orig,
                    'nc': nc,
                    'final': final
                })
        
        print(f"\nTraffic Distribution:")
        print(f"  Original policy: {original_count} ({original_count/len(records)*100:.1f}%)")
        print(f"  NC-06 policy: {nc_count} ({nc_count/len(records)*100:.1f}%)")
        print()
        
        print(f"Safety Metrics:")
        print(f"  Fallback count: {fallback_count}")
        print(f"  Safety incidents: {safety_incidents}")
        print()
        
        if disagreements:
            print(f"Disagreements (Original != NC-06): {len(disagreements)}")
            for d in disagreements[:5]:
                print(f"  - {d['task'][:40]}")
                print(f"    Original: {d['original']} -> NC-06: {d['nc']} -> Final: {d['final']}")
        else:
            print("No disagreements detected")
    else:
        print("WARNING: No NC-06 log file created!")
    
    # 6. Summary
    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Tasks executed: {len(results)}")
    success_count = sum(1 for r in results if r.get('success') == True)
    failure_count = sum(1 for r in results if r.get('success') == False)
    error_count = sum(1 for r in results if r.get('success') == 'error')
    print(f"Success: {success_count}")
    print(f"Failure: {failure_count}")
    print(f"Errors: {error_count}")
    print()


if __name__ == "__main__":
    main()
