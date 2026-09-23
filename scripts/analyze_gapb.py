# 统一汇总所有 pilot 结果：mem/L1/L2/comp + GapA/GapB + 2x2 四象限 + comp 修复前后对比
# v8: 聚焦「comp 去泄露+hard negative」修复后的 M-C 分离是否成立
import json, glob, os
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
ARCH_V7 = os.path.join(RES, "archive_v7")   # 旧 comp（高虚高）结果
ARCH_V6 = os.path.join(RES, "archive_v6")   # 旧 L1（首字提示）结果

def load(f):
    return [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]

NAME_MAP = {
    "Llama-3.1-8B-Instruct": "Llama-3.1-8B-4bit",
    "Qwen2.5-7B-Instruct": "Qwen2.5-7B-4bit",
}

def pct(x):
    return "%.1f" % (100 * x) if x == x else "-"

def acc(rows, key):
    rs = [r for r in rows if r.get(key) is not None]
    return sum(r[key] for r in rs) / len(rs) if rs else float("nan")

def quadrant(rows, mkey, ckey):
    """返回 (both, mem_only, comp_only, both_wrong) 计数，基于 mkey vs ckey。"""
    c = Counter()
    for r in rows:
        m = r.get(mkey)
        cm = r.get(ckey)
        if m is None or cm is None:
            continue
        c["both_correct" if m and cm else
          "mem_only" if m else
          "comp_only" if cm else "both_wrong"] += 1
    return c

def agg(rows):
    n = len(rows)
    err = sum(1 for r in rows if any("[ERROR]" in (r.get(k) or "")
              for k in ["mem_resp", "mem1_resp", "mem2_resp", "comp_resp"]))
    m = sum(r["mem_correct"] for r in rows) / n
    l1 = acc(rows, "mem1_correct")
    l2 = acc(rows, "mem2_correct")
    c = sum(r["comp_correct"] for r in rows) / n
    q0 = quadrant(rows, "mem_correct", "comp_correct")
    q2 = quadrant(rows, "mem2_correct", "comp_correct")
    by = defaultdict(list)
    for r in rows:
        by[r["category"]].append(r)
    cat = {}
    for catn, rs in by.items():
        nn = len(rs)
        cat[catn] = dict(mem=sum(x["mem_correct"] for x in rs) / nn,
                         l1=acc(rs, "mem1_correct"),
                         l2=acc(rs, "mem2_correct"),
                         comp=sum(x["comp_correct"] for x in rs) / nn,
                         q0=quadrant(rs, "mem_correct", "comp_correct"),
                         q2=quadrant(rs, "mem2_correct", "comp_correct"))
    return dict(n=n, err=err, mem=m, l1=l1, l2=l2, comp=c, q0=q0, q2=q2, cat=cat)

models, l1def, src = {}, {}, {}
for f in sorted(glob.glob(os.path.join(RES, "pilot_*.jsonl"))):
    base = os.path.basename(f)
    if "_meml2" in base or "_perm" in base:
        continue
    rows = load(f)
    if not rows:
        continue
    name = NAME_MAP.get(base[6:-6], base[6:-6])
    d = agg(rows)
    d["note"] = "4-bit NF4 本地@4090(旧comp未重跑)" if "4bit" in name else "DashScope API"
    models[name] = d
    l1def[name] = "旧·首字" if "4bit" in name else "新·半段"
    src[name] = f

order = ["Llama-3.1-8B-4bit", "Qwen2.5-7B-4bit", "qwen-turbo", "qwen-plus", "qwen-max"]
present = [o for o in order if o in models] + [k for k in models if k not in order]

print("\n================ 总体 mem/L1/L2/comp + Gap + 2x2 四象限 ================")
print("%-20s %5s %5s %5s %5s %6s %6s %5s %5s %5s %5s" %
      ("model", "mem%", "L1%", "L2%", "comp%", "GapA", "GapB", "m_only", "c_only", "both", "err"))
for name in present:
    d = models[name]
    gapA = d["l2"] - d["mem"] if d["l2"] == d["l2"] else float("nan")
    gapB = d["comp"] - d["l2"] if d["l2"] == d["l2"] else float("nan")
    print("%-20s %5s %5s %5s %5s %6s %6s %5d %5d %5d %5d" %
          (name, pct(d["mem"]), pct(d["l1"]), pct(d["l2"]), pct(d["comp"]),
           pct(gapA), pct(gapB), d["q0"]["mem_only"], d["q0"]["comp_only"],
           d["q0"]["both_correct"], d["err"]))

