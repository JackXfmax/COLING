# 新 parse_letter 的离线单测：覆盖干净输出 / 显式答案 / 长思维链三类。
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_pilot

CASES = [
    ("C", "C"),                                   # 干净单字母
    ("  B  ", "B"),                               # 带空白
    ("答案：E", "E"),                              # 显式标记
    ("综上所述，故选D。", "D"),                     # 显式标记在句中
    ("答案是 A", "A"),
    # 长思维链（模拟 deepseek-v4-pro）：结论在结尾
    ("这是一段很长的分析。我先看看A选项，它说的是……然后再看B，不太对。"
     "接着C似乎也沾边，但D偏离了。E描述了帮忙改方案对方不领情，非常贴合。"
     "F是代值班被投诉。综合来看，最典型的情境是 E。", "E"),
    # 长思维链 + 显式结尾
    ("前面分析了一大堆A和B的区别，又讨论C与D。"
     "最后权衡之下，答案：F", "F"),
]


def main():
    ok = True
    for text, want in CASES:
        got = run_pilot.parse_letter(text)
        flag = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print("%s  want=%s  got=%s   | %s" % (flag, want, got, text[:40].replace("\n", " ")))
    print("\nALL PASS" if ok else "\nSOME FAILED")


if __name__ == "__main__":
    main()
