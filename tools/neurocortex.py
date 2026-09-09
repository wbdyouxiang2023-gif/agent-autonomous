#!/usr/bin/env python3
"""NeuroCortex 自动分析工具 — 供 Agnes 在对话中调用"""
import sys, json, urllib.request, subprocess, os

MCP_URL = "http://localhost:9100/chat"
PERSONALITY_DIR = os.path.expanduser("~/.neuro-cortex")

def analyze(msg, session="default"):
    """分析用户消息，返回意图和成功率"""
    data = json.dumps({"msg": msg, "session": session}).encode()
    req = urllib.request.Request(MCP_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())

def get_personality():
    """获取当前人格状态"""
    src_dir = "/root/.openclaw/workspace/neuro-cortex/src"
    try:
        result = subprocess.run(
            ["go", "run", ".", "personality", "--name", "Agnes"],
            cwd=src_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GOPROXY": "https://goproxy.cn", "GOTOOLCHAIN": "local"}
        )
        return result.stdout.strip()
    except Exception as e:
        return f"人格系统错误: {e}"

def update_personality(action):
    """更新人格状态（根据动作调整特质）"""
    src_dir = "/root/.openclaw/workspace/neuro-cortex/src"
    try:
        result = subprocess.run(
            ["go", "run", ".", "personality", "--name", "Agnes", "--act", action],
            cwd=src_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GOPROXY": "https://goproxy.cn", "GOTOOLCHAIN": "local"}
        )
        return result.stdout.strip()
    except Exception as e:
        return f"更新人格失败: {e}"

def save_personality():
    """保存人格到文件（含Tick动态更新）"""
    src_dir = "/root/.openclaw/workspace/neuro-cortex/src"
    try:
        # 先调用 tick 让人格动态变化
        tick_result = subprocess.run(
            ["go", "run", ".", "tick"],
            cwd=src_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GOPROXY": "https://goproxy.cn", "GOTOOLCHAIN": "local"}
        )
        # 再保存
        result = subprocess.run(
            ["go", "run", ".", "save"],
            cwd=src_dir,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GOPROXY": "https://goproxy.cn", "GOTOOLCHAIN": "local"}
        )
        return f"{tick_result.stdout.strip()}\n{result.stdout.strip()}"
    except Exception as e:
        return f"保存人格失败: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: neurocortex.py [analyze|personality|save] <message>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "analyze":
        msg = sys.argv[2] if len(sys.argv) > 2 else ""
        result = analyze(msg)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == "personality":
        print(get_personality())
    elif cmd == "save":
        print(save_personality())
    else:
        print(f"Unknown command: {cmd}")
