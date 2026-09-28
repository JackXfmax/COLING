# 官方 DeepSeek 一键跑分：从官方端点拉模型列表 -> 自动解析 "deepseek-v4 pro" 真实 id
# -> 复用 run_pilot.py（同 80 题 / PERMS=6 / 同提示词）跑官方 DeepSeek。
# 用法（Bash 恢复后）:
#   python scripts/run_deepseek_official.py
# 环境变量可选覆盖: DS_KEY, DS_ENDPOINT
import os, sys, json, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run_pilot  # 复用 run_pilot 的全部逻辑，保证同口径

KEY = os.environ.get("DS_KEY", "")
if not KEY:
    raise SystemExit("请先在环境变量 DS_KEY 中设置 DeepSeek API key（切勿硬编码进仓库）")
EP = os.environ.get("DS_ENDPOINT", "https://api.deepseek.com/v1").rstrip("/")


def list_models():
    req = urllib.request.Request(EP + "/models",
                                 headers={"Authorization": "Bearer " + KEY})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        return [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print("[WARN] 拉模型列表失败:", e)
        return []


def find_v4(ids):
    # 优先匹配 "v4" + "pro"（用户指定的 deepseek-v4 pro）
    pro = sorted(i for i in ids if "v4" in i.lower() and "pro" in i.lower())
    if pro:
        return pro[0]
    v4 = sorted(i for i in ids if "v4" in i.lower())
    if v4:
        return v4[0]
    return None


def main():
    ids = list_models()
    print("=== 官方 DeepSeek 可用模型 ===")
    for i in ids:
        print("   ", i)

    targets = []
    v4 = find_v4(ids)
    if v4:
        targets.append(v4)
        print("[select] v4-pro 模型 ->", v4)
    else:
        print("[WARN] 未在官方端点找到含 'v4' 的模型，请检查模型名")

    # 用户此前决策"两个都跑"：把 chat / reasoner 也纳入（infra 交叉 + 推理范式），若端点有
    for extra in ["deepseek-chat", "deepseek-reasoner"]:
        if extra in ids and extra not in targets:
            targets.append(extra)
            print("[select] 额外交叉模型 ->", extra)

    if not targets:
        sys.exit("[ERR] 没有任何可跑的 DeepSeek 官方模型，退出")

    print("=== 最终要跑的模型:", targets, "===")

    os.environ["PILOT_ENDPOINT"] = EP
    os.environ["PILOT_API_KEY"] = KEY
    os.environ["PILOT_PERMS"] = "6"
    os.environ["PILOT_THREADS"] = os.environ.get("PILOT_THREADS", "4")
    os.environ["PILOT_RETRY"] = "5"
    sys.argv = ["run_pilot.py", "--models", ",".join(targets)]
    run_pilot.main()


if __name__ == "__main__":
    main()
