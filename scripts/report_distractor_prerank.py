# 第二关 · 干扰项强度均衡 —— 结果报告生成器
#
# 读取 distractor_prerank.py 产出的 results/distractor_prerank.json
# （list of {"id","over":[[key,percent],...],"distractor_text":{key:text}}），
# 结合 pilot.jsonl 的原文/类别上下文，产出按类别分组的 markdown 报告。
#
# 用法:
#   python scripts/report_distractor_prerank.py
import os, json
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "pilot.jsonl")
IN = os.path.join(ROOT, "results", "distractor_prerank.json")
IN_BYM = os.path.join(ROOT, "results", "prerank_by_model.json")
OUT = os.path.join(ROOT, "results", "distractor_prerank_report.md")

CATNAME = {"xiehouyu": "XHY 歇后语", "allusion_idiom": "AID 典故成语",
           "agrarian_proverb": "NY 农谚", "phonetic_play": "YY 谐音隐语"}


def main():
    items = [json.loads(l) for l in open(DATA, encoding="utf-8") if l.strip()]
    meta = {d["id"]: d for d in items}
    over = json.load(open(IN, encoding="utf-8"))
    by_model = None
    if os.path.exists(IN_BYM):
        try:
            by_model = json.load(open(IN_BYM, encoding="utf-8"))
        except Exception:
            by_model = None
    n_models = len(by_model["models"]) if by_model else 3

    by_cat = defaultdict(list)
    for o in over:
        d = meta.get(o["id"])
        cat = d["category"] if d else "?"
        by_cat[cat].append(o)

    lines = ["# 第二关 · 干扰项强度均衡 —— 过强干扰项报告", ""]
    lines.append("阈值：某干扰项被 %d 模型（跨厂商）错选率 > 40%% 即标记「过强」(随机期望≈20%%)。" % n_models)
    lines.append("")
    tot = len(over)
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 类别 | 过强条目数 | 占该类 comp 题比 |")
    lines.append("|---|---|---|")
    for cat in ("xiehouyu", "agrarian_proverb", "phonetic_play"):
        n_comp = sum(1 for d in items if d["category"] == cat)
        n_over = len(by_cat.get(cat, []))
        pct = "%.0f%%" % (100 * n_over / n_comp) if n_comp else "-"
        lines.append("| %s | %d | %s |" % (CATNAME.get(cat, cat), n_over, pct))
    lines.append("| **合计** | **%d** |  |" % tot)
    lines.append("")
    lines.append("> 注：AID 典故成语按设计不参与 comp 干扰项预跑（干扰项=近义成语，机制不同）。")
    lines.append("")

    if by_model:
        def vendor(m):
            m = m.lower()
            if m.startswith("qwen"):
                return "阿里 Qwen"
            if m.startswith("kimi") or m.startswith("moonshot"):
                return "月之暗面 Kimi"
            if m.startswith("deepseek"):
                return "DeepSeek"
            return "其他"

        lines.append("### 各模型过强条目数（per-model 口径）")
        lines.append("")
        lines.append("| 模型 | 厂商 | 过强条目数 |")
        lines.append("|---|---|---|")
        for m in by_model["models"]:
            lines.append("| %s | %s | %d |" % (m, vendor(m), by_model["per_model_over_count"][m]))
        lines.append("")

    for cat in ("xiehouyu", "agrarian_proverb", "phonetic_play"):
        lst = by_cat.get(cat, [])
        if not lst:
            continue
        lines.append("## %s（%d 条过强）" % (CATNAME.get(cat, cat), len(lst)))
        lines.append("")
        for o in lst:
            d = meta.get(o["id"])
            orig = d.get("original", "") if d else ""
            lines.append("- **%s**  `%s`" % (o["id"], orig))
            for k, pct in o["over"]:
                txt = o["distractor_text"].get(k, "")
                lines.append("  - 干扰项 %s 错选率 **%.0f%%** — %s" % (k, pct, txt))
        lines.append("")

    lines.append("## 处置建议")
    lines.append("")
    lines.append("1. 对每条「过强」干扰项，用 `comp_distractors.hn` 池中语义相似度较低的候选替换，")
    lines.append("   或重写该干扰项使其不再与 gold 情境高度重叠；替换后需重跑预跑确认错选率回落到 ≤40%。")
    lines.append("2. 全量重跑 `distractor_prerank.py` 直至过强条目数收敛为 0（或仅剩可接受的少数）。")
    lines.append("3. 本脚本仅统计 comp_task；mem_l2_task 的形式补全 MCQ 如需同等质检，可后续扩展。")

    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print("报告已写入", OUT, "| 过强条目合计", tot)


if __name__ == "__main__":
    main()
