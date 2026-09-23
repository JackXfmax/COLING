# 外推引擎：用「模型主效应 + 类别难度主效应」双因素加性模型补全缺失格，
# 并用 leave-one-out 交叉验证量化外推误差界（无需再调 API，纯计算）。
#
# 模型:  y(m,c) ≈ mu + alpha_m + beta_c
#   alpha_m = 该模型相对全局均值的强/弱偏移（跨类别稳定）
#   beta_c  = 该类别相对全局均值的难/易偏移（跨模型稳定）
# 已观测格用交替最小二乘(ALS)拟合；缺失格用 mu+alpha+beta 预测。
#
# 用法: python scripts/extrapolate.py
import os, sys, json, math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (文件名, 展示名, 家族, 是否强模型)
FILES = [
    ("pilot_qwen-max.jsonl",              "qwen-max",        "Qwen(dashscope)",      True),
    ("pilot_qwen-plus.jsonl",             "qwen-plus",       "Qwen(dashscope)",      False),
    ("pilot_qwen-turbo.jsonl",            "qwen-turbo",      "Qwen(dashscope)",      False),
    ("pilot_qwen3-max.jsonl",             "qwen3-max",       "Qwen(openlux)",        True),
    ("pilot_gpt-4o.jsonl",                "gpt-4o",          "OpenAI",               True),
    ("pilot_claude-sonnet-4-6.jsonl",     "claude-sonnet-4-6","Anthropic",           True),
    ("pilot_gemini-2.5-flash.jsonl",      "gemini-2.5-flash","Google",               True),
    ("pilot_deepseek-v3.1.jsonl",         "deepseek-v3.1",   "DeepSeek(via openlux)",True),
    ("pilot_deepseek-v4-pro.jsonl",       "deepseek-v4-pro", "DeepSeek(官方)",        True),
    ("pilot_Qwen2.5-7B-Instruct.jsonl",   "Qwen2.5-7B",      "Qwen(本地开源)",       False),
    ("pilot_Llama-3.1-8B-Instruct.jsonl", "Llama-3.1-8B",    "Meta(本地开源)",       False),
]

CATS = ["xiehouyu", "phonetic_play", "allusion_idiom", "agrarian_proverb"]
SHORT = {"xiehouyu": "XHY", "phonetic_play": "YY",
         "allusion_idiom": "AID", "agrarian_proverb": "NY"}


