#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B7 · Zhipu(glm) + MiniMax 补测（第三个中国厂商）

背景：跨家族报告曾跑过 glm-5.2，但因 run_pilot.py 无 enable_thinking=false，
      思考链吃满 max_tokens=1024 导致响应被截断（80 题仅 33 行可解析，XHY 仅 1 行）→ 被排除。
      MiniMax-M2.7 有结果文件但未纳入。
修复：本脚本复用 run_mem_layers.py 的 call_model（已含 enable_thinking=false），
      强制走百炼端点，按跨家族同一 80 题子集（各类前 20 条）重跑四层。

口径：mem-L0 自由回忆 / mem-L1 半段提示 / mem-L2 N选一(PERMS=6) / comp 六选一(PERMS=6)
      —— 与 CROSSFAMILY_REPORT 完全一致，结果可直接并入跨家族表。

用法：
  BAILIAN_API_KEY=... python -u scripts/run_b7_zhipu_minimax.py
可选环境变量：B7_MODELS（逗号分隔）、B7_WORKERS、B7_ENDPOINT
"""
import json, os, sys, time, collections
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_mem_layers as M  # call_model 已含 enable_thinking=false

EP = os.environ.get("B7_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
KEY = os.environ.get("BAILIAN_API_KEY", "")
MODELS = [m.strip() for m in os.environ.get("B7_MODELS", "glm-5.2,MiniMax-M2.5").split(",") if m.strip()]
PERMS = 6


def _call_raw(prompt, model, eth=False):
    """原始 OpenAI 兼容调用（可控制是否带 enable_thinking）"""
    import urllib.request
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.0, "max_tokens": int(os.environ.get("B7_MAX_TOKENS", "512"))}
    if eth:
        payload["enable_thinking"] = False
    req = urllib.request.Request(
        EP.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        m = d["choices"][0]["message"]
        return (m.get("content") or m.get("reasoning_content") or "")
    except Exception as e:
        return "[ERROR] %s" % e


def call(prompt, model):
    """分模型路由：MiniMax 实测不接受 enable_thinking 参数（传则 400），故走不带该参数的调用。"""
    if model.lower().startswith("minimax"):
        return _call_raw(prompt, model, eth=False)
    return M.call_model(prompt, model, EP, KEY)
WORKERS = int(os.environ.get("B7_WORKERS", "8"))
RAW = os.path.join(ROOT, "results", "b7_raw.jsonl")
REF = os.path.join(ROOT, "results", "pilot_qwen-max.jsonl")   # 跨家族 80 题 id 来源
DATA = os.path.join(ROOT, "data", "pilot.jsonl")
OUTMD = os.path.join(ROOT, "results", "B7_ZHIPU_MINIMAX.md")

CATN = {"xiehouyu": "XHY", "phonetic_play": "YY",
        "allusion_idiom": "AID", "agrarian_proverb": "NY"}

# ---------- 载入 80 题子集 ----------
with open(REF, encoding="utf-8") as f:
    ids80 = set(json.loads(l)["id"] for l in f if l.strip())
items = []
with open(DATA, encoding="utf-8") as f:
    for l in f:
        if not l.strip():
            continue
        d = json.loads(l)
        if d["id"] in ids80:
            items.append(d)
print("[B7] 80题子集载入: %d 条 (参考集 %d)" % (len(items), len(ids80)))

# ---------- checkpoint ----------
done = set()
if os.path.exists(RAW):
    with open(RAW, encoding="utf-8") as f:
        for l in f:
            if l.strip():
                try:
                    d = json.loads(l)
                    done.add((d["id"], d["model"]))
                except Exception:
                    pass
print("[B7] 已完成组合: %d，待跑: %d" % (len(done), len(items) * len(MODELS) - len(done)))


def run_choice(task, model, ep, key, perms=PERMS):
    """N选一：循环置换去偏，返回 (acc, preds)"""
    if not task:
        return None, []
    keys = sorted(task["options"].keys())
    n = len(keys)
    if n == 0:
        return None, []
    labels = M.labels_for(n)
    gold_key = task.get("answer")
    oks, preds = [], []
    for shift in range(perms):
        order = M.order_at(keys, shift, n)
        body = "\n".join("%s. %s" % (labels[i], task["options"][order[i]]) for i in range(n))
        prompt = task["prompt"] + "\n" + body + "\n只输出正确选项字母（A-%s）。" % labels[n - 1]
        resp = call(prompt, model)
        pred = M.parse_letter(resp)
        preds.append(pred)
        try:
            gi = order.index(gold_key)
            oks.append(1 if (pred is not None and pred == labels[gi]) else 0)
        except ValueError:
            oks.append(0)
    return (sum(oks) / len(oks)) if oks else None, preds


def run_free(task, model, ep, key):
    """自由回忆：返回 (ok, resp)"""
    if not task:
        return None, ""
    resp = call(task["prompt"], model)
    accepts = [task.get("answer")] + list(task.get("accept") or [])
    accepts = [a for a in accepts if a]
    return (1 if M.grade_mem(resp, accepts) else 0), resp


def run_one(it, model):
    rec = {"id": it["id"], "model": model, "category": it.get("category")}
    try:
        o0, r0 = run_free(it.get("mem_task"), model, EP, KEY)
        o1, r1 = run_free(it.get("mem_l1_task"), model, EP, KEY)
    except Exception as e:
        o0 = o1 = None
        r0 = r1 = "[ERR] %s" % e
    try:
        l2, p2 = run_choice(it.get("mem_l2_task"), model, EP, KEY)
    except Exception as e:
        l2, p2 = None, []
    try:
        cp, pc = run_choice(it.get("comp_task"), model, EP, KEY)
    except Exception as e:
        cp, pc = None, []
    rec.update({"l0_ok": o0, "l1_ok": o1, "l2_acc": l2, "comp_acc": cp,
                "mem_resp": r0[:200], "comp_preds": pc})
    return rec


# ---------- 主循环 ----------
todo = [(it, m) for m in MODELS for it in items if (it["id"], m) not in done]
print("[B7] 开始跑批: %d 组合 × %d 次调用/组合 ≈ %d 次 API 调用"
      % (len(todo), 2 + 2 * PERMS, len(todo) * (2 + 2 * PERMS)))
t0 = time.time()
rawf = open(RAW, "a", encoding="utf-8")
n = 0
if todo:
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run_one, it, m): (it["id"], m) for it, m in todo}
        for fu in as_completed(futs):
            try:
                rec = fu.result()
            except Exception as e:
                iid, m = futs[fu]
                rec = {"id": iid, "model": m, "category": None, "l0_ok": None,
                       "l1_ok": None, "l2_acc": None, "comp_acc": None,
                       "mem_resp": "[ERR] %s" % e, "comp_preds": []}
            rawf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            rawf.flush()
            n += 1
            if n % 20 == 0:
                el = time.time() - t0
                print("  %d/%d  (%.0fs, %.2f 组合/s)" % (n, len(todo), el, n / el), flush=True)
rawf.close()
print("[B7] 跑批完成，用时 %.1f 分钟" % ((time.time() - t0) / 60))

# ---------- 汇总 ----------
rows = []
with open(RAW, encoding="utf-8") as f:
    for l in f:
        if l.strip():
            try:
                rows.append(json.loads(l))
            except Exception:
                pass

by = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    by[r["model"]][r["category"]].append(r)

lines = ["# B7 · Zhipu(glm) + MiniMax 补测结果", "",
         "> 脚本：`scripts/run_b7_zhipu_minimax.py`（强制百炼端点 + `enable_thinking=false`，修复历史截断问题）。",
         "> 子集：跨家族同一 **80 题**（XHY/YY/AID/NY 各 20）；口径：mem-L0/L1、mem-L2(PERMS=6)、comp(PERMS=6)。",
         "> 用途：并入 `CROSSFAMILY_REPORT.md`，补齐**第三个中国厂商**。", ""]

pct = lambda v: "—" if v is None else "%.1f%%" % (100 * v)
def avg(rs, f):
    v = [r[f] for r in rs if r.get(f) is not None]
    return statistics.mean(v) if v else None
import statistics

for m in MODELS:
    lines += ["## %s" % m, "",
              "| 类别 | n | mem-L0 | mem-L1 | mem-L2 | comp |", "|---|---|---|---|---|---|"]
    for cat in ["xiehouyu", "phonetic_play", "allusion_idiom", "agrarian_proverb"]:
        rs = by[m].get(cat, [])
        if not rs:
            continue
        lines.append("| %s | %d | %s | %s | %s | %s |" % (
            CATN.get(cat, cat), len(rs), pct(avg(rs, "l0_ok")), pct(avg(rs, "l1_ok")),
            pct(avg(rs, "l2_acc")), pct(avg(rs, "comp_acc"))))
    allr = [r for c in by[m].values() for r in c]
    lines.append("| **整体** | %d | **%s** | **%s** | **%s** | **%s** |" % (
        len(allr), pct(avg(allr, "l0_ok")), pct(avg(allr, "l1_ok")),
        pct(avg(allr, "l2_acc")), pct(avg(allr, "comp_acc"))))
    miss = sum(1 for r in allr if r.get("comp_acc") is None)
    lines += ["", "- 解析失败/缺失：comp %d 条，mem-L2 %d 条（若偏高说明该模型格式不稳定，需检查）"
              % (miss, sum(1 for r in allr if r.get("l2_acc") is None)), ""]

with open(OUTMD, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("[B7] 汇总写入:", OUTMD)
for m in MODELS:
    allr = [r for c in by[m].values() for r in c]
    print("  %-22s n=%3d  L0=%s L1=%s L2=%s comp=%s" % (
        m, len(allr), pct(avg(allr, "l0_ok")), pct(avg(allr, "l1_ok")),
        pct(avg(allr, "l2_acc")), pct(avg(allr, "comp_acc"))))
