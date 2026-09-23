# 第二关 · 过强干扰项替换（迭代收敛第一步）
#
# 依据 results/distractor_prerank.json 的 151 条「过强」标记，替换 XHY/NY 的 comp 干扰项：
#   - XHY/NY 的 comp 干扰项来自 comp_hn.json（LLM 撰写 hn 池）或自动相似度近邻回退；
#     本脚本从 comp_hn.json[id].hn 剔除过强值，并从同类别 _b_raw 池补「相似度中段」候选，
#     使 build_pilot.py 重建时直接采用新 hn（不再回退到会自动过强的近邻）。
#   - YY 走 canon_yy_genre 固定谜格集（不读 comp_hn.json），过强根因是三谜格认知重叠 +
#      decoy「会意合成（会意）」默认吸引力过强；盲改 hn 文本无效，故仅输出诊断（results/yy_overstrong_diagnosis.md）。
#
# 用法: python scripts/replace_overstrong.py
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_pilot as bp

DATA = os.path.join(ROOT, "data")
items = bp.build()
id2 = {it["id"]: it for it in items}
cat_items = {c: [it for it in items if it["category"] == c]
             for c in ("xiehouyu", "agrarian_proverb", "phonetic_play")}
hn = json.load(open(os.path.join(DATA, "comp_hn.json"), encoding="utf-8"))
over = json.load(open(os.path.join(ROOT, "results", "distractor_prerank.json"), encoding="utf-8"))

N_OPT = 6
MID_LO, MID_HI = 0.18, 0.45   # 中段相似度区间（既非同义、又非完全不搭）


def fill(gold, cat, exclude, n_need):
    """从同类别其他条目的 _b_raw 池，按『距中段中心 0.32 最近』优先取候选补足。"""
    cands = []
    for x in cat_items[cat]:
        t = x["_b_raw"]
        if t in exclude:
            continue
        s = bp.cos(gold, t)
        if s >= 0.85:        # 近乎同义，跳过以免不可解
            continue
        cands.append((s, t))
    # 中段优先（abs(s-0.32) 最小），同档按相似度降序（尽量"像但不太像"）
    cands.sort(key=lambda z: (abs(z[0] - 0.32), -z[0]))
    return [t for s, t in cands[:n_need]]


replaced = filled = short = 0
for o in over:
    iid = o["id"]
    if iid.startswith("YY"):
        continue
    it = id2[iid]
    cat = it["category"]
    gold = it["_b_raw"]
    over_txt = set(o["distractor_text"].values())
    cur = list(hn.get(iid, {}).get("hn") or [])
    new = [h for h in cur if h not in over_txt and h != gold]
    need = N_OPT - 1 - len(new)
    if need > 0:
        ex = set(new) | over_txt | {gold}
        new += fill(gold, cat, ex, need)
        filled += need
    new = list(dict.fromkeys(new))[:N_OPT - 1]
    if len(new) < N_OPT - 1:
        short += 1
    hn.setdefault(iid, {})["hn"] = new
    replaced += 1

json.dump(hn, open(os.path.join(DATA, "comp_hn.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("XHY/NY 替换条目: %d | 中段补足候选: %d | 仍不足 5(将回退近邻): %d"
      % (replaced, filled, short))


# ---------- YY 诊断（不盲改）----------
yy_over = [o for o in over if o["id"].startswith("YY")]
golds = Counter(id2[o["id"]]["genre"] for o in yy_over)
txtc = Counter()
for o in yy_over:
    for k, t in o["distractor_text"].items():
        txtc[t] += 1
L = ["# YY 过强干扰项诊断（%d 条，需人工仲裁 / decoy 重设计）" % len(yy_over), ""]
L.append("YY comp 任务走 `canon_yy_genre` 固定谜格集（谐音双关/离合拆字/隐语藏词）+ 3 个 decoy，"
         "**不读 comp_hn.json**，故不能靠换 hn 池解决。过强根因=三谜格认知重叠 + decoy「会意合成（会意）」默认吸引力过强。")
L.append("")
L.append("过强项 gold 谜格分布: " + ", ".join("%s=%d" % (k, v) for k, v in golds.items()))
L.append("")
L.append("过强『值文本』频次:")
for t, c in txtc.most_common():
    L.append("  %2d  %s" % (c, t))
L.append("")
L.append("## 逐条（gold 谜格 → 被误选的过强值）")
for o in yy_over:
    iid = o["id"]
    g = id2[iid]["genre"]
    parts = ", ".join("%s(%.0f%%)" % (o["distractor_text"][k], p) for k, p in o["over"])
    L.append("- **%s** [gold=%s] 过强: %s" % (iid, g, parts))
open(os.path.join(ROOT, "results", "yy_overstrong_diagnosis.md"), "w", encoding="utf-8").write("\n".join(L))
print("YY 诊断已写 results/yy_overstrong_diagnosis.md")
