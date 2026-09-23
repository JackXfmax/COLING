# CHANGELOG · LongTailChineseRhetoric（数据治理 C1 · 版本冻结与变更日志）

> 配套文档：`docs/DATASHEET.md`（数据卡）、`docs/ETHICS_AND_LICENSE.md`（伦理版权）、`docs/REPRODUCE.md`（可复现）、`docs/provenance_audit.md`（原典核对）。
> 治理规范母本：`data/annotation_standard.md` §十二「版本控制」。

---

## 🧊 当前冻结版本：`v1.0.0-frozen`（2026-09-21）

**定义**：`pilot.jsonl` 扩量定稿版（**658 条**），经三道 QC 关（字面 / 干扰项 / 来源）+ 两轮过强项替换 + 端点路由 bug 修复后冻结。**论文所有主结果引用本版本数据及其聚合产物。**

### 冻结对象与指纹

| 文件 | 内容 | SHA256 | 行数 | 字节 |
|---|---|---|---|---|
| `data/pilot.jsonl` | 主数据集 658 条 | `76f923851c86d568191a739dc3171c8249fba1c6158ae5ce36218ce85a37cd06` | 658 | 1,319,474 |
| `data/comp_hn.json` | 手写 hard-negative 干扰项库 | `0980d0de2829eb9073c9d772c8997c08f0137081bfca6744a5168ba26f71bbc1` | 1781 | 75,708 |
| `results/four_layers.json` | 四层聚合结果（权威产物） | `9dcc165d2f98a3863e15803d20546f4576a4e4f62e2290841ab2104c12a4f20f` | 341 | 7,422 |

**校验方法**（任何人拿到数据都应先跑这一步）：
```bash
python -c "import hashlib;print(hashlib.sha256(open('data/pilot.jsonl','rb').read()).hexdigest())"
```
> ⚠️ 若哈希与上表不符 → 数据已被改动，**论文数字必须重算**。

### 冻结快照：数据构成

| 类别 | 代码 | 条数 | comp 覆盖 |
|---|---|---|---|
| 乡土歇后语 | `xiehouyu`（XHY） | **208** | ✅ |
| 谐音隐语 / 字谜 | `phonetic_play`（YY） | 150 | ✅ |
| 冷门典故成语 | `allusion_idiom`（AID） | 150 | ❌（按设计：干扰项=近义成语，机制不同） |
| 北方农耕隐喻农谚 | `agrarian_proverb`（NY） | 150 | ✅ |
| **合计** | | **658** | **508** |

- 答案形式：`fixed_form_completion` 358 ／ `idiom_form_recall` 150 ／ `hidden_meaning` 150
- 每条含 **4 层**任务：mem-L0（自由回忆）／ mem-L1（前半提示）／ mem-L2（N 选一）／ comp（理解）

### ⚠️ 冻结范围**外**（未完成项，论文必须声明为局限性）

| # | 缺口 | 状态 | 影响 |
|---|---|---|---|
| 1 | `exposure_bin` 字段 | **658/658 全为 `TBD`**（空壳） | 冷门度无实测三源审计值；现以 `source` 类型作代理 |
| 2 | 98 条 `source` 仍含「待核页码」 | 核对结果**未回填**数据 | 需回填后清除标记，见 C5 |
| 3 | 人类基线数据 | 用户已完成但**未入库**（不在项目目录） | datasheet 与审稿必问，见 C2 §8 |
| 4 | comp 干扰项同家族污染 | 作者=`qwen-plus`，待测多 qwen 系 | **B5 正在修**（全量 508 重写） |

### 版本政策

- 候选池 / pilot / 正式版**分开标号，互不复用号段**（母本 §十二）
- 任何数据改动 → **升 minor 版本** + 本 CHANGELOG 记录 + **重新哈希** + 同步更新 DATASHEET
- **cameraready 期间禁止改动数据**；若必须改 → 升 `v1.1.0` 并**重跑全部实验**

---

## 变更沿革

> 说明：v0.x 代号与日期依据 `data/` 下文件快照的 mtime **推定**（项目无 git 仓库），用于描摹数据演进脉络；自 v1.0.0-frozen 起为正式冻结记录。

### v1.0.0-frozen · 2026-09-21 — 扩量定稿 + 冻结
- 数据集 481 → **658 条**（XHY 208／YY 150／AID 150／NY 150），全部 6 选项、A/B 级来源
- **三道 QC 关**：①字面捷径（XHY gold-dominant **2.0%**，≤22% 警戒线）；②干扰项预跑收敛（R1→R2，混合口径过强 106→92，XHY/NY 42→29）；③来源升级（AID 6 + YY 11 升源）
- **修复端点路由 bug**：3 个非 qwen 前缀模型（deepseek×2 + kimi）被错送 openlux 端点 → mem 三层全 0；改 `resolve()` 并强制重跑修复
- 四层权威结果重聚合：**XHY(208) mem→comp gap = +49.4pp**（7 模型均值：comp 60.9% vs mem-L0 11.5%）
  > 取代 pilot 80 题口径的 +62.3pp；后者降级为附录 A 早期一致性证据

### v0.95 · 2026-09-20 — 扩量 tranches + 第一轮过强替换
- AID 典故成语 +44 条、NY 农谚 +23 条、YY 谐音隐语 +110 条（3 谜格）陆续入库（`pilot_ny.md` 18:12 / `pilot_aid.md`·`pilot_yy.md` 21:05）
- 第一轮过强干扰项自动替换（`comp_hn.json.bak_before_replace_20260920` 22:07）

### v0.9 · 2026-09-18 — pilot v9 / v9b / probe_xy
- `pilot.jsonl.bak_v9`(11:45) → `bak_v9b`(11:51)；此前 `bak_probe_xy`(10:21) 为 XY 探针版本
- 此阶段为真 pilot 80 题口径（每类前 20 条），后期的跨家族 11 模型表即此子集

### v0.7 · 2026-09-16 — 类别落地与去重
- `pilot_aid.md.bak`(21:45) → `.bak2`(23:25)；`pilot_yy.md.bak`(23:34)

### v0.5 · 2026-09-15 — 治理前置规范定稿（"先不跑"阶段）
- `annotation_standard.md` **v0.5 定稿**（22:44）：冷门度三源测量法、来源 A/B/C 分级、mem/comp 配对、RAG 四条件、曝光审计、人类验证协议、数据划分、伦理版权、版本控制
- `candidates.md` 候选池建立（22:48）
- 严守「先不跑」：本阶段只修订规范与候选池，不写 schema / 不跑 pipeline

---

## 后续待升版事件（触发 v1.1.0）

- [ ] B5 完成 → 全量 508 题干扰项替换为非 Qwen 家族重写版 → 数据变，`comp` 全量重跑
- [ ] C5 完成 → 98 条页码回填，`source` 字符串变更 → `pilot.jsonl` 重哈希（**注意：仅改元数据不改答案，须在 CHANGELOG 明示"无答案变更"**）
- [ ] 曝光审计（3-source）跑完 → `exposure_bin` 由 TBD 填实值 → v1.2.0
