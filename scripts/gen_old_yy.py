# 生成「改动前」的 YY comp 选项版本，用于与新版做**同口径**对照。
#
# 背景：第二关第一轮用的是 3 模型（含千问），现在千问 key 额度耗尽，只能跑 openlux 的
# gpt-4o-mini。模型口径变了，过强率不能直接和第一轮的 71 条比；必须把「改动前」的版本
# 复原出来、用同一个 gpt-4o-mini 再跑一遍，两者的差才是本次改动的真实效果。
#
# 这里只还原 YY 的 comp_task 选项（三谜格用短名标签、decoy 换回「会意合成（会意）」），
# 其余字段（含 mem / L1 / L2）保持不变。
import json, os, sys, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_pilot as bp

LETTERS = ["A", "B", "C", "D", "E", "F", "G"]
N_OPT = 6

items = [json.loads(l) for l in open(os.path.join(ROOT, "data", "pilot.jsonl"), encoding="utf-8") if l.strip()]
n = 0
for it in items:
    if it["category"] != "phonetic_play":
        continue
    g = bp.canon_yy_genre(it.get("genre"))
    cand = ["谐音双关", "离合拆字", "隐语藏词",
            "字面直解（字面义）", "无法确定", "会意合成（会意）"]
    rng = random.Random(it["id"] + "_yygenre")
    others = [c for c in cand if c != g]
    rng.shuffle(others)
    vals = (others[:N_OPT - 1] + [g])
    rng.shuffle(vals)
    vals = list(dict.fromkeys(vals))[:N_OPT]
    keys = LETTERS[:len(vals)]
    gk = [k for k, v in zip(keys, vals) if v == g] or [keys[0]]
    it["comp_task"] = {
        "prompt": "隐语/字谜「%s」。它主要运用了下列哪种修辞手法（谜格）？" % it["original"],
        "options": dict(zip(keys, vals)),
        "answer": gk[0],
    }
    n += 1

out = os.path.join(ROOT, "data", "pilot_yy_old.jsonl")
with open(out, "w", encoding="utf-8") as f:
    for it in items:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")
print("已生成改动前 YY 版本: %s（改写 %d 条 YY comp 选项）" % (out, n))
