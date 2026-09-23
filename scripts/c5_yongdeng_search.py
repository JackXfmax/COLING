# -*- coding: utf-8 -*-
"""C5 · 永登县志 19 条精确页码检索。
用已下载的永登县志1997版PDF(有文本层)，针对每条歇后语的谜面/谜底检索命中页码。
输出 results/_c5_dl/yongdeng_search.json 供人工核对回填。
"""
import json, re, os
from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "results/_c5_dl/yongdeng_xianzhi_1997.pdf")
PILOT = os.path.join(ROOT, "data/pilot.jsonl")
OUT = os.path.join(ROOT, "results/_c5_dl/yongdeng_search.json")

IDS = [("XHY-%03d" % i) for i in list(range(21, 26)) + list(range(38, 52))]

def extract_mian(prompt):
    # 谜面在「」内，形如 歇后语上半句：「癞蛤蟆跳姜窝子——？」。
    m = re.search(r"[「『](.+?)[」』]", prompt or "")
    return m.group(1) if m else ""

def main():
    d = [json.loads(l) for l in open(PILOT, encoding="utf-8") if l.strip()]
    by_id = {x["id"]: x for x in d}
    reader = PdfReader(PDF)
    n_pages = len(reader.pages)
    print("PDF 页数:", n_pages)
    page_texts = []
    for i, pg in enumerate(reader.pages):
        try:
            txt = pg.extract_text() or ""
        except Exception:
            txt = ""
        page_texts.append(txt)
    results = {}
    for iid in IDS:
        x = by_id.get(iid)
        if not x:
            results[iid] = {"error": "not found in pilot"}
            continue
        ct = x.get("comp_task") or {}
        mt = x.get("mem_task") or {}
        prompt = str(ct.get("prompt", ""))
        mian = extract_mian(prompt)
        accept = mt.get("accept", [])
        # 候选关键词：谜面「」内整句 + 各谜底
        kws = []
        if mian:
            kws.append(mian)
        for a in accept:
            kws.append(a)
        hits = {}  # page -> snippets
        for ki, kw in enumerate(kws):
            if not kw or len(kw) < 2:
                continue
            for pno, txt in enumerate(page_texts, 1):
                if kw in txt:
                    # 取关键词上下文
                    idx = txt.find(kw)
                    snip = txt[max(0, idx-25): idx+len(kw)+25].replace("\n", " ")
                    hits.setdefault(pno, []).append((ki, kw, snip))
        results[iid] = {
            "mian": mian, "accept": accept,
            "hit_pages": sorted(hits.keys()),
            "snips": {str(p): [s for s in v] for p, v in sorted(hits.items())},
        }
        print("%s 谜面=「%s」 谜底=%s -> 命中页 %s" % (iid, mian, accept, sorted(hits.keys())))
    json.dump({"n_pages": n_pages, "results": results}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("已写", OUT)

if __name__ == "__main__":
    main()
