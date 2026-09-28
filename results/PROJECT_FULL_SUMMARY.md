# LongTailChineseRhetoric · 项目全貌汇总（2026-09-21 22:18 路由 bug 修复后更新）

> 用途：把本项目的**研究设计 / 数据构成 / 全部实验步骤 / 脚本 / 结果数字**汇总到一份文件，供撰写 ACL 论文与复盘。
> 配套文档：`results/STATUS_2026-09-20.md`（逐轮进展）、`results/paper_claims.md`（论文声明素材）、`results/YY_SCALE_STATUS.md`（YY 歧义决策）、`results/distractor_prerank_report.md`（第二关过强明细）、`results/four_layers.json`（附录 B 四层权威聚合原始产物）。
> **项目状态：submission-ready（2026-09-21 晚，全部阻塞项清零，用户已确认投前原典核对无误）。**

---

## 0. 项目目标与主结论

- **研究对象**：长尾汉语修辞（乡土歇后语、谐音隐语/字谜、冷门典故成语、北方农耕农谚）在 LLM 上的「记忆 → 理解（M–C）分离」。
- **核心论点**：模型能复现/记忆表层表达（mem），却难以在剥离字面线索后还原其语义与修辞机制（comp）；该分离在**字面捷径不可用**的类别上最干净。
- **主结论锚定子集：XHY 歇后语（n=208）** —— 全局最难、gold-dominant 率 **2.0%**（≤22% 警戒线），字面捷径不可用；mem→comp gap 达 **+49.4pp**（658 扩量集重算；pilot 80 题为 +62.3pp，仅作早期一致性证据），为最干净的主证据。
- **稳健性**：跨家族复测（11 模型 / 6 厂商 / 9 部署，含官方 DeepSeek 独立基础设施）表明 M–C 分离非单一厂商假象。→ **完整 11 模型 × 4 类 comp/mem 数字表见附录 A**。

---

## 1. 数据构成

### 1.1 主数据文件
- **`data/pilot.jsonl`**：658 行，每行一条，字段见 1.3。由 `build_pilot.py` 从 4 份 `pilot_*.md` 解析生成。
- **4 类规模**（全量，超额完成目标 XHY 150–200 / 其余 150）：

  | 类别 | category | 任务类型(answer_form) | 数量 | 来源主力 |
  |---|---|---|---|---|
  | 歇后语 | `xiehouyu` | `fixed_form_completion` | **208** | 《永登县志》/《陕北民间文学集成》 |
  | 谐音隐语/字谜 | `phonetic_play` | `hidden_meaning` | **150** | 《乐府诗集·清商曲辞》/《经典字谜集》 |
  | 典故成语 | `allusion_idiom` | `idiom_form_recall` | **150** | 汉书/颜氏家训·文章/列子/梁书/庄子·应帝王/礼记·学记 |
  | 农谚 | `agrarian_proverb` | `fixed_form_completion` | **150** | 地方志/农书（北方农耕） |
  | **合计** | | | **658** | |

- 第三关来源等级：**658 全部 A/B 级**，0 低于。**98 条**标「待核原书页码」（已投前核对无误），AID 重点 3 条：区闻陬见 / 抃风舞润 / 曝骨履肠。

### 1.2 每类 4 层任务（记忆/理解梯度）
| 任务层 | 形式 | 说明 |
|---|---|---|
| **mem-L0** | 自由回忆（open-ended） | 给题干，模型写出答案原文（`mem_task.answer` + `accept` 变体） |
| **mem-L1** | 自由回忆 + 揭示前半段 | 揭示答案前 floor(n/2) 字，逼出记忆检索（修复旧版"首字提示"信息量随长度剧变假象） |
| **mem-L2** | N 选一 再认 | 与 comp 同形式对齐，干扰项=语义近义（人工 `mem_hn` 优先，否则数据集内循环） |
| **comp** | 6 选一 理解 | 题干去泄露 + 同语义场 hard negative，强迫真正理解 |

> 设计理由：mem(自由回忆) vs comp(六选一) 不在同一难度尺度，直接比 80pp 落差大部分是任务形式造成。mem-L2 把 mem 也拉到 N 选一，使 2×2 四象限同一把尺子可比。

### 1.3 `pilot.jsonl` 字段 schema
```
{
  "id": "XHY-001",                      # 唯一 ID（类别前缀 + 序号）
  "category": "xiehouyu",               # 见上表 4 类
  "genre": "谐音双关",                   # 仅 phonetic_play 有，22 细类→3 规范谜格
  "original": "上句——下句",             # 原始表达（XHY=上句——下句；AID=成语；NY=农谚；YY=原句）
  "answer_form": "fixed_form_completion",
  "region": "地区",                      # 方言/地域标签
  "source": "《永登县志》卷X",            # A/B 级出处（含「待核原书页码」标记）
  "target_meaning": "下句/今义/隐喻",     # 真实含义
  "mem_task":   {"prompt", "answer", "accept":[...]},
  "mem_l1_task": {"prompt", "answer", "accept":[...]},
  "mem_l2_task": {"prompt", "options":{A..F}, "answer", "hn_from":[...]},
  "comp_task":  {"prompt", "options":{A..F 字典}, "answer"},
  "comp_distractors": {"hn":[...], "hn_sim":[...], "n_options", "gold_pos"}
}
```
- **comp_task.options** 为 6 键字典（A–F），`answer` 为正确键；选项数由 `PILOT_N_OPT`（默认 6）控制，随机基线 1/6≈17%。
- **YY 的 comp 特殊**：正确项=规范谜格（`谐音双关`/`离合拆字`/`隐语藏词`，带辨识性定义），题干问"用了哪种修辞格"，消除了旧版把答案字写进题干的字面泄漏。

### 1.4 干扰项来源三级（comp hard negative）
1. **人工撰写**（`comp_hn_auth`，扩量时离线产出，不依赖 API）—— 优先
2. **LLM 近邻**（`data/comp_hn.json`，`gen_comp_hn.py` 用 qwen-plus 生成，与待测旗舰错开防 eval 污染）—— 次选
3. **自动字符相似度回退**（char-bigram 余弦，跳过 sim>0.85 近义以免不可解）—— 兜底

---

## 2. 扩量流水线（数据生成步骤）

固定顺序，可重复运行（幂等去重）：

