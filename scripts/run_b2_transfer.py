#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B2 · 迁移/鲁棒性测试（泛化诊断）
================================
科学问题：模型在原始 comp 上低分，究竟是「过拟合了特定措辞/方言线索」，
          还是「真的没习得 表达→含义 的映射」？

构造四类受控变体（均不改变正确答案），测 comp 在扰动下的保留率：
  T1 同义改写    ：题干 + 正确选项用同义表达重写（语义不变，措辞变）  → 测措辞鲁棒性
  T2 方言转普通话：original 的方言表达改写为普通话说法（去方言线索）   → 测方言依赖
  T3 新造类比    ：保留 target_meaning，构造一个全新、未出现过的类比情境 → 测抽象泛化
  T4 反事实      ：修改情境中的关键实体/关系，使正确选项文字改变       → 测是否真理解

每个变体生成一个 comp_task（题干+6选项，沿用 PERMS=6 循环置换去位置偏置），
用百炼 7 模型跑（与 B1 同口径）。指标：
  保留率_Tk = comp(变体 Tk) / comp(原始)
  鲁棒性 = min(保留率_T1, 保留率_T2)   泛化 = 保留率_T3   抗干扰 = 保留率_T4

两阶段（均带 checkpoint）：
  1) 生成阶段 --gen ：用 LLM 把原始 comp_task 改写成四类变体，缓存 results/b2_variants.json
  2) 跑分阶段      ：对变体 comp_task 按 PERMS=6 跑分，落盘 results/b2_transfer_raw.jsonl
聚合生成 results/B2_TRANSFER.json（各模型 × 变体 的保留率）。

用法：
  BAILIAN_API_KEY=... python -u scripts/run_b2_transfer.py --cats xiehouyu --gen   # 先生成变体
  BAILIAN_API_KEY=... python -u scripts/run_b2_transfer.py --cats xiehouyu          # 再跑分
  BAILIAN_API_KEY=... python -u scripts/run_b2_transfer.py --cats xiehouyu --limit 3 --gen  # 冒烟
