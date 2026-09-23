# 第三关 · A/B 级来源检测（批量版）
#
# 目的：扩量时每条新条目必须有 A/B 级出处；C 级只能作线索，不能作最终出处。
#       同时汇总参考书目（含"页码待核原书"提示），便于论文引用与人工复核。
#
# 判定：等级 ∈ {A, B}  → 通过；等级 == C / C* / 缺失  → 标记「需升源」。
#       凡标注"待核原书 / TBD 页码"的，书目中显式列出，提示最终需回填页码。
#
# 用法:
#   python scripts/source_gate.py
#   python scripts/source_gate.py --cats xiehouyu
import os, sys, json, argparse, re
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DEFAULT_DATA = os.path.join(DATA, "pilot.jsonl")
MD_FILES = {
    "xiehouyu": os.path.join(DATA, "pilot_xhy.md"),
    "phonetic_play": os.path.join(DATA, "pilot_yy.md"),
    "allusion_idiom": os.path.join(DATA, "pilot_aid.md"),
    "agrarian_proverb": os.path.join(DATA, "pilot_ny.md"),
}


def parse_md(path):
    """从 pilot_*.md 解析 id -> {来源, 等级, 地区, 出处, 原文片段?}。"""
    out = {}
    if not os.path.exists(path):
        return out
    cur = {}
    for ln in open(path, encoding="utf-8"):
        s = ln.rstrip("\n")
        if s.startswith("id:"):
            if cur:
                out[cur.get("_id")] = cur
            cur = {"_id": s.split(":", 1)[1].strip()}
        elif ":" in s and not s.startswith(("#", ">", " ")):
            k, v = s.split(":", 1)
            cur[k.strip()] = v.strip()
    if cur:
        out[cur.get("_id")] = cur
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--cats", default="")
    args = ap.parse_args()
    only = set(c.strip() for c in args.cats.split(",") if c.strip())

    md = {}
    for cat, p in MD_FILES.items():
        md.update(parse_md(p))

    items = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()]
    if only:
        items = [i for i in items if i["category"] in only]

    OK_GRADES = ("A", "B", "A/B", "AB")   # A 或 B 或双源 A/B 均视为通过
    by_cat = defaultdict(list)
    below = []
    biblio = defaultdict(set)   # source -> set of ids
    tbd_page = []
    for it in items:
        cat = it["category"]
        iid = it["id"]
        meta = md.get(iid, {})
        grade = (meta.get("等级") or "").strip().upper()
        src = meta.get("来源") or it.get("source") or ""
        region = meta.get("地区") or it.get("region") or ""
        by_cat[cat].append((iid, grade, src, region))
        biblio[src].add(iid)
        if "待核" in src or "TBD" in src.upper() or "待回" in src or "待升" in src:
            tbd_page.append(iid)
        if grade not in OK_GRADES:
            below.append((iid, grade or "缺失", src))

    cat_name = {"xiehouyu": "XHY 歇后语", "phonetic_play": "YY 谐音隐语",
                "allusion_idiom": "AID 典故成语", "agrarian_proverb": "NY 农谚"}
    print("=" * 78)
    print("第三关 · A/B 级来源检测  (n=%d 条)" % len(items))
    print("=" * 78)
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        n = len(rows)
        ok = sum(1 for _, g, _, _ in rows if g in OK_GRADES)
        bad = n - ok
        verdict = "✅ 全部 A/B" if bad == 0 else "❌ %d 条低于 A/B" % bad
        print("\n### %s (n=%d)  %s" % (cat_name.get(cat, cat), n, verdict))
        print("   A/B 级: %d  低于 A/B(C/缺失): %d" % (ok, bad))

    print("\n" + "=" * 78)
    print("低于 A/B 级、需升源的条目 (%d)：" % len(below))
    for iid, g, src in below:
        print("   %s  等级=%s  来源=%s" % (iid, g, src))

    print("\n" + "=" * 78)
    print("需回填页码 / 升源的条目 (%d)：%s" % (len(tbd_page), ", ".join(tbd_page) or "无"))

    print("\n" + "=" * 78)
    print("参考书目（按来源聚合，条目数）：")
    for src in sorted(biblio, key=lambda s: -len(biblio[s])):
        print("   [%2d] %s" % (len(biblio[src]), src))

    out = os.path.join(ROOT, "results", "source_flags.json")
    json.dump({
        "below_ab": [{"id": i, "grade": g, "source": s} for i, g, s in below],
        "tbd_page": tbd_page,
        "biblio": {s: len(v) for s, v in biblio.items()},
    }, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n已写入 %s" % out)


if __name__ == "__main__":
    main()