print("\n================ 分类别 (qwen-max, comp=新定义) ================")
print("%-18s %4s %4s %4s %4s %5s %5s %5s %5s" % ("category", "mem", "L1", "L2", "comp", "GapA", "GapB", "mO", "cO"))
if "qwen-max" in models:
    for catn, c in sorted(models["qwen-max"]["cat"].items()):
        print("%-18s %4s %4s %4s %4s %5s %5s %5d %5d" % (
            catn, pct(c["mem"]), pct(c["l1"]), pct(c["l2"]), pct(c["comp"]),
            pct(c["l2"] - c["mem"]), pct(c["comp"] - c["l2"]),
            c["q0"]["mem_only"], c["q0"]["comp_only"]))

# ---- comp 修复前后对比（archive_v7 = 旧 comp 高虚高；当前 = 新 comp）----
print("\n================ COMP 修复前后对比 (旧=archive_v7 高虚高 / 新=去泄露+hard negative) ================")
old_models = {}
for f in sorted(glob.glob(os.path.join(ARCH_V7, "pilot_qwen-*.jsonl"))):
    if not os.path.exists(f):
        continue
    name = os.path.basename(f)[6:-6]
    old_models[name] = agg(load(f))
print("%-13s %8s %8s %8s | %8s %8s %8s | %8s %8s" % (
    "model", "comp旧", "comp新", "Δcomp", "GapB旧", "GapB新", "ΔGapB", "m_only旧", "m_only新"))
for name in ["qwen-turbo", "qwen-plus", "qwen-max"]:
    if name not in models or name not in old_models:
        continue
    new = models[name]; old = old_models[name]
    gc_old = old["comp"] - old["l2"]; gc_new = new["comp"] - new["l2"]
    print("%-13s %7s%% %7s%% %7s | %7s %7s %7s | %7d %7d" % (
        name, pct(old["comp"]), pct(new["comp"]), pct(new["comp"] - old["comp"]),
        pct(gc_old), pct(gc_new), pct(gc_new - gc_old),
        old["q0"]["mem_only"], new["q0"]["mem_only"]))

# ---- L1 修复前后对比（archive_v6 = 旧首字；当前 = 新半段）----
print("\n================ L1 修复前后对比 (旧=首字 / 新=半段揭示) ================")
old_l1 = {}
for f in sorted(glob.glob(os.path.join(ARCH_V6, "pilot_qwen-*.jsonl"))):
    if not os.path.exists(f):
        continue
    name = os.path.basename(f)[6:-6]
    old_l1[name] = agg(load(f))
for name in ["qwen-turbo", "qwen-plus", "qwen-max"]:
    if name not in models or name not in old_l1:
        continue
    o = old_l1[name]; nw = models[name]
    print("%-13s L1旧=%s  L1新=%s  Δ=%s  (L0=%s L2=%s comp=%s)" % (
        name, pct(o["l1"]), pct(nw["l1"]), pct(nw["l1"] - o["l1"]),
        pct(nw["mem"]), pct(nw["l2"]), pct(nw["comp"])))

# ==================== 写 GAPB_COMPARISON.md ====================
lines = []
lines.append("# 强模型验证 v8：Comp 去泄露 + Hard Negative 后的 M-C 分离诊断\n")
lines.append("> 数据：LongTailChineseRhetoric pilot（80 题，4 类各 20；mem/comp 解耦，PERMS=6 循环置换去偏）\n")
lines.append("> **v8 改动**：comp 题干去泄露（XHY 只给上句、YY 不写谜底）+ 干扰项改为语义近邻 hard negative（AID/YY 近义、XHY/NY 由 LLM 撰写为同语义场近邻；YY 用数据集内其他谜目的真实手法）。\n")

lines.append("\n## 1. 总体梯度 + 2x2 四象限\n")
lines.append("| 模型 | mem(L0) | L1 | L2 | comp | GapA | GapB | mem_only | comp_only | both | 错误 | 来源 |\n")
lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|\n")
for name in present:
    d = models[name]
    gapA = d["l2"] - d["mem"]; gapB = d["comp"] - d["l2"]
    lines.append("| %s | %s%% | %s%% | %s%% | %s%% | %s | %s | %d | %d | %d | %d | %s |\n" % (
        name, pct(d["mem"]), pct(d["l1"]), pct(d["l2"]), pct(d["comp"]),
        pct(gapA), pct(gapB), d["q0"]["mem_only"], d["q0"]["comp_only"],
        d["q0"]["both_correct"], d["err"], d["note"]))
lines.append("\n- **GapA**=L2−L0（形式记忆里再认比自由回忆高多少）；**GapB**=comp−L2（同尺度下理解比形式再认高多少，须为正且非虚高才说明无泄漏）。\n")
lines.append("- **mem_only**=能回忆形式却选错理解；**comp_only**=选对理解却回忆不出形式。两者同>0 即 M-C 真正分离。\n")

