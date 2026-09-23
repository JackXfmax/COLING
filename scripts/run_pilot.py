# 最小可用 pilot 跑分脚本：读 pilot.jsonl -> 发模型 -> 判分 -> 输出 2x2 四象限
# 用法:
#   python run_pilot.py --dry-run                       # 只看 prompt，不请求接口
#   python run_pilot.py --models gpt-4o                 # 真跑
#   python run_pilot.py --models "gpt-4o,Qwen/Qwen2.5-72B-Instruct,meta-llama/Llama-3.1-70B-Instruct"
# 环境变量:
#   PILOT_ENDPOINT  默认 https://api.openai.com/v1   （本地 vLLM 填 http://localhost:8000/v1）
#   PILOT_API_KEY   OpenAI key（本地 vLLM 随便填）
#   PILOT_THREADS   并发数，默认 8

import json, os, re, sys, random, time, argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DATA = os.path.join(ROOT, "data", "pilot.jsonl")
OUT_DIR = os.path.join(ROOT, "results")

PUNCT = r'[\s，。、；;：:！？!?\.\,\"\'`「」『』《》〈〉（）()\[\]【】—\-_～~]'


def norm(s):
    return re.sub(PUNCT, "", s or "")


# ---------- 1. 调模型 ----------

# ---------- 1b. 本地 HF 模型（服务器上有权重、没 API 时用这个） ----------

_HF = {"tok": None, "model": None}


def load_hf(path):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    mem = os.environ.get("PILOT_MAX_MEM", "3GiB,3GiB")
    max_memory = {i: m.strip() for i, m in enumerate(mem.split(",")) if m.strip()}
    max_memory["cpu"] = os.environ.get("PILOT_CPU_MEM", "40GiB")
    print("[hf] loading %s  max_memory=%s" % (path, max_memory), flush=True)
    tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        path,
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        device_map="balanced",
        max_memory=max_memory,
        trust_remote_code=True,
    )
    model.eval()
    _HF["tok"], _HF["model"] = tok, model
    print("[hf] loaded", flush=True)


def call_hf(prompt, max_new_tokens=48):
    import torch
    tok, model = _HF["tok"], _HF["model"]
    msgs = [{"role": "user", "content": prompt}]
    try:
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    except Exception:
        text = prompt
    inputs = tok(text, return_tensors="pt")
    dev = model.device if hasattr(model, "device") else "cuda:0"
    inputs = {k: v.to(dev) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                            pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def call_model(prompt, model, endpoint, api_key, temperature=0.0, max_tokens=None, _depth=0):
    if _HF["model"] is not None:
        return call_hf(prompt)
    if max_tokens is None:
        # 推理型模型（如 deepseek-v4-pro）思维链会吃掉上千 token，默认 1024 会被截断、
        # 导致它说不出最终答案；用 PILOT_MAX_TOKENS 放大预算。
        max_tokens = int(os.environ.get("PILOT_MAX_TOKENS", "1024"))
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
    )
    MAX_RETRY = int(os.environ.get("PILOT_RETRY", "4"))
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
        # 思考型模型（glm-5.2 等）答案可能在 reasoning_content，或 content 被小预算截断
        msg = data["choices"][0]["message"]
        content = msg.get("content")
        if content is None or (isinstance(content, str) and not content.strip()):
            rc = msg.get("reasoning_content")
            if rc and isinstance(rc, str) and rc.strip():
                content = rc
        # MiniMax 等把思考裹在 <think>...</think> 里，剥掉再判分
        if isinstance(content, str):
            content = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", "", content, flags=re.S)
        # 仍是空（如 200 但空体 / 思考被截断且未产出正文）——按瞬时故障重试
        if (content is None or (isinstance(content, str) and not content.strip())) and _depth < MAX_RETRY:
            time.sleep(1.5 * (_depth + 1))
            return call_model(prompt, model, endpoint, api_key, temperature, max_tokens, _depth + 1)
        return content
    except Exception as e:
        # 超时 / 5xx / 连接抖动 都按瞬时故障重试（最多 MAX_RETRY 次）
        if _depth < MAX_RETRY:
            time.sleep(1.5 * (_depth + 1))
            return call_model(prompt, model, endpoint, api_key, temperature, max_tokens, _depth + 1)
        return "[ERROR] %s" % e


# ---------- 2. 判分 ----------

