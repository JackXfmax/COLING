# 把 4 个 pilot_*.md 解析成 pilot.jsonl（一次性工具，不追求优雅）
# 用法: python build_pilot.py
import json, re, os, math, random
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

FILES = [
    ("pilot_xhy.md", "xiehouyu", "fixed_form_completion"),
    ("pilot_yy.md", "phonetic_play", "hidden_meaning"),
    ("pilot_aid.md", "allusion_idiom", "idiom_form_recall"),
    ("pilot_ny.md", "agrarian_proverb", "fixed_form_completion"),
]

PUNCT = r'[\s，。、；;：:！？!?\.\,\"\'`「」『』《》〈〉（）()\[\]【】—\-_～~]'


def norm(s):
    return re.sub(PUNCT, "", s or "")


# YY 重设 comp 用：把 22 个细粒度「类型」（含区域民歌子类，如 吴歌/白茆/客家…双关）
# 归并到 3 个规范谜格/修辞手法。原因：① 区域流派名并非修辞格，原样当选项会让任务
# 退化为"认区域标签"；② 多个吴歌/双关变体是近义字符串，互为噪声干扰。归并后 comp=
# 识别修辞机制（谐音双关/离合拆字/隐语藏词），与 mem=回忆谜底 形成干净的记忆/理解分层。
def canon_yy_genre(raw):
    r = (raw or "").strip()
    if "离合" in r:
        return "离合拆字"
    if "隐语" in r or "隐喻" in r or "物谜" in r or "风人体" in r:
        return "隐语藏词"
    if "谐音" in r or "双关" in r:
        return "谐音双关"
    return r or "谐音双关"


# YY comp 选项文本：给三谜格加「辨识性定义」，降低模型把标签当空壳猜的概率。
# 缘起（第二关预跑 r1，n=150）：YY 71 条过强，其中 24 次误选「离合拆字」、
# 44 次误选 decoy「会意合成（会意）」。后者是主因：「会意」本是灯谜标准体裁之一，
# 对多数隐语都成立 = 属"几乎总对"的伪选项，而非"错但像对"的合格 foil，必须换掉。
# 边界：这里只改「选项表述 / 干扰项设计」，绝不改 gold 答案——
# 不是把数据改成模型喜欢的样子，而是修掉一个不合格的干扰项 + 消除标签歧义。
GENRE_DESC = {
    "谐音双关": "谐音双关（借同音或近音字表达另一义，如「丝」谐「思」）",
    "离合拆字": "离合拆字（拆并汉字部件组成新字，如「色丝」合为「绝」）",
    "隐语藏词": "隐语藏词（藏去词句、凭上下文会意得出所藏之词）",
}


def parse_blocks(path):
    blocks, cur = [], {}
    with open(path, encoding="utf-8") as f:
        for ln in f:
            s = ln.rstrip("\n")
            if not s.strip():
                if cur:
                    blocks.append(cur)
                    cur = {}
                continue
            if s.startswith("#") or s.startswith(">"):
                continue
            if s.startswith(" "):  # 选项行
                m = re.match(r"\s*([A-D])[.．、]\s*(.*)", s)
                if m:
                    cur.setdefault("_options", {})[m.group(1)] = m.group(2).strip()
                continue
            idx = next((i for i, ch in enumerate(s) if ch in ":："), None)
            if idx is None:
                continue
            cur[s[:idx].strip()] = s[idx + 1:].strip()
    if cur:
        blocks.append(cur)
    return blocks


def make_accept(answer, original=""):
    """生成可接受的答案变体，主要处理 X（Y） 谐音写法与「亦作」。"""
    out = {answer}
    out.add(re.sub(r"（[^）]*）", "", answer))                       # 去括号: 坐了大茬了
    out.add(re.sub(r"([^\s（）])（([^）]+)）", r"\2", answer))         # 换括号: 错了大差了
    m = re.search(r"（([^）]+)）", answer)
    if m:
        out.add(m.group(1))                                        # 括号内容: 陈枣 / 句 / 风
    out.add(answer.split("（")[0])
    m = re.search(r"（亦作(.+?)）", original or "")                   # 亦作噬脐莫及
    if m:
        out.add(m.group(1))
    out = {norm(x) for x in out if norm(x)}
    if any(len(x) >= 2 for x in out):                              # 有长别名时丢掉单字别名，防误判
        out = {x for x in out if len(x) >= 2}
    return sorted(out)


