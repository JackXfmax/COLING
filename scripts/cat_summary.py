# 按类别汇总 mem / mem-L1 / mem-L2 / comp 正确率与 comp 平均正确率(置换平均)。
# 用法: python scripts/cat_summary.py <file> [更多文件...]
import os, sys, json
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(fn):
    path = fn if os.path.isabs(fn) else os.path.join(ROOT, "results", fn)
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def summarize(rows, tag):
    by = defaultdict(list)
    for r in rows:
        by[r["category"]].append(r)
    print("\n===== %s  (n=%d) =====" % (tag, len(rows)))
    print("%-18s %4s %7s %7s %7s %9s %9s" % ("category", "n", "mem%", "mem-L1%", "mem-L2%", "comp%", "compAvg%"))
    tot = defaultdict(list)
    for c, rs in sorted(by.items()):
        n = len(rs)
        mem = sum(x["mem_correct"] for x in rs)
        m1 = [x for x in rs if x.get("mem1_correct") is not None]
        m2 = [x for x in rs if x.get("mem2_correct") is not None]
        comp = sum(x["comp_correct"] for x in rs)
        cavg = sum(x.get("comp_acc", 0) for x in rs)
        print("%-18s %4d %6.0f%% %6.0f%% %6.0f%% %8.0f%% %8.1f%%" % (
            c, n, 100.0 * mem / n,
            100.0 * sum(x["mem1_correct"] for x in m1) / max(1, len(m1)),
            100.0 * sum(x["mem2_correct"] for x in m2) / max(1, len(m2)),
            100.0 * comp / n, 100.0 * cavg / n))
        tot["all"].append((n, mem, len(m1), sum(x["mem1_correct"] for x in m1),
                           len(m2), sum(x["mem2_correct"] for x in m2), comp, cavg))
    n = sum(t[0] for t in tot["all"])
    mem = sum(t[1] for t in tot["all"])
    m1n = sum(t[2] for t in tot["all"])
    m1c = sum(t[3] for t in tot["all"])
    m2n = sum(t[4] for t in tot["all"])
    m2c = sum(t[5] for t in tot["all"])
    comp = sum(t[6] for t in tot["all"])
    cavg = sum(t[7] for t in tot["all"])
    print("%-18s %4d %6.0f%% %6.0f%% %6.0f%% %8.0f%% %8.1f%%" % (
        "-- ALL --", n, 100.0 * mem / n, 100.0 * m1c / max(1, m1n),
        100.0 * m2c / max(1, m2n), 100.0 * comp / n, 100.0 * cavg / n))


def main():
    for fn in sys.argv[1:]:
        rows = load(fn)
        summarize(rows, os.path.basename(fn).replace("pilot_", "").replace(".jsonl", ""))


if __name__ == "__main__":
    main()
