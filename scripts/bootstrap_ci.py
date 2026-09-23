# 两层 bootstrap：给主要数字加置信区间。
#
# 层 1（题目层）：对某模型某类别的 N 道题有放回重抽 —— 反映「题目样本」的不确定性，
#                即换了同分布的另一批题，分数会变多少。
# 层 2（置换层）：对抽中的每道题，再重抽其 6 次置换结果 —— 反映 PERMS=6 的测量噪声。
#
# 用法: python scripts/bootstrap_ci.py [B]   # B=重抽次数，默认 2000
import os, sys, json, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CATS = ["xiehouyu", "phonetic_play", "allusion_idiom", "agrarian_proverb"]
SHORT = {"xiehouyu": "XHY", "phonetic_play": "YY",
         "allusion_idiom": "AID", "agrarian_proverb": "NY"}
MODELS = [
    ("pilot_qwen3-max.jsonl", "qwen3-max"),
    ("pilot_deepseek-v4-pro.jsonl", "ds-v4pro"),
    ("pilot_gemini-2.5-flash.jsonl", "gemini"),
    ("pilot_Qwen2.5-7B-Instruct.jsonl", "Qwen2.5-7B"),
    ("pilot_qwen-max.jsonl", "qwen-max"),
    ("pilot_qwen-plus.jsonl", "qwen-plus"),
    ("pilot_deepseek-v3.1.jsonl", "deepseek-v3.1"),
    ("pilot_claude-sonnet-4-6.jsonl", "claude"),
    ("pilot_gpt-4o.jsonl", "gpt-4o"),
    ("pilot_qwen-turbo.jsonl", "qwen-turbo"),
    ("pilot_Llama-3.1-8B-Instruct.jsonl", "Llama-3.1-8B"),
]


def load(fn):
    p = os.path.join(ROOT, "results", fn)
    if not os.path.isfile(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def clean_rows(rows, cat):
    """只保留 6 次置换全部真实跑出的行，返回 [(id, perms)]，perms 为布尔列表。"""
    out = []
    for r in rows:
        if r.get("category") != cat:
            continue
        if (r.get("comp_resp", "") or "").startswith("[ERROR]"):
            continue
        perms = r.get("comp_perms") or []
        preds = r.get("comp_preds") or []
        if not perms or not preds or any(p is None for p in preds):
            continue
        out.append((r["id"], perms))
    return out


def quantile(xs, q):
    xs = sorted(xs)
    i = int(q * (len(xs) - 1))
    return xs[i]


def boot_cell(pairs, rng, B):
    """两层 bootstrap 的均值分布。"""
    n = len(pairs)
    vals = []
    for _ in range(B):
        tot = 0.0
        cnt = 0
        for _ in range(n):
            iid, perms = pairs[rng.randrange(n)]
            # 置换层：重抽 PERMS 次结果
            for _ in range(len(perms)):
                tot += 1.0 if perms[rng.randrange(len(perms))] else 0.0
                cnt += 1
        vals.append(tot / cnt)
    return vals


def main():
    B = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    rng = random.Random(20260920)

    print("两层 bootstrap（题目层 + 置换层），B=%d\n" % B)
    print("%-16s %-5s %10s %18s" % ("模型", "类别", "点估计", "95% CI"))
    print("-" * 56)

    results = {}
    for fn, name in MODELS:
        rows = load(fn)
        if not rows:
            continue
        results[name] = {}
        for c in CATS:
            pairs = clean_rows(rows, c)
            if len(pairs) < 3:
                continue
            point = sum(sum(1 for x in p if x) for _, p in pairs) / sum(len(p) for _, p in pairs)
            vals = boot_cell(pairs, rng, B)
            lo, hi = quantile(vals, 0.025), quantile(vals, 0.975)
            results[name][c] = (point, lo, hi, len(pairs))
            print("%-16s %-5s %9.1f%%  [%5.1f, %5.1f]  n=%d" %
                  (name, SHORT[c], 100 * point, 100 * lo, 100 * hi, len(pairs)))

    # 整体（各类别等权）
    print("\n整体（四类等权）")
    print("-" * 56)
    for name in results:
        if len(results[name]) < 4:
            continue
        pts = [results[name][c][0] for c in CATS if c in results[name]]
        if len(pts) < 4:
            continue
        pt = sum(pts) / len(pts)
        # 粗略：用各类 CI 半宽的合成
        half = [ (results[name][c][2] - results[name][c][1]) / 2 for c in CATS if c in results[name]]
        hw = (sum(h**2 for h in half) ** 0.5) / len(half)
        print("%-16s %9.1f%%  ±%4.1f  → [%5.1f, %5.1f]" %
              (name, 100 * pt, 100 * hw, 100 * (pt - hw), 100 * (pt + hw)))

    # XHY 是全局最难类别：检验是否显著
    print("\n类别难度序检验（跨模型配对，XHY 是否显著低于其它类别）")
    print("-" * 56)
    diffs = []
    for name in results:
        if "xiehouyu" not in results[name]:
            continue
        for c in ["phonetic_play", "allusion_idiom", "agrarian_proverb"]:
            if c in results[name]:
                diffs.append(results[name][c][0] - results[name]["xiehouyu"][0])
    if diffs:
        d = sorted(diffs)
        print("  其它类别 − XHY 的差值：中位数 %.1f pp，范围 [%.1f, %.1f]，正数占比 %.0f%%" %
              (100 * d[len(d) // 2], 100 * d[0], 100 * d[-1],
               100 * sum(1 for x in diffs if x > 0) / len(diffs)))


if __name__ == "__main__":
    main()
