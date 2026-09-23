#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B5 · 跨家族重写干扰项（GPT 闭环，使用 openlux key）

背景：原 comp 干扰项由 qwen-plus 撰写（gen_comp_hn.py 已确认污染），
      且 comp 评测也用 qwen 系模型 → 同家族污染。本脚本用 GPT（非 qwen 家族）
      重新撰写 5 个 hard-negative 干扰项，并在 GPT 家族评测模型上对比：
        OLD = qwen 撰写干扰项（沿用 pilot 原 comp_task）
        NEW = GPT 撰写干扰项（本脚本生成）
      同一评测模型下比较，隔离"作者家族"效应 → 污染对照。

用法（需先设 OLUX_API_KEY）：
  OLUX_API_KEY=... python -u scripts/run_b5_gpt.py --limit 3 --workers 3      # 冒烟
  OLUX_API_KEY=... python -u scripts/run_b5_gpt.py --workers 8               # 全量 508
环境变量：B5_AUTHORS(gpt-4o)  B5_EVAL(gpt-4o-mini)  B5_PERMS(6)
"""
import json, os, sys, time, argparse, collections, re
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_mem_layers as M
from olux import call, call_json

DATA = os.path.join(ROOT, "data", "pilot.jsonl")
AUTH = os.path.join(ROOT, "results", "b5_auth.jsonl")      # 生成的干净干扰项
RAW = os.path.join(ROOT, "results", "b5_raw.jsonl")        # 评测明细
OUT = os.path.join(ROOT, "results", "B5_GPT.json")
PERMS = int(os.environ.get("B5_PERMS", "6"))
AUTHORS = os.environ.get("B5_AUTHORS", "gpt-4o").split(",")
EVAL_MODELS = os.environ.get("B5_EVAL", "gpt-4o-mini").split(",")


def load_items(limit=0):
    items = []
    with open(DATA, encoding="utf-8") as f:
        for l in f:
            if not l.strip():
                continue
            d = json.loads(l)
            if "comp_task" in d and d.get("comp_task"):
                items.append(d)
    if limit:
        items = items[:limit]
    return items


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
    gold = it["target_meaning"]
    orig = it.get("original", "")
    cat = it.get("category", "")
    name = {"xiehouyu": "歇后语", "phonetic_play": "谐音双关", "allusion_idiom": "典故成语", "agrarian_proverb": "农谚"}[cat]
    return (
        "你是语言学干扰项生成器。给出一条%s：\n原文：%s\n正确释义：%s\n\n"
        "请生成 5 个【干扰性情境选项】，要求：\n"
        "1) 都是日常生活中可能发生的具体情境（与正确释义同属'情境'体裁，长度相近）；\n"
        "2) 语义上'看似符合'该表述，但实际指向错误/不同的含义，能让人在辨析时犹豫；\n"
        "3) 不能是正确释义的同义改写，不能明显荒谬；\n"
        "4) 每条独立成句，口语化、自然。\n"
        "只输出 JSON 数组（5 个字符串），不要解释。例如：[\"情境1\",\"情境2\",\"情境3\",\"情境4\",\"情境5\"]"
        % (name, orig, gold)
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


def build_options(it, distractors):
    """用 GPT 干扰项替换原 comp_task 中 5 个非 gold 选项，gold 文本/字母保留。"""
    ct = it["comp_task"]
    opts = dict(ct["options"])
    gold_letter = ct["answer"]
    non_gold = [k for k in sorted(opts.keys()) if k != gold_letter]
    assert len(non_gold) == len(distractors) == 5, (non_gold, distractors)
    for k, txt in zip(non_gold, distractors):
        opts[k] = txt
    return {"prompt": ct["prompt"], "options": opts, "answer": gold_letter}


def author_one(it):
    rec = {"id": it["id"], "category": it.get("category")}
    prompt = author_prompt(it)
    for attempt in range(3):
        arr = call_json(prompt, AUTHORS[0], max_tokens=900, temperature=0.7, timeout=90)
        if isinstance(arr, list) and len(arr) >= 5:
            rec["new_distractors"] = [str(x) for x in arr[:5]]
            return rec
        time.sleep(2)
    rec["new_distractors"] = None
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--skip-author", action="store_true", help="已生成干扰项，只重跑评测")
    args = ap.parse_args()

    items = load_items(args.limit)
    print("[B5] 载入 %d 条（limit=%d）" % (len(items), args.limit))

    # ---------- 阶段A：生成干净干扰项 ----------
    auth = load_auth()
    need = [it for it in items if it["id"] not in auth and not args.skip_author]
    if need:
        print("[B5] 需生成干扰项: %d 条，作者=%s" % (len(need), AUTHORS))
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
        print("[B5] 干扰项生成完毕")
    else:
        print("[B5] 干扰项均已存在，跳过生成")

    # ---------- 阶段B：评测 OLD vs NEW ----------
    done_eval = set()
    if os.path.exists(RAW):
        for l in open(RAW, encoding="utf-8"):
            if l.strip():
                try:
                    d = json.loads(l)
                    done_eval.add((d["id"], d["cond"], d["model"]))
                except Exception:
                    pass
    tasks = []
    for it in items:
        a = auth.get(it["id"])
        if not a or not a.get("new_distractors"):
            continue
        old_task = it["comp_task"]
        new_task = build_options(it, a["new_distractors"])
        for m in EVAL_MODELS:
            for cond, task in (("OLD", old_task), ("NEW", new_task)):
                if (it["id"], cond, m) not in done_eval:
                    tasks.append((it["id"], it.get("category"), cond, m, task))
    print("[B5] 待评测组合: %d（OLD+NEW × %d 模型）" % (len(tasks), len(EVAL_MODELS)))
    rawf = open(RAW, "a", encoding="utf-8")
    n = 0
    if tasks:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(run_choice, task, m, PERMS): (iid, cond, m) for (iid, cat, cond, m, task) in tasks}
            for fu in as_completed(futs):
                iid, cond, m = futs[fu]
                acc = fu.result()
                rawf.write(json.dumps({"id": iid, "cond": cond, "model": m, "comp_acc": acc},
                                      ensure_ascii=False) + "\n")
                rawf.flush()
                n += 1
                if n % 50 == 0:
                    print("  评测 %d/%d" % (n, len(tasks)))
    rawf.close()
    print("[B5] 评测完成 %d 组合" % n)

    # ---------- 聚合 ----------
    rows = []
    for l in open(RAW, encoding="utf-8"):
        if l.strip():
            try:
                rows.append(json.loads(l))
            except Exception:
                pass
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["model"], r["cond"])].append(r)
    import statistics
    out = {"perms": PERMS, "authors": AUTHORS, "eval_models": EVAL_MODELS, "n_items": len(items),
           "table": {}}
    print("\n[B5] === OLD(qwen撰写) vs NEW(GPT撰写) 在 GPT 评测模型上的 comp 准确率 ===")
    for m in EVAL_MODELS:
        out["table"][m] = {}
        print("模型 %s:" % m)
        for cond in ("OLD", "NEW"):
            v = [r["comp_acc"] for r in by.get((m, cond), []) if r.get("comp_acc") is not None]
            mean = statistics.mean(v) if v else None
            out["table"][m][cond] = mean
            print("  %s = %s (n=%d)" % (cond, "%.1f%%" % (100 * mean) if mean is not None else "—", len(v)))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("[B5] 聚合写入:", OUT)


if __name__ == "__main__":
    main()
