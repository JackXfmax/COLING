# LongTailChineseRhetoric (LTCR)

> 测量大语言模型在**中国乡土长尾修辞**上的「记忆–理解分离」(mem–comp dissociation) 的基准与评测套件。

---

## 一句话简介

主流中文 LLM 基准集中在高频成语与通用推理，而中国乡土长尾修辞——县域歇后语、谐音隐语、冷门典故成语、北方农耕隐喻农谚——从未被系统测量。我们把「**取得出原句吗**」(mem, 形式记忆) 与「**拿到知识后能否理解修辞义**」(comp, 语义整合) **解耦成两层任务**，从而分离两种失败模式：

- mem 低 + comp 高 ⇒ **记忆检索失败**（懂机制，取不出原句）
- mem 低 + comp 低 ⇒ **语义理解缺失**（真不懂）

---

## 数据集 (`data/pilot.jsonl`)

共 **658** 条，四类别：

| 类别 | 代码 | 条数 | 是否有 comp | 典型地域 |
|---|---|---|---|---|
| 乡土歇后语 | `xiehouyu` | 208 | ✅ | 陕北 / 陕西长武 / 甘肃通渭 / 陕西石泉 / 甘肃永登 |
| 谐音隐语 / 字谜 | `phonetic_play` | 150 | ✅ | 传世灯谜 / 民间谜语 / 吴地 |
| 冷门典故成语 | `allusion_idiom` | 150 | ❌（设计上不参与 comp 统计） | — |
| 北方农耕隐喻农谚 | `agrarian_proverb` | 150 | ✅ | 江苏六合 / 福建·台湾 / 江苏南通 |
| **合计** | | **658** | **508** | |

> ⚠️ 地域代表性偏斜：XHY 集中于晋陕甘县域，NY 集中于苏闽。引用时须声明样本偏斜，不可外推为「全中国汉语方言」。

每条 item 含 `original`(本体) / `source`(出处，仅溯源不评分) / `mem_task` / `mem_l1_task` / `mem_l2_task` / `comp_task` 等字段。完整字段说明见 [`docs/DATASHEET.md`](docs/DATASHEET.md)。

---

## 四级评测口径

| 层 | 名称 | 形式 | 判分 |
|---|---|---|---|
| **mem-L0** | 自由回忆 | 开放生成 | `grade_mem` 前 40 字子串匹配 |
| **mem-L1** | 前半提示 | 开放生成（揭示前 `⌊n/2⌋` 字） | `grade_mem` |
| **mem-L2** | N 选一 | 六选一 | `parse_letter` + `PERMS=6` 循环置换去位置偏置 |
| **comp** | 理解 | 六选一 | 同上 |

关键设计：把 mem 也拉到「六选一」(L2) 与 comp 同尺度，才能公平比较形式记忆再认 vs 理解再认；`PERMS=6` 消除模型无脑选固定位置字母的偏置。

**核心发现（658 扩量版）**：在乡土歇后语 (XHY, 208) 上，7 模型均值 **comp 60.9% vs mem-L0 11.5%，gap = +49.4pp**，且 XHY 字面捷径 gold-dominant 仅 **2.0%** ⇒ 支持「记忆检索失败」而非语义缺陷。分离现象跨架构（Qwen / Llama）稳健。

---

## 目录结构

```
LongTailChineseRhetoric/
├── data/
│   ├── pilot.jsonl            # 主数据集（658 条）
│   ├── comp_hn.json           # 手写 hard-negative 干扰项
│   ├── annotation_standard.md # 标注规范
│   ├── candidates.md          # 候选原始素材
│   └── prompts/               # 各层评测 prompt 模板
├── scripts/                   # 评测与处理脚本（run_mem_layers / build_pilot / remote_gpu 等）
├── docs/                      # DATASHEET / REPRODUCE / ETHICS_AND_LICENSE / provenance_audit / CHANGELOG
├── results/                   # *.md 聚合报告（PROJECT_FINAL_REPORT / DISSOCIATION_EXAMPLES / B1-B7 / C5 等）
└── README.md
```

> 注：每模型原始输出 `*.jsonl`、日志、`*.pdf` 版权文件、`.workbuddy/` 等项目内存已按 `.gitignore` 排除，不公开。

---

## 复现

详见 [`docs/REPRODUCE.md`](docs/REPRODUCE.md)。评测需使用者自备 API（百炼 / openlux 端点）或本地 4-bit 权重，**仓库不含任何密钥**。远程 GPU 助手 `scripts/remote_gpu.py` 的主机/用户名/密码均通过环境变量 `REMOTE_HOST` / `REMOTE_USER` / `REMOTE_PW` 注入，无硬编码。

---

## 引用

```bibtex
@inproceedings{ltcr2026,
  title     = {LongTailChineseRhetoric: Probing the Memory--Comprehension Dissociation of LLMs on Chinese Rural Long-Tail Rhetoric},
  author    = {Xu, Fei and others},
  booktitle = {Proceedings of COLING},
  year      = {2026},
  note      = {Benchmark and evaluation suite: \url{https://github.com/JackXfmax/COLING}},
}
```

---

## 许可

- **代码**：MIT（见 [`LICENSE`](LICENSE)）
- **数据集** `data/pilot.jsonl` 及其衍生标注：拟以 **CC BY-SA 4.0** 发布（最终以 [`docs/ETHICS_AND_LICENSE.md`](docs/ETHICS_AND_LICENSE.md) 为准）

---