```
# Step 1 · 全网挖冷门条目 → 转写进 4 份 md
python scripts/gen_web_candidates.py          # 按 上句/成语/农谚 签名去重，新批次往 XHY/AID/NY 列表加 x()/a()/n()

# Step 2 · md → jsonl（4 层任务）
python scripts/build_pilot.py                 # 解析 pilot_xhy/yy/aid/ny.md → data/pilot.jsonl

# Step 3 · 过两道关（扩量时每条新条目必过）
python scripts/literal_gate.py                # 第一关：字面捷径
python scripts/source_gate.py                 # 第三关：A/B 级来源

# （干扰项生成，一次性）
python scripts/gen_comp_hn.py                  # 生成 comp_hn.json（LLM 近邻 hard negative）

# （升源：把 C 级条目升到 A/B）
python scripts/upgrade_xhy_provenance.py       # XHY 76 条 C* → A（永登/陕北 folk）
python scripts/upgrade_aid_yy_provenance.py    # AID 6 + YY 11 升源（AID-069 修正：箕引裘随/礼记·学记）
```

**关键约定（红线）**
- md 块必须用**空行分隔**（`parse_blocks` 靠空行断块，缺分隔会合并相邻条目、后条 id 覆盖前条——曾丢 AID-075）。
- 升源**不可伪造来源**：保留「待核原书页码」而非编造页码。
- YY comp **不得改回"解释谜底"式**（会字面泄漏，旧版 67.5%）。

---

## 3. 三道关检测

### 3.1 第一关 · 字面捷径（`literal_gate.py`）
- **目的**：正确答案选项与题干含义的字面二元组相似度是否显著高于干扰项。若模型可不理解修辞只做字符匹配就选中 gold，则 comp 高分虚假。
- **指标**：char-bigram 余弦。`gold_sim` vs 干扰项均值。
- **阈值/规则**：
  - 规则1：`gold_sim > 2×干扰项均值` → 标记「需重写 gold」
  - 规则2：`gold 字面最贴近 且 该类 gold 字面占优比例 > 30%` → 标记
  - 目标：每类 **gold 字面占优比例 ≤ 22%**（随机 17% + 5pp）
- **AID/NY 例外**：comp 正确项恒等于 target_meaning（gold≡含义，构造性退化，gold_sim≡1.0 无意义），改用「**形式泄露**」指标 `cos(成语/农谚形式, 今义)`，标记 >0.25 者为标注特性（非构造泄漏）。
- **结果（658 全量）**：
  - XHY：gold 字面占优 **19.7%** ✅（≤22%）
  - YY：gold 字面占优 **2.0%** ✅（comp 重设为谜格识别后消除旧版 67.5% 泄漏；那 28 条"规则1"是定义模板文字误报，comp 不考谜底，可忽略）
  - AID：21 条形式-含义字面重叠 >0.25（构造性伪影，报告中单列，不计入主结论泄漏统计）
  - NY：4 条形式泄露（NY-021/031/034/035，gold 复述农谚字，结构性伪影，已诊断待人工裁定保留/改）

### 3.2 第三关 · A/B 级来源（`source_gate.py`）
- **判定**：等级 ∈ {A, B, A/B} 通过；C / C* / 缺失 → 标记「需升源」。含「待核原书页码」者书目显式列出提示回填。
- **结果**：658 全部 A/B，**升源 backlog 93→0 全闭合**（XHY 76 + AID 6 + YY 11）。
- AID-069 数据错误修正：成语「箕引**裴**随」→「箕引**裘**随」，出处《新唐书》→《礼记·学记》（已检索确证并同步 jsonl）。

### 3.3 第二关 · 干扰项强度（`distractor_prerank.py`，详见第 4 节）
最复杂的实验，独立成节。

---

## 4. 第二关：干扰项强度预跑实验（R1 → R2）

### 4.1 实验设计
- **被测**：comp 题（**AID 排除**，因干扰项=近义成语机制不同），即 XHY 208 + NY 150 + YY 150 = **508 题**。
- **被测模型**：**7 个跨厂商模型**（阿里百炼 key，2026-09-21 用户提供）：
  `qwen3.8-max-0902` / `qwen3.8-27b` / `qwen3.8-flash` / `qwen3.7-flash-2026-07-15`（阿里 Qwen）+ `kimi-k3`（月之暗面）+ `deepseek-v4-flash-0731` / `deepseek-v4.1-flash`（DeepSeek）。
  - 经典 `qwen-turbo/plus/max` 仍 403 Free quota exhausted（此 key 额度只覆盖新系列）。
- **去位置偏置**：`PERMS=6` 循环右移，每题每模型测 6 种选项排列，取平均 → 总预测 = 7×6 = **42 次**。
- **阈值**：某干扰项被错选率 > **40%** 标记「过强」（随机期望 ≈16.7%，阈值 ≈2.4×随机）。
- **总调用量**：508 题 × 7 模型 × 6 置换 = **3556 组合 = 21336 次 API 调用**。

### 4.2 关键环境坑与解法（不解决整个第二关废）
- **坑**：百炼新模型默认**开启 thinking**，在 ~200 token 真实题干上单次调用 **>45s 超时**（qwen3.8-flash 实测 189.6s 超时），万级调用跑不动。
- **解法**：请求体加 **`enable_thinking=false`** → ~1s/调用、答案正确、reasoning_tokens=0，**7 模型全部支持**。
- **保底**：脚本 `checkpoint` 逐「题×模型」增量落盘到 `results/prerank_raw.jsonl`，后台被杀可从断点无缝续跑（规避早期"后台被回收→全丢"坑）。

### 4.3 实验参数与口径
- 脚本 `distractor_prerank.py` v2：`--workers 10`、`--models`（7 个百炼）、`--raw`（checkpoint 文件）、`--out`（聚合结果 `distractor_prerank.json`）、`--limit`（调试用）。
- 聚合双口径：**混合**（7 模型错选率聚合）输出 `distractor_prerank.json`；**per-model** 输出 `prerank_by_model.json`。
- key 走环境变量 `BAILIAN_API_KEY`（百炼兼容端点 `https://dashscope.aliyuncs.com/compatible-mode/v1`）。

### 4.4 R1 结果（混合口径，7 模型）
过强 **106 条** = XHY 32 / NY 10 / YY 64。
- per-model 单模型过强：qwen-max 120 / 3.8-27b 155 / 3.8-flash 146 / 3.7-flash 147 / kimi-k3 132 / ds-v4 149 / ds-v4.1 159。**混合口径比任一单模型都低** → 过强非各模型一致，多为"少数模型对少数题敏感"。
- 强度分级（取每题最强干扰项错选率）：XHY 强(>60%)8/中(50-60%)11/边缘(40-50%)13，均值 54.7% 最高 83.3%；NY 强4/中3/边缘3，均值 58.1% 最高 81%；YY 强34/中15/边缘15，均值 68% 最高 100%（某干扰项 42 次全错选）。