def grams(s, n=1):
    return set(s[i:i + n] for i in range(len(s) - n + 1)) or {s}


def sim(a, b):
    """字面相似度 = 一元组/二元组 Jaccard 各半。"""
    sa = 0.5 * (len(grams(a, 1) & grams(b, 1)) / max(1, len(grams(a, 1) | grams(b, 1))))
    sb = 0.5 * (len(grams(a, 2) & grams(b, 2)) / max(1, len(grams(a, 2) | grams(b, 2))))
    return sa + sb


def sim_key(it):
    """成语按词形挑干扰项（形近成语最易混，如 噬脐何及 / 及瓜而代）；其余按释义挑。"""
    return it["original"] if it["category"] == "allusion_idiom" else it["_b_raw"]


# ---------- comp 去泄露 + hard negative 相关工具 ----------
# 剥掉 md 选项里残留的标注（运行时 LEAK 正则也会再剥一次，这里先清干净存进 jsonl）
_ANNOT = re.compile(r"（(?:正确|字面义?|高频|近义)[^）]*）")


def clean_opt(s):
    return _ANNOT.sub("", s or "").strip()


def char_bigram(s):
    """字符二元组集合，用于中文语义近邻判断（无 embedding 依赖，离线可用）。"""
    s = norm(s)
    if len(s) <= 1:
        return Counter([s]) if s else Counter()
    return Counter(s[i:i + 2] for i in range(len(s) - 1))


def cos(a, b):
    A, B = char_bigram(a), char_bigram(b)
    keys = set(A) | set(B)
    dot = sum(A[k] * B[k] for k in keys)
    na = math.sqrt(sum(v * v for v in A.values()))
    nb = math.sqrt(sum(v * v for v in B.values()))
    return dot / (na * nb) if na and nb else 0.0



