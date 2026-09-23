"""小冒烟 v2：验证百炼新模型在真实 comp 题上的耗时/输出，并测试关思考（enable_thinking=false）。
用法：BAILIAN_API_KEY=... python -u scripts/_smoke_nothink.py <model...>
  环境变量：NO_THINK=1 关闭思考；SMOKE_TIMEOUT 秒；SMOKE_MAXTOK tokens；SMOKE_N 题数
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "pilot.jsonl")
EP = os.environ.get("BAILIAN_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
KEY = os.environ.get("BAILIAN_API_KEY", "")
NO_THINK = os.environ.get("NO_THINK", "0") == "1"
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "90"))
LABELS = "ABCDEF"


def call(m, prompt):
    payload = {"model": m, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0, "max_tokens": int(os.environ.get("SMOKE_MAXTOK", "512"))}
    if NO_THINK:
        payload["enable_thinking"] = False
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(EP.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + KEY})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            d = json.loads(r.read().decode("utf-8"))
        msg = d["choices"][0]["message"]
        return (time.time() - t0, msg.get("content") or "", msg.get("reasoning_content") or "",
                d.get("usage", {}))
    except urllib.error.HTTPError as e:
        return time.time() - t0, "[HTTP %s] %s" % (e.code, e.read().decode("utf-8", "replace")[:160]), "", {}
    except Exception as e:
        return time.time() - t0, "[ERR %s] %s" % (type(e).__name__, e), "", {}


def main():
    models = sys.argv[1:] or ["qwen3.8-flash"]
    items = [json.loads(l) for l in open(DATA, encoding="utf-8") if l.strip()]
    items = [i for i in items if i["category"] != "allusion_idiom"][:int(os.environ.get("SMOKE_N", "1"))]
    print("NO_THINK=%s  TIMEOUT=%ds" % (NO_THINK, TIMEOUT))
    for it in items:
        opts = it["comp_task"]["options"]
        keys = sorted(opts.keys())
        n = len(keys)
        print("=" * 72)
        print("ID=%s gold=%s" % (it["id"], it["comp_task"]["answer"]))
        for m in models:
            opts_txt = "\n".join("%s. %s" % (LABELS[i], opts[keys[i]]) for i in range(n))
            prompt = it["comp_task"]["prompt"] + "\n" + opts_txt + "\n只输出正确选项字母（A-%s）。" % LABELS[n - 1]
            dt, c, rc, usage = call(m, prompt)
            print("  %-26s %6.1fs  content=%r  reason_len=%d  usage=%s"
                  % (m, dt, c[:120], len(rc), usage))


if __name__ == "__main__":
    main()
