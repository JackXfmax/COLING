#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""B6 · 本地 4-bit 弱模型对齐评测（自包含，复刻 run_mem_layers.py 四层口径）。
在远程 GPU（train conda env）运行：
  /home/xufei/miniconda3/envs/train/bin/python run_b6_local.py \
      --data pilot.jsonl --model /home/xufei/models/Qwen2.5-7B-Instruct \
      --out b6_raw.jsonl [--limit N] [--cats xiehouyu]
四层：mem-L0(自由回忆) / mem-L1(首字提示) / mem-L2(N选一,PERMS=6) / comp(6选一,PERMS=6)
判分：grade_mem / parse_letter / order_at 完全照搬 run_mem_layers.py，保证口径一致。
"""
import os, sys, json, re, random, argparse, itertools, threading, time
from collections import defaultdict, Counter

LABELS = "ABCDEF"
PERMS = 6
PUNCT = r'[\s，。、；;：:！？!?\.\,\"\'`「」『』《》〈〉（）()\[\]【】—\-_～~]'

def norm(s):
    return re.sub(PUNCT, "", s or "")

def parse_letter(text):
    if not text or "[ERROR]" in text:
        return None
    t = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", "", text, flags=re.S)
    m = re.search(r"(?:答案|选|项|应为|正确)\s*[:：]?\s*[*]?\s*([A-F])", t)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-F])\b", t)
    if m:
        return m.group(1)
    return None

def grade_mem(resp, accepts):
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

def labels_for(n):
    return list(LABELS[:n])

def prepare_orders(items, field):
    counts = Counter()
    orders = {}
    for it in items:
        t = it.get(field)
        if not t:
            continue
        keys = sorted(t["options"].keys())
        labels = labels_for(len(keys))
        gold_key = t["answer"]
        quota = -(-len(items) // len(keys))
        perms = list(itertools.permutations(keys))
        rng = random.Random(it["id"] + ("_mem" if field == "mem_l2_task" else "_comp"))
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

def load_model(model_path):
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    import torch
    print("加载模型(4-bit):", model_path, flush=True)
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
                             bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, quantization_config=bnb, device_map="auto",
        torch_dtype=torch.float16, trust_remote_code=True)
    model.eval()
    print("模型加载完成，device_map:", model.hf_device_map if hasattr(model, "hf_device_map") else "n/a", flush=True)
    return tok, model

def gen(tok, model, prompt, max_tokens=64):
    msgs = [{"role": "user", "content": prompt}]
    inp = tok.apply_chat_template(msgs, return_tensors="pt", add_generation_prompt=True)
    import torch
    inp = inp.to(model.device)
    with torch.no_grad():
        out = model.generate(inp, max_new_tokens=max_tokens, do_sample=False,
                             temperature=1.0, top_p=1.0)
    resp = tok.decode(out[0][inp.shape[1]:], skip_special_tokens=True)
    return resp

def mc_eval(tok, model, it, field, orders):
    t = it.get(field)
    base, _ = orders.get(it["id"], (sorted(t["options"].keys()), t["answer"]))
    keys = sorted(t["options"].keys())
    n = len(keys)
    labels = labels_for(n)
    gold_key = t["answer"]
    ok_list = []
    for shift in range(min(PERMS, n)):
        disp = order_at(base, shift, n)
        opts_txt = "\n".join("%s. %s" % (labels[i], t["options"][disp[i]]) for i in range(n))
        prompt = t["prompt"] + "\n" + opts_txt + "\n只输出正确选项字母（A-%s）。" % labels[n - 1]
        resp = gen(tok, model, prompt, max_tokens=8)
        p = parse_letter(resp)
        chosen_key = None
        if p is not None and p in labels:
            chosen_key = disp[labels.index(p)]
        else:
            # 文本回退：弱模型常输出选项原文而非字母，按原文命中判分
            for i in range(n):
                if t["options"][disp[i]] in resp:
                    chosen_key = disp[i]
                    break
        ok_list.append(chosen_key == gold_key)
    acc = sum(ok_list) / float(len(ok_list))
    return acc, (acc >= 0.5)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--model", default="/home/xufei/models/Qwen2.5-7B-Instruct")
    ap.add_argument("--out", default="b6_raw.jsonl")
    ap.add_argument("--cats", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    items = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()]
    if args.cats:
        only = set(c.strip() for c in args.cats.split(",") if c.strip())
        items = [i for i in items if i["category"] in only]
    if args.limit:
        items = items[:args.limit]

    mem_orders = prepare_orders(items, "mem_l2_task")
    comp_orders = prepare_orders(items, "comp_task")

    tok, model = load_model(args.model)

    done = set()
    if os.path.exists(args.out):
        for l in open(args.out, encoding="utf-8"):
            try:
                done.add(json.loads(l)["id"])
            except Exception:
                pass
    items = [i for i in items if i["id"] not in done]

    rawf = open(args.out, "a", encoding="utf-8")
    lock = threading.Lock()
    nd = [0]
    total = len(items)

    def run_one(it):
        iid = it["id"]; cat = it["category"]
        mt = it.get("mem_task") or {}
        l0_resp = gen(tok, model, mt.get("prompt", "") + "\n请只给出答案本身，不要解释。", max_tokens=64)
        l0_ok = grade_mem(l0_resp, mt.get("accept", [])) if mt else None
        l1 = it.get("mem_l1_task"); l1_ok = None
        if l1:
            l1_resp = gen(tok, model, l1["prompt"] + "\n请只给出答案本身，不要解释。", max_tokens=64)
            l1_ok = grade_mem(l1_resp, mt.get("accept", []))
        l2_acc = l2_ok = None
        if it.get("mem_l2_task"):
            l2_acc, l2_ok = mc_eval(tok, model, it, "mem_l2_task", mem_orders)
        comp_acc = comp_ok = None
        if it.get("comp_task"):
            comp_acc, comp_ok = mc_eval(tok, model, it, "comp_task", comp_orders)
        rec = {"id": iid, "category": cat, "l0_ok": l0_ok, "l1_ok": l1_ok,
               "l2_ok": l2_ok, "l2_acc": l2_acc, "comp_ok": comp_ok, "comp_acc": comp_acc}
        with lock:
            rawf.write(json.dumps(rec, ensure_ascii=False) + "\n"); rawf.flush()
            nd[0] += 1
            if nd[0] % 10 == 0:
                print("  ... %d/%d" % (nd[0], total), flush=True)
        return rec

    for it in items:
        run_one(it)
    rawf.close()

    # 聚合
    rows = [json.loads(l) for l in open(args.out, encoding="utf-8") if l.strip()]
    print("\n" + "=" * 70)
    print("B6 本地 4-bit 评测完成，共 %d 条" % len(rows))
    print("=" * 70)
    by = defaultdict(list)
    for r in rows:
        by[r["category"]].append(r)
    print("%-16s %6s %6s %6s %6s %6s" % ("class", "n", "L0%", "L1%", "L2%", "comp%"))
    allr = []
    for c, rs in sorted(by.items()):
        allr += rs
        l0=[x["l0_ok"] for x in rs if x["l0_ok"] is not None]
        l1=[x["l1_ok"] for x in rs if x["l1_ok"] is not None]
        l2=[x["l2_ok"] for x in rs if x["l2_ok"] is not None]
        cp=[x["comp_ok"] for x in rs if x["comp_ok"] is not None]
        print("%-16s %6d %6.1f %6.1f %6.1f %6.1f" % (c, len(rs),
            (100*sum(l0)/len(l0) if l0 else float("nan")),
            (100*sum(l1)/len(l1) if l1 else float("nan")),
            (100*sum(l2)/len(l2) if l2 else float("nan")),
            (100*sum(cp)/len(cp) if cp else float("nan"))))
    l0=[x["l0_ok"] for x in allr if x["l0_ok"] is not None]
    l1=[x["l1_ok"] for x in allr if x["l1_ok"] is not None]
    l2=[x["l2_ok"] for x in allr if x["l2_ok"] is not None]
    cp=[x["comp_ok"] for x in allr if x["comp_ok"] is not None]
    print("%-16s %6d %6.1f %6.1f %6.1f %6.1f" % ("ALL", len(allr),
        (100*sum(l0)/len(l0) if l0 else 0),
        (100*sum(l1)/len(l1) if l1 else 0),
        (100*sum(l2)/len(l2) if l2 else 0),
        (100*sum(cp)/len(cp) if cp else 0)))

if __name__ == "__main__":
    main()
