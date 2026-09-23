# 第二关 · 干扰项强度均衡（模型预跑版 v2）
#
# 目的：每条 comp 题跑多个模型，PERMS 次循环右移去位置偏置，统计每个干扰项被错选率；
#       某干扰项错选率 > 40% 标「过强」需重写。目标：各干扰项错选率接近随机期望。
#
# v2 变更（2026-09-21）：
#   1. 支持百炼系新模型（qwen/kimi/deepseek…）。这些模型默认开启思考，长题干下单调用
#      可达 >45s 超时；实测 payload 加 enable_thinking=false 后降到 ~1s 且答案正确，
#      故默认关闭思考（设 PRERANK_THINK=1 可恢复）。
#   2. checkpoint 断点续跑：每题×模型的结果增量写入 --raw（jsonl），重跑自动跳过已完成
#      组合，应对后台中断。
#   3. 聚合从 raw 读全量，输出「混合口径」+「per-model 口径」。
#
# 用法:
#   BAILIAN_API_KEY=... python scripts/distractor_prerank.py --limit 3 --models "qwen3.8-flash,kimi-k3"
#   BAILIAN_API_KEY=... python scripts/distractor_prerank.py          # 全量（默认 7 模型）
import os
import sys
import json
import re
import random
import time
import argparse
import itertools
import threading
import urllib.request as urllib_request
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DEFAULT_DATA = os.path.join(DATA, "pilot.jsonl")
DEFAULT_RAW = os.path.join(ROOT, "results", "prerank_raw.jsonl")
LABELS = "ABCDEFG"
PERMS = 6

DEFAULT_MODELS = ("qwen3.8-max-0902,qwen3.8-27b,qwen3.8-flash,qwen3.7-flash-2026-07-15,"
                  "kimi-k3,deepseek-v4-flash-0731,deepseek-v4.1-flash")

ENABLE_THINK = os.environ.get("PRERANK_THINK", "0") == "1"


# ---------- 确定性排列（与 run_pilot / diagnose_blindspots 一致） ----------
def labels_for(n):
    return list(LABELS[:n])


