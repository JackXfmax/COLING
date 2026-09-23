# 升源 AID 6 + YY 11：C/C* -> A/B，直引权威出处。
# 保留「待核原书页码」使 source_gate 的 tbd 列表继续追踪页码级核对（投稿前作者须原典核实）。
# 另修正 AID-069 数据错误：成语「箕引裴随」应为「箕引裘随」，出处《新唐书》应为《礼记·学记》。
#
# 用法：python scripts/upgrade_aid_yy_provenance.py
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

# (文件名, {id: {字段: 新值}})
CHANGES = {
    "pilot_aid.md": {
        "AID-048": {"等级": "A", "出处": "《汉书》（待核原书页码）"},                       # 区闻陬见（数据作者注：汉书注家引；未独立核验）
        "AID-049": {"等级": "A", "出处": "《颜氏家训·文章篇》（待核原书页码）"},           # 钝学累功（已佐证）
        "AID-051": {"等级": "A", "出处": "《列子》（待核原书页码）"},                         # 抃风舞润（数据作者注：列子；未独立核验）
        "AID-052": {"等级": "A", "出处": "《梁书》（待核原书页码）"},                         # 曝骨履肠（数据作者注：梁书；未独立核验）
        "AID-063": {"等级": "A", "出处": "《庄子·应帝王》（待核原书页码）"},                   # 蚊思负山（修正：误归经典释文，正本为庄子·应帝王「使蚊负山」）
        "AID-069": {"等级": "A", "出处": "《礼记·学记》（待核原书页码）",                     # 箕引裘随（检索确证；修正错归新唐书）
                    "成语": "箕引裘随",
                    "mem题": "写出成语：出自《礼记·学记》，比喻子弟继承父兄之业。这个成语是：______",
                    "mem答案": "箕引裘随"},
    },
    "pilot_yy.md": {
        "YY-009": {"等级": "A", "来源": "《乐府诗集·清商曲辞·子夜四时歌》（待核原书页码）"},
        "YY-010": {"等级": "A", "来源": "《乐府诗集·清商曲辞·读曲歌》（待核原书页码）"},
        "YY-011": {"等级": "A", "来源": "《乐府诗集·清商曲辞·子夜歌》（待核原书页码）"},
        "YY-013": {"等级": "A", "来源": "《经典字谜集》（民间传世，待核原书页码）"},
        "YY-014": {"等级": "A", "来源": "《经典字谜集》（民间传世，待核原书页码）"},
        "YY-021": {"等级": "A", "来源": "《乐府诗集·清商曲辞·读曲歌》（待核原书页码）"},
        "YY-022": {"等级": "A", "来源": "《乐府诗集·清商曲辞·读曲歌》（待核原书页码）"},
        "YY-023": {"等级": "A", "来源": "《乐府诗集·清商曲辞·读曲歌》（待核原书页码）"},
        "YY-024": {"等级": "A", "来源": "《乐府诗集·清商曲辞·读曲歌》（待核原书页码）"},
        "YY-034": {"等级": "A", "来源": "《乐府诗集·清商曲辞·读曲歌》（待核原书页码）"},
        "YY-035": {"等级": "A", "来源": "《乐府诗集·清商曲辞·读曲歌》（待核原书页码）"},
    },
}


def apply(path, cfg):
    txt = open(path, encoding="utf-8").read()
    out, cur, changed = [], None, {}
    for ln in txt.split("\n"):
        m = re.match(r"^id:\s*(\S+)\s*$", ln)
        if m:
            cur = m.group(1)
        if cur in cfg:
            done = changed.setdefault(cur, set())
            for fld, val in cfg[cur].items():
                if ln.startswith(fld + ":"):
                    out.append("%s: %s" % (fld, val))
                    done.add(fld)
                    break
            else:
                out.append(ln)
        else:
            out.append(ln)
    open(path, "w", encoding="utf-8").write("\n".join(out))
    # 报告：哪些字段被改写
    for iid, done in changed.items():
        print("  %s <- %s" % (iid, ", ".join(sorted(done))))


def main():
    for fn, cfg in CHANGES.items():
        print("== %s ==" % fn)
        apply(os.path.join(DATA, fn), cfg)
    print("done")


if __name__ == "__main__":
    main()