"""
import json, os, sys, time, argparse, collections, re
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_mem_layers as M

EP = "https://dashscope.aliyuncs.com/compatible-mode/v1"
KEY = os.environ.get("BAILIAN_API_KEY", "")
# 改写用较强但便宜的模型；如需避开某家族风格可改 env B2_GEN_MODEL
GEN_MODEL = os.environ.get("B2_GEN_MODEL", "qwen-plus")
DEFAULT_MODELS = ["qwen3.8-max-0902", "kimi-k3", "deepseek-v4.1-flash",
                  "qwen3.7-flash-2026-07-15", "qwen3.8-flash", "qwen3.8-27b",
                  "deepseek-v4-flash-0731"]
VARIANTS = ["T1_paraphrase", "T2_dialect", "T3_novel", "T4_counterfactual"]
PERMS = 6

TRANSFORM_PROMPTS = {
    "T1_paraphrase": (
        "你是语言学标注助手。下面是一道歇后语/修辞理解题（题干+6个选项+正确答案）。\n"
        "任务：把【题干】和【正确选项】用同义但措辞不同的方式重写，保持原意与正确答案不变，"
        "其余 5 个干扰项也做相应同义改写（可换说法但不可改变它们之间的区分关系）。\n"
        "仅输出一个 JSON：{\"prompt\": 新题干, \"options\": {A:..,B:..,C:..,D:..,E:..,F:..}, \"answer\": 正确字母}"),
    "T2_dialect": (
        "你是方言转写助手。下面是一道含方言表达的修辞理解题。\n"
        "任务：把题干及选项中出现的方言说法改写为普通话说法（去方言线索），但保留题目考查的含义与正确答案不变。\n"
        "仅输出 JSON：{\"prompt\": 新题干, \"options\": {A:..,B:..,C:..,D:..,E:..,F:..}, \"answer\": 正确字母}"),
    "T3_novel": (
        "你是类比构造助手。给定一道修辞理解题的正确含义，请构造一个全新的、生活中常见的类比情境来考查同一含义，"
        "并相应生成 6 个选项（1 正确+5 干扰），干扰项须是 plausible 但错误的含义映射。\n"
        "仅输出 JSON：{\"prompt\": 新情境题干, \"options\": {A:..,B:..,C:..,D:..,E:..,F:..}, \"answer\": 正确字母}"),
    "T4_counterfactual": (
        "你是反事实改写助手。下面是一道修辞理解题。\n"
        "任务：修改情境中的关键实体或关系，使得题目仍考查同一类修辞但【正确选项的文字表述】随之改变"
        "（即正确答案换成另一个选项的文字），干扰项相应调整。含义类型不变。\n"
        "仅输出 JSON：{\"prompt\": 新题干, \"options\": {A:..,B:..,C:..,D:..,E:..,F:..}, \"answer\": 新正确字母}"),
}


def labels(n):
    return [chr(65 + i) for i in range(n)]


def perms(n):
    base = list(range(n))
    return [tuple(base[k:] + base[:k]) for k in range(n)]


def _extract_json(text):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def gen_variant(item, variant):
    ct = item["comp_task"]
    user = TRANSFORM_PROMPTS[variant] + "\n\n原始题干:\n" + ct["prompt"] + "\n选项:\n" + \
        "\n".join("%s. %s" % (k, v) for k, v in ct["options"].items()) + \
        "\n正确答案: " + ct["answer"]
    resp = M.call_model(user, GEN_MODEL, EP, KEY)
    j = _extract_json(resp)
    if not j or "options" not in j or "answer" not in j or "prompt" not in j:
        return None
    # 规整：选项必须 6 个、answer 在其中
    opts = j["options"]
    if not isinstance(opts, dict) or len(opts) != 6 or j["answer"] not in opts:
        return None
    return {"prompt": j["prompt"], "options": opts, "answer": j["answer"]}


def score_one(vtask, model):
    opts = vtask["options"]
    n = len(opts)
    keys = sorted(opts.keys())
    ans = vtask["answer"]
    correct = 0
    for perm in perms(n)[:PERMS]:
        disp = [opts[keys[perm[i]]] for i in range(n)]
        gold_pos = perm.index(keys.index(ans))
        gold = labels(n)[gold_pos]
        opts_txt = "\n".join("%s. %s" % (labels(n)[i], disp[i]) for i in range(n))
        p = vtask["prompt"] + "\n" + opts_txt + \
            "\n只输出正确选项字母（A-%s）。" % labels(n)[n - 1]
        try:
            r = M.call_model(p, model, EP, KEY)
            if M.parse_letter(r) == gold:
                correct += 1
        except Exception:
            pass
    return correct, PERMS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", default="xiehouyu")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--gen", action="store_true", help="先生成变体（写 b2_variants.json）")
    ap.add_argument("--limit", type=int, default=0, help="每类最多 N 条（冒烟用）")
    ap.add_argument("--raw", default="results/b2_transfer_raw.jsonl")
    ap.add_argument("--out", default="results/B2_TRANSFER.json")
    ap.add_argument("--baseline_json", default="results/rag_conditions.json",
                    help="B1 四条件结果，提供 A 条件 comp 作为保留率基线")
    ap.add_argument("--variants_json", default="results/b2_variants.json")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    cats = [c.strip() for c in args.cats.split(",") if c.strip()]

    items = [json.loads(l) for l in open(os.path.join(ROOT, "data", "pilot.jsonl"),
                                         encoding="utf-8") if l.strip()]
    items = [it for it in items if it["category"] in cats]
    if args.limit:
        capped, seen = [], collections.Counter()
        for it in items:
            if seen[it["category"]] < args.limit:
                capped.append(it); seen[it["category"]] += 1
        items = capped
    print("[B2] 载入 %d 题 cats=%s 变体=%s 模型=%d" % (len(items), cats, variants, len(models)))

    # ---------- 生成阶段 ----------
    variants_cache = {}
    if os.path.exists(args.variants_json):
        with open(args.variants_json, encoding="utf-8") as f:
            variants_cache = json.load(f)
    if args.gen:
        gen_done = set(variants_cache.keys())
        todo = [(it["id"], v) for it in items for v in variants
                if "%s|%s" % (it["id"], v) not in gen_done]
        print("[B2] 待生成变体: %d（缓存 %d）" % (len(todo), len(gen_done)))
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {}
            for tid, v in todo:
                it = next(x for x in items if x["id"] == tid)
                futs[ex.submit(gen_variant, it, v)] = (tid, v)
            for f in as_completed(futs):
                tid, v = futs[f]
                key = "%s|%s" % (tid, v)
                try:
                    res = f.result()
                except Exception:
                    res = None
                if res:
                    variants_cache[key] = res
                    # 增量落盘，防中断丢失
                    json.dump(variants_cache, open(args.variants_json, "w", encoding="utf-8"),
                              ensure_ascii=False, indent=1)
        print("[B2] 变体生成完毕，缓存 %d 条 -> %s" % (len(variants_cache), args.variants_json))

    # ---------- 跑分阶段 ----------
    raw_path = os.path.join(ROOT, args.raw)
    done = set()
    if os.path.exists(raw_path):
        for l in open(raw_path, encoding="utf-8"):
            try:
                d = json.loads(l); done.add((d["id"], d["model"], d["variant"]))
            except Exception:
                pass
    tasks = [(it["id"], m, v) for it in items for m in models for v in variants
             if (it["id"], m, v) not in done and "%s|%s" % (it["id"], v) in variants_cache]
    print("[B2] 待跑分组合: %d（已完 %d）" % (len(tasks), len(done)))
    rawf = open(raw_path, "a", encoding="utf-8")
    ok = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {}
        for tid, m, v in tasks:
            vt = variants_cache["%s|%s" % (tid, v)]
            futs[ex.submit(score_one, vt, m)] = (tid, m, v)
        for f in as_completed(futs):
            tid, m, v = futs[f]
            c, t = f.result()
            rawf.write(json.dumps({"id": tid, "model": m, "variant": v,
                                   "correct": c, "total": t}, ensure_ascii=False) + "\n")
            rawf.flush(); ok += 1
            if ok % 20 == 0:
                el = time.time() - t0
                print("  %d/%d (%.0fs, %.2f/s)" % (ok, len(tasks), el, ok / max(el, 1e-6)))
    rawf.close()

    # ---------- 聚合：保留率（基线 = B1 的 A 条件 comp，即无知识原始分） ----------
    base_a = {}  # model -> comp_A (%)
    b1 = os.path.join(ROOT, args.baseline_json)
    if os.path.exists(b1):
        try:
            b1d = json.load(open(b1, encoding="utf-8"))
            for model, conds in b1d.get("comp_by_model_cond", {}).items():
                if "A" in conds and conds["A"] is not None:
                    base_a[model] = conds["A"]
        except Exception:
            pass
    else:
        print("[B2] 警告: 未找到 B1 基线 %s，保留率将无法计算（仅给变体 comp）" % b1)
    var = collections.defaultdict(lambda: [0, 0])       # (model,variant)
    for l in open(raw_path, encoding="utf-8"):
        try:
            d = json.loads(l)
        except Exception:
            continue
        var[(d["model"], d["variant"])][0] += d["correct"]; var[(d["model"], d["variant"])][1] += d["total"]
    table = {}
    for (model, v), (c, t) in var.items():
        comp_v = 100.0 * c / t if t else None
        base = base_a.get(model)
        retain = (comp_v / base) if (comp_v is not None and base) else None
        table.setdefault(model, {})[v] = {"comp": comp_v, "baseline_A": base, "retention": retain}
    out = {"models": models, "variants": variants, "perms": PERMS, "n_items": len(items),
           "comp_by_model_variant": table, "baseline_source": args.baseline_json}
    json.dump(out, open(os.path.join(ROOT, args.out), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("[B2] 聚合完成 -> %s" % args.out)


if __name__ == "__main__":
    main()