def load(fn):
    path = os.path.join(ROOT, "results", fn)
    if not os.path.isfile(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def cell_stats(rows, cat):
    """返回该模型在该类别上「每一次置换都真实跑出」的干净统计。"""
    rs = [r for r in rows if r.get("category") == cat]
    clean = []
    for r in rs:
        preds = r.get("comp_preds") or []
        resp = r.get("comp_resp", "") or ""
        # 剔除任何一次置换失败(含 None)或整条报错的行
        if resp.startswith("[ERROR]"):
            continue
        if len(preds) == 0 or any(p is None for p in preds):
            continue
        clean.append(r)
    n = len(clean)
    if n == 0:
        return None
    comp_avg = sum(r.get("comp_acc", 0.0) for r in clean) / n
    comp = sum(1 for r in clean if r.get("comp_correct")) / n
    mem = sum(1 for r in clean if r.get("mem_correct")) / n
    m2 = [r for r in clean if r.get("mem2_correct") is not None]
    mem2 = (sum(r["mem2_correct"] for r in m2) / len(m2)) if m2 else None
    return dict(n=n, comp_avg=comp_avg, comp=comp, mem=mem, mem2=mem2, total=len(rs))


def fit_additive(Y, obs, models, cats, iters=500):
    mu = sum(Y[k] for k in obs) / len(obs)
    a = {m: 0.0 for m in models}
    b = {c: 0.0 for c in cats}
    for _ in range(iters):
        for m in models:
            ks = [c for c in cats if (m, c) in obs]
            if ks:
                a[m] = sum(Y[(m, c)] - mu - b[c] for c in ks) / len(ks)
        for c in cats:
            ks = [m for m in models if (m, c) in obs]
            if ks:
                b[c] = sum(Y[(m, c)] - mu - a[m] for m in ks) / len(ks)
        ma = sum(a.values()) / len(a)
        mb = sum(b.values()) / len(b)
        for m in models:
            a[m] -= ma
        for c in cats:
            b[c] -= mb
        mu += ma + mb
    return mu, a, b


def predict(mu, a, b, m, c):
    return min(1.0, max(0.0, mu + a[m] + b[c]))


def main():
    data = {}      # (model, cat) -> stats
    meta = {}      # model -> (family, strong)
    for fn, name, fam, strong in FILES:
        rows = load(fn)
        if not rows:
            continue
        meta[name] = (fam, strong)
        for c in CATS:
            st = cell_stats(rows, c)
            if st:
                data[(name, c)] = st

    models = sorted(meta.keys())
    obs = [k for k in data if data[k]["n"] >= 1]

    # ---------- 主拟合 ----------
    Y = {k: data[k]["comp_avg"] for k in obs}
    mu, a, b = fit_additive(Y, obs, models, CATS)
    resid = {k: Y[k] - predict(mu, a, b, k[0], k[1]) for k in obs}
    rmse_fit = math.sqrt(sum(v * v for v in resid.values()) / len(resid))

    # ---------- leave-one-out 交叉验证（量化外推误差界）----------
    errs = []
    for k in obs:
        sub = [x for x in obs if x != k]
        if len(sub) < 5:
            continue
        mu2, a2, b2 = fit_additive({x: Y[x] for x in sub}, sub, models, CATS)
        p = predict(mu2, a2, b2, k[0], k[1])
        errs.append(abs(p - Y[k]))
    errs.sort()
    mae = sum(errs) / len(errs)
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
    p90 = errs[int(0.90 * (len(errs) - 1))]
    mx = errs[-1]

    out = []
    W = out.append
    W("# 跨家族外推分析（实测 + 加性模型补全）\n")
    W("## 方法\n")
    W("对缺失格（deepseek-v4-pro 的 AID/NY）采用**双因素加性模型**：\n")
    W("```\ny(model, category) ≈ mu + alpha_model + beta_category\n```\n")
    W("- `alpha_m`：模型主效应（该模型跨类别稳定强/弱多少）\n")
    W("- `beta_c`：类别主效应（该类别跨模型稳定难/易多少）\n")
    W("- 已观测格用交替最小二乘(ALS)拟合，缺失格用模型预测。\n")
    W("- **误差界由 leave-one-out 交叉验证给出**：逐个挖掉已观测格、用剩余拟合再预测，\n"
      "  统计预测误差。这直接量化了「外推一格能有多不准」。\n")
    W("\n**交叉验证误差界（n=%d 个已观测格）**：MAE=%.1f 个百分点, RMSE=%.1f pp, "
      "90%%分位=%.1f pp, 最大=%.1f pp\n" % (len(errs), 100 * mae, 100 * rmse, 100 * p90, 100 * mx))
    W("\n> 说明：RMSE 是**外推一格**的典型误差量级，不是实测值的误差。实测值本身无此误差。\n")

    W("\n## 主效应分解\n")
    W("| 效应 | 值 (pp，相对全局均值 %.1f%%) |" % (100 * mu))
    W("|---|---|")
    for m in sorted(a, key=lambda x: -a[x]):
        W("| alpha[%s] | %+5.1f |" % (m, 100 * a[m]))
    for c in sorted(b, key=lambda x: -b[x]):
        W("| beta[%s] | %+5.1f |" % (SHORT[c], 100 * b[c]))

    # ---------- 全表 ----------
    W("\n## 全模型 × 类别 comp 均值（%%）\n")
    W("标注：`实测n=xx` 为真实跑出；`外推±RMSE` 为模型补全。\n")
    W("| 模型 | 家族 | " + " | ".join(SHORT[c] for c in CATS) + " | 整体(加权) |")
    W("|---|---|" + "---|" * (len(CATS) + 1))
    overall = {}
    for m in models:
        cells = []
        tot_n, tot_s = 0, 0.0
        for c in CATS:
            if (m, c) in data:
                st = data[(m, c)]
                v = st["comp_avg"]
                cells.append("**%.1f** (n=%d)" % (100 * v, st["n"]))
                tot_n += st["n"]
                tot_s += v * st["n"]
            else:
                p = predict(mu, a, b, m, c)
                cells.append("~%.1f ±%.0f" % (100 * p, 100 * rmse))
                tot_s += p * 20
                tot_n += 20
        overall[m] = tot_s / tot_n if tot_n else 0.0
        W("| %s | %s | %s | **%.1f** |" % (m, meta[m][0], " | ".join(cells), 100 * overall[m]))

    # ---------- v4-pro 专项 ----------
    W("\n## deepseek-v4-pro 外推结果（本次重点）\n")
    W("官方端点余额耗尽，AID 仅 2 条实测、NY 全缺失。外推如下：\n")
    W("| 类别 | 实测 n | 实测值 | 加性模型外推 | 采用值 ± RMSE |")
    W("|---|---|---|---|---|")
    for c in CATS:
        if ("deepseek-v4-pro", c) in data:
            st = data[("deepseek-v4-pro", c)]
            p = predict(mu, a, b, "deepseek-v4-pro", c)
            W("| %s | %d | **%.1f%%** | %.1f%% | **%.1f%%**（实测） |" %
              (SHORT[c], st["n"], 100 * st["comp_avg"], 100 * p, 100 * st["comp_avg"]))
        else:
            p = predict(mu, a, b, "deepseek-v4-pro", c)
            W("| %s | 0 | — | %.1f%% | **%.1f ± %.0f%%**（外推） |" %
              (SHORT[c], 100 * p, 100 * p, 100 * rmse))
    v4_all = overall.get("deepseek-v4-pro", 0.0)
    W("\n**v4-pro 整体 comp 估计：%.1f%%**（XHY/YY 实测 40 条 + AID/NY 外推 40 条）\n" % (100 * v4_all))

    # ---------- 两种外推法交叉检验 ----------
    W("\n## 稳健性检验：另一种外推法（delta-transfer）\n")
    W("不做全局拟合，只用 v4-pro 自身已跑类别相对基准模型的平均差值，迁移到缺失类别：\n")
    ref = "qwen-max"
    ran = [c for c in CATS if ("deepseek-v4-pro", c) in data and (ref, c) in data]
    deltas = [data[("deepseek-v4-pro", c)]["comp_avg"] - data[(ref, c)]["comp_avg"] for c in ran]
    dmean = sum(deltas) / len(deltas)
    W("\n- 基准模型：`%s`\n- 已跑类别 %s 上的平均 delta = %+.1f pp\n" %
      (ref, "/".join(SHORT[c] for c in ran), 100 * dmean))
    W("\n| 类别 | delta-transfer 预测 | 加性模型预测 | 两法差 |")
    W("|---|---|---|---|")
    for c in CATS:
        if (ref, c) not in data:
            continue
        dt = data[(ref, c)]["comp_avg"] + dmean
        am = predict(mu, a, b, "deepseek-v4-pro", c)
        W("| %s | %.1f%% | %.1f%% | %.1f pp |" % (SHORT[c], 100 * dt, 100 * am, 100 * abs(dt - am)))
    W("\n两法一致性越高，外推越可信（差异应小于 CV 的 RMSE）。\n")

    # ---------- 盲区 ----------
    W("\n## 跨家族持续盲区（实测数据，非外推）\n")
    item = defaultdict(dict)
    for fn, name, fam, strong in FILES:
        rows = load(fn)
        for r in rows:
            preds = r.get("comp_preds") or []
            if (r.get("comp_resp", "") or "").startswith("[ERROR]"):
                continue
            if not preds or any(p is None for p in preds):
                continue
            item[r["id"]][name] = r.get("comp_acc", 0.0)
    W("\n列出「在 >=3 个模型上有实测、且平均 comp_acc < 0.5」的条目：\n")
    W("| 条目 | 模型数 | 均值 | 各模型实测 |")
    W("|---|---|---|---|")
    rows_out = []
    for iid, vals in sorted(item.items()):
        if len(vals) >= 3:
            mv = sum(vals.values()) / len(vals)
            if mv < 0.5:
                rows_out.append((mv, iid, vals))
    for mv, iid, vals in sorted(rows_out):
        det = ", ".join("%s:%.0f" % (k, 100 * v) for k, v in sorted(vals.items(), key=lambda x: x[1]))
        W("| %s | %d | **%.1f%%** | %s |" % (iid, len(vals), 100 * mv, det))
    if not rows_out:
        W("| — | — | — | 无 |")

    # ---------- mem 侧 ----------
    W("\n## mem（形式记忆）侧：模型 vs 类别\n")
    W("| 模型 | " + " | ".join(SHORT[c] for c in CATS) + " |")
    W("|---|---|---|---|---|")
    for m in models:
        cells = []
        for c in CATS:
            if (m, c) in data:
                st = data[(m, c)]
                cells.append("%.0f%% (n=%d)" % (100 * st["mem"], st["n"]))
            else:
                cells.append("—")
        W("| %s | %s |" % (m, " | ".join(cells)))

    txt = "\n".join(out)
    path = os.path.join(ROOT, "results", "EXTRAPOLATION.md")
    open(path, "w", encoding="utf-8").write(txt)
    print(txt)
    print("\n>>> written to", path)


if __name__ == "__main__":
    main()
