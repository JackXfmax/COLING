#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B2 · 迁移测试（GPT 闭环，使用 openlux key）

目的：考察模型对修辞项"含义"的理解能否迁移到不同表述（而非死记表面）。
四类变体（只改写题干 stem，选项与 gold 字母不变，保证可比）：
  T1 同义改写   T2 方言/口语转书面普通话   T3 新造类比（平行情境）   T4 反事实（改关键要素）
指标：保留率 = variant_comp / baseline_comp（baseline=原题在 GPT 上的 comp）。

用法（需先设 OLUX_API_KEY）：
  OLUX_API_KEY=... python -u scripts/run_b2_gpt.py --limit 3 --workers 3
  OLUX_API_KEY=... python -u scripts/run_b2_gpt.py --workers 8
环境变量：B2_AUTHORS(gpt-4o)  B2_EVAL(gpt-4o-mini)  B2_PERMS(6)
"""
import json, os, sys, time, argparse, collections, re, statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_mem_layers as M
from olux import call, call_json

DATA = os.path.join(ROOT, "data", "pilot.jsonl")
AUTH = os.path.join(ROOT, "results", "b2_auth.jsonl")
RAW = os.path.join(ROOT, "results", "b2_raw.jsonl")
OUT = os.path.join(ROOT, "results", "B2_GPT.json")
PERMS = int(os.environ.get("B2_PERMS", "6"))
AUTHORS = os.environ.get("B2_AUTHORS", "gpt-4o").split(",")
EVAL_MODELS = os.environ.get("B2_EVAL", "gpt-4o-mini").split(",")
VARIANTS = ["T1", "T2", "T3", "T4"]


def load_items(limit=0):
    items = []
    with open(DATA, encoding="utf-8") as f:
        for l in f:
            if not l.strip():
                continue
            d = json.loads(l)
            if "comp_task" in d and d.get("comp_task"):
                items.append(d)
    return items[:limit] if limit else items


def load_auth():
    auth = {}
    if os.path.exists(AUTH):
        for l in open(AUTH, encoding="utf-8"):
            if l.strip():
                try:
                    d = json.loads(l)
                    auth[d["id"]] = d
                except Exception:
                    pass
    return auth


def author_prompt(it):
    ct = it["comp_task"]
    stem = ct["prompt"]
    gold = it["target_meaning"]
    orig = it.get("original", "")
    cat = it.get("category", "")
    return (
        "你是一条中文修辞理解题的题干改写器。原修辞项：%s（类别：%s），正确释义：%s。\n"
        "原题干：%s\n\n"
        "请输出 JSON：{\"T1\":..,\"T2\":..,\"T3\":..,\"T4\":..}，四种改写都只改【题干陈述】，"
        "保持同样的 6 个选项和正确答案不变：\n"
        "T1=同义改写（换近义词/句式，保留原结构与原意）；\n"
        "T2=把口语/方言/特殊表达转成标准书面普通话，不改变情境；\n"
        "T3=新造一个平行类比情境（不同故事但传达相同含义）；\n"
        "T4=反事实改写（改动一个关键要素，使情境指向一个不同但易混淆的含义）。\n"
        "每条都是一句完整的中文题干陈述（以'下列哪个情境最符合它想表达的意思？'结尾）。只输出 JSON。"
        % (orig, cat, gold, stem)
    )


def run_choice(task, model, perms=PERMS):
    keys = sorted(task["options"].keys())
    n = len(keys)
    if n == 0:
        return None
    labels = M.labels_for(n)
    gold_key = task.get("answer")
    oks = []
    for shift in range(perms):
        order = M.order_at(keys, shift, n)
        body = "\n".join("%s. %s" % (labels[i], task["options"][order[i]]) for i in range(n))
        prompt = task["prompt"] + "\n" + body + "\n只输出正确选项字母（A-%s）。" % labels[n - 1]
        resp = call(prompt, model, max_tokens=16, temperature=0.0, timeout=45)
        pred = M.parse_letter(resp)
        try:
            gi = order.index(gold_key)
            oks.append(1 if (pred is not None and pred == labels[gi]) else 0)
        except ValueError:
            oks.append(0)
    return (sum(oks) / len(oks)) if oks else None


def author_one(it):
    rec = {"id": it["id"], "category": it.get("category")}
    for attempt in range(3):
        d = call_json(author_prompt(it), AUTHORS[0], max_tokens=1100, temperature=0.7, timeout=90)
        if isinstance(d, dict) and all(k in d for k in VARIANTS):
            rec["variants"] = {k: str(d[k]) for k in VARIANTS}
            return rec
        time.sleep(2)
    rec["variants"] = None
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--skip-author", action="store_true")
    args = ap.parse_args()
    items = load_items(args.limit)
    print("[B2] 载入 %d 条（limit=%d）" % (len(items), args.limit))

    auth = load_auth()
    need = [it for it in items if it["id"] not in auth and not args.skip_author]
    if need:
        print("[B2] 需生成变体: %d 条，作者=%s" % (len(need), AUTHORS))
        authf = open(AUTH, "a", encoding="utf-8")
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(author_one, it): it["id"] for it in need}
            done = 0
            for fu in as_completed(futs):
                rec = fu.result()
                authf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                authf.flush()
                auth[rec["id"]] = rec
                done += 1
                if done % 20 == 0:
                    print("  已生成 %d/%d" % (done, len(need)))
        authf.close()
    else:
        print("[B2] 变体均已存在，跳过生成")

    done_eval = set()
    if os.path.exists(RAW):
        for l in open(RAW, encoding="utf-8"):
            if l.strip():
                try:
                    d = json.loads(l)
                    done_eval.add((d["id"], d["variant"], d["model"]))
                except Exception:
                    pass
    tasks = []
    for it in items:
        a = auth.get(it["id"])
        if not a or not a.get("variants"):
            continue
        base_task = it["comp_task"]
        for m in EVAL_MODELS:
            if (it["id"], "ORIG", m) not in done_eval:
                tasks.append((it["id"], it.get("category"), "ORIG", m, base_task))
            for v in VARIANTS:
                if (it["id"], v, m) not in done_eval:
                    vt = {"prompt": a["variants"][v], "options": base_task["options"],
                          "answer": base_task["answer"]}
                    tasks.append((it["id"], it.get("category"), v, m, vt))
    print("[B2] 待评测组合: %d" % len(tasks))
    rawf = open(RAW, "a", encoding="utf-8")
    n = 0
    if tasks:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(run_choice, task, m, PERMS): (iid, var, m) for (iid, cat, var, m, task) in tasks}
            for fu in as_completed(futs):
                iid, var, m = futs[fu]
                acc = fu.result()
                rawf.write(json.dumps({"id": iid, "variant": var, "model": m, "comp_acc": acc},
                                      ensure_ascii=False) + "\n")
                rawf.flush()
                n += 1
                if n % 50 == 0:
                    print("  评测 %d/%d" % (n, len(tasks)))
    rawf.close()
    print("[B2] 评测完成 %d 组合" % n)

    rows = []
    for l in open(RAW, encoding="utf-8"):
        if l.strip():
            try:
                rows.append(json.loads(l))
            except Exception:
                pass
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["model"], r["variant"])].append(r)
    out = {"perms": PERMS, "authors": AUTHORS, "eval_models": EVAL_MODELS, "n_items": len(items),
           "table": {}, "retention": {}}
    for m in EVAL_MODELS:
        base = [r["comp_acc"] for r in by.get((m, "ORIG"), []) if r.get("comp_acc") is not None]
        base_mean = statistics.mean(base) if base else None
        out["table"].setdefault(m, {})["ORIG"] = base_mean
        print("\n[B2] 模型 %s 保留率（vs ORIG baseline）:" % m)
        print("  ORIG = %s (n=%d)" % ("%.1f%%" % (100 * base_mean) if base_mean is not None else "—", len(base)))
        out["retention"][m] = {}
        for v in VARIANTS:
            vv = [r["comp_acc"] for r in by.get((m, v), []) if r.get("comp_acc") is not None]
            vm = statistics.mean(vv) if vv else None
            out["table"][m][v] = vm
            ret = (vm / base_mean) if (vm is not None and base_mean) else None
            out["retention"][m][v] = ret
            print("  %s = %s (n=%d)  保留率=%s" % (
                v, "%.1f%%" % (100 * vm) if vm is not None else "—", len(vv),
                "%.1f%%" % (100 * ret) if ret is not None else "—"))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[B2] 聚合写入:", OUT)


if __name__ == "__main__":
    main()