def build_comp_options(items):
    """comp 任务 v8 重写：去题干泄露 + 同语义场 hard negative。

    旧版两大缺陷（导致 qwen-max comp 97.5%、mem_only=0、GapB 虚高）：
      1) 题干泄露答案：XHY 把「上句——下句」整句给出（下句即答案）；YY 在题干直接写出谜底。
         模型读题干即拿到答案，comp 退化成"复述题干"。
      2) 干扰项过弱：拿同类别**任意**其他条目当干扰项，跨条目语义场完全不搭
         （"家中空无一物" vs "后悔来不及" vs "女子闲雅脱俗"），强模型靠语义排除法秒选。

    新版修复：
      a) 题干去泄露：XHY 只给上句（逼模型从隐喻推断含义）；YY 不写谜底（只给谜面问手法）。
         AID/NY 题干命名形式本身（成语/农谚）但不给含义——命名形式是理解对象，不算泄露答案。
      b) hard negative：干扰项取同类别里与 gold 语义最近的近邻（char-bigram 余弦降序），
         使选项落在同一语义场、只差细微 nuance，强模型必须真正理解才能区分。
         跳过 sim>0.85 的近义项以免出现不可解的同义干扰。
      选项数由 PILOT_N_OPT 控制（默认 6），把随机基线从 25% 压到 17%。
    """
    n_opt = int(os.environ.get("PILOT_N_OPT", "6"))
    letters = ["A", "B", "C", "D", "E", "F", "G"]
    for it in items:
        cat = it["category"]
        gold = it["_b_raw"]                       # 正确选项文本（也是相似度键）
        original = it["original"]

        # ---- YY 重设（用户决策）：comp 改为"谜格/修辞手法识别" ----
        # 旧版 YY comp 正确项=谐音解谜文本，天然包含答案字（gold≡含义），构成字面捷径。
        # 重设后 gold=正确谜格，干扰项=其它谜格+干扰项，题干问"用了哪种修辞格"，
        # 既消除答案字泄露，又让 comp=理解修辞机制、与 mem=回忆谜底 形成干净的记忆/理解分层。
        if cat == "phonetic_play":
            genre = canon_yy_genre(it.get("genre"))          # 规范谜格：谐音双关/离合拆字/隐语藏词
            gopt = GENRE_DESC.get(genre, genre)              # 选项文本（带辨识性定义）
            gp, seen = [], set()
            for x in items:
                if x["category"] == "phonetic_play":
                    g = canon_yy_genre(x.get("genre"))
                    if g and g not in seen:
                        seen.add(g); gp.append(GENRE_DESC.get(g, g))
            # decoy 换掉「会意合成（会意）」：它是灯谜标准体裁之一、对多数隐语成立，
            # 属"几乎总对"的伪选项（预跑中被选 44 次）；改为「比喻象征」——
            # 谜语（尤其字谜/谐音/藏词）少用比喻，是边界清晰的错误选项。
            decoys = ["字面直解（仅按字面的意思理解）", "无法确定", "比喻象征（用他物打比方）"]
            cand = gp + decoys
            rng_yy = random.Random(it["id"] + "_yygenre")
            others = [c for c in cand if c != gopt]
            rng_yy.shuffle(others)
            vals = (others[: n_opt - 1] + [gopt])
            rng_yy.shuffle(vals)
            vals = list(dict.fromkeys(vals))[:n_opt]
            keys = letters[:len(vals)]
            gk = [k for k, v in zip(keys, vals) if v == gopt] or [keys[0]]
            it["comp_task"] = {
                "prompt": "隐语/字谜「%s」。它主要运用了下列哪种修辞手法（谜格）？" % original,
                "options": dict(zip(keys, vals)),
                "answer": gk[0],
            }
            it["comp_distractors"] = {"hn": vals, "hn_sim": [0.0] * len(vals),
                                     "n_options": len(vals), "gold_pos": len(vals) - 1}
            continue

        # LLM 撰写的近邻 hard negative（gen_comp_hn.py 生成）；缺失则回退自动相似度
        hn_path = os.path.join(DATA, "comp_hn.json")
        hn_map = {}
        if os.path.exists(hn_path):
            try:
                hn_map = json.load(open(hn_path, encoding="utf-8"))
            except Exception:
                hn_map = {}

        # ---- a) 题干（去泄露）----
        if cat == "xiehouyu":
            up = original.split("——")[0] if "——" in original else original
            stem = "歇后语上半句：「%s——？」。\n下列哪个情境最符合它想表达的意思？" % up
        elif cat == "phonetic_play":
            stem = "谜面：「%s」。\n下列哪一个最符合这句隐语/字谜想要表达的意指或解谜思路？" % original
        elif cat == "allusion_idiom":
            stem = "成语「%s」的意思最接近下列哪一项？" % original
        else:  # agrarian_proverb
            stem = "农谚「%s」所揭示的道理，最接近下列哪一项？" % original

        # ---- b) hard negative：优先 authored > LLM(comp_hn.json) > 自动相似度 ----
        hn = []
        # (1) 人工撰写的干扰项（扩量时离线产出，不依赖 API；见 data/pilot_*.md 的 comp干扰 字段）
        auth = it.get("comp_hn_auth") or []
        if cat in ("xiehouyu", "agrarian_proverb"):
            for h in auth:
                if len(hn) >= n_opt - 1:
                    break
                if h and h not in hn and h != gold:
                    hn.append(h)
        # (2) LLM 撰写的语义近邻（gen_comp_hn.py 生成）
        extern = (hn_map.get(it["id"], {}) or {}).get("hn", [])
        if len(hn) < n_opt - 1:
            for h in extern:
                if len(hn) >= n_opt - 1:
                    break
                if h and h not in hn and h != gold:
                    hn.append(h)
        # (3) 回退：同类别语义近邻（自动字符相似度）
        if len(hn) < n_opt - 1:
            pool = [x for x in items if x["category"] == cat and x["id"] != it["id"]]
            scored = sorted(pool, key=lambda x: -cos(gold, x["_b_raw"]))
            for x in scored:
                if len(hn) >= n_opt - 1:
                    break
                s = cos(gold, x["_b_raw"])
                if s > 0.85:                      # 近乎同义，跳过以免不可解
                    continue
                if x["_b_raw"] not in hn:
                    hn.append(x["_b_raw"])

        # ---- c) 随机化 gold 与干扰项的相对位置（修复 §2.2：hn[0] 系统性最强）----
        pool = list(dict.fromkeys(hn))             # 去重，保持顺序
        rng = random.Random(it["id"] + "_opt")
        rng.shuffle(pool)                          # 干扰项顺序打乱，gold 不再恒在固定槽位
        pos = rng.randrange(len(pool) + 1)
        vals = pool[:pos] + [gold] + pool[pos:]
        # 保证选项值唯一（兜底）
        seen, uniq = {}, []
        for v in vals:
            if v in seen:
                continue
            seen[v] = True
            uniq.append(v)
        vals = uniq
        keys = letters[:len(vals)]
        gold_key = [kk for kk, vv in zip(keys, vals) if vv == gold]
        it["comp_task"] = {
            "prompt": stem,
            "options": dict(zip(keys, vals)),
            "answer": gold_key[0] if gold_key else keys[0],
        }
        it["comp_distractors"] = {
            "hn": pool,
            "hn_sim": [round(cos(gold, h), 3) for h in pool],
            "n_options": len(vals),
            "gold_pos": pos,
        }
    for it in items:
        it.pop("_lit_raw", None)
        it.pop("_b_raw", None)
        it.pop("comp_hn_auth", None)


