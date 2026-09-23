#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B2 · 迁移测试（四类变体）结果报告生成器。
读取 run_b2_gpt.py 聚合产物 B2_GPT.json（table + retention），生成 B2_RESULTS.md。

保留率定义：retention(v) = comp(v) / comp(ORIG)  （v ∈ {T1,T2,T3,T4}）
  - =100% → 该变换不影响理解
  - <100% → 变换损害理解（surface-form 脆弱性）
  - >100% → 变换反而更易（异常，通常因为变换消除了歧义）

用法：
  python -u scripts/gen_b2_report.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "results", "B2_GPT.json")
OUT = os.path.join(ROOT, "results", "B2_RESULTS.md")
VARIANTS = ["T1", "T2", "T3", "T4"]
VNAME = {"T1": "T1 同义改写", "T2": "T2 方言转普通话", "T3": "T3 新造类比", "T4": "T4 反事实"}


def pct(v):
    return "—" if v is None else "%.1f%%" % (100 * v)


def main():
    if not os.path.exists(SRC):
        print("[gen_b2] 未找到 %s，请先跑完 run_b2_gpt.py" % SRC)
        sys.exit(1)
    d = json.load(open(SRC, encoding="utf-8"))
    models = d.get("eval_models", [])
    table = d.get("table", {})
    retention = d.get("retention", {})
    n_items = d.get("n_items", 0)
    authors = ",".join(d.get("authors", []))
    perms = d.get("perms", 6)

    lines = []
    lines.append("# B2 · 迁移测试（四类 surface-form 变体）结果")
    lines.append("")
    lines.append("> 子集：pilot.jsonl 全量 **%d** 条（4 类修辞）。" % n_items)
    lines.append("> 口径：每条 item 构造 ORIG（原 stem）+ T1 同义改写 / T2 方言转普通话 / T3 新造类比 / T4 反事实 四类变体；"
                 "变体由 **%s** 生成，comp 由 **%s** 评测（PERMS=%d 去位置偏置）。" % (authors, ",".join(models), perms))
    lines.append("> 保留率 = 变体 comp / ORIG comp。越低说明该变换越伤「理解」，即模型对 surface-form 越脆弱。")
    lines.append("")
    lines.append("## 总体保留率表")
    lines.append("")
    header = "| 评测模型 | ORIG | " + " | ".join(VNAME[v] for v in VARIANTS) + " |"
    sep = "|---|---|" + "|".join(["---"] * len(VARIANTS)) + "|"
    lines.append(header)
    lines.append(sep)
    for m in models:
        row = "| %s | %s " % (m, pct(table.get(m, {}).get("ORIG")))
        for v in VARIANTS:
            row += "| %s " % pct(table.get(m, {}).get(v))
        row += "|"
        lines.append(row)
    lines.append("")

    lines.append("## 保留率（%）明细")
    lines.append("")
    lines.append("| 评测模型 | " + " | ".join(VARIANTS) + " |")
    lines.append("|" + "---|" * (len(VARIANTS) + 1))
    for m in models:
        ret = retention.get(m, {})
        row = "| %s |" % m
        for v in VARIANTS:
            rv = ret.get(v)
            row += " %s |" % (pct(rv) if rv is not None else "—")
        lines.append(row)
    lines.append("")

    lines.append("## 解读")
    lines.append("")
    # 自动解读：取第一个评测模型，找最低/最高保留率变体
    if models:
        m0 = models[0]
        ret0 = retention.get(m0, {})
        comp0 = table.get(m0, {})
        # 找最伤理解的变体
        ranked = sorted([(v, ret0.get(v), comp0.get(v)) for v in VARIANTS if ret0.get(v) is not None],
                        key=lambda x: x[1])
        if ranked:
            worst = ranked[0]
            best = ranked[-1]
            lines.append("- 在 **%s** 上，保留率最低的是 **%s（%.1f%%）** —— 该 surface-form 变换最伤理解；"
                         "最高的是 **%s（%.1f%%）**。" % (
                             m0, VNAME[worst[0]], 100 * worst[1], VNAME[best[0]], 100 * best[1]))
            lines.append("- 若某变体保留率显著 <100%%，说明模型对「字面/方言/类比结构」敏感，"
                         "comp 部分来自 surface-form 匹配而非纯语义整合 —— 与 B1「整合缺陷」结论相互印证。")
            lines.append("- 若某变体保留率 ≈100%% 甚至 >100%%，说明该变换不损（或反而澄清）语义，"
                         "模型对该维度鲁棒。")
    lines.append("- 注：本实验为 **GPT 闭环**（gpt-4o 作者 + gpt-4o-mini 评测），与百炼 7 模型家族是两套管线，"
                 "勿与附录 A/B 的跨家族主结论混比。")
    lines.append("")

    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print("[gen_b2] 已写 %s（模型=%s, n=%d）" % (OUT, ",".join(models), n_items))
    return OUT


if __name__ == "__main__":
    main()
