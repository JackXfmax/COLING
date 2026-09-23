import json
from collections import Counter

ROOT = "D:/workbuddy工作目录/2026-09-15-21-31-36/LongTailChineseRhetoric"
items = [json.loads(l) for l in open(ROOT + "/data/pilot.jsonl", encoding="utf-8") if l.strip()]
print("TOTAL", len(items))

cats = Counter(it["category"] for it in items)
print("CATS", dict(cats))

fields = list(items[0].keys())
print("FIELDS", fields)

for f in ("等级", "grade", "level"):
    c = Counter(it.get(f, "<none>") for it in items)
    print("FIELD", f, dict(c))

src = Counter(it.get("source", "<none>") for it in items)
print("SRC_TOP", src.most_common(25))

def canon(r):
    r = str(r or "").strip()
    if "离合" in r:
        return "离合拆字"
    if "隐语" in r or "隐喻" in r or "物谜" in r or "风人体" in r:
        return "隐语藏词"
    if "谐音" in r or "双关" in r:
        return "谐音双关"
    return r or "谐音双关"

yy = [it for it in items if it["category"] == "phonetic_play"]
print("YY_GENRE", dict(Counter(canon(it.get("genre")) for it in yy)))

exp = Counter(it.get("exposure_bin", "<none>") for it in items)
print("EXP", dict(exp))

# 第三关：source 是否含"待核" / C / C* / 今日头条 等未达标标记
bad = [it["id"] for it in items if any(k in (it.get("source", "") or "") for k in ["C*", "待升", "今日头条"])]
print("SUSPECT_SOURCE", bad[:50], "count", len(bad))
