# 诊断某个模型结果文件的原始响应：看 comp_resp / preds / gold，判断是否为解析问题。
# 用法: python scripts/inspect_resp.py <results下的文件名> [条数]
import json, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    if len(sys.argv) < 2:
        print("usage: inspect_resp.py <file> [n]")
        return
    fn = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    path = fn if os.path.isabs(fn) else os.path.join(ROOT, "results", fn)
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    print("FILE:", path, "| rows:", len(rows))
    for r in rows[:n]:
        print("=" * 70)
        print("ID:", r.get("id"), "| comp_gold:", r.get("comp_gold"),
              "| comp_acc:", r.get("comp_acc"))
        print("comp_preds:", r.get("comp_preds"))
        resp = r.get("comp_resp", "") or ""
        print("--- comp_resp len:", len(resp), "| HEAD 400 ---")
        print(repr(resp)[:400])
        print("--- comp_resp TAIL 600 ---")
        print(repr(resp)[-600:])
        print("--- mem_resp (first 200) ---")
        print(repr(r.get("mem_resp", "") or "")[:200])


if __name__ == "__main__":
    main()
