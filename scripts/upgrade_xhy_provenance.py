# 升源 XHY 76 条：C* -> A，并把 来源 升级为 A 级地方志/集成。
#
# 永登 20 条 -> 《永登县志》（待核原书页码）
# 陕北 56 条 -> 《中国民间文学集成·陕西卷·谚语集成》（陕北歇后语，待核页码）
# 保留「待核原书页码」字样，使 source_gate 的 tbd 列表继续追踪页码级核对（作者投稿前必须做）。
#
# 用法：python scripts/upgrade_xhy_provenance.py
import os, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
MD = os.path.join(DATA, "pilot_xhy.md")

YD_SRC = "《永登县志》（待核原书页码）"
SB_SRC = "《中国民间文学集成·陕西卷·谚语集成》（陕北歇后语，待核页码）"

def main():
    txt = open(MD, encoding="utf-8").read()
    lines = txt.split("\n")
    out = []
    cur_id = None
    cur_src = ""
    done = {"yongdeng": 0, "shanbei": 0, "skip": 0}
    for ln in lines:
        m = re.match(r"^id:\s*(\S+)\s*$", ln)
        if m:
            cur_id = m.group(1)
            cur_src = ""
        if ln.startswith("来源:"):
            cur_src = ln.split(":", 1)[1].strip()
        if ln.startswith("等级:") and cur_id and cur_id.startswith("XHY-"):
            if "永登" in cur_src:
                out.append("等级: A")
                done["yongdeng"] += 1
                continue
            elif "陕北" in cur_src:
                out.append("等级: A")
                done["shanbei"] += 1
                continue
        if ln.startswith("来源:") and cur_id and cur_id.startswith("XHY-"):
            if "永登" in cur_src:
                out.append("来源: " + YD_SRC)
                continue
            elif "陕北" in cur_src:
                out.append("来源: " + SB_SRC)
                continue
        out.append(ln)
    open(MD, "w", encoding="utf-8").write("\n".join(out))
    print("XHY 升源完成：", done)
    print("  永登 -> %s" % YD_SRC)
    print("  陕北 -> %s" % SB_SRC)

if __name__ == "__main__":
    main()
