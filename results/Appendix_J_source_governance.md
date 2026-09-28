# Appendix J · Source Governance and Conflict Log

> 数据源：`data/pilot.jsonl`、`results/C5_PENDING_PAGES.md`、`docs/provenance_audit.md`、`docs/DATASHEET.md`、`results/source_flags.json`、`results/DISSOCIATION_EXAMPLES.md`、`results/pilot_qwen-max.jsonl`
> 统计时间：2026-09-28 ｜ 数据集 `v1.0.0-frozen`（658 条）

---

## 第一部分：来源治理与页码回填

### 1. A/B 级来源确认

- 658 条中 A/B 级来源条数：**658 条（100%）**。
- 依据：
  - `docs/DATASHEET.md` §3：「当前 658 条已全部为 A/B 级」（来源分级 A=权威典籍/正式出版物；B=地方政府、媒体、学术文；C=自媒体仅作线索不得上线）。
  - `results/source_flags.json` 的 `below_ab = []`（低于 A/B 级条目数 = 0）。
  - `scripts/source_gate.py`（QC 第三关）确保无 C 级自媒体上线。
- **确认：全部 658 条均为 A/B 级 ✅**

| 指标 | 数值 |
|---|---|
| 数据总条数 | 658 |
| 低于 A/B 级（C 级）条数 | 0 |
| A/B 级占比 | 100% |

### 2. 待核原书页码回填状态

- 曾经标记为「待核原书页码」的条目总数：**98 条**（provenance_audit.md §2；按类别 XHY 81 / YY 11 / AID 6，含 12 部书目）。
- 回填后（C5_PENDING_PAGES.md，2026-09-22 经 `scripts/c5_backfill.py --apply`）：

**（a）精确到页 / 全书定位：32 条**

| 书名 | 条数 | 定位级别 | 页码/卷次 |
|---|---|---|---|
| 《永登县志》（甘肃民族出版社 1997） | 20（XHY-021~051 中 20 条） | 精确页 | 第 733–738 页 |
| 《乐府诗集·清商曲辞·读曲歌》等 | 9（YY-009/010/011/021/022/023/024/034/035） | 卷次 | 卷四四 / 卷四六 · 中华书局 1979 点校本 |
| 《颜氏家训·文章篇》《庄子·应帝王》《礼记·学记》 | 3（AID-049/063/069） | 篇名 + 集释本 | 篇名 + 杨伯峻/中华书局集释本 |

**（b）只到版本 / 类级：63 条（2026-09-28 裁定后）**

| 来源名 | 条数 | 级别 | 裁定结论 |
|---|---|---|---|
| 《中国民间文学集成·陕西卷·谚语集成》 | 61（XHY） | 类级（公开目录仅到「类」，如 事理谚 P3／风土谚 P361，条级页码不可得） | 已核实 · 接受类级引用 |
| 《经典字谜集》 | 2（YY-013/014） | 民间传世，版本与页码待核 | 已核实 · 接受版本级引用 |

**（c）2026-09-28 裁定结论**

| 项目 | 裁定前 | 裁定后 | 结论 |
|---|---|---|---|
| 仍待核（条级页码） | 66 | **63** | 3 条 AID 经核实后已更正来源（见下表，属书目张冠李戴、非仅页码缺失）；余 63 条（陕西卷 61 + 经典字谜集 2）条级页码确证不了，按 C5 红线**诚实保留 limitation 标注**，不剔除、不降级 |
| `source_flags.json` 的 `tbd_page` | 98 | **63** | 原 98 条含已回填精确的 32 条（永登县志 20 + 乐府诗集 9 + 颜氏家训/庄子/礼记 3），2026-09-28 裁定后裁剪为 63 条 |

**3 条 AID 来源张冠李戴 —— 已核实并更正**（原标注书目错误）：

| item_id | 成语 | 原标注来源 | 核实后实际来源 | 核实依据 |
|---|---|---|---|---|
| AID-048 | 区闻陬见 | 《汉书》 | 汉·张衡《东京赋》「目察区陬，司执遗鬼」 | 搜狗百科 / 汉语大辞典 / 一把刀中华成语大词典 一致 |
| AID-051 | 抃风舞润 | 《列子》 | 《宋书》卷八四·孔觊传「直山渊藏引，用不遐弃，故得抃风舞润」 | 教育部《重編國語辭典修訂本》/ 汉典 / 360百科 一致 |
| AID-052 | 曝骨履肠 | 《梁书》 | 《隋书·李德林传》「佐斗嫁祸，纷若猬毛，曝骨履肠，间不容砺」 | 汉典 / 百度百科 / 查字典 一致 |

