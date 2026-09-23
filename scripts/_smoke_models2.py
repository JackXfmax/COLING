# -*- coding: utf-8 -*-
"""探测百炼 key 对指定模型的可用性（含关思考开关对比）。key 走环境变量。"""
import os, sys, json, time
import urllib.request as U
import urllib.error as E

EP = os.environ.get("BAILIAN_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
KEY = os.environ.get("BAILIAN_API_KEY", "")
PROMPT = "补全歇后语：顶到碓窝子唱戏——______\n请只给出答案本身，不要解释。"
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "40"))


def call(model, no_think=True):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": 0.0,
        "max_tokens": 128,
    }
    if no_think:
        payload["enable_thinking"] = False
    req = U.Request(
        EP + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY},
    )
    t0 = time.time()
    try:
        with U.urlopen(req, timeout=TIMEOUT) as r:
            d = json.loads(r.read().decode("utf-8"))
        dt = time.time() - t0
        ch = d.get("choices", [{}])[0]
        msg = ch.get("message", {})
        content = (msg.get("content") or "").strip()
        usage = d.get("usage", {})
        rt = usage.get("completion_tokens_details", {}) or {}
        return "OK", dt, content[:60], rt.get("reasoning_tokens", 0)
    except E.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        return "HTTP%d" % e.code, time.time() - t0, body[:220], None
    except Exception as e:
        return "ERR", time.time() - t0, str(e)[:180], None


def main():
    models = sys.argv[1:] or [
        "glm-5.3",
        "deepseek-v4-pro-0813",
        "qwen3.8-2.4t-a95b",
        "qwen3.8-max",
    ]
    print("endpoint=%s  key=%s...%s" % (EP, KEY[:10], KEY[-6:]))
    print("%-26s %-9s %7s %6s %s" % ("model", "status", "sec", "rTok", "content/err"))
    print("-" * 100)
    for m in models:
        st, dt, out, rt = call(m, no_think=True)
        print("%-26s %-9s %7.2f %6s %s" % (m, st, dt, rt, out))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
