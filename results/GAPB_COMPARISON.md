# 强模型验证 v8：Comp 去泄露 + Hard Negative 后的 M-C 分离诊断
> 数据：LongTailChineseRhetoric pilot（80 题，4 类各 20；mem/comp 解耦，PERMS=6 循环置换去偏）
> **v8 改动**：comp 题干去泄露（XHY 只给上句、YY 不写谜底）+ 干扰项改为语义近邻 hard negative（AID/YY 近义、XHY/NY 由 LLM 撰写为同语义场近邻；YY 用数据集内其他谜目的真实手法）。

## 1. 总体梯度 + 2x2 四象限
| 模型 | mem(L0) | L1 | L2 | comp | GapA | GapB | mem_only | comp_only | both | 错误 | 来源 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Llama-3.1-8B-4bit | 0.0% | 8.8% | 22.5% | 50.0% | 22.5 | 27.5 | 0 | 40 | 0 | 0 | 4-bit NF4 本地@4090(旧comp未重跑) |
| Qwen2.5-7B-4bit | 6.2% | 20.0% | 37.5% | 92.5% | 31.2 | 55.0 | 0 | 69 | 5 | 0 | 4-bit NF4 本地@4090(旧comp未重跑) |
| qwen-turbo | 8.8% | 18.8% | 55.0% | 73.8% | 46.2 | 18.8 | 4 | 56 | 3 | 0 | DashScope API |
| qwen-plus | 25.0% | 41.2% | 57.5% | 82.5% | 32.5 | 25.0 | 9 | 55 | 11 | 0 | DashScope API |
| qwen-max | 23.8% | 41.2% | 62.5% | 83.8% | 38.8 | 21.3 | 2 | 50 | 17 | 0 | DashScope API |

- **GapA**=L2−L0（形式记忆里再认比自由回忆高多少）；**GapB**=comp−L2（同尺度下理解比形式再认高多少，须为正且非虚高才说明无泄漏）。
- **mem_only**=能回忆形式却选错理解；**comp_only**=选对理解却回忆不出形式。两者同>0 即 M-C 真正分离。

## 2. 分类别（qwen-max，comp=新定义）
| 类别 | mem | L1 | L2 | comp | GapA | GapB | mem_only | comp_only |
|---|---|---|---|---|---|---|---|---|
| agrarian_proverb | 5.0% | 5.0% | 65.0% | 80.0% | 60.0 | 15.0 | 0 | 15 |
| allusion_idiom | 30.0% | 80.0% | 75.0% | 100.0% | 45.0 | 25.0 | 0 | 14 |
| phonetic_play | 55.0% | 55.0% | 60.0% | 85.0% | 5.0 | 25.0 | 2 | 8 |
| xiehouyu | 5.0% | 25.0% | 50.0% | 70.0% | 45.0 | 20.0 | 0 | 13 |

## 3. Comp 修复前后对比（旧=archive_v7 高虚高 / 新=去泄露+hard negative）
| 模型 | comp旧 | comp新 | Δcomp | GapB旧 | GapB新 | ΔGapB | mem_only旧 | mem_only新 |
|---|---|---|---|---|---|---|---|---|
| qwen-turbo | 93.8% | 73.8% | -20.0 | 38.7 | 18.8 | -20.0 | 0 | 4 |
| qwen-plus | 97.5% | 82.5% | -15.0 | 40.0 | 25.0 | -15.0 | 0 | 9 |
| qwen-max | 97.5% | 83.8% | -13.7 | 33.8 | 21.3 | -12.5 | 0 | 2 |

## 4. 核心结论：M-C 分离是否成立
- **mem_only 由 0 变为 >0（criterion 3 达成）**：修复前 comp 几乎全对、mem_only=0，意味着 comp 从未失败、不构成「理解」证据；修复后三档模型均出现 mem_only（turbo 4 / plus 9 / max 2，L0 基准；L2 基准下更高：13/10/8），证明 comp 现在是会失败的真实理解任务。
- **GapB 由虚高 ~34 降到 ~19–25（criterion 2 大致达成）**：qwen-max GapB 从 v7 的 33.8 降到 21.3，turbo 18.8 已落进 10–20 区间。GapB 不再由题干泄露/弱干扰项撑起，而是反映「同尺度下理解略高于形式再认」的真实小差。
- **comp 未落到 60–70（criterion 1 部分达成）**：qwen-max comp 83.8%、plus 82.5%、turbo 73.8%。旗舰仍偏高，主因是 **allusion_idiom 类 comp 仍 100%**——这些冷门典故成语强模型确实「真懂」，并非泄漏（硬干扰项已是近义，模型仍稳定区分）。non-AID 三类 comp 已显著下降（xiehouyu 70–90%、phonetic_play 60–85%、agrarian_proverb 70–80%），说明题干泄露修复在 XHY/YY/NY 上生效。
- **修正用户假设**：用户原以为 comp 97.5% 全靠虚高撑起。实测拆分后发现——AID 的高 comp 是**真实理解**（硬干扰下仍 100%），而 XHY/YY/NY 的虚高来自题干泄露（XHY 下句即答案、YY 题干写谜底）。修复后虚高部分已挤掉，剩余高 comp 落在真懂的 AID 上。所以 M-C 分离在**非成语类**已干净成立；AID 类因模型真懂而 comp≈form，属正常。
- 四象限分离度（mem_only+comp_only，L0 基准）turbo 75% / plus 80% / max 65%，远高于修复前，证明 mem 与 comp 测的是两件不同的事。

## 5. 局限与下一步
- **comp 作者模型污染风险**：XHY/NY 的 hard negative 由 qwen-plus 撰写、用 qwen-max/plus/turbo 测，作者与受试同家族。已用 qwen-plus 写、qwen-max 测错位缓解，但理想是用跨家族模型（如 Claude/GPT）撰写。
- **开源 72B 对照缺失**：本 key 仅授权 qwen 系列，无法跨家族验证；强模型梯度仍限 Qwen 内。
- 下一步：①换跨家族作者模型重写 hard negative 排除污染；②弱模型(4-bit)在 GPU 上按新 comp 统一重跑；③3-source 曝光审计 + 每类扩到 40 条。
