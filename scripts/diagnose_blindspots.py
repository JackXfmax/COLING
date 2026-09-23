# 语义级盲区诊断：把每次预测的「字母」还原回「它到底选了哪个语义选项」。
#
# 原理：run_pilot 的置换是确定性的（random.Random(item_id) + 循环右移 shift），
#       因此可以离线重建每个 shift 下的选项顺序，把预测的字母映射回语义选项 key。
#       再检查：模型的错误是集中在同一个语义选项（=> 干扰项有诱导性 / 命题缺陷），
#       还是分散在各选项（=> 模型真的区分不了 / 知识缺失）。
#
# 自校验：用重建结果重算 comp_perms，必须与文件中存储的值完全一致。
#
# 用法: python scripts/diagnose_blindspots.py [--verify-only]
import os, sys, json, random, itertools
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LABELS = "ABCDEFG"

MODELS = [
    ("pilot_qwen-max.jsonl", "qwen-max"),
    ("pilot_qwen-plus.jsonl", "qwen-plus"),
    ("pilot_qwen-turbo.jsonl", "qwen-turbo"),
    ("pilot_qwen3-max.jsonl", "qwen3-max"),
    ("pilot_gpt-4o.jsonl", "gpt-4o"),
    ("pilot_claude-sonnet-4-6.jsonl", "claude"),
    ("pilot_gemini-2.5-flash.jsonl", "gemini"),
    ("pilot_deepseek-v3.1.jsonl", "deepseek-v3.1"),
    ("pilot_deepseek-v4-pro.jsonl", "ds-v4pro"),
    ("pilot_Qwen2.5-7B-Instruct.jsonl", "Qwen2.5-7B"),
    ("pilot_Llama-3.1-8B-Instruct.jsonl", "Llama-3.1-8B"),
]
SMALL = {"Qwen2.5-7B", "Llama-3.1-8B"}
# ds-v4pro 的历史数据是分块跑的，当时存在 run_pilot 的 --limit 截断 bug
# （prepare_orders 的配额基于被截断的题目数），其选项排列与其余模型不同，
# 无法做语义归因。分数本身仍然有效（内部已去偏），但语义映射不可用。
# 该 bug 已于 2026-09-20 修复：prepare_orders 改为始终基于全量题目。
NO_SEMANTIC = {"ds-v4pro"}


def labels_for(n):
    return list(LABELS[:n])