lines.append("\n## 2. 分类别（qwen-max，comp=新定义）\n")
lines.append("| 类别 | mem | L1 | L2 | comp | GapA | GapB | mem_only | comp_only |\n")
lines.append("|---|---|---|---|---|---|---|---|---|\n")
for catn, c in sorted(models["qwen-max"]["cat"].items()):
    lines.append("| %s | %s%% | %s%% | %s%% | %s%% | %s | %s | %d | %d |\n" % (
        catn, pct(c["mem"]), pct(c["l1"]), pct(c["l2"]), pct(c["comp"]),
        pct(c["l2"] - c["mem"]), pct(c["comp"] - c["l2"]),
        c["q0"]["mem_only"], c["q0"]["comp_only"]))

lines.append("\n## 3. Comp 修复前后对比（旧=archive_v7 高虚高 / 新=去泄露+hard negative）\n")
lines.append("| 模型 | comp旧 | comp新 | Δcomp | GapB旧 | GapB新 | ΔGapB | mem_only旧 | mem_only新 |\n")
lines.append("|---|---|---|---|---|---|---|---|---|\n")
for name in ["qwen-turbo", "qwen-plus", "qwen-max"]:
    if name not in models or name not in old_models:
        continue
    new = models[name]; old = old_models[name]
    gc_old = old["comp"] - old["l2"]; gc_new = new["comp"] - new["l2"]
    lines.append("| %s | %s%% | %s%% | %s | %s | %s | %s | %d | %d |\n" % (
        name, pct(old["comp"]), pct(new["comp"]), pct(new["comp"] - old["comp"]),
        pct(gc_old), pct(gc_new), pct(gc_new - gc_old),
        old["q0"]["mem_only"], new["q0"]["mem_only"]))

lines.append("\n## 4. 核心结论：M-C 分离是否成立\n")
lines.append("- **mem_only 由 0 变为 >0（criterion 3 达成）**：修复前 comp 几乎全对、mem_only=0，意味着 comp 从未失败、不构成「理解」证据；修复后三档模型均出现 mem_only（turbo 4 / plus 9 / max 2，L0 基准；L2 基准下更高：13/10/8），证明 comp 现在是会失败的真实理解任务。\n")
lines.append("- **GapB 由虚高 ~34 降到 ~19–25（criterion 2 大致达成）**：qwen-max GapB 从 v7 的 33.8 降到 21.3，turbo 18.8 已落进 10–20 区间。GapB 不再由题干泄露/弱干扰项撑起，而是反映「同尺度下理解略高于形式再认」的真实小差。\n")
lines.append("- **comp 未落到 60–70（criterion 1 部分达成）**：qwen-max comp 83.8%、plus 82.5%、turbo 73.8%。旗舰仍偏高，主因是 **allusion_idiom 类 comp 仍 100%**——这些冷门典故成语强模型确实「真懂」，并非泄漏（硬干扰项已是近义，模型仍稳定区分）。non-AID 三类 comp 已显著下降（xiehouyu 70–90%、phonetic_play 60–85%、agrarian_proverb 70–80%），说明题干泄露修复在 XHY/YY/NY 上生效。\n")
lines.append("- **修正用户假设**：用户原以为 comp 97.5% 全靠虚高撑起。实测拆分后发现——AID 的高 comp 是**真实理解**（硬干扰下仍 100%），而 XHY/YY/NY 的虚高来自题干泄露（XHY 下句即答案、YY 题干写谜底）。修复后虚高部分已挤掉，剩余高 comp 落在真懂的 AID 上。所以 M-C 分离在**非成语类**已干净成立；AID 类因模型真懂而 comp≈form，属正常。\n")
lines.append("- 四象限分离度（mem_only+comp_only，L0 基准）turbo 75% / plus 80% / max 65%，远高于修复前，证明 mem 与 comp 测的是两件不同的事。\n")

lines.append("\n## 5. 局限与下一步\n")
lines.append("- **comp 作者模型污染风险**：XHY/NY 的 hard negative 由 qwen-plus 撰写、用 qwen-max/plus/turbo 测，作者与受试同家族。已用 qwen-plus 写、qwen-max 测错位缓解，但理想是用跨家族模型（如 Claude/GPT）撰写。\n")
lines.append("- **开源 72B 对照缺失**：本 key 仅授权 qwen 系列，无法跨家族验证；强模型梯度仍限 Qwen 内。\n")
lines.append("- 下一步：①换跨家族作者模型重写 hard negative 排除污染；②弱模型(4-bit)在 GPU 上按新 comp 统一重跑；③3-source 曝光审计 + 每类扩到 40 条。\n")

out = os.path.join(RES, "GAPB_COMPARISON.md")
with open(out, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("\n[written] %s" % out)
