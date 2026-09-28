# YY 与扩量现状澄清 + YY 歧义处置方案（2026-09-21）

> ## ✅ 决策已定（2026-09-21）：用户拍板 **B 路线**
> YY 歧义以 **limitations 声明**处置——**数据不动、不洗样本、不改任务形式**；
> 主结论锚定 XHY，YY comp 精度视为 *exploratory*，不作主结论依据。
> 论文级声明素材已固化至 `results/paper_claims.md`。A / C 两路线放弃。

> 背景：用户以为数据仍停在 177 题、YY 字面泄漏未解、扩量卡住。本轮基于
> `data/pilot.jsonl`（658 行）与第三关/第一关脚本**全量实测**，纠正过时认知，
> 并给出 YY 歧义（第二关过强）的处置方案。

## 一、重大澄清：两项"卡住"实际已完成

### 1. 扩量补量（原决策项 2）—— 已超额达成，无需补量
- 实测规模：**658 题** = XHY 208 + YY 150 + AID 150 + NY 150。
- 目标原为 XHY 150–200 / 其余 150 ≈ 650；当前 XHY 208 已超上限，其余正好达标。
- 第三关（来源）：658 条 **全部 A/B 级，0 低于**（source_gate 全量验证）。
- 唯一遗留：**98 条"待核原书页码"**（来源标注"待核原书页码"，如《永登县志》20 条、
  《乐府诗集·读曲歌》7 条等）。这是**投前核对**项，非数据卡点，不阻断实验。

### 2. YY 字面泄漏（原决策项 4）—— 已通过 comp 重设消除
- 旧版 YY comp：gold = 谐音解谜文本，天然含答案字 → 第一关 67.5% gold-dominant（27 条）。
- 重设后（build_pilot：comp = 谜格/修辞识别）：gold = 谜格定义文本，**不再含答案字**。
- 实测：YY gold 字面占优比例 **2.0%（✅ ≤22%）**。
- 注：literal_gate 仍报 YY 28 条触发"规则1"，但均为 GENRE_DESC 模板文字
  （"谐音双关（…如「丝」谐「思」）"）与谜底的微弱字面重叠；comp 任务根本不考
  target_meaning（考修辞格），故属**指标误报**，不构成构造性泄漏。

## 二、真正待解决：YY 歧义（原决策项 1，第二关过强）

### 现状
- 第二关预跑（换 decoy + 加定义后，gpt-4o-mini 同口径对照）：YY 过强 **−15%**
  （旧 27/30 → 新 23/30）。改文案/decoy 收益极低，已证实。
- 根因（非文案问题）：YY comp 强制"单选一种主要修辞格"，但**真实隐语常多谜格共存**
  （谐音双关歌同时是隐语；字谜既离合又谐音）。模型选另一个"同样合理的手法"被判错
  = **标注/任务内在歧义**。
- 过强分布（`results/yy_overstrong_diagnosis.md`，71 条）：换掉 decoy「会意合成」后，
  残余过强主要来自"gold=物谜/乐府双关，但模型选离合拆字"的**真实谜格歧义**（约 40 条）。

### 三条处置路线
- **A. 自动清洗多解题（减样本）**：用预跑数据识别"gold 与另一谜格均高比例被选中"的
  YY 题，剔除/降级。清洗候选 ≈ `yy_overstrong_diagnosis.md` 的谜格歧义子集（~40 条），
  剔除后 YY 样本约 110。干净但**牺牲样本量**，且删题需谨慎（不为好看改数据）。
- **B. limitations 声明（推荐，与 AID 谨慎处理一致）**：在论文中明示 YY comp 的选择项带
  内在歧义（多谜格共存），**不作为主结论依据**；主结论锚定 XHY（全局最难、字面捷径
  不可用，M-C 分离 +62.3pp 最干净）。**不动数据、不破坏四类可比性**。
- **C. 改任务形式（多选/排序/是非）**：消除强制单选，但**破坏四类口径可比性**，不推荐。

### 本轮落地（默认 B，无损）
- 已拟好 limitations 段落（见第四节），可直接贴论文。
- A 路线**仅做标记、不删数据**，待你拍板是否清洗。

## 三、待办（依赖用户恢复 API）
- 千问（DashScope）额度恢复后，第二关以 3 模型口径**全量重跑 658 条** comp 题，
  出权威干扰项强度报告（当前仅单模型 openlux gpt-4o-mini 可用，且早期只跑过 508 子集）。
- 98 条"待核原书页码"投前由原典核对（AID 3 条未独立核验条目尤需重点：区闻陬见/抃风舞润/曝骨履肠）。

## 四、拟好的论文 limitations 段落（可直接贴）

> **Limitations on the phonetic-play (YY) subset.** The YY comprehension task
> requires selecting the dominant rhetorical device (xiéyīn púnyǔ / líhé chāizì /
> yǐnyǔ cángcí) of a hidden-meaning riddle. Because traditional Chinese riddles
> routinely combine multiple devices within a single surface form (e.g. a
> homophonic love-song that is simultaneously an yǐnyǔ, or a character riddle that
> is both lihé and xiéyīn), the forced single-choice formulation carries an
> inherent annotation ambiguity: a model selecting a *plausible alternative device*
> is scored incorrect even when defensible. Pilot pre-ranking shows YY distractors
> remain ~15% over-attractive after prompt/decoy revision, and the effect is
> structural rather than cosmetic. We therefore treat YY comprehension accuracy as
> *exploratory* and anchor all primary M–C separation claims on the xiehouyu (XHY)
> subset, where literal shortcuts are unavailable (gold-dominant rate 2.0% vs. the
> 22% guard) and the mem→comp gap reaches +62.3pp. The AID subset is likewise
> reported with caution due to its larger cross-family variance.

（中文对应：YY 子集因多谜格共存导致强制单选存在标注内在歧义，故 comp 精度视为探索性，
主结论锚定 XHY；AID 因跨家族方差大同样谨慎报告。）
