# 论文级声明素材 · LongTailChineseRhetoric（2026-09-21 定稿）

> 用途：撰写 ACL 论文时直接引用的 **主结论 claim 锚定** 与 **limitations 文本**。
> 配套决策文档：`results/YY_SCALE_STATUS.md`（YY 歧义 B 路线，用户 2026-09-21 拍板）。
> 本文件为论文写作规范，不改任何数据。

---

## 1. 主结论（Primary Claim）

- 长尾汉语修辞存在稳定的「记忆 → 理解（M–C）分离」现象：模型能复现/记忆表层表达，
  却难以在剥离字面线索后还原其语义与修辞机制；该分离在**字面捷径不可用**的类别上最干净。
- **锚定子集：XHY（歇后语，n = 208）**——全局最难、gold-dominant 率 **2.0%**（≤22% 警戒线），
  字面捷径不可用；mem→comp gap 达 **+62.3pp**，为最干净的主证据。
- 跨家族复测（11 模型 / 6 厂商 / 9 部署，含官方 DeepSeek 独立基础设施）表明
  M–C 分离非单一厂商（如 Qwen）的假象，而是跨基础设施一致的规律。

---

## 2. YY（phonetic_play）子集处理 —— Limitations 定稿（B 路线）

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

中文对应（供方法/讨论节参考）：YY 子集因真实隐语多谜格共存，强制单选存在标注内在歧义，
故其 comp 精度视为探索性，主结论锚定 XHY；AID 因跨家族方差较大同样谨慎报告。

---

## 3. AID（典故成语）谨慎声明

- AID 跨家族方差较大，不单独支撑主结论，仅作为跨类别一致性的佐证之一。
- 第一关标记 21 条「形式–含义字面重叠 >0.25」为构造性退化（gold≡含义），属标注特性，
  非构造泄漏；报告中单列说明，不计入主结论的泄漏统计。

---

## 4. 分析口径约定（写 paper / 跑后续分析时贯彻）

1. **YY comp 一律标注 *exploratory***：不进入主结论数值统计（主 gap 表只列 XHY / AID / NY，
   YY 单列探索列），避免误导读者其与主结论同口径。
2. **四类呈现区分**：YY 的 comp 列与 AID / NY 明确区隔；XHY 为主锚点列于首位。
3. **第二关干扰项强度**：API 恢复后以 **3 模型口径全量重跑 658 条** comp 题，
   YY 过强率仅作探索性附注（当前单模型 openlux gpt-4o-mini 仅跑过 508 子集）。
4. **绝对不洗 YY 样本、不改 comp 任务形式为多选/排序**，保持四类可比口径（B 路线红线）。

---

## 5. 数据完整性声明（投前核对项，非实验卡点）

- 658 条全 A/B 级来源；**98 条标「待核原书页码」** 投前由原典核对。
  重点：AID 3 条未独立核验条目——**区闻陬见 / 抃风舞润 / 曝骨履肠**。
- 第三关升源 backlog **93 → 0 全闭合**（XHY 76 + AID 6 + YY 11）。
- 第一关 YY 字面泄漏已通过 comp 重设（谜格识别）消除，实测 **2.0%**（STATUS 旧记 12.5% 为
  早期子集口径，以全量实测为准）。