def build_mem_options(items):
    """mem-L2（形式再认）：同样一道补全题，但改成 N 选一。

    存在的理由：现有 mem 是自由回忆（open-ended，字符串精确匹配），comp 是六选一再认，
    两者不在同一难度尺度上——人类被试上 recall/recognition 也差 40-60 个点。
    直接拿 mem(自由回忆) 和 comp(六选一) 比，80 点的落差里大部分是任务形式造成的，
    不是能力造成的。mem-L2 把 mem 也拉到 N 选一，跟 comp 形式对齐，
    这样 2x2 四象限才是在同一把尺子上量出来的。
    干扰项 = 同类别其他条目的真实答案（形式层面的 hard negative）。
    """
    n_opt = int(os.environ.get("PILOT_N_OPT", "6"))
    letters = ["A", "B", "C", "D", "E", "F", "G"]
    for it in items:
        cat = it["category"]
        gold = it["mem_task"]["answer"]
        k = n_opt - 1

        # 优先用数据里人工写的「语义近义」干扰项。
        # 原因：数据集内循环干扰（拿同类别其他条目的答案当干扰项）会造成语义泄漏——
        # 干扰项与目标释义分属完全不同的语义场，模型读懂释义即可排除全部干扰项，
        # 无需记住词形。典故成语类尤其严重：删除引文后 L2 仍达 100%，GapB 为负。
        # 近义干扰项逼模型真正检索词形，而非做语义排除。
        hn = [x for x in (it.get("mem_hn") or []) if x and norm(x) != norm(gold)]
        hn = list(dict.fromkeys(hn))[:k]
        hn_from = ["custom"] * len(hn)

        # 不足则用数据集内其他条目补齐（回退路径，仍按字面相似度挑最易混的）
        if len(hn) < k:
            pool = [x for x in items if x["category"] == cat and x["id"] != it["id"]]
            pool_sorted = sorted(pool, key=lambda x: -sim(gold, x["mem_task"]["answer"]))
            for x in pool_sorted:
                if len(hn) >= k:
                    break
                cand = x["mem_task"]["answer"]
                if norm(cand) != norm(gold) and cand not in hn:
                    hn.append(cand)
                    hn_from.append(x["id"])

        k = len(hn)
        keys = letters[:k + 1]
        vals = hn[:1] + [gold] + hn[1:]
        it["mem_l2_task"] = {
            "prompt": it["mem_task"]["prompt"],
            "options": dict(zip(keys, vals)),
            "answer": keys[1],
            "hn_from": hn_from,
        }


