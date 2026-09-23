#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b1_finalize.py — B1(RAG四条件) 收尾看守脚本

作用：
  轮询 B1 跑批进程（默认 PID 28968）。当进程结束后：
    1) 对 results/rag_conditions_raw.jsonl 按 (id,model,cond) 去重
       （历史双进程重复 bug 遗留 2485 条重复行，聚合脚本不去重会扭曲指标）
    2) 调用 run_rag_conditions.py 指向去重后的 raw 做聚合
       （done=全5824 -> tasks空 -> 直接干净聚合）生成 rag_conditions.json
    3) 写 results/B1_FINALIZED.log 记录去重/聚合结果

注意：本脚本只做本地计算，不调用任何 API，无需 BAILIAN_API_KEY。
      B7(MiniMax续跑) 因需要密钥，不在本脚本内，由后续单独带 key 启动。
"""
import os, sys, json, time, subprocess, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "rag_conditions_raw.jsonl")
DEDUP = os.path.join(ROOT, "results", "rag_conditions_raw_dedup.jsonl")
OUT = os.path.join(ROOT, "results", "rag_conditions.json")
LOG = os.path.join(ROOT, "results", "B1_FINALIZED.log")
B1_PID = 28968
PY = sys.executable


def b1_alive():
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % B1_PID],
                             capture_output=True, text=True, timeout=10).stdout
        return "python" in out.lower()  # 命中 python 进程即视为存活
    except Exception:
        return True  # 检测失败则保守认为仍存活


def dedup():
    seen = {}
    rows = 0
    with open(RAW, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            rows += 1
            seen[(d.get("id"), d.get("model"), d.get("cond"))] = d  # 保留最后一行
    with open(DEDUP, "w", encoding="utf-8") as f:
        for d in seen.values():
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    return rows, len(seen)


def main():
    logf = open(LOG, "w", encoding="utf-8")

    def L(msg):
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    L("watcher 启动，看守 B1 PID=%d" % B1_PID)
    waited = 0
    while b1_alive():
        time.sleep(30)
        waited += 30
        if waited % 300 == 0:
            L("B1 仍在运行（已等待 %d min）" % (waited // 60))
    L("B1 进程已结束，开始去重聚合")
    rows, uniq = dedup()
    L("去重: %d 行 -> %d 唯一组合（移除 %d 重复行）" % (rows, uniq, rows - uniq))
    cmd = [PY, "-u", os.path.join(ROOT, "scripts", "run_rag_conditions.py"),
           "--cats", "xiehouyu", "--workers", "8",
           "--raw", DEDUP, "--out", OUT]
    L("聚合命令: " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    L("聚合返回码: %d" % r.returncode)
    tail = (r.stdout.strip().splitlines()[-6:]) if r.stdout.strip() else []
    for t in tail:
        L("  | " + t)
    if os.path.exists(OUT):
        L("rag_conditions.json 已生成: %d bytes" % os.path.getsize(OUT))
    else:
        L("警告: rag_conditions.json 未生成！stderr=" + (r.stderr.strip()[:500] if r.stderr else ""))
    L("watcher 完成")


if __name__ == "__main__":
    main()
