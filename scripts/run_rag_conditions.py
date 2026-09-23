#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B1 · RAG 四条件实验（A 无知识 / B 文化背景 / C 部分片段 / D oracle）

科学问题：模型 comp 低，是「缺知识」还是「缺整合」？
  - A（无知识）   ：原 comp 题干                              → baseline
  - B（文化背景） ：附加地域/文体背景说明，**不含答案信息**
  - C（部分片段） ：附加释义的**前半段**线索                   → 测「部分线索能否被整合」
  - D（oracle）   ：附加**完整释义**                          → 测「给全知识后能否整合」

关键设计（天然规避天花板效应）：
  XHY 的 comp 正确项是**具体情境句**（如「帮同事熬夜改方案对方不领情」），
  而 oracle 给出的是**抽象释义**（如「出力不讨好」），二者**不字面重合** →
  D 条件下模型仍需把抽象释义**映射**到具体情境，是真正的整合测试，而非字符串匹配。
  若 D 条件 comp 仍 < 100%，则「整合缺陷 = 100% − comp_D」即为论文最想要的量。

核心指标（聚合后）：
  知识增益     = comp_C − comp_A
  整合缺陷     = 100% − comp_D        ← 给全知识后仍失败的部分
  单调性检验   = A ≤ B ≤ C ≤ D（缺知识 → 给线索 → 给全释 应单调上升）

四个条件全部由 pilot.jsonl 现有字段构造（region / category / target_meaning），零生成成本。
comp 用 PERMS=6 循环置换去位置偏置，与正文 comp 口径一致。

用法：
  BAILIAN_API_KEY=... python -u scripts/run_rag_conditions.py --cats xiehouyu
  BAILIAN_API_KEY=... python -u scripts/run_rag_conditions.py --cats xiehouyu --limit 3   # 冒烟