def grade_mem(resp, accepts):
    """mem 判分：长答案用包含匹配，单字答案要求在开头 10 字内出现。"""
    r = norm(resp)
    if not r:
        return False
    head = r[:40]
    for a in accepts:
        if len(a) >= 2 and a in head:
            return True
        if len(a) == 1 and a in head[:10]:
            return True
    return False


def parse_letter(resp):
    """comp 判分：抽取模型回答中的选项编号（字母或数字，取决于 OPT_STYLE）。"""
    r = (resp or "").strip()
    if OPT_STYLE == "digit":
        m = re.search(r"(?<![0-9])([1-9])(?![0-9])", r[:80])
        if m and int(m.group(1)) <= len(DIGITS):
            return m.group(1)
        return None
    # ① 显式答案写法（推理模型常在结尾写"答案：X"/"故选X"），取最后一次
    exp = list(re.finditer(
        r"(?:答案|正确答案|应选|故选|选择|答案是)\s*(?:是|为)?\s*[:：]?\s*([A-G])(?![A-Za-z])", r))
    if exp:
        return exp[-1].group(1)
    # ② 干净短回答：取第一个孤立字母（原行为，兼容 gpt-4o / qwen 等简洁输出）
    if len(r) <= 60:
        m = re.search(r"(?<![A-Za-z])([A-G])(?![A-Za-z])", r[:80])
        return m.group(1) if m else None
    # ③ 长思维链：思维链写在 content 里、结论在结尾，取最后一个孤立字母
    ms = list(re.finditer(r"(?<![A-Za-z])([A-G])(?![A-Za-z])", r))
    return ms[-1].group(1) if ms else None


# ---------- 3. 构造 prompt（去泄漏 + 打乱选项） ----------

LEAK = re.compile(r"（[^）]*(?:正确|字面|高频)[^）]*）")

# 选项编号样式：letter=A/B/C…（默认）；digit=1/2/3…
# 弱模型对字母有位置偏好（实测 Llama-3.1-8B 选 A 占 52.5%），数字编号可缓解。
OPT_STYLE = os.environ.get("PILOT_OPT_STYLE", "letter").strip().lower()
LETTERS = ["A", "B", "C", "D", "E", "F", "G"]
DIGITS = ["1", "2", "3", "4", "5", "6", "7"]


# 每题把选项循环置换 PERMS 次再取多数投票，用于消除模型对固定编号的位置偏好。
# 实测 Llama-3.1-8B 会把 52.5% 的回答压在同一个编号上（换字母/数字都只是换个编号），
# 单次抽样的 comp 分数因此不可信。PERMS=选项数 时每个选项都轮到每个位置一次。
PERMS = int(os.environ.get("PILOT_PERMS", "1"))


def labels_for(n):
    return DIGITS[:n] if OPT_STYLE == "digit" else LETTERS[:n]
_ORDERS = {}   # id -> (打乱后的原始选项键顺序, 金标字母)


def opt_keys(item):
    return sorted(item["comp_task"]["options"].keys())


