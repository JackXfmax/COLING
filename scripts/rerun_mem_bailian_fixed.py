# 修复重跑：deepseek/kimi 实为百炼(dashscope)托管模型，但 run_mem_layers.py 的
# resolve() 把非 qwen 前缀模型错路由到 openlux 端点 → 鉴权/托管失败 → [ERROR] → mem 三层全 0。
# 本脚本强制这 2 个模型走百炼端点重跑（enable_thinking=False，与正式跑批一致），
# 输出到 mem_layers_raw_bailian_fixed.jsonl，供重新合并聚合。
import os, sys, json, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_mem_layers as M
from concurrent.futures import ThreadPoolExecutor

BAILIAN_EP = "https://dashscope.aliyuncs.com/compatible-mode/v1"
BAILIAN_KEY = os.environ.get("BAILIAN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or ""
assert BAILIAN_KEY, "需设置 BAILIAN_API_KEY"
MODELS = ["deepseek-v4.1-flash"]
RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "results", "mem_layers_raw_bailian_fixed.jsonl")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
items = [json.loads(l) for l in open(os.path.join(ROOT, "data", "pilot.jsonl"), encoding="utf-8") if l.strip()]
mem_orders = M.prepare_mem_orders(items)


def run_one(it, model):
    iid, cat = it["id"], it["category"]
    mt = it.get("mem_task") or {}
    l0_resp = M.call_model(mt.get("prompt", "") + "\n请只给出答案本身，不要解释。",
                           model, BAILIAN_EP, BAILIAN_KEY)
    l0_ok = M.grade_mem(l0_resp, mt.get("accept", [])) if mt else None
    l1_ok = None
    l1t = it.get("mem_l1_task")
    if l1t:
        l1_resp = M.call_model(l1t["prompt"] + "\n请只给出答案本身，不要解释。",
                               model, BAILIAN_EP, BAILIAN_KEY)
        l1_ok = M.grade_mem(l1_resp, mt.get("accept", []))
    l2_ok, l2_acc = None, None
    t = it.get("mem_l2_task")
    if t:
        base, _ = mem_orders.get(iid, (sorted(t["options"].keys()), t["answer"]))
        keys = sorted(t["options"].keys()); n = len(keys); labels = M.labels_for(n); gold = t["answer"]
        ok = []
        for shift in range(min(M.PERMS, n)):
            disp = M.order_at(base, shift, n)
            opts = "\n".join("%s. %s" % (labels[i], t["options"][disp[i]]) for i in range(n))
            p = M.parse_letter(M.call_model(t["prompt"] + "\n" + opts +
                              "\n只输出正确选项字母（A-%s）。" % labels[n - 1], model, BAILIAN_EP, BAILIAN_KEY))
            if p is None or p not in labels:
                ok.append(False); continue
            ok.append(disp[labels.index(p)] == gold)
        l2_acc = sum(ok) / float(len(ok)); l2_ok = (l2_acc >= 0.5)
    return {"id": iid, "model": model, "category": cat,
            "l0_ok": l0_ok, "l1_ok": l1_ok, "l2_ok": l2_ok, "l2_acc": l2_acc}


todo = [(it, m) for it in items for m in MODELS]
rawf = open(RAW, "a", encoding="utf-8")
lock = threading.Lock(); nd = [0]
print("修复重跑 %d 组合（%d 模型 × %d 题，每组合 8 调用）" % (len(todo), len(MODELS), len(items)), flush=True)


def work(pair):
    rec = run_one(*pair)
    with lock:
        rawf.write(json.dumps(rec, ensure_ascii=False) + "\n"); rawf.flush(); nd[0] += 1
        if nd[0] % 25 == 0:
            print("  ... %d/%d" % (nd[0], len(todo)), flush=True)


with ThreadPoolExecutor(max_workers=int(os.environ.get("MEM_WORKERS", "32"))) as ex:
    list(ex.map(work, todo))
rawf.close()
print("FIXED 完成，写入 %s，共 %d 条" % (RAW, nd[0]), flush=True)
