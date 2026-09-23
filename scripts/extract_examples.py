#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从模型输出中按类提取 comp 对 + mem-L0 错 的代表性实例。
人类 comp / mem-L0 按'全对'假定处理（填金标准答案）。"""
import json, re, sys

ROOT = "D:/workbuddy工作目录/2026-09-15-21-31-36/LongTailChineseRhetoric"
DATA = f"{ROOT}/data/pilot.jsonl"
MODEL_FILE = f"{ROOT}/results/pilot_qwen-max.jsonl"   # 主模型：qwen-max (百炼旗舰)

CATMAP = {
    "xiehouyu": "XHY",
    "phonetic_play": "YY",
    "agrarian_proverb": "NY",
    "allusion_idiom": "AID",
}

def load_data():
    out = {}
    for l in open(DATA, encoding="utf-8"):
        l = l.strip()
        if not l:
            continue
        d = json.loads(l)
        out[d["id"]] = d
    return out

def parse_comp_option(prompt, letter):
    """从 comp_prompt 中解析出 letter 对应的选项文字。"""
    if not letter:
        return ""
    pat = re.compile(r"^%s[.\．、]\s*(.+)$" % re.escape(letter), re.M)
    m = pat.search(prompt)
    if m:
        return m.group(1).strip()
    # 回退：按行找以 letter 开头的
    for line in prompt.splitlines():
        if line.strip().startswith(letter):
            return line.strip()[1:].lstrip(".．、 ").strip()
    return ""

def main():
    data = load_data()
    model_items = {}
    for l in open(MODEL_FILE, encoding="utf-8"):
        l = l.strip()
        if not l:
            continue
        d = json.loads(l)
        model_items[d["id"]] = d

    # 每个类别收集候选
    cands = {c: [] for c in CATMAP}
    for cid, m in model_items.items():
        cat = m.get("category")
        if cat not in CATMAP:
            continue
        comp_ok = bool(m.get("comp_correct")) or (m.get("comp_acc", 0) >= 1.0)
        mem_l0_ok = bool(m.get("mem_correct"))
        if comp_ok and not mem_l0_ok:
            cands[cat].append(m)

    # 手工优选：mem-L0 输出与金标准完全无关（编造式失败）且 comp 对的更强示例
    PREFERRED = {
        "xiehouyu": "XHY-013",
        "phonetic_play": "YY-013",
        "agrarian_proverb": "NY-001",
        "allusion_idiom": "AID-003",
    }

    results = []
    for cat, items in cands.items():
        if not items:
            print(f"[!] {CATMAP[cat]} ({cat}) 在 {MODEL_FILE} 无 comp对+memL0错 的候选", file=sys.stderr)
            results.append({"category": CATMAP[cat], "found": False})
            continue
        # 优先采用手工优选 id（若其在候选内）
        pref = PREFERRED.get(cat)
        chosen = None
        if pref:
            for m in items:
                if m["id"] == pref:
                    chosen = m
                    break
        # 否则自动挑选 mem-L0 输出与金标准"互不包含"（明显不同）的实例，论证更干净；
        # 同时 comp 须为单一字母命中、且 comp_pred 与模型文件 gold 一致。
        def clarity(m):
            d = data.get(m["id"])
            if not d:
                return 0
            gold_mem = d["mem_task"].get("accept") or [""]
            g0 = gold_mem[0]
            r = (m.get("mem_resp") or "").strip()
            # 互不包含 → 明显不同，得分高
            score = 0
            if g0 and r:
                if r not in g0 and g0 not in r:
                    score += 2
                else:
                    score += 0
            pred = m.get("comp_pred")
            if isinstance(pred, str) and len(pred) == 1 and pred.isalpha():
                score += 1
            return score
        if chosen is None:
            items_sorted = sorted(items, key=clarity, reverse=True)
            chosen = items_sorted[0]
        m = chosen
        d = data[m["id"]]
        gold_mem = d["mem_task"].get("accept") or [d.get("original", "")]
        gold_mem0 = gold_mem[0] if gold_mem else ""
        # 人类 comp 正确 = 模型文件 gold（实验口径），而非数据集 answer（两者修订不一致）
        comp_gold = m.get("comp_gold") or d["comp_task"].get("answer")
        comp_pred = m.get("comp_pred")
        model_opt_text = parse_comp_option(m.get("comp_prompt", ""), comp_pred)
        human_opt_text = parse_comp_option(m.get("comp_prompt", ""), comp_gold)
        # 数据集 gold 与模型文件 gold 是否冲突
        data_gold = d["comp_task"].get("answer")
        gold_conflict = (data_gold and comp_gold and str(data_gold) != str(comp_gold))
        results.append({
            "category": CATMAP[cat],
            "found": True,
            "item_id": m["id"],
            "model": m.get("model"),
            "original": d.get("original"),
            "mem_l0_gold": gold_mem0,
            "model_mem_l0_resp": m.get("mem_resp"),
            "model_comp_pred": comp_pred,
            "model_comp_option_text": model_opt_text,
            "comp_gold": comp_gold,
            "human_comp_option_text": human_opt_text,
            "source": d.get("source"),
            "gold_conflict": gold_conflict,
            "data_gold": data_gold,
        })

    # 输出 JSON
    with open(f"{ROOT}/results/_examples_qwenmax.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 输出 Markdown 表格
    print("\n# 代表性实例（模型 comp 对 + mem-L0 错；人类按全对假定）\n")
    print("数据源：", MODEL_FILE)
    print()
    for r in results:
        if not r.get("found"):
            print(f"## {r['category']} — 未找到候选（见 stderr）\n")
            continue
        print(f"## {r['category']} · {r['item_id']}")
        print()
        print(f"- **item_id**: {r['item_id']}")
        print(f"- **category**: {r['category']}")
        print(f"- **original（题干/原句）**: {r['original']}")
        print(f"- **模型 comp 输出（选中选项 {r['model_comp_pred']}）**: {r['model_comp_option_text']}")
        print(f"- **模型 mem-L0 输出（错误回答原文）**: {r['model_mem_l0_resp']}")
        print(f"- **人类 comp 回答（正确选项 {r['comp_gold']}）**: {r['human_comp_option_text']}  （假定全对，填金标准）")
        print(f"- **人类 mem-L0 回答（正确原句）**: {r['mem_l0_gold']}  （假定全对，填金标准）")
        print(f"- **source（出处）**: {r['source']}")
        if r.get("gold_conflict"):
            print(f"  - ⚠️ **gold 冲突注**：模型文件 gold={r['comp_gold']} 与数据集 `comp_task.answer`={r['data_gold']} 不一致（项目内已知修订差异）；本例以**模型文件 gold（实验口径）**判定 comp 正确。")
        print()

if __name__ == "__main__":
    main()
