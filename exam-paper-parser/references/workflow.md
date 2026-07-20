# 解析主流程

质量必须在过程中生成，而不是在最终检查里补救。每个阶段都要产出可复验文件，并用 `pipeline.py complete` 登记阶段凭据。

开始 `source_inventory` 前先确认试卷类型，并写入 `metadata.paper_type`：真题或真题诊断卷为 `realPaper`，普通模考卷为 `mockPaper`，AI 生成练习卷为 `aiPaper`。用户未说明时必须先询问，不得根据文件名猜测。

## 1. source_inventory

- 枚举题卷、答题册、答案、评分方案和考官报告。
- 记录文件名、SHA-256、页数、考试名称、年份、试卷编号与文件角色。
- 同一年 ENGAA/NSAA 材料用于 ESAT legacy 库时，必须同时纳入同一个年度 JSON，并在来源清单中标明文件归属、年份和目标考试 `ESAT`。

## 2. source_inspection

- 逐页检查题号、选项、公式、图形、页眉页脚和答案来源。
- 对同批次所有题卷执行跨来源重复扫描，至少比较规范化题干、选项内容、图形语义和正确答案；为确认重复、疑似重复和冲突重复分别建立候选组。
- 发现缺页、扫描模糊、答案冲突或页码歧义时，暂停受影响题目，不得猜测。
- 图形只截取可打印题面区域；页眉、脚注、水印或相邻题污染会阻断该题。

## 3. evidence_packets

- 为每道题建立证据包：题面定位、答案定位、官方解析定位、图形资产、来源哈希。
- 同一确认重复组优先只建立一个主事务，证据包同时登记所有来源位置；若已经分别建立事务，`finalize` 仍会在验证全部事务后保守合并并保留审计记录。
- 优先使用矢量提取；失败时再使用渲染裁剪或重绘，并记录原因。
- 证据包是逐题事务的第一输入，后续步骤必须引用上一环节输出。

## 4. question_transactions

每题按固定顺序闭环：

`证据充分性确认 → 题面结构恢复 → 考纲映射 → 独立求解 → 官方答案对齐 → 解题轨迹构建 → 学习分析构建 → 图形复原 → 题内微验证 → 原子提交`

- 独立求解必须在官方答案对齐之前完成。
- `solution_trace` 是中文解析和学习分析的唯一推理来源。
- ESAT legacy 题目必须在考纲映射步骤读取 `../exam-paper-core/syllabus/esat_syllabus.json`，再写入 `target_exam_scope`：使用 `scope_status` 标明 `in_scope`、`out_of_scope`、`partially_in_scope` 或 `unknown`，并给出唯一科目、6 位考纲代码和 `syllabus_items`。
- `syllabus_codes` 必须全部来自 `esat_syllabus.json`，不得使用自由文本旧代码；`syllabus_items` 必须与 code 对应的 label、module、parent、path 完全一致。
- ESAT 的 `in_scope`、`partially_in_scope` 题目必须满足 `target_exam_scope.modules == [subject]`，且 `subject_code` 与考纲科目 code 一致。
- 不在 ESAT 范围内的题目保留在年度 JSON 中，但必须写明 `mapping_reason`，不得进入后续正式组合卷。
- `out_of_scope` 与 `unknown` 题目的 `modules`、`syllabus_codes`、`syllabus_items` 必须为空。
- `mapping_status` 使用 `auto_verified`、`human_verified` 或 `needs_review`；只有前两种可进入组卷。
- TMUA 题目必须在考纲映射步骤读取 `../exam-paper-core/syllabus/tmua_syllabus.json` 和 `references/tmua-output-template.md`。`target_exam_scope.modules` 对 TMUA 表示 Paper，不表示 ESAT 模块；只允许 `Paper 1` 或 `Paper 2`。
- TMUA 每题必须且只能归属一个 Paper，直接写入 `target_exam_scope.modules`。
- TMUA `syllabus_codes` 必须全部来自 `tmua_syllabus.json`，`syllabus_items` 必须与 code 对应的 label、module、parent、path 完全一致；不得写 ESAT 的 Biology/Chemistry/Physics 模块。
- TMUA Paper 1 不得映射到 `Logic & Proof` 知识域；Paper 2 可使用 Mathematics 1、Mathematics 2 和 Logic & Proof。
- TMUA 题型必须是 `multiple_choice`，解析必须逐一解释错误选项；不得声称能从真题 JSON 直接得到官方 scaled score。
- 原子提交后题目片段不可再改；若发现问题，必须让该题事务失效并从对应步骤局部返工。
- 使用 `../exam-paper-core/scripts/question_transaction.py` 创建、推进、校验和回退事务。每次执行 `status` 读取当前必要输出角色，不直接编辑 transaction JSON。
- 原子提交前使用 `prepare-fragment` 计算题目指纹并验证单题片段；最终草稿可直接聚合这些已校验片段。
- `difficulty` 只使用 `easy`、`medium`、`hard`、`composite`。`composite` 仅用于至少两个知识点都实际参与求解的跨考点题，不能把“步骤较多”直接等同于复合。

## 5. independent_review

- 独立复核页码证据、题号连续性、答案一致性、英文题面、中文解析、图形引用、当前考试 syllabus code/label/path 和目标考试范围标注；ESAT 与 TMUA 必须分别按各自模板核对。
- 复核跨卷重复组：题干、选项、正确答案和考纲归属全部一致才标记为确认重复；仅题干相同、图形证据不足或高相似题必须保留，不能自动删除。
- 同题面出现答案或考纲归属冲突时，退回“官方答案对齐”或“考纲映射”步骤，解决前不得导出。
- 复核只做拦截和定位，不直接补写字段。
- 任何不确定内容都回到相应逐题步骤修订。

## 6. export

- 使用 `pipeline.py finalize` 构建并校验唯一正式契约。
- `finalize` 先写出去重审计报告，再把确认重复合并为一条 canonical 题目；报告保留 keeper、excluded 及二者题卷/答案页来源。
- 只有所有阶段凭据和逐题事务均通过，才允许写出 `parsed_exam`。
- 如需按 ESAT 模块组合拆卷，交给 `exam-paper-assembler`，不要在解析流程中筛掉 legacy 来源题。