def prepare_orders(items):
    """复刻 run_pilot.prepare_orders 的确定性逻辑。"""
    counts = Counter()
    orders = {}
    for it in items:
        keys = sorted(it["comp_task"]["options"].keys())
        labels = labels_for(len(keys))
        gold_key = it["comp_task"]["answer"]
        quota = -(-len(items) // len(keys))
        perms = list(itertools.permutations(keys))
        rng = random.Random(it["id"])
        cand = perms[:]
        rng.shuffle(cand)
        chosen = None
        for o in cand:
            g = labels[list(o).index(gold_key)]
            if counts[g] < quota:
                chosen = o
                break
        if chosen is None:
            chosen = cand[0]
        g = labels[list(chosen).index(gold_key)]
        counts[g] += 1
        orders[it["id"]] = (list(chosen), g)
    return orders


def order_at(base, shift, n):
    k = shift % n
    if k == 0:
        return list(base)
    return list(base[-k:]) + list(base[:-k])


def load(fn):
    p = os.path.join(ROOT, "results", fn)
    if not os.path.isfile(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def init_context():
    """加载题目并重建订单字典，返回 (items, orders, gold_key, opt_text, key_len)。"""
    items = [json.loads(l) for l in open(os.path.join(ROOT, "data", "pilot.jsonl"), encoding="utf-8") if l.strip()]
    orders = prepare_orders(items)
    gold_key = {it["id"]: it["comp_task"]["answer"] for it in items}
    opt_text = {it["id"]: dict(it["comp_task"]["options"]) for it in items}
    key_len = {it["id"]: len(sorted(it["comp_task"]["options"].keys())) for it in items}
    return items, orders, gold_key, opt_text, key_len


def main():
    items, orders, gold_key, opt_text, key_len = init_context()

    # ---------- 自校验 ----------
    print("=" * 74)
    print("自校验：重建 gold 位置并重算 comp_perms（%s 因历史 --limit bug 不适用）"
          % "/".join(sorted(NO_SEMANTIC)))
    print("=" * 74)
    total = mismatch = 0
    for fn, name in MODELS:
        if name in NO_SEMANTIC:
            continue
        rows = load(fn)
        for r in rows:
            base = orders.get(r["id"])
            if not base:
                continue
            keys = sorted(opt_text[r["id"]].keys())
            labels = labels_for(len(keys))
            gk = gold_key[r["id"]]
            preds = r.get("comp_preds") or []
            for k, p in enumerate(preds):
                ok_stored = r["comp_perms"][k]
                if p is None:
                    ok_re = False
                else:
                    ordk = order_at(base[0], k, len(keys))
                    g = labels[ordk.index(gk)]
                    ok_re = (p == g)
                total += 1
                if ok_stored != ok_re:
                    mismatch += 1
    print("  比对 %d 次置换，不一致 %d 次 → %s\n" %
          (total, mismatch, "✅ 重建正确" if mismatch == 0 else "❌ 逻辑有误"))
    if mismatch and "--verify-only" not in sys.argv:
        print("重建不一致，分析终止。")
        return

    # ---------- 语义级错选分析 ----------
    # sem_choice[(model, item_id)] = Counter(语义key)
    sem = defaultdict(Counter)
    for fn, name in MODELS:
        if name in NO_SEMANTIC:
            continue
        for r in load(fn):
            keys = sorted(opt_text[r["id"]].keys())
            labels = labels_for(len(keys))
            for k, p in enumerate(r.get("comp_preds") or []):
                if p is None or p not in labels:
                    continue
                ordk = order_at(orders[r["id"]][0], k, len(keys))
                sem[(name, r["id"])][ordk[labels.index(p)]] += 1

    # 每条目聚合
    print("=" * 74)
    print("语义级错选分析（仅统计确实答对的置换之外的错误预测）")
    print("=" * 74)

    def analyze(iid, tag=""):
        gk = gold_key[iid]
        strong_gold = 0
        strong_total = 0
        wrong_sem = Counter()
        for fn, name in MODELS:
            if name in SMALL or name in NO_SEMANTIC:
                continue
            c = sem.get((name, iid), Counter())
            if not c:
                continue
            strong_total += sum(c.values())
            strong_gold += c.get(gk, 0)
            for k, v in c.items():
                if k != gk:
                    wrong_sem[k] += v
        if strong_total == 0:
            return None
        gold_rate = strong_gold / strong_total
        tw = wrong_sem.most_common(3)
        top_rate = (tw[0][1] / sum(wrong_sem.values())) if wrong_sem else 0
        return dict(iid=iid, gold_rate=gold_rate, top=tw, top_rate=top_rate,
                    n_wrong=sum(wrong_sem.values()))

    # 关注曲目
    focus = ["XHY-008", "XHY-010", "XHY-011"]
    print("\n### 三个稳健失败项（旗舰模型的语义分布）\n")
    for iid in focus:
        r = analyze(iid)
        if not r:
            continue
        print("【%s】gold=%s  旗舰选 gold 的比例 = %.1f%%" % (iid, gold_key[iid], 100 * r["gold_rate"]))
        print("   gold 文本: %s" % opt_text[iid][gold_key[iid]][:60])
        for k, v in r["top"]:
            print("   错选 %s (%d次, 占错误%.0f%%): %s" %
                  (k, v, 100 * v / r["n_wrong"], opt_text[iid][k][:60]))
        print()

    print("\n### 对照组：XHY 中旗舰模型表现良好的条目\n")
    good = []
    for it in items:
        if it["category"] != "xiehouyu":
            continue
        vals = []
        for fn, name in MODELS:
            if name in SMALL or name in NO_SEMANTIC:
                continue
            for r in load(fn):
                if r["id"] == it["id"]:
                    vals.append(r.get("comp_acc", 0))
        if len(vals) >= 5 and sum(vals) / len(vals) >= 0.8:
            good.append(it["id"])
    for iid in good[:4]:
        r = analyze(iid)
        if not r:
            continue
        print("【%s】旗舰选 gold 比例 = %.1f%%  错选集中度 = %.0f%%" %
              (iid, 100 * r["gold_rate"], 100 * r["top_rate"]))
    print()

    # ---------- 判定表 ----------
    print("=" * 74)
    print("假说判定")
    print("=" * 74)
    print("判定规则：")
    print("  · 错选集中度 ≥50% 且集中在同一语义选项  → 支持【干扰项诱导性/命题缺陷】")
    print("  · 错选集中度 <35%（近似均匀分散）       → 支持【模型真区分不了/知识缺失】\n")
    for iid in focus:
        r = analyze(iid)
        if not r:
            continue
        verdict = ("支持【干扰项诱导性】" if r["top_rate"] >= 0.5
                   else "支持【模型无法区分】" if r["top_rate"] < 0.35
                   else "居中，证据不足")
        print("  %s: gold率=%.1f%%  错选集中度=%.1f%%  → %s" %
              (iid, 100 * r["gold_rate"], 100 * r["top_rate"], verdict))

    # 小模型对照
    print("\n### 小模型在同一批题目上的语义选择（解释反向规模梯度）\n")
    for iid in focus:
        line = ["  %s:" % iid]
        for fn, name in MODELS:
            if name not in SMALL:
                continue
            c = sem.get((name, iid), Counter())
            tot = sum(c.values())
            if not tot:
                line.append("%s=无数据" % name)
                continue
            gr = c.get(gold_key[iid], 0) / tot
            line.append("%s 选gold=%.0f%%" % (name, 100 * gr))
        print("  ".join(line))


if __name__ == "__main__":
    main()
