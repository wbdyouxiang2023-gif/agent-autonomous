#!/usr/bin/env python3
"""NeuroCortex 自动注入 - 每次对话前自动执行"""
import sys, json, subprocess, os

def run_cognitive_loop(message):
    """执行完整的认知循环"""
    
    # 1. 感知阶段
    result = subprocess.run(
        ['python3', '/root/.openclaw/workspace/tools/neurocortex.py', 'analyze', message],
        capture_output=True, text=True, timeout=10
    )
    
    try:
        data = json.loads(result.stdout)
    except:
        data = {'intent': 'general', 'probability': 0.5, 'action': 'respond', 'error': 'parse_failed'}
    
    # 2. 学习阶段 - 保存经验
    subprocess.run(
        ['python3', '/root/.openclaw/workspace/tools/neurocortex.py', 'save'],
        capture_output=True, timeout=5
    )
    
    # 3. 获取人格状态
    personality = subprocess.run(
        ['python3', '/root/.openclaw/workspace/tools/neurocortex.py', 'personality'],
        capture_output=True, text=True, timeout=5
    )
    
    return {
        'intent': data.get('intent', 'general'),
        'probability': data.get('probability', 0.5),
        'action': data.get('action', 'respond'),
        'experience_count': data.get('experience_count', 0),
        'personality': personality.stdout
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'intent': 'general', 'probability': 0.5, 'action': 'noop'}))
        sys.exit(0)
    
    result = run_cognitive_loop(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False))
