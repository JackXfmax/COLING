# -*- coding: utf-8 -*-
"""v3 干扰项生成器：同场异机制 + 严禁近义聚簇。
以 15 条优质探针（manual-nearfield-probe*）为 few-shot 示范，
对 XHY 剩余 15、NY 剩余 15、YY 含义型 4 条 调用 qwen-plus 生成硬干扰项。
生成后做程序化校验，失败项留空交由人工兜底。
"""
import json, os, re, sys, time, urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
HN_PATH = os.path.join(DATA, "comp_hn.json")
PILOT_PATH = os.path.join(DATA, "pilot.jsonl")

ENDPOINT = os.environ.get("PILOT_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
KEY = os.environ.get("PILOT_API_KEY", "")
MODEL = "qwen-plus"

# 目标条目（已硬化探针除外）
TARGETS = {
    "xiehouyu": ["XHY-001","XHY-003","XHY-004","XHY-007","XHY-008","XHY-009",
                 "XHY-010","XHY-011","XHY-013","XHY-014","XHY-015","XHY-016",
                 "XHY-018","XHY-019","XHY-020"],
    "phonetic_play": ["YY-007","YY-009","YY-015","YY-016"],
    # NY 仅重做"通用道理型"11 条（其 gold 非纯农事，v3 强制农事提示导致寄存器错配）；
    # 纯农事 4 条（NY-005/011/013/014）保留 v3 生成的农事干扰项（已同场）。
    "agrarian_proverb": ["NY-002","NY-004","NY-007","NY-008","NY-009","NY-010",
                         "NY-012","NY-015","NY-017","NY-018","NY-019"],
}
PREFIX = {"xiehouyu":"XHY-", "phonetic_play":"YY-", "agrarian_proverb":"NY-"}

RULES = """你正在为中文修辞理解评测构造"干扰项"（distractors）。给定一条正确项（gold），你要写出 5 条"同语义场但不同机制"的干扰项，用于考察模型是否真正理解、而不是靠排除法蒙对。

硬性要求：
1. 同语义场：干扰项必须与正确项属于同一大领域/同一生活情境类型/同一文化寄存器（例如都是婚恋相思、都是农事规律、都是职场人情），不能跨到毫不相干的语义场。
2. 异机制（最关键）：每条干扰项必须是与正确项【不同的具体情境/机制/道理】；而且 5 条干扰项彼此之间也必须是不同机制，【严禁出现近义聚簇】——即不能 5 条都在复述正确项的同一个核心机制。反例：正确项讲"小事酿成大患"，若干扰项全是"蚁穴溃堤/苗头成大患/火星烧林/小错积久/歪风成乱象"，就失败，因为它们是同机制近义复述，人也无法区分。你必须让 5 条各自代表一个独立、可区分的具体情形。
3. 纯含义短句，每条一行，用"- "开头；不要出现原条目名称，不要加解释或序号以外的符号。
4. 必须恰好 5 条，且 5 条互不相同、都不等于正确项。

下面是正确的示范（同领域、各机制互异，可作为风格参考）："""

def call_llm(prompt):
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.8, "max_tokens": 600}
    req = urllib.request.Request(
        ENDPOINT + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]
    except Exception as e:
        return "[ERROR] %s" % e

def parse_items(content):
    if content.startswith("[ERROR]"):
        return []
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    items = []
    for l in lines:
        m = re.match(r'^[\-\*\u2022\u3002]?\s*[\d\u4e00-\u9fff]{0,2}[\.\\\、\。\）\)]\s*(.*)', l)
        if m:
            t = m.group(1).strip().strip('"').strip("'")
            if t:
                items.append(t)
        elif l.startswith("-") or l.startswith("·"):
            t = l[1:].strip().strip('"').strip("'")
            if t:
                items.append(t)
    # 去重保序
    seen, out = set(), []
    for t in items:
        if t not in seen:
            seen.add(t); out.append(t)
    return out

# 手写"非纯农事"NY 校准样本，避免模型把 NY 一律农事化
NY_NONAG_FEWSHOT = [
    ("本性难移，人到老也改不掉积习",
     ["近朱者赤近墨者黑，环境最能塑造一个人",
      "三岁看老，幼时心性便定了一生格局",
      "上梁不正下梁歪，上位者行事底下人自会效仿",
      "树挪死人挪活，换个环境反倒能把旧习改掉",
      "一回生二回熟，相处久了生疏自然变亲近"]),
    ("人们会把毫不相干的征兆拿来解释行情起伏",
     ["物候早迟主年景丰歉，农人据此估仓廪盈虚",
      "市井谣谚应旱涝，商贾借以揣米价涨落",
      "星象偏斜示收成变数，粮号据此定囤售时机",
      "云气西散兆晴旱，脚夫依此猜脚价高低",
      "朔望更迭积成谷价起伏，囤户借势低吸高抛"]),
]

def fewshot_block(bycat, cat, n=3):
    ex = list(bycat.get(cat, [])[:n])
    if cat == "agrarian_proverb":
        ex = NY_NONAG_FEWSHOT + ex   # 用非农事样本校准，避免一律农事化
    if not ex:
        return ""
    blk = "\n【示范】\n"
    for g, hn in ex:
        blk += f"正确项：{g}\n干扰项：\n" + "\n".join(f"- {d}" for d in hn) + "\n"
    return blk

def build_prompt(cat, gold, bycat):
    prompt = RULES + fewshot_block(bycat, cat)
    cat_hint = {
        "xiehouyu": "（生活情境类：干扰项应是与正确项同领域但机制不同的具体人情世故情境）",
        "phonetic_play": "（子夜歌情诗隐语类：干扰项应是同寄存器（相思/闺怨/爱慕等）但不同具体情思的短句）",
        "agrarian_proverb": "（语义场随 gold 走：NY 条目涵义领域各异——有的讲农时、有的讲征兆预兆、有的讲人性积习、有的讲行情市价、有的讲处世分寸。请严格针对【该句的实际涵义领域】生成同领域但不同机理的干扰项，不要一律写成种地规律；若 gold 讲人性，干扰项也须是其他讲人性/处世的道理）",
    }[cat]
    prompt += f"\n现在请生成。正确项（gold）：{gold}\n{cat_hint}\n请给出 5 条干扰项，每条一行，以'- '开头。"
    return prompt

def main():
    hn = json.load(open(HN_PATH, encoding="utf-8"))
    # 用优质探针作 few-shot
    bycat = defaultdict(list)
    for k, v in hn.items():
        s = str(v.get("source", ""))
        if s.startswith("manual-nearfield-probe"):
            bycat[v["category"]].append((v["gold"], v["hn"]))

    fails = []
    for cat, ids in TARGETS.items():
        for i in ids:
            gold = hn[i]["gold"]
            best = None
            for attempt in range(4):
                c = call_llm(build_prompt(cat, gold, bycat))
                items = parse_items(c)
                if len(items) == 5 and gold not in items and len(set(items)) == 5:
                    best = items
                    break
                time.sleep(0.3)
            if best:
                hn[i]["hn"] = best
                hn[i]["source"] = "llm-v3-verified"
                print(f"[OK]   {i}")
            else:
                fails.append(i)
                print(f"[FAIL] {i}  (gold={gold[:20]}...)")
    json.dump(hn, open(HN_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\nFAILED:", fails)
    return 0

if __name__ == "__main__":
    sys.exit(main())
