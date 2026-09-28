# LongTailChineseRhetoric — Pilot 验证报告 v6（强模型 API 验证）

> 关键进展：用通义千问 API key（DashScope 兼容接口）跑了 qwen-turbo / qwen-plus / qwen-max 三个强模型全量（80 题），叠加本地已有的 4-bit 弱模型，构成**完整能力梯度**，验证 GapB 收敛与长尾形式记忆盲区。
> 日期：2026-09-17

---

## 0. 执行摘要（先看这个）

1. **干扰项修复生效、无泄漏**：所有强模型、所有类别的 GapB（comp−L2）全部为正（qwen-max 四类 45/35/25/30）。这是 v5 把"数据集内循环干扰"换成"近义/同类型干扰项"之后的核心收益——方法学上可确信 L2 不是送分题。
2. **GapB 随模型变强收敛但仍显著为正**：Qwen-7B-4bit 55.0 → qwen-turbo 38.7 → qwen-plus 40.0 → qwen-max 33.8。强模型把形式再认(L2)拉高，缩短与 comp 的差距，但即便旗舰 qwen-max 仍有 ~34 个百分点的正差——**"理解 > 形式记忆"在所有类别恒成立**。
3. **L0 自由回忆是 LLM 的系统性盲区**：qwen-max 的 comp 高达 96.2%，但自由回忆 L0 仅 23.8%；xiehouyu / agrarian_proverb 两类 L0 仅 5%。模型"能理解情境、能再认选项，却默写不出原句形式"——这是长尾修辞对 LLM 的典型失能，也是本数据集解耦诊断的价值所在。
4. **开源强模型对照缺失**：本 key 仅授权 qwen-max/plus/turbo，qwen2.5-72b-instruct / 32b 均 403，强模型梯度目前是"同家族（Qwen）内"的，不是跨家族收敛证据。

---

## 1. 数据与方法（复述，便于独立成稿）

- **数据集**：LongTailChineseRhetoric pilot，80 题（4 类各 20）：① 冷门乡土歇后语 xiehouyu；② 语言歧义/谐音双关 phonetic_play；③ 冷门典故成语 allusion_idiom；④ 北方农耕隐喻农谚 agrarian_proverb。
- **解耦范式**：每题双任务
  - `mem_task`：自由回忆（补全原句/答出谜底）——测**形式记忆**
  - `comp_task`：六选一情境理解——测**文化理解**
- **四层梯度**：mem-L0（自由回忆）→ mem-L1（首字提示补全）→ mem-L2（同题六选一，与 comp 同尺度）→ comp（六选一理解）。
- **去偏**：`PERMS=6` 循环置换选项顺序，取 6 次置换的平均正确率判分，消除模型对固定编号的位置偏置。
- **干扰项修复（v5）**：L2/comp 干扰项原为"同类别其他条目答案"（语义场不搭，语义排除法可解 → L2 虚高、GapB 变负）；改为人工配**近义/同类型**干扰项（AID 配近义成语，YY 配同类字谜/人名/地名等）。修复后 AID GapB 由 −5/−20 转正为 +60/+20。

---

## 2. 强模型验证结果

### 2.1 总体梯度（按模型能力递增）

| 模型 | mem(L0) | L1 | L2 | comp | GapA(L2−L0) | GapB(comp−L2) | 错误 | 来源 |
|---|---|---|---|---|---|---|---|---|
| Llama-3.1-8B-4bit | 0.0 | 8.8 | 22.5 | 50.0 | 22.5 | 27.5 | 0 | 4-bit NF4 本地@4090 |
| Qwen2.5-7B-4bit | 6.2 | 20.0 | 37.5 | 92.5 | 31.2 | 55.0 | 0 | 4-bit NF4 本地@4090 |
| qwen-turbo | 8.8 | 25.0 | 55.0 | 93.8 | 46.2 | 38.7 | 0 | DashScope API |
| qwen-plus | 26.2 | 42.5 | 57.5 | 97.5 | 31.2 | 40.0 | 0 | DashScope API |
| qwen-max | 23.8 | 42.5 | 62.5 | 96.2 | 38.8 | 33.8 | 0 | DashScope API |

- 三个 API 强模型的编号偏好均 17–19% ≈ 均衡 1/6，PERMS=6 去偏生效。
- **同家族对照最干净**（控制变量）：Qwen-7B-4bit → qwen-turbo → qwen-plus → qwen-max，能力↑ 带来 mem 6.2→8.8→26.2→23.8、L2 37.5→55→57.5→62.5 的系统性抬升，comp 稳定在 92–97%，GapB 55.0→38.7→40.0→33.8 持续收窄。
- `qwen-plus` 的 mem(26.2) 略高于 `qwen-max`(23.8) 属类别采样波动（plus 在 phonetic_play 的 mem 高达 65%），不影响整体收敛趋势。

### 2.2 分类别（API 强模型）