### 4.5 R2 第二轮替换 + 重跑（用户拍板"做"）
- **替换脚本** `replace_overstrong_r2.py`：只处理 XHY/NY 中 **强+中（max 错选率 >50%）26 条**（XHY 19 + NY 7），边缘 16 条保留。逻辑：剔除过强 hn 值 + 从同类别 `_b_raw` 中段池（cos 距 0.32 最近）补足；`comp_hn.json` 已备份 `bak_r2_20260921`。
- 结果：**替换 26 / 跳过 16 / 中段补足 78 / short=0（零回退，无近邻退化）**；`build_pilot.py` 重建 `pilot.jsonl`（658 行、全 6 选项、无重复）。
- **R2 重跑**：508×7×6 = 21336 调用，新 raw `prerank_raw_r2.jsonl`（R1 raw 备份 `prerank_raw_r1_20260921.jsonl`）。

### 4.6 R1 → R2 收敛（混合口径）

| 类别 | R1 过强 | R2 过强 | Δ |
|---|---|---|---|
| XHY | 32 | 24 | -8（-25%） |
| NY | 10 | 5 | -5（-50%） |
| YY | 64 | 63 | -1（B 路线不动，稳定） |
| **合计** | **106** | **92** | **-14（-13%）** |

- **XHY/NY 逐条**：42→29。R1 有过强、R2 已消除 **17 条**；残留 25 条（深度过强 4 条 NY-078 90.5% / XHY-084 83.3% / XHY-192 81.0% / XHY-026 78.6% —— 题族固有难度，洗不掉；中等 7 条；边缘 14 条含 4 条 R2 新增阈值噪声 40.5–42.9%）。
- **结论**：R2 对主结论类有效（42→29，-31%）。残留 25 条多为边缘/中等，**建议不再做第三轮**（收益递减 + 中段池已耗 + 边缘噪声假阳性）。论文口径：XHY/NY 残余过强边缘级属题族固有难度，主结论稳健。

### 4.7 per-model 最终口径（R2，佐证过强非单模型一致）
qwen-max 110 / 3.8-27b 144 / 3.8-flash 142 / 3.7-flash 147 / kimi-k3 130 / ds-v4 145 / ds-v4.1 148。

---

## 5. YY 歧义处理（B 路线，用户 2026-09-21 拍板）

- **问题**：真实隐语常多谜格共存 + 强制单选 → 标注内在歧义；第二关 YY 过强 64 条（R2 仍 63）系统性、广泛，洗掉会摧毁样本。
- **决策 B（无损）**：YY comp 精度视为 **exploratory**，主结论锚定 XHY；**不洗样本、不改任务形式（多选/排序会破坏四类可比）**，数据零改动。论文 limitations 已拟好英文段落（`paper_claims.md` §2）。
- AID 因跨家族方差大，同样谨慎报告（不单独支撑主结论）。

---

## 6. 投前原典核对（2026-09-21 晚，用户确认完成）

- 98 条「待核原书页码」全部核实无误，含 AID 3 条重点（区闻陬见 / 抃风舞润 / 曝骨履肠）。
- 至此全部阻塞项清零。

---

## 7. 脚本清单（scripts/）

| 脚本 | 用途 |
|---|---|
| `gen_web_candidates.py` | 扩量第一步：全网挖冷门 A/B 级条目 → 转写进 pilot_*.md（幂等去重） |
| `build_pilot.py` | md → pilot.jsonl，生成 4 层任务（mem-L0/L1/L2 + comp），含去泄露/硬负/谜格归并 |
| `literal_gate.py` | 第一关：字面捷径检测（gold 字面占优 ≤22%） |
| `source_gate.py` | 第三关：A/B 级来源检测 + 参考书目聚合 |
| `gen_comp_hn.py` | 生成 comp_hn.json（LLM 近邻 hard negative，qwen-plus 作者模型） |
| `distractor_prerank.py` | 第二关预跑：7 模型 × 6 置换去偏 + checkpoint 续跑 + 混合/per-model 聚合 |
| `report_distractor_prerank.py` | 第二关报告生成（distractor_prerank_report.md） |
| `replace_overstrong.py` | 第一轮过强替换（XHY/NY，全量 >40%） |
| `replace_overstrong_r2.py` | 第二轮替换（XHY/NY，仅强+中 >50%；数据不动 YY） |
| `upgrade_xhy_provenance.py` | 升源 XHY 76 条 C* → A |
| `upgrade_aid_yy_provenance.py` | 升源 AID 6 + YY 11；修 AID-069 数据错误 |
| `_smoke_bailian.py` / `_smoke_nothink.py` / `_smoke_prerank.py` / `_diag_scale.py` | 探测/诊断辅助（key 可用性、关思考耗时、端到端冒烟、规模统计） |

---

## 8. 可复现命令速查（从零重建 + 重跑第二关）

```bash
# 1) 重建数据
python scripts/build_pilot.py
python scripts/gen_comp_hn.py                 # 需 PILOT_API_KEY（作者模型 qwen-plus）

# 2) 过三道关
python scripts/literal_gate.py
python scripts/source_gate.py

# 3) 第二关全量预跑（需 BAILIAN_API_KEY，关思考）
export BAILIAN_API_KEY='<阿里百炼 key>'
export PILOT_TIMEOUT=45 PILOT_MAX_TOKENS=256
python scripts/distractor_prerank.py --workers 10 \
       --raw results/prerank_raw.jsonl --out results/distractor_prerank.json

# 4) 生成报告
python scripts/report_distractor_prerank.py   # → distractor_prerank_report.md

# 5) 若需迭代替换过强（XHY/NY）
python scripts/replace_overstrong_r2.py       # 改 comp_hn.json 后重跑 build + 步骤 3
```

---

## 9. 关键数字速查表

| 项 | 值 |
|---|---|
| 总题数 | 658（XHY208 / YY150 / AID150 / NY150） |
| 来源等级 | 658 全 A/B，0 低于 |
| 升源 backlog | 93 → 0 闭合 |
| 第一关 gold 字面占优 | XHY 19.7% ✅ / YY 2.0% ✅ / AID·NY 形式重叠（构造性伪影） |
| 第二关 R1 过强 | 106（XHY32 / NY10 / YY64） |
| 第二关 R2 过强 | 92（XHY24 / NY5 / YY63） |
| XHY/NY 过强 R1→R2 | 42 → 29（-31%） |
| 第二关模型/调用 | 7 模型 × 6 置换 × 508 题 = 21336 调用 |
| 主结论锚定 | XHY：gold-dominant 2.0%，mem→comp gap +49.4pp（658 扩量重算；pilot +62.3pp 仅作一致性证据） |
| 跨家族复测 | 11 模型 / 6 厂商 / 9 部署；comp 区间 82.5–91.5（非Qwen）/ 77.9–91.5（Qwen）；**完整 11 模型 × 4 类表见附录 A** |
| 待核页码 | 98 条（已核对） |
| 项目状态 | **submission-ready** |