"""
import json, os, sys, time, argparse, collections, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_mem_layers as M

EP = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # B1 全用百炼 7 模型
KEY = os.environ.get("BAILIAN_API_KEY", "")

DEFAULT_MODELS = ["qwen3.8-max-0902", "kimi-k3", "deepseek-v4.1-flash",
                  "qwen3.7-flash-2026-07-15", "qwen3.8-flash", "qwen3.8-27b",
                  "deepseek-v4-flash-0731"]
CONDS = ["A", "B", "C", "D"]
PERMS = 6

CAT_DESC = {
    "xiehouyu": "乡土歇后语（前半是比喻、后半是含义）",
    "phonetic_play": "字谜/隐语（用拆字、谐音等手法隐藏真意）",
    "allusion_idiom": "冷门典故成语",
    "agrarian_proverb": "北方农耕隐喻农谚",
}


def labels(n):
    return [chr(65 + i) for i in range(n)]


def perms(n):
    base = list(range(n))
    return [tuple(base[k:] + base[:k]) for k in range(n)]  # 循环右移，n 个置换


def build_prefix(it, cond):
    """构造附加在题干前的知识片段（cond=A 为空）"""
    if cond == "A":
        return ""
    region = (it.get("region") or "").strip()
    cat = it.get("category")
    tm = (it.get("target_meaning") or "").strip()
    if cond == "B":
        where = ("流传于%s的" % region) if region else ""
        return ("【背景知识】这是%s中国民间修辞表达（%s）。其含义多来自生活经验与地域文化，"
                "答题需结合语境理解，不要只看字面。" % (where, CAT_DESC.get(cat, "修辞表达")))
    if cond == "C":
        half = tm[: max(1, len(tm) // 2)] if tm else ""
        return "【线索】该表达的含义与以下意思有关：%s……（提示不完整）" % half
    if cond == "D":
        return "【完整释义】该表达的含义是：%s" % tm
    return ""


def comp_one(item, model, cond, ep, key):
    ct = item["comp_task"]
    options = ct["options"]
    n = len(options)
    keys = sorted(options.keys())
    answer_key = ct["answer"]
    prefix = build_prefix(item, cond)
    correct = 0
    for perm in perms(n)[:PERMS]:
        disp = [options[keys[perm[i]]] for i in range(n)]
        gold_pos = perm.index(keys.index(answer_key))
        gold_label = labels(n)[gold_pos]
        opts_txt = "\n".join("%s. %s" % (labels(n)[i], disp[i]) for i in range(n))
        prompt = ((prefix + "\n\n") if prefix else "") + ct["prompt"] + "\n" + opts_txt + \
                 "\n只输出正确选项字母（A-%s）。" % labels(n)[n - 1]
        try:
            resp = M.call_model(prompt, model, ep, key)
            if M.parse_letter(resp) == gold_label:
                correct += 1
        except Exception:
            pass
    return correct, PERMS


def main():
    global PERMS
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", default="xiehouyu",
                    help="逗号分隔类别，默认 xiehouyu（先做 XHY 208）")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--conds", default=",".join(CONDS))
    ap.add_argument("--perms", type=int, default=PERMS)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="每类最多取 N 条（冒烟用）")
    ap.add_argument("--raw", default="results/rag_conditions_raw.jsonl")
    ap.add_argument("--out", default="results/rag_conditions.json")
    args = ap.parse_args()

    PERMS = args.perms
    cats = [c.strip() for c in args.cats.split(",") if c.strip()]
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    conds = [c.strip() for c in args.conds.split(",") if c.strip()]

    items = [json.loads(l) for l in open(os.path.join(ROOT, "data", "pilot.jsonl"),
                                          encoding="utf-8") if l.strip()]
    items = [it for it in items if it["category"] in cats]
    if args.limit:
        capped = []
        seen = collections.Counter()
        for it in items:
            if seen[it["category"]] < args.limit:
                capped.append(it); seen[it["category"]] += 1
        items = capped
    print("[B1] 载入 %d 题（cats=%s），模型 %d，条件 %s，PERMS=%d"
          % (len(items), cats, len(models), conds, PERMS))

    # checkpoint：已完成的 (id, model, cond)
    done = set()
    if os.path.exists(args.raw):
        for l in open(args.raw, encoding="utf-8"):
            try:
                d = json.loads(l); done.add((d["id"], d["model"], d["cond"]))
            except: pass
    print("[B1] 已完成组合: %d" % len(done))

    tasks = [(it["id"], model, cond) for it in items for model in models for cond in conds
             if (it["id"], model, cond) not in done]
    by_id = {it["id"]: it for it in items}
    print("[B1] 待跑组合: %d（每组合 %d 调用）" % (len(tasks), PERMS))

    rawf = open(args.raw, "a", encoding="utf-8")
    t0 = time.time()
    ok = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {}
        for tid, model, cond in tasks:
            f = ex.submit(comp_one, by_id[tid], model, cond, EP, KEY)
            futs[f] = (tid, model, cond)
        for f in as_completed(futs):
            tid, model, cond = futs[f]
            correct, total = f.result()
            rawf.write(json.dumps({"id": tid, "model": model, "cond": cond,
                                   "correct": correct, "total": total},
                                  ensure_ascii=False) + "\n")
            rawf.flush()
            ok += 1
            if ok % 10 == 0:
                el = time.time() - t0
                print("  %d/%d  (%.0fs, %.2f 组合/s)" % (ok, len(tasks), el, ok / max(el, 1e-6)))
    rawf.close()
    print("[B1] 跑批完成，聚合中...")

    # 聚合
    agg = collections.defaultdict(lambda: [0, 0])  # (model,cond) -> [correct, total]
    for l in open(args.raw, encoding="utf-8"):
        try:
            d = json.loads(l)
            agg[(d["model"], d["cond"])][0] += d["correct"]
            agg[(d["model"], d["cond"])][1] += d["total"]
        except: pass
    table = {}
    for (model, cond), (c, t) in agg.items():
        table.setdefault(model, {})[cond] = (100.0 * c / t) if t else None
    out = {"models": models, "conds": conds, "cats": cats, "perms": PERMS,
           "n_items": len(items), "comp_by_model_cond": table}
    json.dump(out, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 打印
    print("\n=== B1 · comp (%) by 模型 × 条件 ===")
    hdr = "模型".ljust(24) + "".join(("  " + c).rjust(10) for c in conds)
    print(hdr)
    for m in models:
        row = m.ljust(24)
        for c in conds:
            v = table.get(m, {}).get(c)
            row += ("  %.1f" % v).rjust(10) if v is not None else "    —".rjust(10)
        print(row)
    # 均值行
    means = {}
    for c in conds:
        vals = [table[m][c] for m in models if table.get(m, {}).get(c) is not None]
        means[c] = (sum(vals) / len(vals)) if vals else None
    mrow = "均值".ljust(24) + "".join(("  %.1f" % means[c]).rjust(10) for c in conds)
    print(mrow)
    if all(means[c] is not None for c in conds):
        print("\n指标（7 模型均值）：")
        print("  知识增益 comp_C − comp_A = %.1fpp" % (means["C"] - means["A"]))
        print("  整合缺陷 100%% − comp_D   = %.1fpp" % (100 - means["D"]))
        mono = "是" if means["A"] <= means["B"] <= means["C"] <= means["D"] else "否（异常，需查）"
        print("  单调性 A≤B≤C≤D          = %s" % mono)


def _pid_alive(pid):
    """跨平台判断进程是否存活（Windows 用 ctypes 查句柄，避免 tasklist 的 GBK 编码坑）。"""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_INFORMATION = 0x0400
            h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            alive = h != 0
            if h:
                kernel32.CloseHandle(h)
            return alive
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _safe_remove(p):
    try:
        os.remove(p)
    except OSError:
        pass


def _acquire_single_instance_lock():
    """防止同一脚本双实例并发写 rag_conditions_raw.jsonl（B1 曾因双进程导致 45% 重复行）。
    用 PID 锁文件：启动即原子创建并写入本进程 PID；若已存在且其中 PID 仍存活 -> 退出；
    若 PID 已死（陈旧锁，如前次崩溃）-> 删除后重试。进程正常退出时 atexit 清理锁文件。"""
    import atexit
    lock_path = os.path.join(ROOT, "results", ".rag_conditions.lock")
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            atexit.register(lambda: _safe_remove(lock_path))
            return
        except FileExistsError:
            try:
                with open(lock_path, "r") as f:
                    pid = int((f.read() or "0").strip() or 0)
            except Exception:
                pid = 0
            if _pid_alive(pid):
                print("⚠️ 另一个 run_rag_conditions.py 实例正在运行（PID %d，锁文件 %s）。\n"
                      "    本实例退出，避免两个进程同时写 results/rag_conditions_raw.jsonl 造成重复行。\n"
                      "    若确认无其它实例在跑，请手动删除该锁文件后重试。" % (pid, lock_path))
                sys.exit(1)
            else:
                _safe_remove(lock_path)   # 陈旧锁，回收后重试
                continue


if __name__ == "__main__":
    _acquire_single_instance_lock()
    main()
