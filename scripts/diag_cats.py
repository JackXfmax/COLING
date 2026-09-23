import os, json, glob
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

for fn in sorted(glob.glob(os.path.join(ROOT, "results", "pilot_*.jsonl"))):
    rows = [json.loads(l) for l in open(fn, encoding="utf-8") if l.strip()]
    by = defaultdict(list)
    for r in rows:
        by[r.get("category")].append(r)
    base = os.path.basename(fn)
    print("=" * 60)
    print(base, "| total rows =", len(rows))
    for cat, rs in sorted(by.items(), key=lambda x: str(x[0])):
        # 分类别统计：多少行 preds 完整 / 含 None / ERROR
        err = sum(1 for r in rs if (r.get("comp_resp", "") or "").startswith("[ERROR]"))
        nonone = sum(1 for r in rs if any(p is None for p in (r.get("comp_preds") or [])))
        empty = sum(1 for r in rs if not (r.get("comp_preds") or []))
        nok = sum(1 for r in rs if (r.get("comp_preds") or []) and
                  all(p is not None for p in r["comp_preds"]) and
                  not (r.get("comp_resp", "") or "").startswith("[ERROR]"))
        cavg = (sum(r.get("comp_acc", 0) for r in rs) / len(rs)) if rs else 0
        print("  %-22s n=%3d  clean=%3d  err=%3d  hasNone=%3d  emptyPreds=%3d  mean_comp_acc=%.3f"
              % (str(cat), len(rs), nok, err, nonone, empty, cavg))
