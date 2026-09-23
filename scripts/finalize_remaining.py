#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收尾脚本（无 API 调用，纯本地聚合/外推）

背景：百炼 token 已耗尽。B1 已 100% 跑完但 raw 含 2485 条重复行（双进程 bug 残留）；
      B7 的 glm-5.2 跑满 80/80，MiniMax-M2.5 仅 23/80（余 57 条无 token 可跑）。

动作：
  A) B1：按 (id,model,cond) 去重（保留首条），检测冲突（重复副本取值不一致），
         干净重聚合 → 覆盖 rag_conditions.json（保持原 schema）+ 写 B1_RESULTS.md。
  B) B7：glm-5.2 用 80 条实测；MiniMax-M2.5 用 23 条实测均值「保持外推」到 80 条
         （carry-forward mean imputation，显式标注低置信）→ 写 b7_final.json + B7_RESULTS.md。
"""
import json, os, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
B1RAW = os.path.join(ROOT, "results", "rag_conditions_raw.jsonl")
B1JSON = os.path.join(ROOT, "results", "rag_conditions.json")
B1MD = os.path.join(ROOT, "results", "B1_RESULTS.md")
B7RAW = os.path.join(ROOT, "results", "b7_raw.jsonl")
B7JSON = os.path.join(ROOT, "results", "b7_final.json")
B7MD = os.path.join(ROOT, "results", "B7_RESULTS.md")

TARGET_B1 = 5824  # 208 题 × 7 模型 × 4 条件
CONDS = ["A", "B", "C", "D"]

# ============================ B1 ============================
print("=" * 60)
print("[B1] 去重 + 干净聚合")
rows = []
with open(B1RAW, encoding="utf-8") as f:
    for l in f:
        l = l.strip()
        if not l:
            continue
        try:
            rows.append(json.loads(l))
        except Exception:
            continue

seen = {}
conflicts = 0
rows_u = []
for d in rows:
    key = (d.get("id"), d.get("model"), d.get("cond"))
    cv = (d.get("correct"), d.get("total"))
    if key in seen:
        if seen[key] != cv:
            conflicts += 1
        continue
    seen[key] = cv
    rows_u.append(d)

print("  总行数=%d | 去重后唯一组合=%d | 重复行=%d | 冲突(取值不一致)副本数=%d"
      % (len(rows), len(seen), len(rows) - len(seen), conflicts))
print("  覆盖率=%.1f%% (%d/%d)" % (len(seen) / TARGET_B1 * 100, len(seen), TARGET_B1))

# 聚合：每 (model, cond) 累加 correct/total
agg = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))  # [correct,total]
models = set()
for d in rows_u:
    m = d["model"]; c = d["cond"]
    models.add(m)
    agg[m][c][0] += d["correct"]; agg[m][c][1] += d["total"]

comp_by_model_cond = {}
for m in sorted(models):
    comp_by_model_cond[m] = {}
    for c in CONDS:
        cor, tot = agg[m][c]
        comp_by_model_cond[m][c] = (100.0 * cor / tot) if tot else None

out = {
    "models": sorted(models),
    "conds": CONDS,
    "cats": ["xiehouyu"],
    "perms": 6,
    "n_items": 208,
    "comp_by_model_cond": comp_by_model_cond,
    "dedup_conflicts": conflicts,
    "coverage": len(seen) / TARGET_B1,
}
json.dump(out, open(B1JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("  已写 rag_conditions.json（已去重，schema 不变）")

# 头条指标：知识增益 / 整合缺陷 / 单调性
def pct(v):
    return "—" if v is None else "%.1f%%" % v

lines = ["# B1 · RAG 四条件实验结果（干净去重版）", "",
         "> 去重后唯一组合 %d/%d（覆盖率 %.1f%%），冲突副本 %d 条已按首条裁决。" % (
             len(seen), TARGET_B1, out["coverage"] * 100, conflicts),
         "> 条件：A=无知识 / B=文化背景 / C=部分片段 / D=oracle（抽象释义）。", ""]
lines += ["## 各模型四条件准确率", "",
          "| 模型 | A(无知识) | B(文化背景) | C(部分片段) | D(oracle) | 知识增益 C−A | 整合缺陷 100−D |",
          "|---|---|---|---|---|---|---|"]
kg_all, id_all = [], []
mono_ok = 0
for m in sorted(models):
    A, B, C, D = (comp_by_model_cond[m][k] for k in CONDS)
    kg = (C - A) if (A is not None and C is not None) else None
    integ = (100 - D) if D is not None else None
    if None not in (A, B, C, D):
        if A <= B <= C <= D:
            mono_ok += 1
    if kg is not None:
        kg_all.append(kg)
    if integ is not None:
        id_all.append(integ)
    lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
        m, pct(A), pct(B), pct(C), pct(D), pct(kg), pct(integ)))

mA = statistics.mean([comp_by_model_cond[m]["A"] for m in models if comp_by_model_cond[m]["A"] is not None])
mB = statistics.mean([comp_by_model_cond[m]["B"] for m in models if comp_by_model_cond[m]["B"] is not None])
mC = statistics.mean([comp_by_model_cond[m]["C"] for m in models if comp_by_model_cond[m]["C"] is not None])
mD = statistics.mean([comp_by_model_cond[m]["D"] for m in models if comp_by_model_cond[m]["D"] is not None])
lines += ["", "## 七模型均值与结论", "",
          "- **A 无知识**: %.1f%%" % mA,
          "- **B 文化背景**: %.1f%%" % mB,
          "- **C 部分片段**: %.1f%%" % mC,
          "- **D oracle**: %.1f%%" % mD,
          "- **知识增益 (C−A)**: **%.1f pp**" % (mC - mA),
          "- **整合缺陷 (100−D)**: **%.1f pp**" % (100 - mD),
          "- **单调性 A≤B≤C≤D 满足模型数**: %d/%d" % (mono_ok, len(models)),
          "", "> 整合缺陷=100−comp_D：即使给了抽象释义(oracle)，模型仍无法把「字面片段」整合进正确释义的比例——这是本实验核心卖点。", ""]
open(B1MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("  已写 B1_RESULTS.md")
print("  [B1头条] 知识增益=%.1fpp 整合缺陷=%.1fpp 单调性=%d/%d" % (mC - mA, 100 - mD, mono_ok, len(models)))

# ============================ B7 ============================
print("=" * 60)
print("[B7] glm 实测 + MiniMax 均值保持外推(23→80)")
b7rows = []
with open(B7RAW, encoding="utf-8") as f:
    for l in f:
        l = l.strip()
        if not l:
            continue
        try:
            b7rows.append(json.loads(l))
        except Exception:
            continue

by_m = collections.defaultdict(list)
for d in b7rows:
    by_m[d["model"]].append(d)

TARGET_B7 = 80
metrics = ["l0_ok", "l1_ok", "l2_acc", "comp_acc"]
CATN = {"xiehouyu": "XHY", "phonetic_play": "YY", "allusion_idiom": "AID", "agrarian_proverb": "NY"}
res = {}

def block_avg(rs, f):
    v = [r[f] for r in rs if r.get(f) is not None]
    return statistics.mean(v) if v else None

b7lines = ["# B7 · Zhipu(glm-5.2) + MiniMax-M2.5 补测（收尾版）", "",
           "> ⚠️ **MiniMax-M2.5 仅 23/80 实测**（剩余 57 条因百炼 token 耗尽未跑）。",
           "> 本报告对 MiniMax 采用「均值保持外推」：以 23 条实测均值作为 80 条整体估计（carry-forward mean imputation）。",
           "> **此为低置信外推，非实测**，正式投稿前建议补 token 重跑剩余 57 条。",
           "> 子集：跨家族同一 80 题（XHY/YY/AID/NY 各 20）；口径 mem-L0/L1、mem-L2(PERMS=6)、comp(PERMS=6)。", ""]
b7lines += ["## 整体（四层）", "",
            "| 模型 | n(实测) | 覆盖 | mem-L0 | mem-L1 | mem-L2 | comp | 备注 |",
            "|---|---|---|---|---|---|---|---|"]

for m in ["glm-5.2", "MiniMax-M2.5"]:
    rs = by_m.get(m, [])
    n_obs = len(rs)
    cov = n_obs / TARGET_B7
    means = {f: block_avg(rs, f) for f in metrics}
    is_extrap = (n_obs < TARGET_B7)
    res[m] = {"n_obs": n_obs, "target": TARGET_B7, "coverage": cov,
              "extrapolated": is_extrap, "metrics": means}
    note = "实测" if not is_extrap else "外推(均值保持)"
    b7lines.append("| %s | %d | %.0f%% | %s | %s | %s | %s | %s |" % (
        m, n_obs, cov * 100,
        pct(means["l0_ok"]), pct(means["l1_ok"]), pct(means["l2_acc"]), pct(means["comp_acc"]), note))

# 分四类
b7lines += ["", "## 分修辞类别", "",
            "| 模型 | 类别 | n | mem-L0 | mem-L1 | mem-L2 | comp |",
            "|---|---|---|---|---|---|---|"]
for m in ["glm-5.2", "MiniMax-M2.5"]:
    rs = by_m.get(m, [])
    for cat in ["xiehouyu", "phonetic_play", "allusion_idiom", "agrarian_proverb"]:
        crs = [r for r in rs if r.get("category") == cat]
        if not crs:
            continue
        b7lines.append("| %s | %s | %d | %s | %s | %s | %s |" % (
            m, CATN.get(cat, cat), len(crs),
            pct(block_avg(crs, "l0_ok")), pct(block_avg(crs, "l1_ok")),
            pct(block_avg(crs, "l2_acc")), pct(block_avg(crs, "comp_acc"))))

json.dump(res, open(B7JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
b7lines += ["", "## 说明", "",
            "- glm-5.2：80/80 全实测，可直接并入跨家族表。",
            "- MiniMax-M2.5：23/80 实测，剩余 57 条以实测均值外推；外推假设「未测 57 题与该 23 题同分布」，置信度有限。",
            "- 外推方法：对每个指标 f，整体估计 = mean(r[f] for r in 实测 23 条)；不引入其他模型做回归（避免引入额外假设）。", ""]
open(B7MD, "w", encoding="utf-8").write("\n".join(b7lines) + "\n")
print("  已写 b7_final.json + B7_RESULTS.md")
for m in ["glm-5.2", "MiniMax-M2.5"]:
    r = res[m]
    print("  %-14s n=%d(覆盖%.0f%%) L0=%s L1=%s L2=%s comp=%s %s" % (
        m, r["n_obs"], r["coverage"] * 100, pct(r["metrics"]["l0_ok"]),
        pct(r["metrics"]["l1_ok"]), pct(r["metrics"]["l2_acc"]), pct(r["metrics"]["comp_acc"]),
        "实测" if not r["extrapolated"] else "外推"))
print("=" * 60)
print("DONE")
