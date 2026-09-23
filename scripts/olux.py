#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
openlux 网关的 OpenAI 兼容调用封装（用于 B5/B2 在 GPT 家族闭环）。
密钥通过环境变量 OLUX_API_KEY 注入（不在代码里硬编码）。
注意：GPT 不接受 enable_thinking 参数，这里只发标准 OpenAI payload。
"""
import json, os, time, re, threading
import urllib.request, urllib.error

OLUX_EP = os.environ.get("OLUX_ENDPOINT", "https://api.openlux.ai/v1")
OLUX_KEY = os.environ.get("OLUX_API_KEY", "")


def _raw_call(prompt, model, max_tokens, temperature, timeout):
    """单次 HTTP 调用（在子线程里跑，便于上层做线程级硬超时）。"""
    url = OLUX_EP.rstrip("/") + "/chat/completions"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": temperature, "max_tokens": max_tokens}
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + OLUX_KEY})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        msg = d["choices"][0]["message"]
        return (msg.get("content") or msg.get("reasoning_content") or "")
    except urllib.error.HTTPError as e:
        return "[ERROR] HTTP %s" % e.code
    except Exception as e:
        return "[ERROR] %s" % e


def call(prompt, model, max_tokens=512, temperature=0.0, timeout=60, _depth=0, hard_cap=None):
    """带线程级硬超时的调用（防止 urlopen 超时在某些网络/SSL 下不生效导致进程挂死）。
    hard_cap：整体上限（含重试），超时返回 '[ERROR] TIMEOUT' 且**不重试**（端点疑似宕机/限流，快速失败避免空转）。"""
    if hard_cap is None:
        hard_cap = timeout + 15
    res = [None]

    def worker():
        res[0] = _raw_call(prompt, model, max_tokens, temperature, timeout)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    th.join(hard_cap)
    if th.is_alive():
        return "[ERROR] TIMEOUT"
    r = res[0]
    if r is None:
        return "[ERROR] UNKNOWN"
    if r.startswith("[ERROR] TIMEOUT"):
        return r  # 超时致命，不重试
    if r.startswith("[ERROR]") and _depth < 3:
        time.sleep(2 * (_depth + 1))
        return call(prompt, model, max_tokens, timeout, _depth + 1, hard_cap)
    return r


def call_json(prompt, model, max_tokens=900, temperature=0.0, timeout=90):
    """调用并尝试解析返回中的 JSON（用于干扰项/变体生成）。"""
    txt = call(prompt, model, max_tokens=max_tokens, temperature=temperature, timeout=timeout)
    if "[ERROR]" in txt:
        return None
    # 抽取首个 [...] 或 {...}
    m = re.search(r"\[.*\]|\{.*\}", txt, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None