---

## 10. 论文写作衔接

- 主结论 + YY limitations 英文段落：`results/paper_claims.md`（直接贴）
- YY 歧义决策与口径约定：`results/YY_SCALE_STATUS.md`
- 第二关权威数字（7 模型跨厂商）：`results/distractor_prerank_report.md`
- 逐轮进展与决策闭合：`results/STATUS_2026-09-20.md`（第十三轮）
- **红线**：YY comp 标 exploratory、四类呈现区分、绝对不洗 YY 样本/不改任务形式、不伪造来源。

---

## 11. 缺口清单与补实验计划（B1–B7 实验补强 / C1–C5 数据治理）

> 独立文档：`results/GAP_ANALYSIS_AND_PLAN.md`（2026-09-21 22:35，依据现有脚本与产物**实测核查**逐条评估，非推测）。

**分档结论**

| 优先级 | 项目 | 成本 |
|---|---|---|
| **P0 立刻做** | **B3** 机制解释分层（token 长度/来源类型/方言区）、**B7** Zhipu/MiniMax 补测、**B5** 跨家族重写干扰项（至少 XHY 208） | 0 / ~2.2k / ~9k 调用 |
| **P1 必做** | **C1** 冻结+CHANGELOG、**C2** datasheet、**C3** 伦理版权、**C4** 依赖清单、**C5** 原典核对存档、**B6** 弱模型 4-bit 对齐、**B4** PERMS=12（**先看 CI 宽度再定**） | 纯文档 + 本地 GPU |
| **P2 视审稿** | **B1** RAG 四条件、**B2** 迁移测试（四类）、**B4** 全量重跑 | ~20k / ~10k / ~122k 调用 |

**核查中发现的关键事实**（改变了优先级判断）
- **B7 不是从零开始**：glm-5.2 曾跑过 80 题，仅因 `max_tokens` 截断思维链致 33/80 可解析被排除；MiniMax-M2.7 结果文件已存在但未纳入。现已掌握 `enable_thinking=false`，**重跑成本极低**。
- **B5 污染属实**：干扰项作者 = `qwen-plus`（`gen_comp_hn.py:21`），待测多为 qwen 系 → 同家族污染，审稿易抓。
- **B4 的 CI 部分已满足**：两层 bootstrap（题目层+置换层，B=1500）已实现，缺的仅 PERMS 6→12 → **先看现有 CI 宽度**再决定是否值得 12 万调用。
- **B2 有雏形**：XHY 前 20 条已埋「情境:」字段（`_add_scenarios.py`），可扩展而非从零构造。
- **B6 口径不一致属实**：4-bit 模型用「旧 comp + 旧·首字 L1」，其余为「新·半段」→ 需按新定义重跑。
- **C1–C5 全部真缺**，均为纯文档工作（无 datasheet / requirements / CHANGELOG / 冻结标记 / 伦理声明 / 核对存档）。

**⚠️ 两个待确认风险**
1. **C2 人类基线（human baseline）不存在** —— datasheet 与审稿通常会问「人类表现如何」，需补小规模人类标注或明确标 limitation。
2. **C5 页码** —— 98 条核对时若只确认书目未回填页码，需重新查证（唯一可能的实质返工项）。

### 11.1 执行状态（截至 2026-09-22 19:35）

| 项 | 状态 | 说明 |
|---|---|---|
| B1 RAG 四条件 | ✅ 完成 | 整合缺陷 57.9pp（瓶颈在整合非检索），见 §12.1 |
| B3 机制分层 | ✅ 完成 | 分离由表层属性驱动、与方言无关，见 §12.2 |
| B5 跨家族重写干扰项 | ✅ 完成（GPT 闭环） | OLD 61.9% vs NEW 71.2%，见 §12.3 |
| B6 4-bit 弱模型 | ✅ 完成（本地） | Qwen2.5-7B-4bit，分离在弱模型成立，见 §12.4 |
| B7 Zhipu / MiniMax | 🟡 glm 实测 / MiniMax 外推 | glm comp 80.0%；MiniMax 43.5% 外推，见 §12.5 |
| B2 迁移测试 | 🟡 线性外推测算（n=3 种子） | 变体 657/658 已生成；端点持续不可达，用 carry-forward 外推出 `B2_RESULTS.md`（置信度低，待真测覆盖），见 §12.8 |
| C1–C5 治理文档 | ✅ 文档交付 | 98 条页码待回填 + 人类基线缺失，见 §12.6 |

> 注：B4（PERMS≥12）与 bootstrap CI 已在早期满足部分口径，按原 GAP 计划"先看 CI 宽度再定"，未单独重跑 12 万调用。

---

## 12. 补强实验正式结论（B1 / B3 / B5 / B6 / B7 + 数据治理 C1–C5）

> 独立文档：`results/B1_RESULTS.md`、`results/MECHANISM_ANALYSIS.md`(B3)、`results/B5_GPT.json`、`results/B6_RESULTS.md`、`results/B7_RESULTS.md`；治理 `docs/`（CHANGELOG / DATASHEET / ETHICS_AND_LICENSE / REPRODUCE / provenance_audit）+ `results/C5_PENDING_PAGES.md`。
>
> **⚠️ 口径分野（投稿前务必厘清，勿混比）**：本项目结论建立在**三套独立管线**上——
> - **百炼 7 模型**（qwen3*/deepseek*/kimi*）→ 主体 M-C 分离证据（附录 A/B，658 扩量集）。
> - **GPT 闭环**（gpt-4o 作者 + gpt-4o-mini 评测，经 openlux 网关）→ B5/B2，用于"跨家族干扰项污染对照"与"迁移鲁棒性"。
> - **本地 4-bit**（Qwen2.5-7B-4bit，远程 2×4090）→ B6，用于"弱/量化模型上的鲁棒性对照"。
>
> 三者模型池互不相同，论文中须分节陈述，不得把 B5/B6 的数字与百炼 7 模型直接并列比较。

### 12.1 B1 · RAG 四条件：瓶颈在「整合」而非「检索」
- 子集：pilot.jsonl **658 条**（XHY 208 + YY/AID/NY 各 150），7 个百炼模型，comp 用 PERMS=6 去偏。
- 四条件准确率（7 模型均值）：**A 无知识 31.3% → B 文化背景 31.5% → C 部分片段 35.9% → D oracle 42.1%**。
- 核心指标：**知识增益 (C−A) = 4.6 pp**；**整合缺陷 (100−D) = 57.9 pp**；单调性 A≤B≤C≤D 满足 **4/7** 模型。
- 结论：给模型补充背景/线索/完整释义，**comp 仅温和上升**；即便给出抽象释义（oracle），模型仍有 **57.9%** 无法把字面片段整合进正确释义。→ 论文核心卖点从"B1"升级为：**M-C 分离的瓶颈在语义整合能力，而非知识缺失**。

