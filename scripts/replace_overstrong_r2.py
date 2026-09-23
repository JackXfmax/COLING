# 第二关 · 过强干扰项替换（迭代收敛第二步 / R2）
#
# 仅处理 XHY/NY 中【强(>60%)+中(50-60%)】的条目（聚焦 ~26 条），边缘(40-50%) 保留。
# 依据当前 results/distractor_prerank.json（7 模型跨厂商口径）。
# 逻辑复用第一轮 replace_overstrong.py：从 comp_hn.json[id].hn 剔除过强值，
# 并从同类别 _b_raw 池补「相似度中段」候选，使 build_pilot 重建时采用新 hn。
#
# 幂等前提：comp_hn.json 已在运行前备份（comp_hn.json.bak_r2_20260921）。
# 用法: python scripts/replace_overstrong_r2.py
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
R2_MIN = 50.0   # 只处理 max 错选率 > 50% 的强+中条目；<=50% 边缘保留


def fill(gold, cat, exclude, n_need):
    """从同类别其他条目的 _b_raw 池，按『距中段中心 0.32 最近』优先取候选补足。"""
    cands = []
    for x in cat_items[cat]:
        t = x.get("_b_raw")
        if not t or t in exclude:
            continue
        s = bp.cos(gold, t)
        if s >= 0.85:        # 近乎同义，跳过以免不可解
            continue
        cands.append((s, t))
    cands.sort(key=lambda z: (abs(z[0] - 0.32), -z[0]))
    return [t for s, t in cands[:n_need]]


replaced = filled = short = skipped_edge = 0
for o in over:
    iid = o["id"]
    if iid.startswith("YY"):
        continue
    mx = max(p for _, p in o["over"])
    if mx <= R2_MIN:          # 边缘保留，不处理
        skipped_edge += 1
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
print("R2 替换条目(强+中): %d | 跳过边缘: %d | 中段补足候选: %d | 仍不足5(将回退近邻): %d"
      % (replaced, skipped_edge, filled, short))
