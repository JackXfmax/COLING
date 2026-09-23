# 跨家族模型对比分析：把 v10 的 Qwen 三档 + 新测的 openlux 多家族结果
# 放在同一张表里，检验 "M-C 分离 / Comp 真实理解" 是否只属于 Qwen 家族。
#
# 用法:
#   python analyze_crossfamily.py
# 输出:
#   results/crossfamily_analysis.md

import json, os, statistics
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")

# id 前缀 -> 类别中文
CATCN = {"AID": "爱迪(双关)", "XHY": "歇后语", "YY": "隐喻", "NY": "逆喻"}
CATS = ["AID", "XHY", "YY", "NY"]

# 家族归属（用于展示与分组）
FAMILY = {
    "qwen-turbo": "Qwen", "qwen-plus": "Qwen", "qwen-max": "Qwen",
    "gpt-4o": "OpenAI", "claude-sonnet-4-6": "Anthropic",
    "gemini-2.5-flash": "Google", "llama-3.1-70b": "Meta",
    "deepseek-v3.1": "DeepSeek", "glm-5.2": "Zhipu",
    "qwen3-max": "Qwen(openlux)", "kimi-k2": "Moonshot",
}

def load(fn):
    out = []
    if not os.path.exists(fn):
        return out
    for l in open(fn, encoding="utf-8"):
        l = l.strip()
        if l:
            out.append(json.loads(l))
    return out

def cat_of(d):
    return d["id"].split("-")[0]

def summarize(rows):
    n = len(rows)
    if n == 0:
        return None
    mem = sum(r["mem_correct"] for r in rows)
    m1 = [r for r in rows if r.get("mem1_correct") is not None]
    m1c = sum(r["mem1_correct"] for r in m1)
    m2 = [r for r in rows if r.get("mem2_correct") is not None]
    m2c = sum(r["mem2_correct"] for r in m2)
    comp_ok = sum(r["comp_correct"] for r in rows)
    comp_acc = [r["comp_acc"] for r in rows]
    q = Counter(r["quadrant"] for r in rows)
    sep = q["mem_only"] + q["comp_only"]
    # 编号偏好
    allp = Counter()
    for r in rows:
        allp.update(r.get("comp_pred_dist", {r.get("comp_pred"): 1}))
    top = max(allp.values()) if allp else 0
    tot = sum(allp.values()) if allp else 1
    return {
        "n": n, "mem": mem / n, "mem1": m1c / len(m1) if m1 else None,
        "mem2": m2c / len(m2) if m2 else None,
        "comp_ok": comp_ok / n, "comp_avg": statistics.mean(comp_acc),
        "sep": sep / n, "bidir": q["both_wrong"] / n,
        "posbias": top / tot,
        "per_cat_comp_avg": {c: statistics.mean([r["comp_acc"] for r in rows if cat_of(r) == c]) for c in CATS if any(cat_of(r) == c for r in rows)},
    }

