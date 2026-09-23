#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B2 本地看守脚本：等 run_b2_gpt.py 跑完（检测到 b2_full.log 出现「[B2] 聚合写入」），
自动调用 gen_b2_report.py 生成 results/B2_RESULTS.md，并写 watch_b2.log。
每 30s 轮询；带 150min 超时兜底（避免 B2 崩溃时无限等待）。

用法：
  python -u scripts/watch_b2.py
"""
import os, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

LOG = os.path.join(ROOT, "results", "b2_full.log")
OUT_JSON = os.path.join(ROOT, "results", "B2_GPT.json")
REPORT = os.path.join(ROOT, "results", "B2_RESULTS.md")
WATCH_LOG = os.path.join(ROOT, "results", "watch_b2.log")
DONE_MARK = "[B2] 聚合写入"
POLL = 30
TIMEOUT = 150 * 60  # 150 分钟


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = "[%s] %s" % (ts, msg)
    print(line, flush=True)
    with open(WATCH_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def b2_done():
    # 主判据：日志出现聚合标记
    if os.path.exists(LOG):
        try:
            with open(LOG, encoding="utf-8", errors="ignore") as f:
                if DONE_MARK in f.read():
                    return True
        except Exception:
            pass
    # 兜底：B2_GPT.json 已存在且 n_items 满，且日志不再增长（粗略）
    if os.path.exists(OUT_JSON):
        try:
            d = json.load(open(OUT_JSON, encoding="utf-8"))
            if d.get("n_items", 0) >= 658:
                return True
        except Exception:
            pass
    return False


def main():
    log("watch_b2 启动，等待 B2 完成标记「%s」..." % DONE_MARK)
    start = time.time()
    generated = False
    while True:
        if b2_done():
            log("检测到 B2 完成，生成报告...")
            try:
                import gen_b2_report as G
                G.main()
                log("报告已生成: %s" % REPORT)
            except Exception as e:
                log("生成报告失败: %r" % e)
            generated = True
            break
        if time.time() - start > TIMEOUT:
            log("超时（%d min）仍未检测到完成标记，停止看守（可手动跑 gen_b2_report.py）。" % (TIMEOUT // 60))
            break
        time.sleep(POLL)
    if not generated:
        log("未生成报告（B2 未完成或超时）。")


if __name__ == "__main__":
    main()
