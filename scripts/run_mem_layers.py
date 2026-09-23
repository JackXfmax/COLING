# mem 四层跑批（658 扩量版，2026-09-21）
#
# 目的：对 pilot.jsonl 全量（658 条）跑 mem-L0 / mem-L1 / mem-L2 三层记忆任务，
#       配合已完成的 comp 预跑（prerank_raw_r2.jsonl），补全「四层完整数字表」。
#
# 设计（复用 distractor_prerank.py 的可靠基础设施）：
#   - call_model 默认 enable_thinking=false（百炼推理模型关思考 ~1s/调用）
#   - checkpoint 断点续跑：每 (id, model) 结果增量写入 --raw，重跑自动跳过
#   - mem-L0/L1 为自由回忆（grade_mem 子串匹配，单调用，无需置换）
#   - mem-L2 为 N 选一（与 comp 同尺度），PERMS=6 循环置换去位置偏置
#   - 判分逻辑完全照搬 run_pilot.py 的 grade_mem / parse_letter，保证与 pilot 阶段口径一致
#
# 用法:
#   BAILIAN_API_KEY=... python scripts/run_mem_layers.py --limit 1 --models qwen3.8-flash
#   BAILIAN_API_KEY=... python scripts/run_mem_layers.py            # 全量 658 × 7 模型
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
DEFAULT_RAW = os.path.join(ROOT, "results", "mem_layers_raw.jsonl")
LABELS = "ABCDEF"
PERMS = 6

DEFAULT_MODELS = ("qwen3.8-max-0902,qwen3.8-27b,qwen3.8-flash,qwen3.7-flash-2026-07-15,"
                  "kimi-k3,deepseek-v4-flash-0731,deepseek-v4.1-flash")

ENABLE_THINK = os.environ.get("MEM_THINK", "0") == "1"
PUNCT = r'[\s，。、；;：:！？!?\.\,\"\'`「」『』《》〈〉（）()\[\]【】—\-_～~]'


def norm(s):
    return re.sub(PUNCT, "", s or "")


# ---------- 调模型（与 distractor_prerank.py 一致） ----------
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
    m = re.search(r"(?:答案|选|项|应为|正确)\s*[:：]?\s*[*]?\s*([A-F])", t)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-F])\b", t)
    if m:
        return m.group(1)
    return None


def grade_mem(resp, accepts):
    """自由回忆判分：长答案用包含匹配，单字答案要求开头 10 字内出现。"""
    r = norm(resp)
    if not r:
        return False
    head = r[:40]
    for a in accepts:
        if len(a) >= 2 and a in head:
            return True
        if len(a) == 1 and a in head[:10]:
            return True
    return False


# ---------- mem-L2 选项均衡置换（与 run_pilot / distractor_prerank 一致） ----------
def labels_for(n):
    return list(LABELS[:n])