def main():
    # ---- 载入 v10 Qwen（dashscope） ----
    qwen_files = {
        "qwen-turbo": "pilot_qwen-turbo.jsonl",
        "qwen-plus": "pilot_qwen-plus.jsonl",
        "qwen-max": "pilot_qwen-max.jsonl",
    }
    # ---- 载入 openlux 跨家族 ----
    cross_files = {
        "gpt-4o": "pilot_gpt-4o.jsonl",
        "claude-sonnet-4-6": "pilot_claude-sonnet-4-6.jsonl",
        "gemini-2.5-flash": "pilot_gemini-2.5-flash.jsonl",
        "llama-3.1-70b": "pilot_llama-3.1-70b.jsonl",
        "deepseek-v3.1": "pilot_deepseek-v3.1.jsonl",
        "glm-5.2": "pilot_glm-5.2.jsonl",
        "qwen3-max": "pilot_qwen3-max.jsonl",
        "kimi-k2": "pilot_kimi-k2.jsonl",
    }

    data = {}
    for name, fn in {**qwen_files, **cross_files}.items():
        rows = load(os.path.join(RES, fn))
        if rows:
            data[name] = summarize(rows)

    # ---- 主汇总表 ----
    lines = []
    lines.append("# 跨家族模型对比分析 (openlux.ai)\n")
    lines.append("> 同一批 80 题 (AID/XHY/YY/NY 各 20) + PERMS=6 去偏。\n")
    lines.append("> 目的：检验 v10 结论（Comp 真实理解、M-C 分离在 Mem 侧）是否只属于 Qwen 家族。\n")
    lines.append("")
    lines.append("## 1. 总览表\n")
    lines.append("| 模型 | 家族 | mem(L0) | mem-L1 | mem-L2 | comp_ok% | comp_avg% | 分离% | 双向错% | 编号偏好% |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    order = ["qwen-turbo", "qwen-plus", "qwen-max", "gpt-4o", "claude-sonnet-4-6",
             "gemini-2.5-flash", "llama-3.1-70b", "deepseek-v3.1", "glm-5.2",
             "qwen3-max", "kimi-k2"]
    for name in order:
        s = data.get(name)
        if not s:
            lines.append(f"| {name} | {FAMILY.get(name,'?')} | — (未跑/缺失) |")
            continue
        def pct(x):
            return f"{100*x:.1f}" if x is not None else "—"
        lines.append(
            f"| {name} | {FAMILY.get(name,'?')} | {pct(s['mem'])} | {pct(s['mem1'])} | {pct(s['mem2'])} | "
            f"{pct(s['comp_ok'])} | {pct(s['comp_avg'])} | {pct(s['sep'])} | {pct(s['bidir'])} | {pct(s['posbias'])} |")
    lines.append("")

    # ---- 分类别 comp_avg ----
    lines.append("## 2. 分类别 comp_avg（去偏平均正确率）\n")
    lines.append("| 模型 | 家族 | AID | XHY | YY | NY |")
    lines.append("|---|---|---|---|---|---|")
    for name in order:
        s = data.get(name)
        if not s:
            continue
        pc = s["per_cat_comp_avg"]
        def f(c):
            return f"{100*pc[c]:.1f}" if c in pc else "—"
        lines.append(f"| {name} | {FAMILY.get(name,'?')} | {f('AID')} | {f('XHY')} | {f('YY')} | {f('NY')} |")
    lines.append("")

    # ---- 跨家族真实盲区检测 ----
    lines.append("## 3. 跨家族真实盲区（comp_avg 持续 < 0.5）\n")
    # 收集每个 item 的 comp_acc，按 "强模型" 集合
    strong = [n for n in ["qwen-max", "gpt-4o", "claude-sonnet-4-6", "gemini-2.5-flash",
                          "deepseek-v3.1", "glm-5.2", "qwen3-max", "kimi-k2"] if n in data]
    item_acc = defaultdict(dict)  # id -> {model: comp_acc}
    for name in strong:
        fn = cross_files.get(name) or qwen_files.get(name)
        for r in load(os.path.join(RES, fn)):
            item_acc[r["id"]][name] = r["comp_acc"]
    lines.append("强模型集合: " + ", ".join(strong) + "\n")
    lines.append("| 条目 | 类别 | " + " | ".join(strong) + " | 均值 | 判级 |")
    lines.append("|---|---" + "|---" * len(strong) + "|---|---|")
    blind = []
    for iid in sorted(item_acc):
        vals = item_acc[iid]
        meanv = statistics.mean(vals.values())
        judge = "真实盲区" if meanv < 0.5 else ("边际" if meanv < 0.75 else "通过")
        if meanv < 0.75:
            blind.append((iid, meanv, judge))
        cells = " | ".join(f"{100*vals.get(m,float('nan')):.2f}" if m in vals else "—" for m in strong)
        lines.append(f"| {iid} | {cat_of({'id':iid})} | {cells} | {100*meanv:.2f} | {judge} |")
    lines.append("")
    lines.append(f"**持续 <0.5 的条目 ({len([b for b in blind if b[2]=='真实盲区'])} 条):** " +
                 ", ".join(b[0] for b in blind if b[2] == "真实盲区") or "无")
    lines.append("")

    # ---- qwen 内部交叉验证 ----
    lines.append("## 4. Qwen 内部交叉验证（dashscope qwen-max vs openlux qwen3-max）\n")
    qmax = {r["id"]: r["comp_acc"] for r in load(os.path.join(RES, "pilot_qwen-max.jsonl"))}
    q3 = {r["id"]: r["comp_acc"] for r in load(os.path.join(RES, "pilot_qwen3-max.jsonl"))}
    common = [i for i in qmax if i in q3]
    if common:
        diffs = [q3[i] - qmax[i] for i in common]
        bias = sum(1 for d in diffs if d > 0.01) - sum(1 for d in diffs if d < -0.01)
        lines.append(f"共同条目 {len(common)} 条；qwen3-max 平均差 (openlux - dashscope) = {100*statistics.mean(diffs):.1f}pp")
        lines.append(f"openlux 更高 {sum(1 for d in diffs if d>0.01)} 条，更低 {sum(1 for d in diffs if d<-0.01)} 条，持平 {sum(1 for d in diffs if abs(d)<=0.01)} 条")
        lines.append("")
        lines.append("| 条目 | qwen-max(dash) | qwen3-max(openlux) | 差 |")
        lines.append("|---|---|---|---|")
        for i in sorted(common):
            d = q3[i] - qmax[i]
            lines.append(f"| {i} | {100*qmax[i]:.2f} | {100*q3[i]:.2f} | {100*d:+.2f} |")
    lines.append("")

    # ---- 结论提示 ----
    lines.append("## 5. 初步解读\n")
    cf = [n for n in ["gpt-4o", "claude-sonnet-4-6", "gemini-2.5-flash", "llama-3.1-70b",
                      "deepseek-v3.1", "glm-5.2", "kimi-k2"] if n in data]
    if cf:
        cavg = {n: data[n]["comp_avg"] for n in cf}
        mavg = {n: data[n]["mem"] for n in cf}
        lines.append(f"- 非 Qwen 家族平均 comp_avg = {100*statistics.mean(cavg.values()):.1f}%，"
                     f"平均 mem(L0) = {100*statistics.mean(mavg.values()):.1f}%。")
        lines.append("- 若 comp 普遍高、mem 普遍低 → M-C 分离在 Mem 侧是跨家族共性，非 Qwen 偏置。")
        lines.append(f"- 跨家族持续真实盲区: {', '.join(b[0] for b in blind if b[2]=='真实盲区') or '无'}。")
    lines.append("")
    out = os.path.join(RES, "crossfamily_analysis.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("wrote", out)
    # 也打印到 stdout 方便看
    print("\n".join(lines[:40]))

if __name__ == "__main__":
    main()
