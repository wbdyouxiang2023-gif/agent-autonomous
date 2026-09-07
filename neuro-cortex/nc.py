#!/usr/bin/env python3
"""NeuroCortex 管理工具 — 查看状态、发送消息、管理记忆"""
import sys, os, json, urllib.request

PORT = 9100
URL = f"http://localhost:{PORT}"
STORE = os.path.expanduser("~/.neurocortex_memory.jsonl")


def chat(msg):
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


def get_stats():
    try:
        req = urllib.request.Request(f"{URL}/stats")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode())
    except:
        return {}


def get_experiences():
    try:
        req = urllib.request.Request(f"{URL}/experiences")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode())
    except:
        return []


def main():
    if len(sys.argv) < 2:
        print("""NeuroCortex 管理工具

用法:
  python3 nc.py chat "你的消息"     发送消息，积累经验
  python3 nc.py stats               查看认知统计
  python3 nc.py list                列出所有经验
  python3 nc.py clear               清空经验库
  python3 nc.py status              检查服务状态
""")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        h = chat("health check") if False else __import__('urllib.request').request.urlopen(f"{URL}/health", timeout=5).read().decode()
        print(f"服务: {'运行中' if 'ok' in h else '未启动'}")
        print(f"经验库: {json.loads(h).get('experiences', '?')} 条")

    elif cmd == "chat" and len(sys.argv) > 2:
        msg = " ".join(sys.argv[2:])
        r = chat(msg)
        if "error" in r:
            print(f"错误: {r['error']}")
        else:
            status = "✓" if r["success"] else "✗"
            print(f"[{status}] '{msg}'")
            print(f"  意图: {r['intent']}  预测p={r['probability']:.2f}  行动: {r['action']}")
            print(f"  回应: {r['response']}")
            print(f"  结果: {'成功' if r['success'] else '失败'}  评估: {r['evaluation']}")
            print(f"  经验库: {r['experience_count']}条 | 匹配: {r['retrieved']}条")

    elif cmd == "stats":
        s = get_stats()
        if not s:
            print("无法获取统计（服务可能未运行）")
        else:
            print(f"\n总经验: {s['total']} 条\n")
            if s.get('strong'):
                print(f"擅长的: {', '.join(s['strong'])}")
            if s.get('weak'):
                print(f"有困难的: {', '.join(s['weak'])}")
            if not s.get('strong') and not s.get('weak'):
                print("暂无足够数据")
            by_intent = s.get('by_intent', {})
            if by_intent:
                print(f"\n按类型分布:")
                for intent, items in sorted(by_intent.items()):
                    succ = sum(1 for e in items if e['success'])
                    tot = len(items)
                    print(f"  {intent}: {tot}次 (成功{succ})")

    elif cmd == "list":
        exps = get_experiences()
        if not exps:
            print("暂无经验")
        else:
            print(f"\n共 {len(exps)} 条经验:\n")
            for i, e in enumerate(exps, 1):
                status = "✓" if e['success'] else "✗"
                print(f"  {i}. [{status}] '{e['raw_input'][:40]}' intent={e['intent']} p={e['predicted_prob']:.2f}")

    elif cmd == "clear":
        if os.path.exists(STORE):
            os.remove(STORE)
            print(f"已清空: {STORE}")
        else:
            print("经验库已为空")

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
