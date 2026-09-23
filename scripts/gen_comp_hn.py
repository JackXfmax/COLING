# 用 LLM 为每条 comp 题生成「语义近邻 hard negative」干扰项。
# 为什么需要它：每类 20 条是刻意挑选的多样化长尾样例，类内含义天然不搭，
# 自动字符相似度（char-bigram 余弦）在完整句子上几乎全 0，无法产出真正近邻干扰项。
# 真正的 hard negative 必须来自类外近义表达 —— 由 LLM 按"同语义场但明确不同"撰写。
#
# 特例：phonetic_play（字谜/隐语）的正确选项是"解谜手法"，干扰项必须是【其他谜目的真实手法】
#       （数据集内其他 YY 条目的 _b_raw 即手法文本），不能用 LLM 乱编（会变成赞语、类型错配）。
#
# 作者模型用 qwen-plus（与待测旗舰 qwen-max 错开，降低 eval 污染）。
# 用法:
#   python gen_comp_hn.py                      # 全部（YY 走数据集内手法）
#   python gen_comp_hn.py --cats xiehouyu,agrarian_proverb   # 只重生成这两类，保留其余
import json, os, re, urllib.request, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

ENDPOINT = os.environ.get("PILOT_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY = os.environ.get("PILOT_API_KEY", "")
AUTHOR_MODEL = os.environ.get("PILOT_AUTHOR_MODEL", "qwen-plus")
OUT = os.path.join(DATA, "comp_hn.json")

CAT_DESC = {
    "xiehouyu": "乡土歇后语（前半是比喻，后半是含义）",
    "phonetic_play": "字谜/隐语（用拆字、谐音等手法隐藏真意）",
    "allusion_idiom": "冷门典故成语",
    "agrarian_proverb": "北方农耕隐喻农谚",
}

# 每类给 LLM 的"硬约束"——直接针对上一轮抽检发现的缺陷
STRICT = {
    "xiehouyu": "干扰项必须是与正确答案【句式、长度相近】的具体情境描述句（写成'某人…结果…'这样的完整句子，"
                "不要写成四字短语或成语）；含义必须明显不同，不能是原答案的近义复述、同义改写或仅换种说法"
                "（例如原答案是'出力不讨好、被人嫌'，干扰项就不能是'白费力气反被嫌'这种近义句）；"
                "应是同一话题（人情/做事/境遇）下但指向不同的情形。",
    "agrarian_proverb": "干扰项必须是与正确答案【句式、长度相近】的抽象道理句（如'……预示……''……积累成……'），"
                        "不要写成四字短语或具体农活贴士（如'灶台湿滑要小心''锅台冷热关乎收成'）；"
                        "且与正确答案在抽象层面相近但结论不同。",
    "allusion_idiom": "干扰项与原答案同属情绪/境遇语义场但含义明确不同，可含少量近义与少量反义对照。",
}


def call(prompt):
    url = ENDPOINT.rstrip("/") + "/chat/completions"
    payload = {"model": AUTHOR_MODEL, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.7, "max_tokens": 400}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + API_KEY})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]


def extract_array(text):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        return [str(x).strip() for x in json.loads(m.group(0)) if str(x).strip()]
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", default="", help="只重生成这些类别(逗号分隔)，其余保留")
    args = ap.parse_args()
    only = set(c.strip() for c in args.cats.split(",") if c.strip())

    rows = [json.loads(l) for l in open(os.path.join(DATA, "pilot.jsonl"), encoding="utf-8") if l.strip()]
    # 预存每类其他条目的真实手法（供 YY 使用）
    methods_by_cat = {}
    for r in rows:
        methods_by_cat.setdefault(r["category"], []).append(r)

    out = {}
    if os.path.exists(OUT):
        try:
            out = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            out = {}

    todo = [r for r in rows if (not only or r["category"] in only)]
    for i, r in enumerate(todo, 1):
        cat = r["category"]
        cid = r["id"]
        gold = r["comp_task"]["options"][r["comp_task"]["answer"]]
        if cat == "phonetic_play":
            # 干扰项 = 其他谜目的真实手法（类型正确、封闭小集合、真难）
            hn = []
            for x in methods_by_cat[cat]:
                if x["id"] == cid:
                    continue
                m = x["comp_task"]["options"][x["comp_task"]["answer"]]
                if m and m not in hn and m != gold:
                    hn.append(m)
                if len(hn) >= 5:
                    break
            out[cid] = {"category": cat, "gold": gold, "hn": hn[:5],
                        "source": "in-dataset-methods"}
            print("[%d/%d] %s (YY->数据集内手法) -> %d" % (i, len(todo), cid, len(hn)))
            continue
        # 其余类别走 LLM
        form = r["original"]
        gold_meaning = r.get("target_meaning", "")
        strict = STRICT.get(cat, "")
        prompt = (
            "你是一位中文修辞评测的命题专家。下面是一道「%s」理解题。\n"
            "题目形式：%s\n"
            "正确答案（含义）：%s\n\n"
            "请生成 5 个【干扰项】（错误选项）。硬性要求：\n"
            "%s\n"
            "通用要求：长度与正确答案相近（中文 8-22 字），简洁自然；不得与原答案字面重复、"
            "不得出现该形式的原词；对不懂该知识点的人有迷惑性，但懂的人能明确区分。"
            "只输出一个 JSON 数组，如 [\"一\",\"二\",\"三\",\"四\",\"五\"]，不要解释。"
        ) % (CAT_DESC.get(cat, "中文修辞"), form, gold_meaning or gold, strict)
        text = call(prompt)
        arr = extract_array(text)
        seen, clean = set(), []
        for a in arr:
            a = re.sub(r"[（(][^）)]*[)）]", "", a).strip()
            if not a or a in seen or a == (gold_meaning or gold):
                continue
            seen.add(a)
            clean.append(a)
        out[cid] = {"category": cat, "gold": gold, "hn": clean[:5], "source": "llm"}
        print("[%d/%d] %s -> %d 个干扰项" % (i, len(todo), cid, len(clean)))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
