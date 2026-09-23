# -*- coding: utf-8 -*-
"""C5 · 98 条 source 页码/版本分层回填。
分层原则（诚实优先，绝不编造精确条级页）：
  A 精确页(权威, 从原书目录读到): 永登县志 -> 第733-738页
  B 卷次(权威, 典籍): 乐府诗集 读曲歌=卷46 / 子夜歌·子夜四时歌=卷44
  C 版本级(公开目录只到类级, 无法精确到条): 中国谚语集成·陕西卷
  D 篇名/版本(能确证篇名者填篇名, 冷僻者标待核): 颜氏家训/庄子/礼记 等
用法: python c5_backfill.py [--apply]   (不加 --apply 为 dry-run)
"""
import json, os, sys, shutil, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOT = os.path.join(ROOT, "data/pilot.jsonl")

# source 原文 -> 回填后 source
MAP = {
    "《中国民间文学集成·陕西卷·谚语集成》（陕北歇后语，待核页码）":
        "《中国谚语集成·陕西卷》（中国民间文学集成全国编辑委员会编，北京：中国ISBN中心，2000年，ISBN 9787507601800，815页；陕北谚语/歇后语，条级页码待核原书）",
    "《永登县志》（待核原书页码）":
        "《永登县志》（永登县地方史志编纂委员会编，兰州：甘肃民族出版社，1997年7月第1版，ISBN 7-5421-0459-4，第十九篇·方言·第六节歇后语，第733–738页）",
    "《乐府诗集·清商曲辞·读曲歌》（待核原书页码）":
        "《乐府诗集》卷四十六·清商曲辞·吴声歌曲·读曲歌（宋·郭茂倩编，中华书局1979年点校本）",
    "《经典字谜集》（民间传世，待核原书页码）":
        "《经典字谜集》（民间传世，版本与页码待核）",
    "《乐府诗集·清商曲辞·子夜四时歌》（待核原书页码）":
        "《乐府诗集》卷四十四·清商曲辞·吴声歌曲·子夜四时歌（宋·郭茂倩编，中华书局1979年点校本）",
    "《乐府诗集·清商曲辞·子夜歌》（待核原书页码）":
        "《乐府诗集》卷四十四·清商曲辞·吴声歌曲·子夜歌（宋·郭茂倩编，中华书局1979年点校本）",
    "《汉书》（待核原书页码）":
        "《汉书》（汉·班固撰，中华书局点校本；典故出处具体篇目待核）",
    "《颜氏家训·文章篇》（待核原书页码）":
        "《颜氏家训·文章篇》（北齐·颜之推撰，王利器《颜氏家训集解》，中华书局）",
    "《列子》（待核原书页码）":
        "《列子》（杨伯峻《列子集释》，中华书局；典故出处具体篇目待核）",
    "《梁书》（待核原书页码）":
        "《梁书》（唐·姚思廉撰，中华书局点校本；典故出处具体篇目待核）",
    "《庄子·应帝王》（待核原书页码）":
        "《庄子·应帝王》（郭庆藩《庄子集释》，中华书局）",
    "《礼记·学记》（待核原书页码）":
        "《礼记·学记》（郑玄注、孔颖达疏《礼记正义》，中华书局）",
}

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    apply = "--apply" in sys.argv
    rows = [json.loads(l) for l in open(PILOT, encoding="utf-8") if l.strip()]
    hit = 0
    from collections import Counter
    c = Counter()
    for x in rows:
        s = str(x.get("source", ""))
        if s in MAP:
            c[s] += 1
            if apply:
                x["source"] = MAP[s]
            hit += 1
    print("待核条数:", sum(1 for x in rows if "待核" in str(x.get("source",""))), "| 命中映射:", hit)
    for k, n in c.items():
        print("  %2d  %s" % (n, k[:42]))
    if not apply:
        print("\n[DRY-RUN] 未写文件。加 --apply 执行回填。")
        return
    # 备份原始(仅首次)
    bak = os.path.join(ROOT, "data/pilot.v1.0.jsonl")
    if not os.path.exists(bak):
        shutil.copy2(PILOT, bak)
        print("已备份 ->", bak, "sha256(orig)=", sha256(bak)[:16])
    with open(PILOT, "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    remain = sum(1 for x in rows if "待核" in str(x.get("source","")))
    print("回填完成。新 pilot.jsonl sha256=", sha256(PILOT)[:16])
    print("仍含'待核'字样条数(保留 limitation 标注):", remain)

if __name__ == "__main__":
    main()