def prepare_mem_orders(items):
    counts = Counter()
    orders = {}
    for it in items:
        t = it.get("mem_l2_task")
        if not t:
            continue
        keys = sorted(t["options"].keys())
        labels = labels_for(len(keys))
        gold_key = t["answer"]
        quota = -(-len(items) // len(keys))
        perms = list(itertools.permutations(keys))
        rng = random.Random(it["id"] + "_mem")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--models", default=os.environ.get("MEM_MODELS", DEFAULT_MODELS))
    ap.add_argument("--cats", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--raw", default=DEFAULT_RAW)
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()

    # 双 provider：qwen* 走百炼，其余（OpenAI 系）走 openlux（同 distractor_prerank.py）
    dash_ep = os.environ.get("DASHSCOPE_ENDPOINT",
                             "https://dashscope.aliyuncs.com/compatible-mode/v1")
    dash_key = (os.environ.get("BAILIAN_API_KEY")
                or os.environ.get("DASHSCOPE_API_KEY")
                or os.environ.get("PILOT_API_KEY", ""))
    openlux_ep = os.environ.get("OPENLUX_ENDPOINT", "https://api.openlux.ai/v1")
    openlux_key = os.environ.get("OPENLUX_API_KEY", "")
    pilot_key = os.environ.get("PILOT_API_KEY", "")

    def resolve(model):
        # qwen* 与 dashscope 托管的 deepseek*/kimi* 走百炼；其余（OpenAI 系）走 openlux
        if model.startswith("qwen") or model.startswith("deepseek") or model.startswith("kimi"):
            return dash_ep, (dash_key or pilot_key)
        return openlux_ep, (openlux_key or pilot_key)

    if not (dash_key or openlux_key or pilot_key):
        print("❌ 未设置任何 API key（BAILIAN_API_KEY / DASHSCOPE_API_KEY / OPENLUX_API_KEY / "
              "PILOT_API_KEY），无法跑 mem。", flush=True)
        sys.exit(2)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    items = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()]
    if args.cats:
        only = set(c.strip() for c in args.cats.split(",") if c.strip())
        items = [i for i in items if i["category"] in only]
    if args.limit:
        items = items[:args.limit]
    mem_orders = prepare_mem_orders(items)

    # checkpoint
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
    print("mem 四层跑批 %d 条 × %d 模型 = 约 %d 次调用（已完成 %d 组合，本次待跑 %d）"
          % (len(items), len(models), len(items) * len(models) * (2 + PERMS),
             len(done), len(todo)), flush=True)
    print("模型：%s" % ", ".join(models), flush=True)

    rawf = open(args.raw, "a", encoding="utf-8")
    lock = threading.Lock()
    n_done = [0]

    def run_one(it, model):
        iid = it["id"]
        cat = it["category"]
        ep, kk = resolve(model)
        # L0 自由回忆
        mt = it.get("mem_task") or {}
        l0_resp = call_model(mt.get("prompt", "") + "\n请只给出答案本身，不要解释。",
                             model, ep, kk)
        l0_ok = grade_mem(l0_resp, mt.get("accept", [])) if mt else None
        # L1 首字提示自由回忆
        l1 = it.get("mem_l1_task")
        l1_ok = None
        if l1:
            l1_resp = call_model(l1["prompt"] + "\n请只给出答案本身，不要解释。",
                                model, ep, kk)
            l1_ok = grade_mem(l1_resp, mt.get("accept", []))
        # L2 N 选一（PERMS=6 去偏）
        l2_ok = None
        l2_acc = None
        t = it.get("mem_l2_task")
        if t:
            base, _ = mem_orders.get(iid, (sorted(t["options"].keys()), t["answer"]))
            keys = sorted(t["options"].keys())
            n = len(keys)
            labels = labels_for(n)
            gold_key = t["answer"]
            ok_list = []
            for shift in range(min(PERMS, n)):
                disp = order_at(base, shift, n)
                opts_txt = "\n".join("%s. %s" % (labels[i], t["options"][disp[i]])
                                     for i in range(n))
                prompt = t["prompt"] + "\n" + opts_txt + "\n只输出正确选项字母（A-%s）。" % labels[n - 1]
                p = parse_letter(call_model(prompt, model, ep, kk))
                if p is None or p not in labels:
                    ok_list.append(False)
                    continue
                chosen_key = disp[labels.index(p)]
                ok_list.append(chosen_key == gold_key)
            l2_acc = sum(ok_list) / float(len(ok_list))
            l2_ok = (l2_acc >= 0.5)
        return {"id": iid, "model": model, "category": cat,
                "l0_ok": l0_ok, "l1_ok": l1_ok, "l2_ok": l2_ok, "l2_acc": l2_acc}

    def work(pair):
        it, m = pair
        rec = run_one(it, m)
        with lock:
            rawf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            rawf.flush()
            n_done[0] += 1
            if n_done[0] % 25 == 0:
                print("  ... 已完成本次任务 %d/%d" % (n_done[0], len(todo)), flush=True)
        return rec

    workers = args.workers or min(10, len(models) * 2)
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, todo))
    rawf.close()

    # ---------- 聚合（读 raw 全量） ----------
    rows = [json.loads(l) for l in open(args.raw, encoding="utf-8") if l.strip()]
    print("\n" + "=" * 78)
    print("mem 四层跑批完成，共 %d 条 (id,model) 记录" % len(rows))
    print("=" * 78)
    # per model × per class
    by = defaultdict(list)
    for r in rows:
        by[(r["model"], r["category"])].append(r)
    print("%-26s %-14s %6s %6s %6s" % ("model", "class", "L0%", "L1%", "L2%"))
    for (m, c), rs in sorted(by.items()):
        l0 = [x["l0_ok"] for x in rs if x["l0_ok"] is not None]
        l1 = [x["l1_ok"] for x in rs if x["l1_ok"] is not None]
        l2 = [x["l2_ok"] for x in rs if x["l2_ok"] is not None]
        l0p = 100.0 * sum(l0) / len(l0) if l0 else float("nan")
        l1p = 100.0 * sum(l1) / len(l1) if l1 else float("nan")
        l2p = 100.0 * sum(l2) / len(l2) if l2 else float("nan")
        print("%-26s %-14s %6.1f %6.1f %6.1f" % (m, c, l0p, l1p, l2p))


if __name__ == "__main__":
    main()
