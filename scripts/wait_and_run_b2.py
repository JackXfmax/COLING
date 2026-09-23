#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B2 自动恢复看守：openlux 端点因限流/宕机不可达时，每 5 分钟探活一次；
一旦可达，自动续跑 run_b2_gpt.py（checkpoint 跳过已生成的 657 个变体，只跑评测），
跑完再调用 gen_b2_report.py 生成 B2_RESULTS.md。最长等待 3 小时。
需 OLUX_API_KEY 环境变量（启动时继承）。

用法：
  OLUX_API_KEY=... python -u scripts/wait_and_run_b2.py
"""
import os, sys, time, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PY = "C:/Users/机械革命/.workbuddy/binaries/python/versions/3.13.12/python.exe"
LOG = os.path.join(ROOT, "results", "wait_b2.log")
POLL = 5 * 60
MAX_WAIT = 3 * 3600


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = "[%s] %s" % (ts, msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def probe_ok():
    import concurrent.futures
    import olux
    def go():
        return olux.call([{"role": "user", "content": "hi"}],
                         model="gpt-4o-mini", max_tokens=5, timeout=20)
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        fut = ex.submit(go)
        try:
            r = fut.result(timeout=25)
            return not (isinstance(r, str) and r.startswith("[ERROR]"))
        except Exception:
            return False


def main():
    log("wait_and_run_b2 启动：openlux 不可达时每 %d min 探活，最长等 %.0f min。" % (POLL // 60, MAX_WAIT / 60))
    start = time.time()
    launched = False
    while time.time() - start < MAX_WAIT:
        if probe_ok():
            log("openlux 已可达，启动 B2 续跑（评测，checkpoint 跳过已生成变体）...")
            try:
                env = dict(os.environ)
                subprocess.run([PY, "-u", os.path.join(HERE, "run_b2_gpt.py"), "--workers", "6"],
                               cwd=ROOT, timeout=7200, env=env)
            except Exception as e:
                log("B2 续跑异常: %r" % e)
            # 生成报告
            try:
                import gen_b2_report as G
                G.main()
                log("B2_RESULTS.md 已自动生成。")
            except Exception as e:
                log("报告生成失败: %r" % e)
            launched = True
            break
        else:
            log("openlux 仍不可达，%d min 后重试。" % (POLL // 60))
            time.sleep(POLL)
    if not launched:
        log("已达最长等待，放弃自动续跑。可稍后手动跑 run_b2_gpt.py + gen_b2_report.py。")


if __name__ == "__main__":
    main()
