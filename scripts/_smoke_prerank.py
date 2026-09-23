"""小冒烟：用真实 comp 题验证百炼新模型（含推理模型）的原始输出与字母解析。
用法：BAILIAN_API_KEY=... python scripts/_smoke_prerank.py <model...>
"""
import os
import sys
import json
import time

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import distractor_prerank as dp  # noqa: E402

ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "pilot.jsonl")
EP = "https://dashscope.aliyuncs.com/compatible-mode/v1"
KEY = os.environ.get("BAILIAN_API_KEY", "")

models = sys.argv[1:] or ["qwen3.8-flash"]
items = [json.loads(l) for l in open(DATA, encoding="utf-8") if l.strip()]
items = [i for i in items if i["category"] != "allusion_idiom"][:int(os.environ.get("SMOKE_N", "1"))]

for it in items:
    opts = it["comp_task"]["options"]
    keys = sorted(opts.keys())
    labels = dp.labels_for(len(keys))
    gold = it["comp_task"]["answer"]
    print("=" * 72)
    print("ID=%s cat=%s gold=%s" % (it["id"], it["category"], gold))
    print("STEM:", it["comp_task"]["prompt"][:140].replace("\n", " "))
    print("OPTS:", {k: opts[k][:24] for k in keys})
    for m in models:
        opts_txt = "\n".join("%s. %s" % (labels[i], opts[keys[i]]) for i in range(len(keys)))
        prompt = it["comp_task"]["prompt"] + "\n" + opts_txt + "\n只输出正确选项字母（A-%s）。" % labels[-1]
        t0 = time.time()
        resp = dp.call_model(prompt, m, EP, KEY)
        dt = time.time() - t0
        p = dp.parse_letter(resp)
        flag = "✅" if p == labels[keys.index(gold)] else "  "
        print("  %s %-26s %5.1fs parsed=%s resp=%r" % (flag, m, dt, p, resp[:180]))
