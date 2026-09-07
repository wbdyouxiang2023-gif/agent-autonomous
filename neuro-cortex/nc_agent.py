#!/usr/bin/env python3
"""NeuroCortex 对话代理 — 每条消息自动通过 NeuroCortex 处理并积累经验"""
import sys, os, json, urllib.request

PORT = 9100
URL = f"http://localhost:{PORT}"

def chat(msg):
    """发送消息到 NeuroCortex，返回结构化结果"""
    try:
        req = urllib.request.Request(
            f"{URL}/chat",
            data=json.dumps({"msg": msg}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e), "experience_count": 0}

def stats():
    try:
        req = urllib.request.Request(f"{URL}/stats")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode())
    except:
        return {}

def health():
    try:
        req = urllib.request.Request(f"{URL}/health")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode())
    except:
        return {"status": "error"}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 nc_agent.py \"你的消息\"")
        print("或: echo '消息' | python3 nc_agent.py")
        sys.exit(1)
    
    msg = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read().strip()
    result = chat(msg)
    
    if "error" in result:
        print(f"NeuroCortex 错误: {result['error']}")
        sys.exit(1)
    
    status = "✓" if result["success"] else "✗"
    print(f"[{status}] intent={result['intent']} p={result['probability']:.2f} resp={result['response']} exps={result['experience_count']}")