def build_mem_l1_tasks(items):
    """mem-L1（揭示前一半字符补全）：同一道 mem 自由回忆题，但题干揭示答案的前半段字符。

    修复说明（v6 -> v7）：旧版 L1 用"首字提示"，提示信息量随答案长度剧烈变化——
    单字答案=100%、两字=50%、七字歇后语仅 14%，导致"首字"对长答案（乡土歇后语、
    农谚）几乎零信息量，L1 在该类恒为 0% 是方法学假象而非模型能力。
    新版改为"揭示前 floor(n/2) 字"（单字 n<=1 退化为揭示 0 字 = 等同 L0），
    使每条提示比例稳定在 ~33-50%，跨长度 / 跨类别可比，L0->L1->L2->comp 梯度才有意义。
    """
    for it in items:
        ans = it["mem_task"]["answer"]
        n = len(ans)
        if n <= 1:
            hint = "提示：答案为单字，无前半段可揭示，请直接写出该字。"
            shown = ""
        else:
            reveal = n // 2
            shown = ans[:reveal]
            hint = "提示：答案共 %d 字，已揭示前 %d 字「%s」，请补全其余 %d 字。" % (
                n, reveal, shown, n - reveal)
        it["mem_l1_task"] = {
            "prompt": it["mem_task"]["prompt"] + "\n" + hint,
            "answer": ans,
            "accept": it["mem_task"]["accept"],
        }


def build():
    items = []
    for fname, category, answer_form in FILES:
        for b in parse_blocks(os.path.join(DATA, fname)):
            if "id" not in b:
                continue
            if category == "xiehouyu":
                original = "%s——%s" % (b.get("上句", ""), b.get("下句", ""))
                region, source, meaning = b.get("地区", ""), b.get("来源", ""), b.get("下句", "")
            elif category == "phonetic_play":
                original = b.get("原句", "")
                region, source, meaning = b.get("地区", ""), b.get("来源", ""), b.get("隐藏义", "")
            elif category == "allusion_idiom":
                original = b.get("成语", "")
                region, source, meaning = "", b.get("出处", ""), b.get("今义", "")
            else:
                original = b.get("农谚", "")
                region, source, meaning = b.get("地区", ""), b.get("来源", ""), b.get("隐喻", "")

            opts = b.get("_options", {})
            gold_key = b.get("comp答案", "B")
            gold_raw = opts.get(gold_key, "")
            # 字面义干扰项 = 带「字面义」标注的那个选项（有的题正确项在 A，不能按 A/B 硬取）
            lit_raw = next((v for v in opts.values() if "字面" in v), "")
            if not lit_raw or lit_raw == gold_raw:
                lit_raw = next((v for k, v in opts.items() if k != gold_key), "")
            items.append({
                "_lit_raw": lit_raw,
                # 歇后语：下句本身即含义，问"什么意思"=同义改写，comp 用「情境」出题
                "_b_raw": clean_opt((b.get("情境") if category == "xiehouyu" else "") or gold_raw),
                "id": b["id"],
                "category": category,
                # YY 重设 comp 用：谜格/修辞手法=md 里的「类型」字段（如 离合字谜/吴歌谐音/隐语诗）。
                # 旧版漏填 -> 重设后全部退化成"谐音双关"+空干扰池。这里显式映射过去。
                "genre": b.get("类型", "") if category == "phonetic_play" else "",
                "original": original,
                "answer_form": answer_form,
                "region": region,
                "source": source,
                "target_meaning": meaning,
                "mem_task": {
                    "prompt": b["mem题"],
                    "answer": b["mem答案"],
                    "accept": make_accept(b["mem答案"], original),
                },
                "comp_task": {
                    "prompt": b["comp题"],
                    "options": b.get("_options", {}),
                    "answer": b["comp答案"],
                },
                # 人工撰写的 mem-L2 语义近义干扰项（可选；缺省则回退到数据集内循环干扰）
                "mem_hn": [x.strip() for x in re.split(r"[,，、]", b.get("mem干扰", "")) if x.strip()],
                # 人工撰写的 comp 干扰项（XHY/NY 扩量时离线产出，不依赖 API）
                "comp_hn_auth": [x.strip() for x in re.split(r"[,，、;；]", b.get("comp干扰", "")) if x.strip()],
                "exposure_bin": "TBD",
            })
    return items


if __name__ == "__main__":
    items = build()
    build_comp_options(items)
    build_mem_options(items)
    build_mem_l1_tasks(items)
    out = os.path.join(DATA, "pilot.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print("wrote %d items -> %s" % (len(items), out))
    from collections import Counter
    print(Counter(i["category"] for i in items))
    from collections import Counter as _C
    dist = _C(len(i["comp_task"]["options"]) for i in items)
    print("选项数分布:", dict(dist))
    bad = [i["id"] for i in items if len(set(i["comp_task"]["options"].values())) != len(i["comp_task"]["options"])]
    print("选项有重复的条目:", bad if bad else "无")
