# 可复现指南 · LongTailChineseRhetoric（C4）

> 数据版本：`v1.0.0-frozen` ｜ 配套：`requirements.txt`、`docs/CHANGELOG.md`、`docs/DATASHEET.md`
> **依赖极简**：全部脚本仅用 Python 标准库，**零第三方包**（无需 `pip install` 任何内容）

---

## 1. 环境

| 项 | 值 |
|---|---|
| Python | **>= 3.10**（开发实测 3.13.14） |
| 第三方包 | **无**（`requirements.txt` 为空依赖占位） |
| 操作系统 | Windows（开发）；Linux 亦可（4090 实验机 Ubuntu 22.04，用于 B6 本地 4-bit 重跑） |
| 主 API 端点 | 百炼兼容模式 `https://dashscope.aliyuncs.com/compatible-mode/v1` |

```bash
git clone <repo> && cd LongTailChineseRhetoric
python -c "import sys;print(sys.version)"     # 无需 pip install
python -c "import hashlib;print(hashlib.sha256(open('data/pilot.jsonl','rb').read()).hexdigest())"
# 期望 76f923851c86d568191a739dc3171c8249fba1c6158ae5ce36218ce85a37cd06
```

---

## 2. API 凭据（不落盘）

凭据**只走环境变量**，任何脚本不含硬编码 key：

```bash
export BAILIAN_API_KEY="sk-..."      # 阿里百炼（qwen / deepseek / kimi / glm / MiniMax）
export OPENLUX_API_KEY="sk-..."      # openlux 中转（跨家族佐证：claude / gpt-*）
```

**端点路由约定**（2026-09-21 修复后）：

| 模型前缀 | 端点 |
|---|---|
| `qwen*` / `deepseek*` / `kimi*` / `glm*` / `MiniMax*` | **百炼** |
| `gpt-*` / `claude-*` | **openlux** |

> ⚠️ **历史教训**：曾按「仅 qwen 前缀走百炼」错路由，导致 deepseek×2 + kimi 的 mem 三层全 0%（被误判为"模型不会"）。**接入新模型务必先用 `--limit 3` 冒烟验证端点可达 + 解析器可用，再全量。**

**推理模型必须关思考**：百炼托管的推理模型默认开 thinking，真实题干单次调用 189s+ 易超时。必须传 `enable_thinking: False`（延迟降至 ~1s，答案正确、`reasoning_tokens=0`）。

> ⚠️ **例外：`MiniMax` 系列不接受 `enable_thinking` 参数，传了必报 400** —— 需按模型分别传参。
> ⚠️ `qwen3.8-2.4t-a95b` / `glm-5.3` 强制思考不可关，万级跑批不适用，暂未纳入。

---

## 3. 最小复现链路（评审人最该跑的 5 步）

```bash
# ① 校验数据指纹（必须先做，不符则论文数字需重算）
python -c "import hashlib;print(hashlib.sha256(open('data/pilot.jsonl','rb').read()).hexdigest())"

# ② 重建数据（一般用冻结的 pilot.jsonl，跳过；如需从源 md 重生成则跑）
# python scripts/build_pilot.py

# ③ 三道 QC 关
python scripts/literal_gate.py           # 第一关 字面捷径：XHY gold-dominant 应 = 2.0%
python scripts/source_gate.py            # 第三关 来源等级：应无 C 级自媒体
python scripts/distractor_prerank.py     # 第二关 干扰项过强检出（约 21k 调用）

# ④ 跑 mem 三层（大规模，约 3.7 万调用/7 模型）
BAILIAN_API_KEY=... python -u scripts/run_mem_layers.py --workers 8

# ⑤ 聚合四层表 → XHY gap
python scripts/aggregate_four_layers.py --mem-raw results/mem_layers_raw_merged.jsonl
```

**期望结果**：`results/four_layers.json` 中 XHY(208) 的 `comp − mem_L0` = **+49.4pp**（7 模型均值：comp 60.9% vs mem-L0 11.5%）。

---

## 4. 脚本清单

### 核心（最小复现链路）