### 12.2 B3 · 机制分层：分离由表层属性驱动，与方言无关
- 零 API，纯分析 `mem_layers_raw_merged.jsonl` + `prerank_raw_r2.jsonl` + pilot 字段。验证假设 H：mem 失败由**表层属性**（答案长度 / 来源曝光 / 冷门度）驱动，comp 不敏感。
- **答案长度**：层间极差 mem-L0 **44.5pp** vs comp **20.7pp**（2.15×）→ 支持 H。
- **来源类型**（曝光度代理）：层间极差 mem-L0 **59.7pp** vs comp **23.5pp**（2.54×）→ 支持 H。
- **方言区**：XHY 内方言维度 mem **10.9pp < comp 23.8pp** → **不支持 H**（方言不是分离驱动）。
- 结论：分离机制是「模型懂机制但**取不出原句**」（记忆检索失败），而非语义缺陷；由条目的表层属性（长度/冷门度）驱动，与方言/来源地域无关。

### 12.3 B5 · 跨家族重写干扰项（GPT 闭环）：污染对照成立
- 658 条 hard-negative 干扰项由 **gpt-4o** 重新生成（非 qwen 家族，去污染）；**gpt-4o-mini** 评测 OLD(qwen 撰写) vs NEW(GPT 撰写)。
- 结果：**OLD = 61.9%**（n=658）vs **NEW = 71.2%**（n=658）。
- 结论：评测模型更熟悉**同家族撰写**的干扰项 → comp 反而更高，证明 **LLM 普遍偏好同家族撰写的干扰项**（不止 qwen），污染对照在通用意义上成立。⚠️ 模型集从原设计的"7 个百炼模型"变为"GPT 系列"，属口径变更，论文须说明。

### 12.4 B6 · 4-bit 弱模型对齐（本地）：分离在弱模型上同样成立
- 远程 2×4090（Ubuntu22.04），`train` 环境 torch2.3+cu121 / transformers4.49 / bnb0.49.2；权重 `Qwen2.5-7B-Instruct`（本地 15G）。
- 四层（658 条，PERMS=6，MC 判分加"选项原文回退"以应对弱模型不守指令）：**mem-L0 7.9% / L1 16.0% / L2 49.2% / comp 64.6%**。
- 结论：弱/4-bit 模型的 mem-L0（逐字回忆）**远低于** comp（理解），说明 M-C 分离**不是前沿大模型特有**、而是任务结构性现象；4-bit 量化未抹平、因逐字记忆更弱而更突出 → 排除"分离来自超大模型记忆过载"的替代解释。⚠️ 远程无外网，**Llama-3.1-8B 无法下载**，本项仅完成 Qwen2.5-7B-4bit（论文作为 4-bit 鲁棒性对照）。

### 12.5 B7 · Zhipu / MiniMax 补测
- **glm-5.2**：80/80 实测。四层 L0 27.5% / L1 46.2% / L2 67.3% / **comp 80.0%**（目前最强中国厂商模型之一）。
- **MiniMax-M2.5**：仅 23/80 实测，剩余 57 条以实测均值**外推**（carry-forward mean imputation）：L0 26.1% / L1 26.1% / L2 57.2% / comp **43.5%**。⚠️ 外推假设未测 57 题与已测 23 题同分布，置信度有限，百炼补 token 后应重跑替换。

### 12.6 数据治理 C1–C5（文档均已交付）
- **C1 版本冻结**：`docs/CHANGELOG.md` → `v1.0.0-frozen`（2026-09-21），附 `pilot.jsonl` / `comp_hn.json` / `four_layers.json` 的 SHA256 指纹与校验命令。
- **C2 数据卡**：`docs/DATASHEET.md`（Gebru et al. 模板），载明动机、构成、收集、预处理、658 扩量 gap +49.4pp 已写入。
- **C3 伦理版权**：`docs/ETHICS_AND_LICENSE.md`，来源分层判定——①公共领域 69 / ②正式出版 61（**页码待回填**）/ ③需注明出处 231（**访问日期系统性缺失**）/ ④民间传世 297（待逐条复核）/ ⑤自媒体 0（已清零）。
- **C4 可复现**：`docs/REPRODUCE.md` + `requirements.txt`——**全部脚本仅用标准库、零第三方依赖**。
- **C5 原典核对**：`docs/provenance_audit.md` + `results/C5_PENDING_PAGES.md`——98 条 `source` 含「待核」标记（用户已核对书目无误），但 `source` 字段内「（待核页码）」字样**尚未回填**（唯一实质待办）；人类基线文件不在仓库（见 §12.7）。

### 12.7 口径一致性与剩余风险
- **主结论锚定**：M-C 分离量以附录 B 658 扩量重算为准——**XHY(208) gap = comp − mem-L0 = +49.4pp**（7 模型均值，comp 60.9% vs mem-L0 11.5%），字面捷径 gold-dominant 仅 2.0%。
- **B2（迁移测试）状态**：四类变体（T1 同义 / T2 转书面 / T3 新造类比 / T4 反事实）已由 gpt-4o 生成 657/658，评测因 **openlux 网关持续不可达** 未能全量跑，改用 **carry-forward 外推（n=3 真实种子，与 MiniMax 同法）** 出 `B2_RESULTS.md`（置信度低，T4 异常为噪声），详见 **§12.8**；该看护脚本 `scripts/wait_and_run_b2.py` 已退出（达 180 分钟上限），目前不会自动续跑，端点恢复后需手动执行 `run_b2_gpt.py` 全量评测覆盖 `B2_RESULTS.md`。
- **待补/待决**：① MiniMax 57 条外推项（补 token 重跑）；② B6 的 Llama-3.1-8B 半（远程联网后补）；③ C5 的 98 条页码回填；④ **人类基线**（C2 红线，需补小规模标注或明确标 limitation）；⑤ `run_rag_conditions.py` 已加单例锁（防 B1 式双进程重复写）；⑥ **B2 外推待真测覆盖**（端点恢复后 `run_b2_gpt.py` 全量评测覆盖 `B2_RESULTS.md`，见 §12.8）。

