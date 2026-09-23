# 按类别诊断结果文件：统计 ERROR / 空响应 / 全 None 预测，并抽样打印原始响应。
# 用法: python scripts/diag_category.py <file> [类别前缀, 如 NY]
import json, sys, os
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    fn = sys.argv[1]
    pref = sys.argv[2] if len(sys.argv) > 2 else None
    path = fn if os.path.isabs(fn) else os.path.join(ROOT, "results", fn)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if pref:
        rows = [r for r in rows if r["id"].upper().startswith(pref.upper())]
    print("FILE:", os.path.basename(path), "| rows in scope:", len(rows))

    err = [r for r in rows if str(r.get("comp_resp", "")).startswith("[ERROR]")]
    empty = [r for r in rows if not str(r.get("comp_resp", "")).strip()]
    allnone = [r for r in rows if all(p is None for p in (r.get("comp_preds") or []))]
    print("ERROR rows:", len(err), "| empty rows:", len(empty), "| all-None preds:", len(allnone))
    if err:
        print("\n--- ALL ERROR ids (%d) ---" % len(err))
        print(" ", ", ".join(sorted(r["id"] for r in err)))
        print("--- sample ERROR ---")
        for r in err[:3]:
            print(" ", r["id"], "|", repr(r.get("comp_resp", ""))[:160])
    print("\n--- per-item comp_acc ---")
    accs = []
    for r in sorted(rows, key=lambda x: x["id"]):
        accs.append(r.get("comp_acc"))
        print("  %-10s acc=%.3f  preds=%s" % (
            r["id"], r.get("comp_acc", 0), r.get("comp_preds")))
    if accs:
        print("\nmean comp_acc = %.3f" % (sum(accs) / len(accs)))
    print("\n--- sample comp_resp (first 3) ---")
    for r in rows[:3]:
        print(" ", r["id"], "|", repr(r.get("comp_resp", ""))[:200])


if __name__ == "__main__":
    main()