- 合计：32（精确）+ 63（版本/类级）= 95；另有 3 条 AID 由「待核」经核实转为「已更正精确」。

> 更正说明：原 Appendix J 记「仍待核 66 / `tbd_page` = 66」，与实际数据（`tbd_page` = 98、其中含待核 66）不符，已据实际数据更正为 98 → 63。
> 另：provenance_audit.md §4 示例 XHY-038 =「第 512 页」，与 C5_PENDING_PAGES / pilot.jsonl 实际的「第 733–738 页」不一致；前者为草稿残留，以 pilot.jsonl 实际 733–738 为准。

### 3. 各类别主要来源（Top 5，全名）

**XHY（乡土歇后语）**
1. 《中国谚语集成·陕西卷》（中国民间文学集成全国编辑委员会编，北京：中国ISBN中心，2000，ISBN 9787507601800，815页；陕北谚语/歇后语）— 61 条
2. 咸阳市地方志办公室《长武方言-歇后语》— 52 条
3. 人民日报人民号《乡言俚语·通渭话歇后语》— 29 条
4. 《永登县志》（永登县地方史志编纂委员会编，兰州：甘肃民族出版社，1997，第733–738页）— 20 条
5. 陕西省地方志办公室《石泉方言——歇后语》— 15 条

**YY（谐音隐语 / 字谜）**
1. 经典字谜集（民间传世）— 39 条
2. 高台民间谜语集（高台县人民政府）— 30 条
3. 《乐府诗集·清商曲辞·子夜歌》— 8 条
4. 《乐府诗集》卷四十六·清商曲辞·吴声歌曲·读曲歌（宋·郭茂倩编，中华书局1979年点校本）— 7 条
5. 湖北省政府 hubei.gov.cn — 7 条

**NY（北方农耕隐喻农谚）**
1. 南京市六合区人民政府《谚语》— 31 条
2. 福州市人民政府《闽台民间二十四节气农谚述略》— 31 条
3. 全国农业展览馆《二十四节气经典谚语释义》— 16 条
4. 南通市档案馆《二十四节气与南通气象谚语》— 14 条
5. 人民日报全国党媒《农民伯伯挂在嘴边的农谚》— 6 条

**AID（冷门典故成语）**
1. 《世说新语·言语》— 8 条
2. 《世说新语·德行》— 3 条
3. 《史记·邹阳列传》— 3 条
4. 《世说新语·贤媛》「故有林下风气」— 2 条
5. 《世说新语·赏誉》「季野有皮里阳秋」— 2 条

---

## 第二部分：comp gold 与数据集 answer「冲突」清单 —— 2026-09-28 裁定结论

> **裁定摘要（重要结论）**
> 经逐条核实 **64/64 条**：`data/pilot.jsonl` 的 `comp_task.answer` 与模型文件 `comp_gold` **指向同一个正确项**（`target_meaning`），
> 二者字母不同**仅因 PERMS=6 循环置换造成的跨帧错位**：
> - `comp_task.answer` = **规范帧**字母（`build_pilot.py` 随机定位 gold 后写入，`comp_task.options` 同帧）；
> - `comp_gold` = **shift=0 帧**字母（`run_pilot.py::build_comp(item, shift=0)` 输出，`comp_shown` 同帧）。
>
> 逐条比对 `comp_prompt` + `comp_shown` 六选项 + `target_meaning` 后确认：**64 条 `comp_gold` 项的内容全部等于 `target_meaning`**，
> 而 `comp_task.answer` 在其规范帧内同样等于 `target_meaning`。故这 64 条**并非内容性冲突**，
> 而是把两个不同置换帧的字母直接比对所产生的统计口径误判。
>
> **裁定：64 条全部「已核实 · 无实质内容冲突」。实验侧以 `comp_gold`（内容正确）评分有效，comp 正确率无需改动，论文可直接采用实验侧 comp 口径。**
> 数据集 `comp_task.answer` 在规范帧内同样内容正确，保留原值不予改动。