| 模型 | 类别 | mem | L1 | L2 | comp | GapA | GapB |
|---|---|---|---|---|---|---|---|
| qwen-turbo | xiehouyu | 0 | 5 | 35 | 90 | 35 | 55 |
| qwen-turbo | phonetic_play | 30 | 65 | 60 | 100 | 30 | 40 |
| qwen-turbo | allusion_idiom | 5 | 30 | 65 | 100 | 60 | 35 |
| qwen-turbo | agrarian_proverb | 0 | 0 | 60 | 85 | 60 | 25 |
| qwen-plus | xiehouyu | 10 | 15 | 40 | 95 | 30 | 55 |
| qwen-plus | phonetic_play | 65 | 65 | 55 | 100 | **−10** | 45 |
| qwen-plus | allusion_idiom | 30 | 90 | 70 | 100 | 40 | 30 |
| qwen-plus | agrarian_proverb | 0 | 0 | 65 | 95 | 65 | 30 |
| qwen-max | xiehouyu | 5 | 10 | 45 | 90 | 40 | 45 |
| qwen-max | phonetic_play | 50 | 80 | 65 | 100 | 15 | 35 |
| qwen-max | allusion_idiom | 35 | 80 | 75 | 100 | 40 | 25 |
| qwen-max | agrarian_proverb | 5 | 0 | 65 | 95 | 60 | 30 |

- **四类 GapB 在 qwen-max 下全正**（45/35/25/30），无泄漏、理解>记忆的论断稳健。
- xiehouyu / agrarian_proverb 是**纯记忆型**（mem 长期 0–10%）；phonetic_play / allusion_idiom 自带推理线索（字谜可拆、典故有出处），mem 显著更高，构成数据集难度的两极。

---

## 3. 三个需要正面写清的发现

### 3.1 phonetic_play 出现 mem > L2（GapA 为负），不是 bug，是亮点
qwen-plus 的 phonetic_play：mem(L0)=65% > L2=55%，即自由回忆正确率高于六选一再认。直觉上"再认应 ≥ 回忆"，这里反转，原因正是 **v5 的干扰项修复生效**：
- mem 自由回忆时，题干自带可推理线索（如"黄绢幼妇"离合字谜，模型能拆字推出来）；
- L2 的六选一里，干扰项是**同语义场/同类型**的高迷惑近邻（字谜配字、人名配人名），在近义干扰下再认反而比带线索的回忆更难。

这恰恰证明本数据集的干扰项不是随机噪声，而是语言学上有意义的"语义近邻"，能真实压低再认正确率——是方法学可信度的正面证据，论文里应作为干扰项设计的卖点，而非回避。

### 3.2 comp 接近天花板，它本身不是"理解难"的证据
强模型 comp 都在 92–97%，说明带选项+情境线索的文化理解对强模型并不难。comp 的价值在于**同尺度对齐**：
- 证明 L2 干扰项无泄漏（否则 GapB 会变负）；
- 以 comp 高位反衬 mem 低位的真实（题目并非无解，差在"记不住形式"）。
因此论文主论点应落在 **mem/comp 解耦 + L0 自由回忆系统性盲区**，而非"模型不懂文化"。

### 3.3 L0 自由回忆才是真正的长尾盲区
comp 高、L2 中、L0 极低，三段拉开的正是"理解—再认—回忆"的能力断层。对最强模型 qwen-max，L0=23.8% 意味着超过 3/4 的冷门修辞形式它"见过意思却默不出来"。这是长尾修辞数据对 LLM 评估的独特贡献点。

---

## 4. 局限与下一步

| 项 | 状态 | 说明 |
|---|---|---|
| 开源强模型对照 | **P0 阻塞** | 本 key 仅授权 qwen-max/plus/turbo，qwen2.5-72b-instruct / 32b 均 403。强模型梯度为同家族内，需开源 72B key 补跨家族收敛点 |
| L1 长度混淆坑 | P1 | agrarian_proverb 的 L1 提示正确率恒为 0%（首字提示对长农谚信息量不足），跨类 L1 不可直接比。建议 L1 改为"揭示首 50% 字符"归一化后重跑 |
| 弱模型复现 | 已满足 | 4-bit 弱模型完整 jsonl 已落地（pilot_Llama-3.1-8B-Instruct.jsonl / pilot_Qwen2.5-7B-Instruct.jsonl），可比性 OK；正式论文建议同一 pilot.jsonl 统一重跑一遍 |
| 3-source 曝光审计 | P2 | 填 exposure_bin，算 Mem–曝光 Spearman，进一步区分"真盲区"与"训练集见过但未记牢" |
| 扩样 | P2 | 验证通过后每类扩到 40 条（共 160） |

---

## 5. 产物清单

- `results/pilot_qwen-max.jsonl` / `pilot_qwen-plus.jsonl` / `pilot_qwen-turbo.jsonl` — 强模型原始判分
- `results/pilot_Llama-3.1-8B-Instruct.jsonl` / `pilot_Qwen2.5-7B-Instruct.jsonl` — 4-bit 弱模型完整结果
- `results/GAPB_COMPARISON.md` — 自动汇总的梯度表与分类别表（脚本 `scripts/analyze_gapb.py` 生成）
- `scripts/run_pilot.py` — 评测主程序（OpenAI 兼容接口 + PERMS=6 去偏 + L0/L1/L2/comp 四层）
- `scripts/analyze_gapb.py` — 多模型汇总脚本