def prepare_orders(items):
    counts = Counter()
    orders = {}
    for it in items:
        keys = sorted(it["comp_task"]["options"].keys())
        labels = labels_for(len(keys))
        gold_key = it["comp_task"]["answer"]
        quota = -(-len(items) // len(keys))
        perms = list(itertools.permutations(keys))
        rng = random.Random(it["id"])
        cand = perms[:]
        rng.shuffle(cand)
        chosen = None
        for o in cand:
            g = labels[list(o).index(gold_key)]
            if counts[g] < quota:
                chosen = o
                break
        if chosen is None:
            chosen = cand[0]
        g = labels[list(chosen).index(gold_key)]
        counts[g] += 1
        orders[it["id"]] = (list(chosen), g)
    return orders


def order_at(base, shift, n):
    k = shift % n
    if k == 0:
        return list(base)
    return list(base[-k:]) + list(base[:-k])


# ---------- 调模型 ----------
def call_model(prompt, model, endpoint, api_key, max_tokens=None, _depth=0):
    if max_tokens is None:
        max_tokens = int(os.environ.get("PILOT_MAX_TOKENS", "256"))
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.0, "max_tokens": max_tokens}
    if not ENABLE_THINK:
        payload["enable_thinking"] = False
    req = urllib_request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + api_key})
    MAX_RETRY = int(os.environ.get("PILOT_RETRY", "3"))
    try:
        with urllib_request.urlopen(req, timeout=int(os.environ.get("PILOT_TIMEOUT", "45"))) as r:
            data = json.loads(r.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        content = msg.get("content") or msg.get("reasoning_content") or ""
        content = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", "", content, flags=re.S)
        if not content.strip() and _depth < MAX_RETRY:
            time.sleep(1.5 * (_depth + 1))
            return call_model(prompt, model, endpoint, api_key, max_tokens, _depth + 1)
        return content
    except Exception as e:
        if _depth < MAX_RETRY:
            time.sleep(1.5 * (_depth + 1))
            return call_model(prompt, model, endpoint, api_key, max_tokens, _depth + 1)
        return "[ERROR] %s" % e


def parse_letter(text):
    if not text or "[ERROR]" in text:
        return None
    t = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", "", text, flags=re.S)
    m = re.search(r"(?:答案|选|项|应为|正确)\s*[:：]?\s*[*]?\s*([A-G])", t)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-G])\b", t)
    if m:
        return m.group(1)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--models", default=os.environ.get("PILOT_PRERANK_MODELS", DEFAULT_MODELS))
    ap.add_argument("--cats", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--perms", type=int, default=PERMS)
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "distractor_prerank.json"))
    ap.add_argument("--raw", default=DEFAULT_RAW)
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    # 多 provider 解析：百炼系（qwen/kimi/deepseek/glm/minimax…）走 DashScope 兼容端点，
    # 其余（OpenAI 系）走 openlux。
    dash_ep = os.environ.get("DASHSCOPE_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    dash_key = (os.environ.get("BAILIAN_API_KEY")
                or os.environ.get("DASHSCOPE_API_KEY")
                or os.environ.get("PILOT_API_KEY", ""))
    openlux_ep = os.environ.get("OPENLUX_ENDPOINT", "https://api.openlux.ai/v1")
    openlux_key = os.environ.get("OPENLUX_API_KEY", "")
    pilot_key = os.environ.get("PILOT_API_KEY", "")
    BAILIAN_PREFIXES = ("qwen", "kimi", "deepseek", "glm", "minimax", "moonshot", "ernie")

    def resolve(model):
        m = model.lower()
        if m.startswith(BAILIAN_PREFIXES):
            return dash_ep, (dash_key or pilot_key)
        return openlux_ep, (openlux_key or pilot_key)

    if not (dash_key or openlux_key or pilot_key):
        print("❌ 未设置任何 API key（BAILIAN_API_KEY / DASHSCOPE_API_KEY / OPENLUX_API_KEY / "
              "PILOT_API_KEY），无法预跑。")
        sys.exit(2)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    items = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()]
    if args.cats:
        only = set(c.strip() for c in args.cats.split(",") if c.strip())
        items = [i for i in items if i["category"] in only]
    if args.limit:
        items = items[:args.limit]
    items = [i for i in items if i["category"] != "allusion_idiom"]  # AID 干扰项=近义成语，机制不同

    orders = prepare_orders(items)

    # checkpoint：读已完成 (id, model)
    done = set()
    if os.path.exists(args.raw):
        for l in open(args.raw, encoding="utf-8"):
            l = l.strip()
            if not l:
                continue
            try:
                d = json.loads(l)
                done.add((d["id"], d["model"]))
            except Exception:
                pass

    todo = [(it, m) for it in items for m in models if (it["id"], m) not in done]
    print("预跑 %d 条 × %d 模型 × %d 置换 = 约 %d 次调用（已完成 %d 个 题×模型 组合，本次待跑 %d）"
          % (len(items), len(models), args.perms, len(items) * len(models) * args.perms,
             len(done), len(todo)))
    print("模型：%s" % ", ".join(models))

    rawf = open(args.raw, "a", encoding="utf-8")
    lock = threading.Lock()
    n_done = [0]

    def run_one(it, model):
        iid = it["id"]
        base, _ = orders[iid]
        keys = sorted(it["comp_task"]["options"].keys())
        n = len(keys)
        labels = labels_for(n)
        stem = it["comp_task"]["prompt"]
        tot = 0
        err = defaultdict(int)
        for shift in range(min(args.perms, n)):
            disp = order_at(base, shift, n)
            opts_txt = "\n".join("%s. %s" % (labels[i], it["comp_task"]["options"][disp[i]])
                                 for i in range(n))
            prompt = stem + "\n" + opts_txt + "\n只输出正确选项字母（A-%s）。" % labels[n - 1]
            ep, k = resolve(model)
            p = parse_letter(call_model(prompt, model, ep, k))
            if p is None or p not in labels:
                continue
            chosen_key = disp[labels.index(p)]
            tot += 1
            if chosen_key != it["comp_task"]["answer"]:
                err[chosen_key] += 1
        return {"id": iid, "model": model, "tot": tot, "err": dict(err)}

    def work(pair):
        it, m = pair
        rec = run_one(it, m)
        with lock:
            rawf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            rawf.flush()
            n_done[0] += 1
            if n_done[0] % 25 == 0:
                print("  ... 已完成本次任务 %d/%d" % (n_done[0], len(todo)))
        return rec

    workers = args.workers or min(8, len(models) * 2)
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, todo))
    rawf.close()

    # ---------- 聚合（读 raw 全量） ----------
    sem_tot = Counter()                     # iid -> 有效预测
    sem_err = defaultdict(int)              # (iid, key) -> 错选
    pm_tot = Counter()                      # (model, iid)
    pm_err = defaultdict(int)               # (model, iid, key)
    n_pred = 0
    for l in open(args.raw, encoding="utf-8"):
        l = l.strip()
        if not l:
            continue
        try:
            d = json.loads(l)
        except Exception:
            continue
        iid = d["id"]
        m = d["model"]
        t = d.get("tot", 0)
        if t == 0:
            continue
        sem_tot[iid] += t
        pm_tot[(m, iid)] += t
        n_pred += t
        for k, v in (d.get("err") or {}).items():
            sem_err[(iid, k)] += v
            pm_err[(m, iid, k)] += v

    print("\n" + "=" * 78)
    print("第二关 · 干扰项强度均衡  (有效预测 %d 次, 混合口径)" % n_pred)
    print("=" * 78)
    over = []
    for it in items:
        iid = it["id"]
        opts = it["comp_task"]["options"]
        keys = sorted(opts.keys())
        gk = it["comp_task"]["answer"]
        tot = sem_tot[iid]
        if tot == 0:
            continue
        rate = {k: sem_err[(iid, k)] / tot for k in keys if k != gk}
        strong = [(k, round(100 * rate[k], 1)) for k in rate if rate[k] > 0.40]
        if strong:
            over.append({"id": iid, "over": strong,
                         "distractor_text": {k: opts[k] for k, _ in strong}})
            print("   [过强] %s  错选率>40%%: %s" %
                  (iid, ", ".join("%s=%.0f%%(%s)" % (k, v, opts[k][:18]) for k, v in strong)))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(over, f, ensure_ascii=False, indent=2)
    print("\n过强干扰项条目(混合口径): %d  → 已写入 %s" % (len(over), args.out))

    # per-model 口径
    per_model = {}
    for m in models:
        mo = []
        for it in items:
            iid = it["id"]
            opts = it["comp_task"]["options"]
            keys = sorted(opts.keys())
            gk = it["comp_task"]["answer"]
            tot = pm_tot[(m, iid)]
            if tot == 0:
                continue
            rate = {k: pm_err[(m, iid, k)] / tot for k in keys if k != gk}
            strong = [(k, round(100 * rate[k], 1)) for k in rate if rate[k] > 0.40]
            if strong:
                mo.append({"id": iid, "over": strong})
        per_model[m] = mo
    by_model_path = (os.environ.get("PRERANK_BY_MODEL_PATH")
                     or os.path.join(ROOT, "results", "prerank_by_model.json"))
    with open(by_model_path, "w", encoding="utf-8") as f:
        json.dump({"models": models,
                   "per_model_over_count": {m: len(per_model[m]) for m in models},
                   "per_model_over": per_model}, f, ensure_ascii=False, indent=2)
    print("per-model 过强条目数: %s  → 已写入 %s"
          % (", ".join("%s=%d" % (m, len(per_model[m])) for m in models), by_model_path))


if __name__ == "__main__":
    main()
