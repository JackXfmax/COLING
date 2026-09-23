# 四层完整数字聚合（mem-L0 / mem-L1 / mem-L2 / comp）
#
# 输入：
#   data/pilot.jsonl                 题目元数据（category / answer）
#   results/mem_layers_raw.jsonl     mem 三层跑批结果（run_mem_layers.py 产出；缺失则 mem 层标 pending）
#   results/prerank_raw_r2.jsonl     comp 预跑结果（R2 最终干扰项；508 题 XHY/YY/NY）
# 输出：
#   results/four_layers.json         结构化结果
#   终端打印「四层完整表」+「XHY mem→comp gap」
import os
import json
import argparse
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CATNAME = {"xiehouyu": "XHY", "phonetic_play": "YY", "allusion_idiom": "AID",
           "agrarian_proverb": "NY"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comp-raw", default=os.path.join(ROOT, "results", "prerank_raw_r2.jsonl"))
    ap.add_argument("--mem-raw", default=os.path.join(ROOT, "results", "mem_layers_raw.jsonl"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "four_layers.json"))
    args = ap.parse_args()

    items = [json.loads(l) for l in open(os.path.join(ROOT, "data", "pilot.jsonl"), encoding="utf-8") if l.strip()]
    meta = {d["id"]: d["category"] for d in items}

    # ---------- comp 层 ----------
    comp = defaultdict(lambda: {"cor": 0, "tot": 0})       # (model, cat)
    comp_id = defaultdict(lambda: {"cor": 0, "tot": 0})    # (model, id)
    if os.path.exists(args.comp_raw):
        for l in open(args.comp_raw, encoding="utf-8"):
            l = l.strip()
            if not l:
                continue
            r = json.loads(l)
            iid, m, t = r["id"], r["model"], r.get("tot", 0)
            if t == 0:
                continue
            ok = t - sum((r.get("err") or {}).values())
            c = meta.get(iid)
            comp[(m, c)]["cor"] += ok
            comp[(m, c)]["tot"] += t
            comp_id[(m, iid)]["cor"] += ok
            comp_id[(m, iid)]["tot"] += t
    else:
        print("⚠️ 未找到 comp raw：%s（comp 层标 pending）" % args.comp_raw)

    # ---------- mem 层 ----------
    mem = defaultdict(lambda: {"l0": 0, "l1": 0, "l2": 0, "n0": 0, "n1": 0, "n2": 0})
    mem_ok = False
    if os.path.exists(args.mem_raw):
        for l in open(args.mem_raw, encoding="utf-8"):
            l = l.strip()
            if not l:
                continue
            r = json.loads(l)
            k = (r["model"], meta.get(r["id"]))
            if r.get("l0_ok") is not None:
                mem[k]["l0"] += bool(r["l0_ok"]); mem[k]["n0"] += 1
            if r.get("l1_ok") is not None:
                mem[k]["l1"] += bool(r["l1_ok"]); mem[k]["n1"] += 1
            if r.get("l2_ok") is not None:
                mem[k]["l2"] += bool(r["l2_ok"]); mem[k]["n2"] += 1
        mem_ok = any(v["n0"] for v in mem.values())
    if not mem_ok:
        print("⚠️ mem raw 缺失或无有效记录：mem-L0/L1/L2 层标 pending")

    models = sorted({k[0] for k in comp} | {k[0] for k in mem})
    cats = ["xiehouyu", "phonetic_play", "allusion_idiom", "agrarian_proverb"]

    def pct(x, n):
        return None if n == 0 else round(100.0 * x / n, 1)

    print("\n" + "=" * 92)
    print("四层完整数字表（658 扩量集；comp 覆盖 XHY208/YY150/NY150=508，AID 按设计无 comp）")
    print("=" * 92)
    print("%-26s %-4s %7s %7s %7s %7s" % ("model", "cat", "mem-L0", "mem-L1", "mem-L2", "comp"))
    table = {}
    for m in models:
        for c in cats:
            cm = comp.get((m, c))
            cp = pct(cm["cor"], cm["tot"]) if cm and cm["tot"] else None
            mm = mem.get((m, c))
            l0 = pct(mm["l0"], mm["n0"]) if mm and mm["n0"] else None
            l1 = pct(mm["l1"], mm["n1"]) if mm and mm["n1"] else None
            l2 = pct(mm["l2"], mm["n2"]) if mm and mm["n2"] else None
            if cp is None and l0 is None:
                continue
            f = lambda v: ("%6.1f%%" % v) if v is not None else "   pend"
            print("%-26s %-4s %7s %7s %7s %7s"
                  % (m, CATNAME.get(c, c), f(l0), f(l1), f(l2), f(cp)))
            table["%s|%s" % (m, c)] = {"mem_L0": l0, "mem_L1": l1, "mem_L2": l2, "comp": cp}
        cm_all = {"cor": sum(comp[(m, c)]["cor"] for c in cats if (m, c) in comp),
                  "tot": sum(comp[(m, c)]["tot"] for c in cats if (m, c) in comp)}
        mm_all = {"l0": sum(mem[(m, c)]["l0"] for c in cats if (m, c) in mem),
                  "n0": sum(mem[(m, c)]["n0"] for c in cats if (m, c) in mem),
                  "l1": sum(mem[(m, c)]["l1"] for c in cats if (m, c) in mem),
                  "n1": sum(mem[(m, c)]["n1"] for c in cats if (m, c) in mem),
                  "l2": sum(mem[(m, c)]["l2"] for c in cats if (m, c) in mem),
                  "n2": sum(mem[(m, c)]["n2"] for c in cats if (m, c) in mem)}
        cp = pct(cm_all["cor"], cm_all["tot"])
        l0 = pct(mm_all["l0"], mm_all["n0"])
        l1 = pct(mm_all["l1"], mm_all["n1"])
        l2 = pct(mm_all["l2"], mm_all["n2"])
        f = lambda v: ("%6.1f%%" % v) if v is not None else "   pend"
        print("%-26s %-4s %7s %7s %7s %7s" % (m, "ALL", f(l0), f(l1), f(l2), f(cp)))
        print("-" * 92)
        table["%s|ALL" % m] = {"mem_L0": l0, "mem_L1": l1, "mem_L2": l2, "comp": cp}

    # ---------- XHY mem→comp gap ----------
    print("\n" + "=" * 92)
    print("XHY（208 条）mem→comp gap —— 与 pilot 80 题 +62.3pp 对照")
    print("=" * 92)
    gaps = {}
    for m in models:
        cm = comp.get((m, "xiehouyu"))
        if not cm or cm["tot"] == 0:
            continue
        cp = 100.0 * cm["cor"] / cm["tot"]
        mm = mem.get((m, "xiehouyu"))
        if mm and mm["n0"]:
            l0 = 100.0 * mm["l0"] / mm["n0"]
            gaps[m] = {"comp": round(cp, 1), "mem_L0": round(l0, 1), "gap": round(cp - l0, 1)}
            print("  %-26s comp %.1f%%  mem-L0 %.1f%%  gap %+.1fpp" % (m, cp, l0, cp - l0))
        else:
            gaps[m] = {"comp": round(cp, 1), "mem_L0": None, "gap": None}
            print("  %-26s comp %.1f%%  mem-L0 pend   gap 待补跑" % (m, cp))
    if gaps:
        cs = [g["comp"] for g in gaps.values() if g["comp"] is not None]
        gs = [g["gap"] for g in gaps.values() if g["gap"] is not None]
        ms = [g["mem_L0"] for g in gaps.values() if g["mem_L0"] is not None]
        print("\n  XHY comp 均值 = %.1f%%" % mean(cs))
        if ms and gs:
            print("  XHY mem-L0 均值 = %.1f%%" % mean(ms))
            print("  ★ XHY gap 均值 = %+.1fpp   (pilot 80 题为 +62.3pp)" % mean(gs))
        else:
            print("  ★ XHY gap 均值 = 待补跑（mem-L0 未跑）")

    with open(args.out, "w", encoding="utf-8") as fp:
        json.dump({"table": table, "xhy_gap": gaps}, fp, ensure_ascii=False, indent=2)
    print("\n已写入 %s" % args.out)


if __name__ == "__main__":
    main()
