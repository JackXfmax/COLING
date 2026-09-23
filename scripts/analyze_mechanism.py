#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B3 · 机制解释分层分析（零 API）

问题：M-C 分离（mem 低 / comp 高）为什么发生在 mem 侧？
假设 H：mem 侧失败由**表层属性**（答案长度、来源曝光度、方言区）驱动，
       而 comp 侧对这些属性不敏感 → 分离的机制是「记忆检索失败」而非「语义理解缺失」。

做法：完全基于现有产物（mem_layers_raw_merged.jsonl + prerank_raw_r2.jsonl + pilot.jsonl），
      按 3 个维度分层，比较 mem 三层与 comp 对各分层的敏感度（极差 / 相关性）。

输出：results/MECHANISM_ANALYSIS.md
"""
import json, os, re, collections, statistics, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

# ---------- 1. 载入题目 ----------
items = {}
with open(P("data", "pilot.jsonl"), encoding="utf-8") as f:
    for l in f:
        if l.strip():
            d = json.loads(l)
            items[d["id"]] = d

# ---------- 2. mem 三层聚合（每题 × 跨模型均值）----------
mem = collections.defaultdict(lambda: {"l0": [], "l1": [], "l2": []})
with open(P("results", "mem_layers_raw_merged.jsonl"), encoding="utf-8") as f:
    for l in f:
        if not l.strip():
            continue
        d = json.loads(l)
        m = mem[d["id"]]
        m["l0"].append(1.0 if d.get("l0_ok") else 0.0)
        m["l1"].append(1.0 if d.get("l1_ok") else 0.0)
        m["l2"].append(float(d.get("l2_acc") or 0.0))

# ---------- 3. comp 聚合（err 记录非 gold 选中次数 → correct = tot - Σerr）----------
comp = collections.defaultdict(list)
with open(P("results", "prerank_raw_r2.jsonl"), encoding="utf-8") as f:
    for l in f:
        if not l.strip():
            continue
        d = json.loads(l)
        tot = d.get("tot") or 6
        wrong = sum((d.get("err") or {}).values())
        comp[d["id"]].append((tot - wrong) / tot)

# ---------- 4. 分层维度 ----------
def alen(it):
    return len(it.get("mem_task", {}).get("answer", "") or "")

def len_bucket(n):
    if n <= 3:  return "① ≤3字"
    if n <= 5:  return "② 4–5字"
    if n <= 7:  return "③ 6–7字"
    return "④ ≥8字"

def source_type(s):
    s = s or ""
    if "集成" in s:                              return "民间文学集成"
    if ("县志" in s or "地方志" in s or "方志" in s): return "地方志/县志"
    if "谜" in s:                                return "谜语集"
    if ("政府" in s or "人民号" in s or "日报" in s or "网" in s): return "政府/媒体网站"
    if re.search(r"《.+》", s):                   return "古籍/文献"
    return "其他"

def region_group(r):
    r = (r or "").strip()
    return r if r else "（未标地域）"

CATS = [("xiehouyu", "XHY 歇后语"), ("phonetic_play", "YY 谐音"),
        ("allusion_idiom", "AID 典故"), ("agrarian_proverb", "NY 农谚")]
CATN = dict(CATS)

# ---------- 5. 组装逐题记录 ----------
rows = []
for iid, it in items.items():
    if iid not in mem:
        continue
    m = mem[iid]
    c = comp.get(iid, [])
    rows.append({
        "id": iid,
        "cat": it.get("category"),
        "len": alen(it),
        "lb": len_bucket(alen(it)),
        "src": source_type(it.get("source")),
        "reg": region_group(it.get("region")),
        "l0": statistics.mean(m["l0"]) if m["l0"] else None,
        "l1": statistics.mean(m["l1"]) if m["l1"] else None,
        "l2": statistics.mean(m["l2"]) if m["l2"] else None,
        "comp": statistics.mean(c) if c else None,
    })

def agg(rs, keyfn, label):
    """按 keyfn 分组，返回 [(层名, n, l0, l1, l2, comp), ...]"""
    g = collections.defaultdict(list)
    for r in rs:
        g[keyfn(r)].append(r)
    out = []
    for k in sorted(g):
        gr = g[k]
        def av(f):
            v = [r[f] for r in gr if r[f] is not None]
            return statistics.mean(v) if v else None
        out.append((k, len(gr), av("l0"), av("l1"), av("l2"), av("comp")))
    return out

def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else None

def fmt(v):
    return "—" if v is None else "%.1f%%" % (100 * v)

MIN_N = 5   # 极差统计的最小组容量：方言区存在大量 n=1 散点，会把极差拉到 100pp 掩盖真实效应

def spread(vals):
    v = [x for x in vals if x is not None]
    return (max(v) - min(v)) if len(v) >= 2 else None

def spread_n(a, idx):
    """仅对 n>=MIN_N 的组计算极差（a 的元素形如 (层名, n, l0, l1, l2, comp)）"""
    v = [x[idx] for x in a if x[1] >= MIN_N and x[idx] is not None]
    return (max(v) - min(v)) if len(v) >= 2 else None

def table(rs, keyfn, title, note=""):
    a = agg(rs, keyfn, title)
    lines = ["", "### " + title, ""]
    if note:
        lines += ["> " + note, ""]
    lines += ["| 层 | n | mem-L0 | mem-L1 | mem-L2 | comp |", "|---|---|---|---|---|---|"]
    for k, n, l0, l1, l2, cp in a:
        flag = " ⚠️" if n < MIN_N else ""
        lines.append("| %s%s | %d | %s | %s | %s | %s |" % (k, flag, n, fmt(l0), fmt(l1), fmt(l2), fmt(cp)))
    if any(x[1] < MIN_N for x in a):
        lines += ["", f"> ⚠️ = n < {MIN_N} 的散点组，**不计入极差统计**（单题组易出现 0%/100% 极端值）。"]
    # 敏感度（仅 n>=MIN_N 的组）
    s0, s1, s2, sc = (spread_n(a, 2), spread_n(a, 3), spread_n(a, 4), spread_n(a, 5))
    lines += ["", "- **层间极差**（仅 n≥%d 的组）：mem-L0 %s ｜ mem-L1 %s ｜ mem-L2 %s ｜ comp %s" % (MIN_N,
              "—" if s0 is None else "%.1fpp" % (100 * s0),
                 "—" if s1 is None else "%.1fpp" % (100 * s1),
                 "—" if s2 is None else "%.1fpp" % (100 * s2),
                 "—" if sc is None else "%.1fpp" % (100 * sc))]
    return "\n".join(lines), (s0, s1, s2, sc)

# ---------- 6. 生成报告 ----------
out = []
out.append("# B3 · 机制解释：为什么分离发生在 Mem 侧？")
out.append("")
out.append("> 生成脚本：`scripts/analyze_mechanism.py`（**零 API**，纯分析现有产物）。")
out.append("> 数据：`mem_layers_raw_merged.jsonl`（10 模型 × 658 题 mem 三层）+ `prerank_raw_r2.jsonl`（7 模型 × 508 题 comp，PERMS=6）+ `pilot.jsonl` 字段。")
out.append("> 口径：mem-L0/L1 = 跨模型答对比例均值；mem-L2 = 6 次置换平均正确率；comp = (tot − Σerr)/tot 的跨模型均值。")
out.append("> ⚠️ `exposure_bin` 字段实测 **658 条全为 'TBD'（空壳）**，故曝光度改用 **来源类型** 作代理。")
out.append("")
out.append("## 0. 核心假设")
out.append("")
out.append("**H（记忆检索失败假说）**：mem 侧失败率由**表层属性**（答案长度 / 来源曝光 / 方言区）驱动，")
out.append("而 comp 侧对这些属性**不敏感**。若成立，则 M-C 分离的机制不是「模型不懂修辞」，")
out.append("而是「模型**懂机制但取不出原句**」——比单纯报告 gap 更强的主张。")
out.append("")

# --- 全体分层 ---
t, sp_all = table(rows, lambda r: r["lb"], "① 答案长度分层（全体 658 题）",
                  "长度 = `mem_task.answer` 字符数（min1 / max35 / 均值 5.67 / 中位 4）。")
out.append(t)
t, sp_src = table(rows, lambda r: r["src"], "② 来源类型分层（曝光度代理，全体 658 题）")
out.append(t)
t, sp_reg = table(rows, lambda r: r["reg"], "③ 方言区 / 地域分层（全体 658 题）")
out.append(t)

# --- 分类别：长度 ---
out.append("")
out.append("## 1. 分主体类别复核（排除「类别混淆」）")
out.append("")
out.append("各类答案长度分布不同（AID 成语恒 4 字），故按类别分别看长度效应，避免把「类别差异」误读为「长度效应」。")
for cat, cn in CATS:
    rs = [r for r in rows if r["cat"] == cat]
    if not rs:
        continue
    t, _ = table(rs, lambda r: r["lb"], "①-%s 答案长度���层（%s，n=%d）" % (cat, cn, len(rs)))
    out.append(t)

# --- 类别内方言分层：排除「地域 × 类别」混淆 ---
out.append("")
out.append("## 1b. 类别内方言分层（排除「地域 × 类别」混淆）")
out.append("")
out.append("> **重要修正**：全体方言分层的两侧极差都极高（80+pp），但这主要不是方言效应——")
out.append("> `region` 与 `category` **高度耦合**（「传世灯谜」「民间谜语」只出现在 YY；")
out.append("> 「陕北」「陕西长武」只出现在 XHY），故全体方言极差主要反映**类别差异**。")
out.append("> 以下在 **XHY 内部**做方言分层，才是干净的方言效应检验。")
rs = [r for r in rows if r["cat"] == "xiehouyu"]
t, sp_xr = table(rs, lambda r: r["reg"], "④ XHY 内部方言/地域分层（n=%d，已排除类别混淆）" % len(rs))
out.append(t)

# --- 相关性 ---
out.append("")
out.append("## 2. 相关性：答案长度 vs 各层成功率（Pearson）")
out.append("")
out.append("| 范围 | n | r(len, mem-L0) | r(len, mem-L1) | r(len, mem-L2) | r(len, comp) |")
out.append("|---|---|---|---|---|---|")
def corr_row(label, rs):
    xs = [r["len"] for r in rs]
    def rr(f):
        pairs = [(r["len"], r[f]) for r in rs if r[f] is not None]
        return pearson([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None
    f = lambda v: "—" if v is None else "%+.3f" % v
    out.append("| %s | %d | %s | %s | %s | %s |" % (label, len(rs), f(rr("l0")), f(rr("l1")), f(rr("l2")), f(rr("comp"))))
corr_row("全体", rows)
for cat, cn in CATS:
    rs = [r for r in rows if r["cat"] == cat]
    if rs:
        corr_row(cn, rs)

# --- 敏感度对比（关键）---
out.append("")
out.append("## 3. 关键对比：mem 侧 vs comp 侧的分层敏感度")
out.append("")
out.append("| 分层维度 | mem-L0 极差 | mem-L1 极差 | mem-L2 极差 | comp 极差 | 判读 |")
out.append("|---|---|---|---|---|---|")
def verdict(sm, sc):
    if sm is None or sc is None:
        return "—"
    if sm > sc * 1.5:
        return "**mem 侧敏感得多** ✅ 支持 H"
    if sc > sm * 1.5:
        return "comp 侧更敏感 ❌ 不支持 H"
    return "两侧相当（中性）"
for name, sp in [("① 答案长度", sp_all), ("② 来源类型", sp_src),
                 ("③ 方言区（全体，含类别混淆）", sp_reg),
                 ("④ XHY 内方言（已排除类别混淆）", sp_xr)]:
    s0, s1, s2, sc = sp
    g = lambda v: "—" if v is None else "%.1fpp" % (100 * v)
    # 用 mem-L0 作主判读量（自由回忆，最纯粹的"记忆"）
    out.append("| %s | %s | %s | %s | %s | %s |" % (name, g(s0), g(s1), g(s2), g(sc), verdict(s0, sc)))

out.append("")
out.append("## 4. 实测结论（自动汇总）")
out.append("")

def concl(name, sp):
    s0, s1, s2, sc = sp
    if s0 is None or sc is None:
        return "- **%s**：数据不足（无可比层）" % name
    ratio = (s0 / sc) if sc else float("inf")
    p = lambda v: "%.1fpp" % (100 * v)
    if ratio >= 1.5:
        return "- **%s**：mem-L0 %s vs comp %s（**%.2f×**）→ mem 侧显著更敏感，**支持 H**" % (name, p(s0), p(sc), ratio)
    if ratio <= 0.67:
        return "- **%s**：mem-L0 %s vs comp %s（%.2f×）→ comp 侧更敏感，**不支持 H**" % (name, p(s0), p(sc), ratio)
    return "- **%s**：mem-L0 %s vs comp %s（%.2f×）→ 两侧相当，中性" % (name, p(s0), p(sc), ratio)

for name, sp in [("① 答案长度", sp_all), ("② 来源类型（曝光代理）", sp_src),
                 ("③ 方言区（全体，含类别混淆，不建议采信）", sp_reg),
                 ("④ XHY 内方言（已排除类别混淆）", sp_xr)]:
    out.append(concl(name, sp))

out.append("")
out.append("**综合判读（草稿，可人工润色）**：")
out.append("")
out.append("- **支持 H 的维度**：答案长度、来源类型（曝光代理）。mem 侧对这些**表层/语料属性**的敏感度")
out.append("  是 comp 侧的 **2 倍以上**，说明 mem 失败主要由「条目有多长、语料里有多常见」驱动，")
out.append("  而 comp（语义理解）对这些属性相对稳定 → **分离的机制是记忆检索失败，而非语义理解缺失**。")
out.append("- **不支持 H 的维度**：方言区。在排除「地域×类别」混淆后（XHY 内部），mem-L0 的层间差异")
out.append("  （10.9pp）反而**小于** comp（23.8pp）——即各方言区的记忆失败是**普遍而均匀**的，")
out.append("  方言本身不是 mem 侧失败的驱动因素；而 comp 的地域差异更可能反映**条目难度/可理解性**差异。")
out.append("- **结论**：M-C 分离主要由 **条目表层属性（长度、曝光度）** 驱动，**不是**由地域/方言驱动。")
out.append("  这使主论断更精确：模型**懂机制但取不出原句**，且「取不出」与条目多冷门多长有关，与其方言来源无关。")
out.append("")
out.append("**注意事项**：")
out.append("- comp 仅覆盖 XHY/YY/NY（508 题，AID 按设计无 comp），故含 AID 的分层中 comp 为该层非 AID 题目均值。")
out.append("- **曝光度**：`exposure_bin` 字段实测 658 条全为 `TBD`（空壳），本报告用**来源类型**作代理；")
out.append("  若需严格曝光审计，需另做 3-source 检索统计（可作为后续补做项）。")
out.append("- 分层为**观察性**分析，非因果；长度与曝光度本身相关（长条目往往更冷门），两者不可完全分离。")

with open(P("results", "MECHANISM_ANALYSIS.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")

print("wrote results/MECHANISM_ANALYSIS.md")
print("rows:", len(rows), "| with comp:", sum(1 for r in rows if r["comp"] is not None))
print("sensitivity (mem-L0 vs comp):")
for name, sp in [("len", sp_all), ("src", sp_src), ("reg", sp_reg)]:
    s0, s1, s2, sc = sp
    print("  %-4s mem-L0=%s mem-L1=%s mem-L2=%s comp=%s" % (
        name,
        "—" if s0 is None else "%.1fpp" % (100 * s0),
        "—" if s1 is None else "%.1fpp" % (100 * s1),
        "—" if s2 is None else "%.1fpp" % (100 * s2),
        "—" if sc is None else "%.1fpp" % (100 * sc)))