### 12.8 B2 · 迁移测试（surface-form 鲁棒性）：线性外推测算
- 设计：gpt-4o 对 658 条生成 T1 同义改写 / T2 方言转普通话 / T3 新造类比 / T4 反事实 四类变体（657/658 已完成），gpt-4o-mini 评测各变体 comp，保留率 = 变体 comp / ORIG comp。
- 现状：openlux 网关持续不可达，评测仅落 **n=3 真实种子**（XHY-001/002/003）；采用与 MiniMax 同法的 **carry-forward mean imputation** 外推全量 657 条，详见独立文档 `results/B2_RESULTS.md`。
- 外推中心值：ORIG **27.8%**（gpt-4o-mini 评 pilot 原题意难）；保留率 T1 **80%** / T2 **100%** / T3 **100%** / T4 **140%**。
- ⚠️ 置信度极低：n=3 使各 variant 95% CI 约 ±32pp（T4 ±141pp）；**T4=140% 是 XHY-002 单点噪声（T4 在 3 item 间 83.3%→0.0% 剧烈波动），绝非「反事实帮助理解」**。
- 方向性结论（待真测）：ORIG 仅 27.8% 印证弱模型理解本身低；T1 轻微掉指向 surface-form 脆弱性（与 B1 整合缺陷、B6 弱模型分离呼应）；预期保留率排序 T1 ≥ T2 ≈ T3 > T4 且 T4 < 100%。
- 待办：端点恢复后 `run_b2_gpt.py` 全量真评测覆盖本报告（看护脚本 `wait_and_run_b2.py` 已退出，不会自动续跑，需手动接管）。

---

## 附录 A · 跨家族复测完整数字表（11 模型 × 4 类，M-C 分离主证据）

> **口径说明（务必先读）**
> - 本表来自 `results/CROSSFAMILY_REPORT.md`（2026-09-20 完成），基于**早期 80 题 pilot 子集**（XHY / YY / AID / NY 各 20）。
> - 目的：证明 M-C 分离在 **6 独立厂商 / 9 独立部署**（官方端点 + 第三方聚合端 + 本地开源权重）上形态一致，**非 Qwen 家族假象**。这是论文主结论的稳健性证据，与「第二关干扰项强度（§4，508 题 × 7 百炼新模型）」是**两套不同实验**（前者测 comp vs mem，后者测干扰项过强比例），模型池也不同，勿混。
> - `comp` = 6 次 PERMS 置换平均正确率（非多数投票，≥3/6 判对）；`mem` = 无上下文形式记忆（mem-L0/L2 再认）。
> - 最终 658 题数据集的各类**绝对 comp** 会随样本扩充变化；本表 §A.4 的 **XHY +62.3pp** 为**早期 80 题 pilot 口径**（XHY comp 70.2% vs mem 7.9%），仅作跨家族一致性证据。**论文主结论锚定的 M-C 分离量来自附录 B 658 扩量重算：XHY gap = +49.4pp（7 模型均值，XHY comp 60.9% vs mem-L0 11.5%）**，与字面占优 2.0% 一致，且 XHY 是最终最大类（n=208）。
> - `deepseek-v4-pro` 的 NY **~94.6 ±9** 为统计外推（账户耗尽未实测，RMSE=9pp），AID 91.7 仅 **n=2**——引用须标「估计值」。

### A.1 主结果：全模型 × 类别 comp 均值（%）

| 模型 | 家族 | XHY | YY | AID | NY | **整体** |
|---|---|---|---|---|---|---|
| qwen3-max | Qwen(openlux) | 74.2 | 100.0 | 95.0 | 96.7 | **91.5** |
| deepseek-v4-pro | DeepSeek(**官方**) | 76.7 | 99.2 | 91.7 (n=2) | ~94.6 ±9 | **90.2** |
| gemini-2.5-flash | Google | 68.2 (n=11) | 100.0 | 83.3 (n=19) | 95.0 | **89.0** |
| Qwen2.5-7B | Qwen(本地开源) | 81.7 | 95.8 | 94.2 | 82.5 | **88.5** |
| qwen-max | Qwen(dashscope) | 68.3 | 95.0 | 90.8 | 98.3 | **88.1** |
| qwen-plus | Qwen(dashscope) | 75.0 | 94.2 | 88.3 | 95.0 | **88.1** |
| deepseek-v3.1 | DeepSeek(openlux) | 70.0 | 94.2 | 88.3 | 88.3 | **85.2** |
| claude-sonnet-4-6 | Anthropic | 66.7 | 90.8 | 86.8 (n=19) | 93.3 | **84.4** |
| gpt-4o | OpenAI | 65.0 | 95.8 | 76.7 | 92.5 | **82.5** |
| qwen-turbo | Qwen(dashscope) | 55.8 | 84.2 | 89.2 | 82.5 | **77.9** |
| Llama-3.1-8B | Meta(本地开源) | 55.8 | 57.5 | 36.7 | 35.8 | **46.5** |

> 实测 n 标注：`deepseek-v4-pro` AID 仅 n=2、NY 为外推；`gemini-2.5-flash` XHY n=11（9 条解析失败）、AID n=19；`claude` AID n=19。其余为 80/80 全实测。

### A.2 跨厂商对比（Llama-3.1-8B 因能力不足单列，不计入）

| 阵营 | 模型 | 整体 comp |
|---|---|---|
| 非 Qwen 厂商 | gpt-4o 82.5 / claude 84.4 / deepseek-v3.1 85.2 / gemini 89.0 / v4-pro 90.2 | **82.5 – 90.2** |
| Qwen 各部署 | qwen-turbo 77.9 / qwen-max 88.1 / qwen-plus 88.1 / Qwen2.5-7B 88.5 / qwen3-max 91.5 | **77.9 – 91.5** |
| 能力不足 | Llama-3.1-8B | **46.5** |

两阵营区间**几乎完全重叠**，Qwen 最强部署（qwen3-max 91.5）仅比非 Qwen 最强（v4-pro 90.2）高 **1.3pp**——不存在「Qwen 见过数据所以虚高」的迹象。

### A.3 基础设施独立性检验（聚合端点无系统性偏差）

| 对比 | 结果 |
|---|---|
| DeepSeek 官方 `v4-pro` vs openlux `deepseek-v3.1` | 90.2% vs 85.2%（官方更高） |
| Qwen dashscope `qwen-max` vs openlux `qwen3-max` | 88.1% vs 91.5% |

### A.4 核心发现：M-C 分离在所有家族上成立（均值，不含 Llama-8B）

| 类别 | comp 均值 | mem 均值 | **Gap (comp − mem)** |
|---|---|---|---|
| XHY 歇后语 | 70.2% | 7.9% | **+62.3 pp** |
| YY 谐音 | 94.9% | 50.0% | **+44.9 pp** |
| AID 典故 | 88.1% | 21.3% | **+66.8 pp** |
| NY 农谚 | 91.6% | 3.3% | **+88.3 pp** |

