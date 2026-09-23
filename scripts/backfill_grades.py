# 一次性回填：把 candidates.md 中各条目的「等级」写回 pilot_*.md 的对应块。
# 原因：早期 80 条 pilot 块没有 等级 字段，source_gate 会把全部既有条目误判为「缺失」。
#       本脚本按「主键文本」对齐回填（主键: XHY上句 / AID成语 / NY农谚 / YY原句）。
# 用法: python scripts/backfill_grades.py
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CAND = os.path.join(DATA, "candidates.md")

PUNCT = r'[\s，。、；;：:！？!?\.,"\'`「」『』《》〈〉（）()\[\]【】—\-_～~/\u3000]'

KEY_FIELD = ("上句", "成语", "农谚", "原句")
SRC_FIELD = ("来源", "出处")


def norm_key(s):
    s = s or ""
    s = s.replace("**", "")
    s = re.sub(r"〔[^〕]*〕", "", s)        # 去 〔新增…〕
    s = re.sub(r"（[^）]*）", "", s)        # 去 （亦作…）
    s = re.sub(PUNCT, "", s)               # 去全部标点/空格
    return s.strip()


def parse_candidates():
    text = open(CAND, encoding="utf-8").read()
    lines = text.splitlines()
    sec = None
    key_col, grade_col = 1, 5
    mp = {}
    for ln in lines:
        if ln.startswith("## 一"):
            sec, key_col, grade_col = "xhy", 1, 5
        elif ln.startswith("## 二"):
            sec = "yy_split"
        elif ln.startswith("### 子类 A"):
            sec, key_col, grade_col = "yyA", 1, 5
        elif ln.startswith("### 子类 B"):
            sec, key_col, grade_col = "yyB", 1, 5
        elif ln.startswith("## 三"):
            sec, key_col, grade_col = "aid", 1, 4
        elif ln.startswith("## 四"):
            sec, key_col, grade_col = "ny", 1, 4
        if sec is None or not ln.strip().startswith("|"):
            continue
        if re.match(r"^\|\s*-", ln):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) <= grade_col or not re.match(r"^\d+$", cells[0]):
            continue
        if sec == "yyA":
            continue
        k, g = norm_key(cells[key_col]), cells[grade_col].strip()
        if k and g:
            mp[k] = g
    return mp


def match_grade(pilot_key, mp):
    pk = norm_key(pilot_key)
    if not pk:
        return None
    if pk in mp:
        return mp[pk]
    for k, g in mp.items():
        if pk in k or k in pk:
            return g
    return None


def backfill(fname, mp):
    path = os.path.join(DATA, fname)
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    out, n_added, n_miss = [], 0, 0
    pending_key = None
    for ln in lines:
        st = ln.rstrip("\n")
        m = re.match(r"^\s*(" + "|".join(KEY_FIELD) + r")\s*[:：]\s*(.*)$", st)
        if m:
            pending_key = m.group(2).strip()
        if any(st.startswith(f + ":") or st.startswith(f + "：") for f in SRC_FIELD) and pending_key is not None:
            g = match_grade(pending_key, mp)
            if g:
                out.append("等级: %s\n" % g)   # 插在 来源/出处 之后
                n_added += 1
            else:
                n_miss += 1
            pending_key = None
        out.append(ln)
    # 去重：删除因历史原因可能出现的连续重复 等级 行
    final, i = [], 0
    while i < len(out):
        line = out[i]
        if line.rstrip("\n").startswith("等级:") and final and final[-1].rstrip("\n").startswith("等级:"):
            i += 1
            continue
        final.append(line)
        i += 1
    open(path, "w", encoding="utf-8").writelines(final)
    print("%-14s 插入等级 %2d 条, 未匹配 %2d 条" % (fname, n_added, n_miss))


def main():
    mp = parse_candidates()
    print("candidates 等级表大小: %d" % len(mp))
    backfill("pilot_xhy.md", mp)
    backfill("pilot_aid.md", mp)
    backfill("pilot_ny.md", mp)
    backfill("pilot_yy.md", mp)


if __name__ == "__main__":
    main()
