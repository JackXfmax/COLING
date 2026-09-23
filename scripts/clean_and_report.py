# 剔除被 429/402 污染的行，只保留"每次置换都真实跑出来"的数据，并重算报告。
# 判脏标准：任一响应为 [ERROR]，或 comp_preds 里出现 None。
# 用法: python scripts/clean_and_report.py <file>
import os, sys, json

os.environ.setdefault("PILOT_PERMS", "6")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_pilot


def is_clean(r):
    for k in ["comp_resp", "mem_resp", "mem1_resp", "mem2_resp"]:
        v = r.get(k)
        if v is None:
            continue
        if str(v).startswith("[ERROR]"):
            return False
    preds = r.get("comp_preds") or []
    if not preds or any(p is None for p in preds):
        return False
    return True


def main():
    fn = sys.argv[1]
    path = fn if os.path.isabs(fn) else os.path.join(ROOT, "results", fn)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    clean = [r for r in rows if is_clean(r)]
    dropped = [r for r in rows if not is_clean(r)]

    print("FILE :", os.path.basename(path))
    print("total=%d  clean=%d  dropped=%d" % (len(rows), len(clean), len(dropped)))
    if dropped:
        print("dropped ids:", ", ".join(sorted(r["id"] for r in dropped)))

    with open(path, "w", encoding="utf-8") as f:
        for r in clean:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("(已剔除污染行，文件只保留干净数据，便于充值后续跑)")

    if clean:
        print("\n===== 干净子集报告 =====")
        run_pilot.report(clean, os.path.basename(path).replace("pilot_", "").replace(".jsonl", ""))


if __name__ == "__main__":
    main()