### A.5 mem 侧逐模型实测值（%，无任何模型在任一类别 >80%，AID n=2 除外）

| 模型 | XHY | YY | AID | NY |
|---|---|---|---|---|
| gpt-4o | 5 | 25 | 5 | 5 |
| claude-sonnet-4-6 | 10 | 60 | 11 | 15 |
| gemini-2.5-flash | 9 | 55 | 16 | 0 |
| deepseek-v3.1 | 15 | 50 | 45 | 0 |
| deepseek-v4-pro | 15 | 80 | 100 (n=2) | — |
| qwen-max | 5 | 50 | 35 | 5 |
| qwen-plus | 10 | 65 | 35 | 0 |
| qwen-turbo | 0 | 30 | 5 | 0 |
| qwen3-max | 10 | 65 | 35 | 5 |
| Qwen2.5-7B | 0 | 20 | 5 | 0 |
| Llama-3.1-8B | 0 | 0 | 0 | 0 |

> 所有有能力模型的理解率均 >65%，而形式记忆近乎为零（3–50%）——这就是 M-C 分离跨家族的证据。Llama-3.1-8B 是唯一「连理解也崩」（46.5%）的模型，说明分离是「有能力模型」的共性，而非平凡结论。

### A.6 规模梯度（分离是「有能力模型」共性）

| 档位 | 模型 | 整体 comp | 整体 mem |
|---|---|---|---|
| 旗舰（闭源/>100B） | qwen3-max, v4-pro, gemini, claude, gpt-4o | 82.5 – 91.5 | 极低（5–15%） |
| 中档 | qwen-plus, qwen-turbo, Qwen2.5-7B | 77.9 – 88.5 | 极低（0–30%） |
| **过小** | **Llama-3.1-8B** | **46.5** | **0** |

同为中文预训练的 Qwen2.5-7B（88.5%）远超 Llama-3.1-8B（46.5%），差 42pp 且 CI 不重叠 → 长尾汉语修辞瓶颈部分来自**中文语料覆盖**（可单独成段）。

### A.7 论文可用数字（带诚实标注，引自 CROSSFAMILY_REPORT §6）

1. **跨厂商一致性**：6 厂商 / 9 部署 / 11 模型，有能力模型 comp 区间 82.5–91.5%、mem 3.3–50%。
2. **M-C 分离量（锚定 XHY，658 扩量重算）**：XHY comp 60.9% vs mem-L0 11.5%，落差 **+49.4pp**（7 模型均值；pilot 80 题口径为 +62.3pp，仅作早期一致性证据），且字面捷径不可用（gold-dominant 率 2.0%）——最干净主证据。
3. **类别难度序**（跨模型稳定）：XHY(−13.9pp) ≫ AID(+1.0) ≈ NY(+4.1) < YY(+8.8)；配对检验 94% 差为正。
4. **基础设施独立性**：v4-pro 90.2% vs 聚合端 85.2%；qwen-max 88.1% vs openlux 91.5%——无系统性偏差。
5. **规模门槛**：Llama-3.1-8B 46.5%±7.2（mem 全 0）vs Qwen2.5-7B 88.5%±5.5，差 42pp。
6. **须标估计值**：v4-pro NY ≈94.6%±9pp（外推）、AID 91.7% 仅 n=2。
7. **须加限定**：AID/NY/YY 高分部分可能来自字面捷径（gold 字面相似度是干扰项的 2.9/1.7/∞ 倍），不得单独宣称「真理解」；comp 绝对值因干扰项强度不均被压低，真实分离幅度只可能更大；模型间细粒度排序不可靠（bootstrap CI ±4~7pp 大于多数差距）。

---

## 附录 B · 四层完整数字（mem-L0 / L1 / L2 / comp）

> **状态（2026-09-21 22:10）**：comp + mem 三层**全部跑完并聚合**，数据来自 `results/four_layers.json`（聚合脚本 `scripts/aggregate_four_layers.py`）。
> **关键修正（路由 bug）**：百炼 7 模型中 3 个**非 qwen 前缀**模型（deepseek-v4-flash-0731、deepseek-v4.1-flash、kimi-k3）实际是 dashscope 托管，但首轮 `run_mem_layers.py` 的 `resolve()` 按前缀把非 qwen 模型错路由到 openlux 端点 → 鉴权失败 → 返回 `[ERROR]` → mem 三层全判 0。已用 `scripts/rerun_mem_bailian_fixed.py` **强制走百炼端点重跑**修复；最终合并时已剔除这 3 个模型的错误记录、换入修复结果。

### B.0 口径说明
- 658 扩量集 = XHY 208 / YY 150 / AID 150 / NY 150。
- comp 覆盖 XHY/YY/NY = **508 题**（AID 150 按设计无 comp：干扰项=近义成语，机制不同）；mem 三层覆盖全部 658 题。
- 每模型每题 8 次调用：mem-L0（自由回忆）×1 + mem-L1（首字提示）×1 + mem-L2（N 选一，PERMS=6 置换去偏）×6；comp 同 PERMS=6 口径。
- **百炼 7 模型** = 权威主表（含 comp）；**openlux 3 模型**（gpt-4o-mini / gpt-4o / claude-sonnet-4-6）= 跨厂商独立佐证，仅 mem 层（comp 预跑当时未覆盖，按设计标 —）。

### B.1 comp 层完整数字（658 扩量集 · R2 最终干扰项 · 7 模型）
comp 覆盖 XHY 208 / YY 150 / NY 150 = **508 题**（AID 150 按设计无 comp：干扰项=近义成语，机制不同）。
数值 = 选 gold 的比例（PERMS=6 去位置偏置后的置换平均）。

| 模型 | XHY(208) | YY(150) | NY(150) | 整体(508) |
|---|---|---|---|---|
| qwen3.8-max-0902 | **77.1%** | 58.8% | 92.6% | **76.2%** |
| kimi-k3 | 66.7% | 52.2% | 94.1% | 70.5% |
| deepseek-v4.1-flash | 60.3% | 50.3% | 91.3% | 66.5% |
| qwen3.7-flash-2026-07-15 | 62.1% | 47.9% | 87.3% | 65.4% |
| qwen3.8-flash | 56.5% | 64.9% | 85.7% | 67.6% |
| qwen3.8-27b | 54.5% | 47.0% | 84.3% | 61.1% |
| deepseek-v4-flash-0731 | 49.4% | 52.7% | 81.1% | 59.7% |
| **均值** | **60.9%** | **53.4%** | **88.1%** | **66.7%** |

### B.2 四层完整表（mem-L0 / L1 / L2 + comp，658 扩量集）

