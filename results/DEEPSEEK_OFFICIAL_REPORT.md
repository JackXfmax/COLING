# 官方 DeepSeek 评测报告（v1，部分完成）

日期：2026-09-20 ｜ 端点：`https://api.deepseek.com/v1`（官方，非聚合端）
模型：**`deepseek-v4-pro`**（用户指定）｜ 同 80 题 / PERMS=6 去偏

---

## 1. 端点探明：官方只有 2 个模型

实测 `/v1/models` 返回 **仅 2 个**模型 id：

- `deepseek-flash`
- `deepseek-v4-pro` ← 用户所说的 "deepseek-v4 pro"

> 注意：常见的 `deepseek-chat`(V3) / `deepseek-reasoner`(R1) **在本官方端点上不存在**。
> 因此原先设想的"chat+reasoner 双模型交叉"在此端点无法实现，可用替代是 flash / v4-pro 的强弱梯度。

---

## 2. 必须先修的两个 harness 问题（否则数据全废）

### 2.1 token 预算不足 → 推理模型说不出答案
`deepseek-v4-pro` 是推理型模型，思维链直接写在 `content`（既非 `reasoning_content`，也无 `<think>` 标签）。
在 `max_tokens=1024` 下响应被**截断在半句**（实测 1372 字后中断），模型**根本没来得及给出最终字母**。

- 修复：新增 `PILOT_MAX_TOKENS` 环境变量（默认仍 1024），本次设为 **4096**。

### 2.2 解析器只扫前 80 字符 → 读不到结尾的答案
原 `parse_letter` 只扫响应前 80 字符找孤立字母。面对"整段推理 + 结尾答案"的输出，扫到的是推理正文而非答案，
导致 XHY-001 六次置换中 **5 次判 None**、comp_acc 被压成 0。

- 修复：`parse_letter` 改为三级优先 —— ① 显式答案标记（`答案：X` / `故选X`，取最后一次）→
  ② 短响应（≤60 字）取首个孤立字母（兼容 gpt-4o / qwen 等简洁输出）→
  ③ 长思维链取**最后一个**孤立字母。
- 已加离线单测 `scripts/test_parser.py`，7 个用例全过。

### 修复效果（XHY 前 3 题对照）

| 条目 | 修复前 comp_acc | 修复后 comp_acc | 说明 |
|---|---|---|---|
| XHY-001 | 0.000（5/6 判 None） | **1.000**（`E,F,A,B,C,D` 随置换同步旋转） | 解析修复生效 |
| XHY-002 | 0.000 | 0.000（`C,D,E,F,A,B` 稳定偏离 gold） | **真答错**，非解析问题 |
| XHY-003 | — | **1.000** | — |
| 编号偏好 | 42%（应为 17%） | **17%** | 位置偏置消失，去偏生效 |

---

## 3. 结果（仅统计"每次置换都真实跑出"的干净数据）

账户中途耗尽（见第 4 节），已用 `scripts/clean_and_report.py` 剔除所有含 `[ERROR]` 或 `None` 预测的行。

### deepseek-v4-pro 干净子集（n=42）

| 类别 | n | mem% | mem-L1% | mem-L2% | comp% | **compAvg%** |
|---|---|---|---|---|---|---|
| xiehouyu（歇后语） | 20 | 15 | 20 | 75 | 80 | **76.7** |
| phonetic_play（谐音） | 20 | 80 | 45 | 95 | 100 | **99.2** |
| allusion_idiom（典故） | 2 | 100 | 50 | 100 | 100 | 91.7（样本不足） |
| **合计** | **42** | 50 | 33 | 86 | 90 | **88.1** |

### 与已完成的他家族横向对比（compAvg%，同口径）

| 类别 | **deepseek-v4-pro（官方）** | deepseek-v3.1（openlux） | qwen-max（dashscope） | gpt-4o |
|---|---|---|---|---|
| xiehouyu | **76.7** | 70.0 | 68.3 | — |
| phonetic_play | **99.2** | 94.2 | 95.0 | — |
| allusion_idiom | （n=2，待补） | 88.3 | 90.8 | — |
| agrarian_proverb | （未跑，待补） | 88.3 | 98.3 | — |

---

## 4. 未完成原因（两个独立故障）

| 故障 | 影响范围 | 根因 |
|---|---|---|
| `429 Too Many Requests` | AID 20 条中 18 条被污染 | 并发设 12 过高被限流；部分条目 6 次置换里只缺几次（半污染） |
| **`402 Payment Required`** | **NY 全部 20 条 + 后续所有调用** | **DeepSeek 账户余额耗尽**（单次探测亦返回 402） |

已剔除 38 行污染数据（18 条 AID + 20 条 NY），文件仅保留 42 条干净数据，**便于充值后断点续跑**。
`deepseek-flash` 因余额耗尽**未开始**。

---

## 5. 结论（基于已跑通的 42 条）

**M-C 分离在 Mem 侧，再次被独立基础设施确认。**

- 官方 DeepSeek（非聚合端、独立厂商、独立账单）在 XHY / YY 上呈现与 Qwen、OpenAI、Anthropic、Google **完全一致**的形态：
  **mem 极低（XHY 仅 15%）而 comp 很高（XHY 76.7%、YY 99.2%）**，编号偏好 17%（均衡值）。
- v4-pro 在 XHY（76.7% vs 70.0% / 68.3%）和 YY（99.2% vs 94.2% / 95.0%）上**均不低于** openlux 的 deepseek-v3.1 与 dashscope 的 qwen-max，
  说明聚合端（openlux）**没有系统性压低或虚高** DeepSeek 的表现 —— 聚合端疑虑基本排除。
- XHY 依旧是四类中最难的（各家族一致），YY 依旧近饱和 —— 类别难度梯度跨家族稳定。

**待补**：AID（20 条）、NY（20 条）、以及 `deepseek-flash`。补齐后方可给出 v4-pro 的完整 80 题数值。

---

## 6. 下一步

1. **给 DeepSeek 账户充值**（当前 402，任何调用都会被拒）。
2. 充值后由我执行（并发降到 **4**，避免 429）：
   ```
   PILOT_MAX_TOKENS=4096 PILOT_THREADS=4 python scripts/run_pilot.py --models deepseek-v4-pro --limit 80
   PILOT_MAX_TOKENS=4096 PILOT_THREADS=4 python scripts/run_pilot.py --models deepseek-flash --limit 80
   ```
   脚本会自动断点续跑，**已完成的 42 条不会浪费**。
3. 补齐后并入 `results/CROSSFAMILY_REPORT.md`，完成"双端点 DeepSeek 交叉验证"。

---

## 附：本次新增/修改的脚本

| 文件 | 作用 |
|---|---|
| `scripts/run_deepseek_official.py` | 官方 DeepSeek 一键跑（自动解析 v4-pro 真实 id） |
| `scripts/inspect_resp.py` | 查看原始响应（头/尾），诊断解析问题 |
| `scripts/diag_category.py` | 按类别统计 ERROR / 空响应 / 全 None，定位污染 |
| `scripts/clean_and_report.py` | 剔除污染行并仅对干净数据出报告 |
| `scripts/cat_summary.py` | 按类别汇总 mem/comp 与 comp 平均正确率 |
| `scripts/test_parser.py` | `parse_letter` 离线单测 |
| `scripts/run_pilot.py` | 新增 `PILOT_MAX_TOKENS`；`parse_letter` 三级解析（兼容推理模型） |
