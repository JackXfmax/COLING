"""冒烟探测：阿里百炼 OpenAI 兼容端点可用性 + 模型可用性。
key 从环境变量 BAILIAN_KEY 读取，脚本本身不含 key。
用法：BAILIAN_KEY=... python scripts/_smoke_bailian.py <model1> <model2> ...
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error

KEY = os.environ.get("BAILIAN_KEY", "").strip()
BASE = os.environ.get("BAILIAN_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()


def call(model, timeout=40):
    url = BASE.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "只回一个字：好"}],
        "max_tokens": 8,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": "Bearer " + KEY,
        "Content-Type": "application/json",
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        dt = time.time() - t0
        msg = data.get("choices", [{}])[0].get("message", {})
        txt = msg.get("content") or msg.get("reasoning_content") or ""
        usage = data.get("usage", {})
        return "OK  %5.1fs  out=%r  usage=%s" % (dt, txt[:20], usage)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")[:220]
        return "HTTP %s -> %s" % (e.code, raw)
    except Exception as e:
        return "ERR %s -> %s" % (type(e).__name__, e)


def main():
    if not KEY:
        print("!! BAILIAN_KEY 为空")
        return
    models = sys.argv[1:] or ["qwen-turbo"]
    print("BASE =", BASE)
    print("KEY  =", KEY[:12] + "..." + KEY[-4:], "(len=%d)" % len(KEY))
    print("-" * 72)
    for m in models:
        print("%-34s %s" % (m, call(m)))


if __name__ == "__main__":
    main()