def prepare_orders(items):
    """按 id 种子打乱选项，并让各金标字母占比均衡，消除位置偏好混淆。
       支持任意选项数（4/5/6…），金标字母配额 = ceil(题目数 / 选项数)。"""
    import itertools
    counts = Counter()
    for it in items:
        keys = opt_keys(it)
        labels = labels_for(len(keys))
        gold_key = it["comp_task"]["answer"]
        quota = -(-len(items) // len(keys))          # ceil
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
        _ORDERS[it["id"]] = (list(chosen), g)


def build_comp(item, shift=0):
    """返回 (prompt, gold_label, shown_options)。标注已剥离，选项顺序已均衡打乱。
       shift>0 时把选项循环右移 shift 位，用于消除模型对固定编号的位置偏好。"""
    opts = item["comp_task"]["options"]
    keys = opt_keys(item)
    clean = {k: LEAK.sub("", opts.get(k, "")).strip() or opts.get(k, "") for k in keys}
    order, _ = _ORDERS.get(item["id"], (keys[:], item["comp_task"]["answer"]))
    order = list(order)
    if shift:
        order = order[-shift:] + order[:-shift]
    gold_key = item["comp_task"]["answer"]
    labels = labels_for(len(keys))
    gold = labels[order.index(gold_key)]
    lines = ["%s. %s" % (labels[i], clean[k]) for i, k in enumerate(order)]
    if OPT_STYLE == "digit":
        tail = "\n请只回答一个数字（%s），不要解释。" % "/".join(labels)
    else:
        tail = "\n请只回答一个字母（%s），不要解释。" % "/".join(labels)
    prompt = item["comp_task"]["prompt"] + "\n" + "\n".join(lines) + tail
    return prompt, gold, lines


def build_mem(item):
    return item["mem_task"]["prompt"] + "\n请只给出答案本身，不要解释。"


def build_mem_l1(item):
    """mem-L1 首字提示版：题干已带首字+字数提示，模型仍需补全其余部分。"""
    t = item.get("mem_l1_task")
    if not t:
        return None
    return t["prompt"] + "\n请只给出答案本身，不要解释。"


# ---- mem-L2：把同一道补全题改成 N 选一，与 comp 形式对齐 ----

_ORDERS_MEM = {}


def prepare_mem_orders(items):
    import itertools
    counts = Counter()
    for it in items:
        t = it.get("mem_l2_task")
        if not t:
            continue
        keys = sorted(t["options"].keys())
        labels = labels_for(len(keys))
        gold_key = t["answer"]
        quota = -(-len(items) // len(keys))
        perms = list(itertools.permutations(keys))
        rng = random.Random(it["id"] + "_mem")
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
        _ORDERS_MEM[it["id"]] = (list(chosen), g)


def build_mem_l2(item):
    """返回 (prompt, gold_label, shown_options)；没有 mem_l2_task 时返回 (None, None, None)。"""
    t = item.get("mem_l2_task")
    if not t:
        return None, None, None
    keys = sorted(t["options"].keys())
    labels = labels_for(len(keys))
    order, gold = _ORDERS_MEM.get(item["id"], (keys[:], t["answer"]))
    lines = ["%s. %s" % (labels[i], t["options"][k]) for i, k in enumerate(order)]
    if OPT_STYLE == "digit":
        tail = "\n请只回答一个数字（%s），不要解释。" % "/".join(labels)
    else:
        tail = "\n请只回答一个字母（%s），不要解释。" % "/".join(labels)
    return t["prompt"] + "\n" + "\n".join(lines) + tail, gold, lines


# ---------- 4. 主流程 ----------

def run_one(item, model, endpoint, api_key):
    mem_prompt = build_mem(item)
    mem_resp = call_model(mem_prompt, model, endpoint, api_key)
    mem_ok = grade_mem(mem_resp, item["mem_task"]["accept"])

    # mem-L1：首字提示版自由回忆（形成 L0→L1→L2→comp 四点梯度）
    mem1_prompt = build_mem_l1(item)
    mem1_resp, mem1_ok = "", None
    if mem1_prompt:
        mem1_resp = call_model(mem1_prompt, model, endpoint, api_key)
        mem1_ok = grade_mem(mem1_resp, item["mem_task"]["accept"])

    # mem-L2：同一道题的 N 选一版本（与 comp 同尺度）
    mem2_prompt, mem2_gold, mem2_shown = build_mem_l2(item)
    mem2_resp, mem2_ok = "", None
    if mem2_prompt:
        mem2_resp = call_model(mem2_prompt, model, endpoint, api_key)
        mem2_ok = (parse_letter(mem2_resp) == mem2_gold)

    # comp：跑 PERMS 次循环置换，取多数投票作为该题的最终判定
    comp_prompt, gold_letter, shown = build_comp(item, shift=0)
    votes, ok_list, resps, preds = [], [], [], []
    for k in range(PERMS):
        p, g, sh = build_comp(item, shift=k) if k else (comp_prompt, gold_letter, shown)
        resp = call_model(p, model, endpoint, api_key)
        pred = parse_letter(resp)
        ok = (pred == g)
        resps.append(resp)
        preds.append(pred)
        ok_list.append(ok)
        votes.append(pred)
    comp_acc = sum(ok_list) / float(PERMS)
    # 判定：PERMS>1 时用"多数置换下答对"（>=0.5）作为该题真会的判据。
    # 不能用多数投票——模型若死盯某个编号，多数投票会把偏好固化成答案。
    # 置换平均正确率才是去偏后的真实能力：真会则每次都对，靠猜则只剩 1/选项数。
    if PERMS > 1:
        comp_ok = (comp_acc >= 0.5)
    else:
        comp_ok = ok_list[0]

    quad = ("both_correct" if mem_ok and comp_ok else
            "mem_only" if mem_ok else
            "comp_only" if comp_ok else
            "both_wrong")
    return {
        "id": item["id"], "model": model, "category": item["category"],
        "mem_prompt": mem_prompt, "mem_resp": mem_resp, "mem_correct": mem_ok,
        "mem1_prompt": mem1_prompt, "mem1_resp": mem1_resp, "mem1_correct": mem1_ok,
        "comp_prompt": comp_prompt, "comp_shown": shown, "comp_gold": gold_letter,
        "comp_resp": resps[0], "comp_pred": preds[0], "comp_correct": comp_ok,
        "comp_acc": comp_acc, "comp_perms": ok_list, "comp_preds": preds,
        "comp_pred_dist": dict(Counter(preds)),
        "mem2_prompt": mem2_prompt, "mem2_resp": mem2_resp,
        "mem2_gold": mem2_gold, "mem2_correct": mem2_ok, "mem2_shown": mem2_shown,
        "quadrant": quad,
        # 用与 comp 同尺度的 mem-L2 再算一次四象限
        "quadrant_l2": ("both_correct" if mem2_ok and comp_ok else
                        "mem_only" if mem2_ok else
                        "comp_only" if comp_ok else
                        "both_wrong") if mem2_prompt else quad,
    }


def report(rows, model):
    n = len(rows)
    if n == 0:
        return {}
    mem = sum(r["mem_correct"] for r in rows)
    comp = sum(r["comp_correct"] for r in rows)
    q = Counter(r["quadrant"] for r in rows)
    sep = q["mem_only"] + q["comp_only"]
    print("\n=== %s  (n=%d) ===" % (model, n))
    print("mem 正确率 : %d/%d = %.1f%%" % (mem, n, 100.0 * mem / n))
    m1 = [r for r in rows if r.get("mem1_correct") is not None]
    if m1:
        print("mem-L1 正确率(半段揭示): %d/%d = %.1f%%" % (
            sum(r["mem1_correct"] for r in m1), len(m1),
            100.0 * sum(r["mem1_correct"] for r in m1) / len(m1)))
    if PERMS > 1:
        mean_acc = sum(r.get("comp_acc", r["comp_correct"]) for r in rows) / n
        # 位置偏好：把所有题目的预测分布合并，看最高频编号占比
        allp = Counter()
        for r in rows:
            allp.update(r.get("comp_pred_dist", {r["comp_pred"]: 1}))
        top = max(allp.values()) if allp else 0
        tot = sum(allp.values()) if allp else 1
        print("comp 正确率(多数投票): %d/%d = %.1f%%" % (comp, n, 100.0 * comp / n))
        print("comp 平均正确率(%d次置换): %.1f%%" % (PERMS, 100.0 * mean_acc))
        print("  编号偏好: 最高频编号占 %.0f%% (均衡应为 %.0f%%)" % (100.0 * top / tot, 100.0 / max(1, len(allp))))
    else:
        print("comp 正确率: %d/%d = %.1f%%" % (comp, n, 100.0 * comp / n))
    m2 = [r for r in rows if r.get("mem2_correct") is not None]
    if m2:
        print("mem-L2 正确率(N选一, 与comp同尺度): %d/%d = %.1f%%"
              % (sum(r["mem2_correct"] for r in m2), len(m2),
                 100.0 * sum(r["mem2_correct"] for r in m2) / len(m2)))
    sep0 = q["mem_only"] + q["comp_only"]
    print("四象限(基于 mem-L0 自由回忆):")
    for k in ["both_correct", "mem_only", "comp_only", "both_wrong"]:
        print("  %-13s %3d  %5.1f%%" % (k, q[k], 100.0 * q[k] / n))
    print("  >> 分离象限(mem_only+comp_only) = %d = %.1f%%" % (sep0, 100.0 * sep0 / n))
    if m2:
        q2 = Counter(r.get("quadrant_l2", r["quadrant"]) for r in m2)
        sep2 = q2["mem_only"] + q2["comp_only"]
        print("四象限(基于 mem-L2 N选一, 与comp同尺度):")
        for k in ["both_correct", "mem_only", "comp_only", "both_wrong"]:
            print("  %-13s %3d  %5.1f%%" % (k, q2[k], 100.0 * q2[k] / len(m2)))
        print("  >> 分离象限(mem_only+comp_only) = %d = %.1f%%" % (sep2, 100.0 * sep2 / len(m2)))
    print("  >> 分离象限(mem_only+comp_only) = %d = %.1f%%" % (sep, 100.0 * sep / n))
    print("分类别:")
    by = defaultdict(list)
    for r in rows:
        by[r["category"]].append(r)
    for c, rs in by.items():
        m = sum(x["mem_correct"] for x in rs)
        m1 = sum(x.get("mem1_correct", False) for x in rs)
        cp = sum(x["comp_correct"] for x in rs)
        print("  %-18s n=%2d  mem %.0f%%  mem-L1 %.0f%%  comp %.0f%%" % (
            c, len(rs), 100.0 * m / len(rs), 100.0 * m1 / len(rs), 100.0 * cp / len(rs)))
    m1_all = sum(r.get("mem1_correct", False) for r in rows)
    return {"model": model, "n": n, "mem": mem / n, "mem1": m1_all / n, "comp": comp / n,
            "both_correct": q["both_correct"], "mem_only": q["mem_only"],
            "comp_only": q["comp_only"], "both_wrong": q["both_wrong"], "sep": sep / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--models", default="")
    ap.add_argument("--backend", default="api", choices=["api", "hf"])
    ap.add_argument("--model-path", default="", help="hf 后端时的本地权重路径")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    items_all = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()]
    # 选项排列必须基于**全量题目**计算：prepare_orders 的均衡配额 = ceil(题目总数/选项数)，
    # 若先 --limit 截断再算配额，分块跑与全量跑会得到不同的选项排列，
    # 导致同一题在不同批次里 gold 落点序列不一致，破坏逐次置换的可比性。
    prepare_orders(items_all)
    prepare_mem_orders(items_all)
    items = items_all[:args.limit] if args.limit else items_all

    endpoint = os.environ.get("PILOT_ENDPOINT", "https://api.openai.com/v1")
    api_key = os.environ.get("PILOT_API_KEY", "")
    threads = int(os.environ.get("PILOT_THREADS", "8"))

    if args.dry_run:
        it = items[0]
        print("--- mem prompt ---\n" + build_mem(it))
        p, g, shown = build_comp(it)
        print("\n--- comp prompt ---\n" + p)
        print("\n[gold=%s] 原始标注答案=%s" % (g, it["comp_task"]["answer"]))
        print("\n--- 第 2 条 comp（验证打乱生效）---")
        p2, g2, _ = build_comp(items[1])
        print(p2)
        print("[gold=%s]" % g2)
        cnt = Counter()
        for x in items:
            _, gg, _ = build_comp(x)
            cnt[gg] += 1
        print("\n金标字母分布:", dict(cnt))
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    if args.backend == "hf":
        if not args.model_path:
            print("hf 后端需要 --model-path")
            return
        load_hf(args.model_path)
        models = [args.models.strip() or os.path.basename(args.model_path.rstrip("/"))]
        threads = 1
    else:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        if not models:
            print("请给 --models，例如 --models gpt-4o")
            return

    summary = []
    for model in models:
        safe = re.sub(r"[^\w\-.]+", "_", model)
        out_path = os.path.join(OUT_DIR, "pilot_%s.jsonl" % safe)
        done = {}
        if os.path.exists(out_path):
            for l in open(out_path, encoding="utf-8"):
                if l.strip():
                    r = json.loads(l)
                    done[r["id"]] = r
            print("[resume] %s 已完成 %d 条" % (model, len(done)))
        todo = [i for i in items if i["id"] not in done]
        print("[run] %s: %d 条待跑" % (model, len(todo)))
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=threads) as ex:
            futs = [ex.submit(run_one, i, model, endpoint, api_key) for i in todo]
            for k, f in enumerate(futs, 1):
                r = f.result()
                done[r["id"]] = r
                if k % 20 == 0:
                    print("  %d/%d  %.0fs" % (k, len(todo), time.time() - t0))
        rows = [done[i["id"]] for i in items]
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        s = report(rows, model)
        s["out"] = out_path
        summary.append(s)

    if len(summary) > 1:
        print("\n########## 汇总 ##########")
        print("%-32s %6s %6s %6s %6s %6s %6s" % ("model", "mem%", "comp%", "both", "memOnly", "compOnly", "sep%"))
        for s in summary:
            print("%-32s %6.1f %6.1f %6d %6d %6d %6.1f" % (
                s["model"], s["mem"] * 100, s["comp"] * 100,
                s["both_correct"], s["mem_only"], s["comp_only"], s["sep"] * 100))
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
