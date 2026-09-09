#!/usr/bin/env python3
"""测试 stepfun_api 接口调用"""
import json
import urllib.request
import urllib.error

BASE_URL = "https://chatapi.stepfun.com/chatapi/v1"
API_KEY = "***REMOVED***"
MODEL_ID = "step-3.7-flash"

def chat_completion(messages, stream=False):
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "model": MODEL_ID,
        "messages": messages,
        "stream": stream
    }).encode()

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
    return result

if __name__ == "__main__":
    print(f"Testing StepFun API...")
    print(f"BaseURL: {BASE_URL}")
    print(f"Model:   {MODEL_ID}")
    print()

    try:
        result = chat_completion([
            {"role": "user", "content": "你好，请回复'连接成功'四个字"}
        ])
        print("✅ 请求成功！")
        content = result["choices"][0]["message"]["content"]
        print(f"回复: {content}")
        print(f"Usage: {result.get('usage', {})}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")