| item_id | 类别 | target_meaning（真值） | 数据集 answer（规范帧） | comp_gold（shift=0 帧） | comp_gold 选项内容 | 核实结论 | 当前状态 |
|---|---|---|---|---|---|---|---|
| XHY-001 | xiehouyu | 出力不讨好 | F | E | 帮同事熬了一整晚改方案，对方不但不领情，还嫌他多管闲事 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-003 | xiehouyu | 装疯（风） | B | F | 他心里一清二楚，却故意装糊涂把事情糊弄过去 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-004 | xiehouyu | 坐（错）了大茬（差）了 | D | C | 入错了行当，硬撑好几年才发现从头到尾方向就不对 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-005 | xiehouyu | 一场空 | D | A | 忙活大半年拉投资，一家都没谈成，全白费了 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-006 | xiehouyu | 一搭括之 | E | F | 好坏材料不挑不拣，混在一起打包处理掉 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-007 | xiehouyu | 惹厌事体 | E | C | 接了个两头都得罪人的差事，进也不是退也不是 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-008 | xiehouyu | 兜（逗）起闹 | E | C | 本来没事，他偏要在群里挑个话头把大家逗得吵起来 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-009 | xiehouyu | 一个麻一个 | F | D | 两个人谈事情都在应付，谁也不肯往心里去 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-010 | xiehouyu | 越小的越精 | E | F | 别看这孩子年纪最小，算起账来比谁都精明 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-011 | xiehouyu | 趁早（陈枣） | D | A | 他劝合伙人趁早把合同签了，别拖到对方变卦 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-013 | xiehouyu | 胆大不知羞 | C | B | 他当众胡说八道还一脸得意，半点不觉得难为情 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-014 | xiehouyu | 勿稳扎 | A | B | 架子搭得晃晃悠悠，一看就根基不牢 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-015 | xiehouyu | 害人不浅 | F | C | 他随手改了一行配置，害得全组返工整整一周 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-016 | xiehouyu | 人家不夸自家夸 | B | F | 没人称赞他，他就自己夸自己能干 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| XHY-019 | xiehouyu | 没品 | C | A | 粗瓷大碗直接端上正式宴席，显得不成体统 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-001 | phonetic_play | 绝妙好辞 | E | C | 色丝=绝、少女=妙、女之子=好、受辛=辞，四组分字合成 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-002 | phonetic_play | 董卓 | D | F | 千里草=董、十日卜=卓，拆字离合 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-003 | phonetic_play | 门 | C | F | "阑"字去掉"柬"剩下"门"，减笔离合 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-004 | phonetic_play | 贾岛 | B | A | "佳人佯醉"=假倒，谐音贾岛 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-005 | phonetic_play | 鲜 | F | E | 鱼+羊合为"鲜"，合字成谜 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-006 | phonetic_play | 大雁 | E | A | "江南虽好是他乡"——回雁峰为雁南飞终点，春来北归 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-007 | phonetic_play | 悲（碑） | B | E | 满含悲伤却说不出来 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-008 | phonetic_play | 丝→思；匹→匹配 | B | E | 情思投入却不能成双配对 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-009 | phonetic_play | 吾子（梧子） | A | C | 我的心上人啊，懂得这长久的情意 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-010 | phonetic_play | 莲→怜；藕→偶 | A | C | 不爱孤独一身，只愿两心相怜、结为配偶 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-011 | phonetic_play | 芙蓉→夫容；莲→怜 | B | F | 看不清丈夫的容颜，怜爱之心也难以明说 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-012 | phonetic_play | 苦心（黄檗味苦 + 相思之苦） | F | A | 相思之苦一天比一天深 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-013 | phonetic_play | 杯盘狼藉 | D | F | 悲盘郎疾→杯盘狼藉（伤心=悲，细问=盘，夫君=郎，病=疾） | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-014 | phonetic_play | 光阴似箭 | E | B | 光阴寺贱→光阴似箭（尼姑=光头之人，庵=寺，不值钱=贱） | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-015 | phonetic_play | 锡→惜 | C | F | 我心里疼你、惜你，你却不知道 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-016 | phonetic_play | 锡→惜；铅→缘 | E | A | 不知道你是惜我还是与我有缘 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-017 | phonetic_play | 寻思→寻丝；匹→匹配 | B | E | 夜夜如织妇般寻丝（思），盼着与你成双匹配 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| YY-020 | phonetic_play | 嘉鱼 | D | F | 堂屋是家，家鱼谐音嘉鱼 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-002 | allusion_idiom | 一贫如洗，家徒四壁 | E | F | 家中空无一物，极其贫穷 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-003 | allusion_idiom | 惩罚过重，罪轻罚重 | B | C | 别人过错轻微，却给予过重的处罚 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-004 | allusion_idiom | 臣可择主而事，不必从一而终 | A | E | 臣子可以择主而事，不必死守一主 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-006 | allusion_idiom | 少见多怪，或自视不凡 | C | D | 见识少，把寻常事物当作罕见奇物 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-007 | allusion_idiom | 文章或画像经少许点染即神情毕现 | C | B | 寥寥数笔的添饰使神采顿出 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-008 | allusion_idiom | 称美妇女娴雅脱俗、有超逸之风 | C | B | 女子闲雅脱俗、有超逸风度 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-009 | allusion_idiom | 不事修饰，以本来面目示人 | E | D | 不加修饰、一任本真的人 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-010 | allusion_idiom | 静中寓动，安居而神采自见 | D | A | 看似沉静无为，实则精神显发、动静自如 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-011 | allusion_idiom | 衣衫褴褛，形容极度贫困 | B | C | 衣服破烂、补丁叠补丁 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-012 | allusion_idiom | 口头不置可否，内心自有褒贬 | F | A | 口不言而心中有褒贬 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-013 | allusion_idiom | 称美优秀子弟 | A | E | 一门之中的优秀子弟 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-014 | allusion_idiom | 知恩图报；亦指困厄中受人之恩 | A | E | 受恩于困厄之中而后报答 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-015 | allusion_idiom | 刑罚苛滥，社会失常 | D | E | 受刑者众，刑罚滥用导致世态失常 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-016 | allusion_idiom | 极微小的利益 | B | D | 微不足道的利益 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-017 | allusion_idiom | 围城绝粮的极困之境 | E | A | 粮尽援绝、困顿到极点的惨境 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-019 | allusion_idiom | 任期届满，由人接替 | E | D | 任职期满、由他人接替 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| AID-020 | allusion_idiom | 因有财富或才具而招致祸患 | F | E | 因身怀珍异（财、才）而招致杀身之祸 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-002 | agrarian_proverb | 物候反常 → 次年灾异 | F | D | 眼前的细微反常，是后续大变故的预兆 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-004 | agrarian_proverb | 不听人言，只认物候信号定播种时机 | B | C | 不要听人鼓动，要看客观信号再行动 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-005 | agrarian_proverb | 土旺日犯忌 → 之后十八天不宜动土耕作 | C | D | 土旺日若破土或触忌，此后十八天都不可耕作 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-006 | agrarian_proverb | 三遍灌溉水量由少到多再到少的节律 | E | C | 灌溉要分次、水量先少后多再少，循序渐进 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-007 | agrarian_proverb | 作物密植各有所宜（胡麻宜密、谷宜稀） | D | B | 不同对象有不同的适宜尺度，不可一律对待 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-008 | agrarian_proverb | 劣根性至死不改 | E | D | 本性难移，人到老也改不掉积习 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-009 | agrarian_proverb | 各有各的门道 | E | D | 各有各的办法和门路，不必强求一致 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-010 | agrarian_proverb | 数九结束、杨花开放 → 农事全面开始 | A | B | 某个信号一出现，积压的事情会一齐涌到眼前 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-011 | agrarian_proverb | 惊蛰打雷 → 主丰收，米价贱如泥 | A | B | 惊蛰打雷主丰收，粮食多到价格低贱 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-012 | agrarian_proverb | 风向定收成 | A | D | 关键节点上出现某个信号，就能决定成败 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-015 | agrarian_proverb | 月相 → 粮价涨落 | F | D | 人们会把毫不相干的征兆拿来解释行情起伏 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-016 | agrarian_proverb | 农时不可耽误，早种有放大收益 | C | B | 起步时的一点先手，到最后会被放大成显著优势 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-017 | agrarian_proverb | 节气决定作物，误了节令就顾此失彼 | A | D | 各有各的时间窗口，抓错一头的窗口就会丢掉另一头 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |
| NY-019 | agrarian_proverb | 秋作物到期不抽穗 → 全无收成，只能作饲料 | B | E | 错过了该出成果的期限，之后就再无价值可言 | comp_gold 内容 = target_meaning ✅ | 已核实·无实质冲突 |

**统计**：64 条（XHY 15 / YY 18 / AID 17 / NY 14），全部裁定为「已核实·无实质冲突」。
原「冲突原因 = comp 干扰项修订差异」的归因不准确，实为 **PERMS 置换跨帧字母错位**；其中 DISSOCIATION_EXAMPLES 注记 2 提到的 XHY-013 / YY-013 / AID-003 亦同属此类，非内容分歧。
NY-001 实际 C=C 一致，注记「4 条全部冲突」表述过宽，维持此前据数据更正的结论。

> **附带修复**：核实过程中发现 `build_pilot.py` 对 `phonetic_play`（YY）类 `comp_distractors.gold_pos` 硬编码为末位（`len(vals)-1`），
> 而 gold 实际位置为随机位（`answer` 所指），导致 118 条 YY 的 `gold_pos` 元数据与实际不符。
> 已于 2026-09-28 按 `gold_pos = 选项键序中 answer 的位置` 修正。**该字段仅为元数据，不参与评分**（评分用 `comp_task.answer` / `comp_gold`），故不影响任何准确率数字。
