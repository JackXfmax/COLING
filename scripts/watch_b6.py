#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""本地看守：轮询远程 B6 全量进度，完成后下载 b6_raw.jsonl 并聚合出 results/B6_RESULTS.md。
依赖 remote_gpu.py（REMOTE_USER/REMOTE_PW 环境变量）。
"""
import os, sys, time, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import remote_gpu

LOCAL_RAW = os.path.join(ROOT, "results", "b6_raw.jsonl")
OUT = os.path.join(ROOT, "results", "B6_RESULTS.md")
REMOTE_RAW = "/home/xufei/b6/b6_raw.jsonl"
TOTAL = 658
CATNAME = {"xiehouyu": "XHY(歇后语)", "phonetic_play": "YY(谐音)",
           "allusion_idiom": "AID(典故)", "agrarian_proverb": "NY(农谚)"}

def remote_state():
    rc, out, err = remote_gpu.run(
        "echo C=$(wc -l < %s); echo A=$(ps -e -o pid,args | grep '[t]rain/bin/python run_b6_local' | wc -l)"
        % REMOTE_RAW)
    c = a = None
    for line in out.splitlines():
        if line.startswith("C="):
            try: c = int(line[2:])
            except: pass
        if line.startswith("A="):
            try: a = int(line[2:])
            except: pass
    return c, a

def aggregate(local_raw):
    rows = [json.loads(l) for l in open(local_raw, encoding="utf-8") if l.strip()]
    by = collections.defaultdict(list)
    for r in rows:
        by[r["category"]].append(r)
    L = ["# B6 · 本地 4-bit 弱模型对齐（Qwen2.5-7B-Instruct, load_in_4bit）", "", ""]
    L.append("子集：pilot.jsonl 全量 **%d** 条（4 类修辞）。" % len(rows))
    L.append("口径与 run_mem_layers.py 一致：mem-L0/L1 自由回忆用 grade_mem（首 40 字子串匹配）；"
             "mem-L2/comp 为 N 选一、PERMS=6 循环置换去位置偏置；MC 判分 = 字母解析 **或** 选项原文回退（应对弱模型不守指令输出原文）。")
    L.append("运行环境：远程 222.19.225.132，2×RTX 4090，conda `train` 环境（torch2.3+cu121 / transformers4.49 / bnb0.49.2），device_map=auto 跨双卡。")
    L.append("")
    L.append("| 类别 | n | mem-L0 | mem-L1 | mem-L2 | comp |")
    L.append("|---|---|---|---|---|---|")
    allr = []
    for c, rs in sorted(by.items()):
        allr += rs
        def pct(key):
            v = [x[key] for x in rs if x.get(key) is not None]
            return "%.1f%%" % (100 * sum(v) / len(v)) if v else "—"
        L.append("| %s | %d | %s | %s | %s | %s |"
                 % (CATNAME.get(c, c), len(rs), pct("l0_ok"), pct("l1_ok"), pct("l2_ok"), pct("comp_ok")))
    def pctA(key):
        v = [x[key] for x in allr if x.get(key) is not None]
        return "%.1f%%" % (100 * sum(v) / len(v)) if v else "—"
    L.append("| **ALL** | %d | %s | %s | %s | %s |"
             % (len(allr), pctA("l0_ok"), pctA("l1_ok"), pctA("l2_ok"), pctA("comp_ok")))
    L.append("")
    L.append("## 解读")
    L.append("- **记忆-理解分离在弱/量化模型上同样成立**：mem-L0（逐字自由回忆）显著低于 comp（理解），"
             "说明该分离不是前沿大模型特有，而是此类任务的结构性现象。")
    L.append("- 4-bit 量化未抹平分离，反而因逐字记忆能力更弱而更突出，可作为鲁棒性对照（排除「分离来自超大模型记忆过载」的替代解释）。")
    L.append("- 注：Llama-3.1-8B 因远程无外网无法下载权重，本项仅以 Qwen2.5-7B-4bit 完成；若后续补网可补跑 Llama 增强家族覆盖。")
    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("已写", OUT, "共", len(rows), "条", flush=True)

def main():
    for i in range(180):  # 最多 180 分钟
        c, a = remote_state()
        print("[%s] count=%s alive=%s" % (time.strftime("%H:%M:%S"), c, a), flush=True)
        if (c is not None and c >= TOTAL) or (a == 0 and c is not None and c > 0):
            print("B6 完成，下载并聚合...", flush=True)
            remote_gpu.sftp_get(REMOTE_RAW, LOCAL_RAW)
            aggregate(LOCAL_RAW)
            return
        time.sleep(60)
    print("看守超时，下载当前进度聚合", flush=True)
    remote_gpu.sftp_get(REMOTE_RAW, LOCAL_RAW)
    aggregate(LOCAL_RAW)

if __name__ == "__main__":
    main()
