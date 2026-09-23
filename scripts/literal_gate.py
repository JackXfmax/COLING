# 第一关 · 字面捷径检测（批量版）
#
# 目的：扩量时每条新条目都必须过这一关。检查"正确答案选项"与题干含义的字面
#       二元组相似度，是否显著高于 5 个干扰项。若模型可以不理解修辞、只做字符
#       匹配就选中 gold，则 comp 高分是虚假的。
#
# 规则（与用户规范一致）：
#   规则1：gold 字面相似度 > 干扰项均值 × 2   → 标记「需重写 gold」
#   规则2：gold 是字面最贴近的，且该类别「gold 字面占优比例」> 30% → 标记「需重写」
#   目标：每类 gold 字面占优比例 ≤ 随机期望(17%) + 5pp = 22%
#
# 注：AID 类 comp 正确项在 build_pilot 中恒等于 target_meaning（今义），gold==tgt
#     属构造性退化，gold_sim≡1.0。对 AID 改用「形式泄露」指标：
#     cos(成语形式, 今义)，并与同类分布比较，标记形式-含义字面重叠异常高的条目。
#
# 用法:
#   python scripts/literal_gate.py                       # 全量
#   python scripts/literal_gate.py --cats xiehouyu       # 只看某类
#   python scripts/literal_gate.py --data data/pilot.jsonl --out results/literal_flags.json
import os, sys, json, argparse, math
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DEFAULT_DATA = os.path.join(DATA, "pilot.jsonl")

# 复用 build_pilot 的字面相似度工具
sys.path.insert(0, HERE)
from build_pilot import char_bigram, cos, norm, PUNCT

RATIO_CAP = 0.22        # 目标上限：17% + 5pp
RULE2_RATIO = 0.30      # 规则2 触发阈值
MULT = 2.0              # 规则1 倍数


def items_from(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def analyze_item(it):
    cat = it["category"]
    opts = it["comp_task"]["options"]
    keys = sorted(opts.keys())
    gold_key = it["comp_task"]["answer"]
    gold = opts[gold_key]
    tgt = it.get("target_meaning", "") or ""
    distractors = [opts[k] for k in keys if k != gold_key]

    res = dict(id=it["id"], cat=cat, gold=gold, tgt=tgt,
               gold_sim=None, dist_sims=[], mean_dist=None,
               gold_closest=None, rule1=False, rule2=False,
               aad_form_leak=None, flag=None)

    if cat == "allusion_idiom" or (tgt and norm(gold) == norm(tgt)):
        # 构造性退化：comp 正确项恒等于 target_meaning（AID/NY 的正确选项即含义本身），
        # gold_sim≡1.0 无意义。改用「形式泄露」指标：成语/农谚的字面形式与含义的字面重叠。
        form = it.get("original", "")
        res["aad_form_leak"] = round(cos(form, tgt), 3) if tgt else 0.0
        res["mode"] = "form_leak"
        return res

    if not tgt:
        return res
    gsim = cos(gold, tgt)
    dsims = [cos(d, tgt) for d in distractors]
    mean_d = sum(dsims) / len(dsims) if dsims else 0.0
    max_d = max(dsims) if dsims else 0.0
    # 「字面占优」需同时满足：① gold 明显高过最强干扰项；② gold 自身字面重叠达到可
    #   被字符匹配利用的量级（≥0.10）。否则所有干扰项≈0 时任何微小 gold 重叠都会被判
    #   为占优，产生假阳性（XHY 情境类天然如此，已验证该阈值复现审计的 XHY≈20%）。
    gold_closest = bool(dsims) and (gsim >= max_d + 0.02) and (gsim >= 0.10)
    rule1 = bool(dsims) and (gsim > MULT * mean_d) and (gsim - mean_d > 0.02)
    res.update(gold_sim=round(gsim, 3), dist_sims=[round(x, 3) for x in dsims],
               mean_dist=round(mean_d, 3), gold_closest=gold_closest, rule1=rule1)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--cats", default="", help="逗号分隔的类别过滤")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "literal_flags.json"))
    args = ap.parse_args()
    only = set(c.strip() for c in args.cats.split(",") if c.strip())

    items = items_from(args.data)
    if only:
        items = [i for i in items if i["category"] in only]

    rows = [analyze_item(i) for i in items]

    # 逐类聚合
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["cat"]].append(r)

    flags = []
    print("=" * 78)
    print("第一关 · 字面捷径检测  (n=%d 条)" % len(rows))
    print("=" * 78)
    cat_name = {"xiehouyu": "XHY 歇后语", "phonetic_play": "YY 谐音隐语",
                "allusion_idiom": "AID 典故成语", "agrarian_proverb": "NY 农谚"}
    for cat in sorted(by_cat):
        rs = by_cat[cat]
        name = cat_name.get(cat, cat)
        if cat in ("allusion_idiom", "agrarian_proverb"):
            leaks = [r["aad_form_leak"] for r in rs if r["aad_form_leak"] is not None]
            ml = sum(leaks) / len(leaks) if leaks else 0
            hi = [r["id"] for r in rs if (r["aad_form_leak"] or 0) > 0.25]
            print("\n### %s (n=%d)  [构造性退化：gold≡含义，改用形式泄露]" % (name, len(rs)))
            print("   形式-含义字面重叠均值 = %.3f" % ml)
            print("   形式泄露 > 0.25 的条目 (%d): %s" % (len(hi), ", ".join(hi) or "无"))
            for r in rs:
                if (r["aad_form_leak"] or 0) > 0.25:
                    flags.append({**r, "flag": "形式泄露偏高"})
            continue

        golds = [r["gold_sim"] for r in rs if r["gold_sim"] is not None]
        dists = [r["mean_dist"] for r in rs if r["mean_dist"] is not None]
        dom = [r for r in rs if r["gold_closest"]]
        ratio = len(dom) / len(rs) if rs else 0
        r1 = [r for r in rs if r["rule1"]]
        r2 = [r for r in rs if r["gold_closest"] and ratio > RULE2_RATIO]
        verdict = "✅ 通过" if ratio <= RATIO_CAP else "❌ 超出阈值"
        print("\n### %s (n=%d)  %s" % (name, len(rs), verdict))
        print("   gold 字面相似度均值 = %.3f   干扰项均值 = %.3f" %
              (sum(golds)/len(golds) if golds else 0, sum(dists)/len(dists) if dists else 0))
        print("   gold 字面占优比例 = %.1f%%   (目标 ≤ %.0f%%)" % (100*ratio, 100*RATIO_CAP))
        print("   规则1 触发（gold>2×干扰）: %d 条" % len(r1))
        print("   规则2 触发（gold最贴近 且 类比例>30%%）: %d 条" % len(r2))
        for r in r1:
            print("     [规则1] %s  gold_sim=%.3f  mean_dist=%.3f  gold=%s"
                  % (r["id"], r["gold_sim"], r["mean_dist"], r["gold"][:30]))
            flags.append({**r, "flag": "rewrite_gold_rule1"})
        for r in r2:
            if r not in r1:
                print("     [规则2] %s  gold_sim=%.3f" % (r["id"], r["gold_sim"]))
                flags.append({**r, "flag": "rewrite_gold_rule2"})

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(flags, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 78)
    print("标记条目总计: %d  → 已写入 %s" % (len(flags), args.out))


if __name__ == "__main__":
    main()