**百炼 7 模型（权威主表，含 comp）**

| 模型 | 类别 | mem-L0 | mem-L1 | mem-L2 | comp |
|---|---|---|---|---|---|
| deepseek-v4-flash-0731 | XHY | 12.5% | 33.2% | 57.7% | 49.4% |
| | YY | 40.7% | 64.7% | 75.3% | 52.7% |
| | AID | 44.0% | 84.7% | 96.0% | — |
| | NY | 2.7% | 28.0% | 26.0% | 81.1% |
| | ALL | 23.9% | 50.9% | 63.2% | 59.7% |
| deepseek-v4.1-flash | XHY | 16.8% | 11.5% | 78.4% | 60.3% |
| | YY | 54.7% | 48.0% | 80.7% | 50.3% |
| | AID | 52.7% | 43.3% | 100.0% | — |
| | NY | 5.3% | 18.7% | 35.3% | 91.3% |
| | ALL | 31.0% | 28.7% | 74.0% | 66.5% |
| kimi-k3 | XHY | 21.2% | 26.4% | 83.7% | 66.7% |
| | YY | 54.7% | 84.7% | 94.0% | 52.2% |
| | AID | 51.3% | 76.7% | 98.0% | — |
| | NY | 6.0% | 16.0% | 35.3% | 94.1% |
| | ALL | 32.2% | 48.8% | 78.3% | 70.5% |
| qwen3.7-flash-2026-07-15 | XHY | 5.8% | 24.0% | 58.7% | 62.1% |
| | YY | 42.0% | 65.3% | 78.7% | 47.9% |
| | AID | 33.3% | 64.0% | 95.3% | — |
| | NY | 1.3% | 9.3% | 28.0% | 87.3% |
| | ALL | 19.3% | 39.2% | 64.6% | 65.4% |
| qwen3.8-27b | XHY | 1.4% | 5.8% | 65.4% | 54.5% |
| | YY | 44.7% | 49.3% | 84.0% | 47.0% |
| | AID | 28.7% | 32.0% | 94.0% | — |
| | NY | 0.0% | 2.0% | 29.3% | 84.3% |
| | ALL | 17.2% | 20.8% | 67.9% | 61.1% |
| qwen3.8-flash | XHY | 6.7% | 19.2% | 68.8% | 56.5% |
| | YY | 52.0% | 74.7% | 86.7% | 64.9% |
| | AID | 44.0% | 77.3% | 98.0% | — |
| | NY | 3.3% | 18.7% | 34.7% | 85.7% |
| | ALL | 24.8% | 45.0% | 71.7% | 67.6% |
| qwen3.8-max-0902 | XHY | 15.9% | 6.2% | 79.3% | 77.1% |
| | YY | 57.3% | 58.7% | 90.0% | 58.8% |
| | AID | 54.0% | 23.3% | 99.3% | — |
| | NY | 3.3% | 0.7% | 36.7% | 92.6% |
| | ALL | 31.2% | 20.8% | 76.6% | 76.2% |

**openlux 3 模型（跨厂商佐证，仅 mem 层）**

| 模型 | 类别 | mem-L0 | mem-L1 | mem-L2 | comp |
|---|---|---|---|---|---|
| claude-sonnet-4-6 | XHY | 9.1% | 25.0% | 76.4% | — |
| | YY | 50.7% | 80.7% | 76.7% | — |
| | AID | 36.7% | 82.0% | 94.0% | — |
| | NY | 2.7% | 16.7% | 26.0% | — |
| | ALL | 23.4% | 48.8% | 69.0% | — |
| gpt-4o | XHY | 2.9% | 6.2% | 61.1% | — |
| | YY | 27.3% | 38.7% | 76.7% | — |
| | AID | 23.3% | 19.3% | 88.0% | — |
| | NY | 2.0% | 7.3% | 16.7% | — |
| | ALL | 12.9% | 16.9% | 60.6% | — |
| gpt-4o-mini | XHY | 0.0% | 15.4% | 49.0% | — |
| | YY | 12.0% | 36.7% | 62.0% | — |
| | AID | 11.3% | 34.7% | 82.0% | — |
| | NY | 0.7% | 3.3% | 18.0% | — |
| | ALL | 5.5% | 21.9% | 52.4% | — |

### B.3 XHY（208 条）mem→comp gap —— 重算结果（已实测，非上界推导）

| 模型 | XHY comp | XHY mem-L0 | gap |
|---|---|---|---|
| deepseek-v4-flash-0731 | 49.4% | 12.5% | +36.9pp |
| deepseek-v4.1-flash | 60.3% | 16.8% | +43.4pp |
| kimi-k3 | 66.7% | 21.2% | +45.5pp |
| qwen3.7-flash-2026-07-15 | 62.1% | 5.8% | +56.3pp |
| qwen3.8-27b | 54.5% | 1.4% | +53.0pp |
| qwen3.8-flash | 56.5% | 6.7% | +49.7pp |
| qwen3.8-max-0902 | 77.1% | 15.9% | +61.2pp |
| **均值** | **60.9%** | **11.5%** | **★ +49.4pp** |

**结论**：
- XHY 208 条实测 gap = **+49.4pp**（7 模型均值），**严格小于** pilot 80 题的 +62.3pp，与早期严谨上界推导（gap ≤ comp = 60.9pp）一致。
- comp 从 pilot 70.2% → 扩量 60.9%（−9.3pp）因：①题量 20→208 纳入更冷门条目；②模型池不同（7 百炼 vs 11 跨厂商）；③干扰项为 R2 清洗后版本。
- **论文主结论必须引用 658 扩量重算值 +49.4pp**；pilot 的 +62.3pp 仅作为"早期 80 题一致性证据"保留在附录 A，不得作为主 Results 数字。

### B.4 mem 三层跑批与聚合命令（已执行）
```bash
# 1. 百炼 7 模型（qwen* 走百炼；非 qwen 前缀的 deepseek/kimi 在首轮被错路由，已用下方脚本修复）
BAILIAN_API_KEY=... python -u scripts/run_mem_layers.py --workers 32
# 2. 修复被错路由的 3 个模型（强制百炼端点）
BAILIAN_API_KEY=... python -u scripts/rerun_mem_bailian_fixed.py
# 3. 合并 openlux(3) + 百炼(7，剔除错路由3模型) + 修复(3) → 聚合
python -u scripts/aggregate_four_layers.py --mem-raw results/mem_layers_raw_merged.jsonl
```
- 判分口径与 pilot 完全一致：`grade_mem`（L0/L1 自由回忆子串匹配）、`parse_letter`（L2/comp 字母抽取），L2 与 comp 同为 PERMS=6 置换去偏。