| 脚本 | 作用 |
|---|---|
| `build_pilot.py` | 由 `data/pilot_*.md` + `comp_hn.json` 重建 `pilot.jsonl` |
| `literal_gate.py` | QC 第一关：字面捷径检出 |
| `source_gate.py` | QC 第三关：来源 A/B/C 分级 |
| `distractor_prerank.py` | QC 第二关：干扰项预跑（7 模型 × PERMS=6） |
| `replace_overstrong_r2.py` | 过强干扰项自动替换（第二轮） |
| `run_mem_layers.py` | mem-L0/L1/L2 跑批（含 checkpoint） |
| `aggregate_four_layers.py` | 四层聚合 → `four_layers.json` |
| `analyze_mechanism.py` | B3 机制分层 → `MECHANISM_ANALYSIS.md` |
| `run_rag_conditions.py` | B1 RAG 四条件（A/B/C/D） |
| `run_b7_zhipu_minimax.py` | B7 Zhipu / MiniMax 补测 |

### 分析与辅助

| 脚本 | 作用 |
|---|---|
| `analyze_crossfamily.py` | 跨家族模型对比 |
| `analyze_gapb.py` | Gap-B 相关分析 |
| `bootstrap_ci.py` | 两层 bootstrap CI（题目层 + 置换层，B=1500） |
| `report_distractor_prerank.py` | 第二关报告生成 |
| `rerun_mem_bailian_fixed.py` | 错路由模型补救重跑 |
| `upgrade_xhy_provenance.py` / `upgrade_aid_yy_provenance.py` | 来源升级批处理 |
| `run_pilot.py` | 早期 pilot（80 题）阶段跑批 |

### 诊断 / 一次性（`_` 前缀多为临时）

`_diag_scale.py` `_smoke_bailian.py` `_smoke_models2.py` `_smoke_nothink.py` `_smoke_prerank.py` `diag_category.py` `diag_cats.py` `cat_summary.py` `clean_and_report.py` `diagnose_blindspots.py` `extrapolate.py` `inspect_resp.py` `test_parser.py` `do_xhy_replace.py` `backfill_grades.py` `gen_*.py` `run_deepseek_official.py` 及 `*.sh`
> 不进最小复现链路，保留供审计溯源。

---

## 5. Checkpoint 续跑

大规模跑批均**逐「题 × 模型（× 条件）」增量落盘**到 `results/*_raw*.jsonl`：

| 跑批 | 产物 | 规模 |
|---|---|---|
| mem 三层 | `results/mem_layers_raw_merged.jsonl` | 10 模型 × 658 = 6580 |
| comp 预跑 R2 | `results/prerank_raw_r2.jsonl` | 508 × 7 × 6 |
| B1 四条件 | `results/rag_conditions_raw.jsonl` | 208 × 4 × 7 = 5824 |
| B7 补测 | `results/b7_raw.jsonl` | 80 × 2 |

**中断后重跑同一命令即可续跑**（自动跳过已完成组合）。

> ⚠️ **续跑前务必确认 raw 干净**：欠费或失败冒烟会留下全 False 的假记录，并被 checkpoint 跳过、带假 0 值污染结果。曾因此重建过一次。
> ✅ 正确姿势：`rm results/<raw>.jsonl` 清干净 → 先 `--limit 3` 冒烟确认非零产出 → 再全量。

---

## 6. 结果非确定性来源（论文须声明）

| 来源 | 说明 | 缓解措施 |
|---|---|---|
| **模型版本漂移** | API 侧模型随 vendor 更新而变化，**无法永久锁定权重** | 记录快照日期、key 所属账号；论文标明"截至 2026-09" |
| **采样抖动** | 即便 `temperature=0`，批量 API 仍有极小概率不一致 | PERMS=6 循环置换去位置偏置 + 两层 bootstrap CI |
| **厂商限流导致的失败** | 超 RPM 返回 429，重试失败会被记为"答错" | `--workers` 保守设 8–32；失败被判答错会污染结果，宁慢勿错 |
| **本地 GPU 非确定性** | 仅 B6 弱模型重跑涉及 | 固定 seed（若脚本支持） |

> 📌 实测吞吐参考：百炼单 key，**停掉重限流模型后**可达 ~14 调用/秒；`MiniMax-M2.5` 在本账户重度限流（~0.5 调用/秒），会拖垮并发，**建议单独低并发后台跑，勿与主管线争抢**。
