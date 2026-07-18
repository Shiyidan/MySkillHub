# ESAT Legacy 诊断组卷流程

组卷只消费已经完成解析、中文解析、图形还原和 ESAT 范围标注的 canonical 年度 JSON。它不修改单题质量字段。内部先构建并校验 `assembled_exam`，然后确定性投影为六个可直接导入项目的完整试卷 JSON。

## 1. ESAT-only

- 仅适用于 ESAT legacy 场景。
- 输入必须来自同一年 ENGAA+NSAA 合并题库，`metadata.source_exam_types` 同时包含两种来源。
- TMUA、STEP 或普通生成题不得使用本流程。

## 2. 年度 6 套组合

ESAT 组合卷以 Mathematics 1 为必选，再从四个进一步模块中选两个：

1. Mathematics 1 + Biology + Chemistry
2. Mathematics 1 + Biology + Physics
3. Mathematics 1 + Biology + Mathematics 2
4. Mathematics 1 + Chemistry + Physics
5. Mathematics 1 + Chemistry + Mathematics 2
6. Mathematics 1 + Physics + Mathematics 2

使用 `assemble-year` 时必须一次生成全部 6 套。

## 3. 模块分段与评分

- 每套卷包含 3 个模块段。
- ESAT 官方完整模块基准为 27 题/40 分钟；legacy 诊断卷不得机械写死每段 40 分钟。
- 每段必须写入 `official_question_count=27`、`official_time_minutes=40`、`actual_question_count`、`suggested_time_minutes` 和 `time_note`。
- 每段必须写入来自 `esat_syllabus.json` 的 `module_code`、`module_label`、`coverage_summary` 和 `syllabus_coverage`。
- 建议限时按 `ceil(actual_question_count × 40 / 27)` 计算；若某模块 0 题，则建议限时为 0 分钟。
- 整卷必须写入 `official_full_test_time_minutes` 和 `total_suggested_time_minutes`，方便系统开发设置三段测试计时器。
- 每题 1 原始分，不倒扣。
- 学生测试和结果解释必须按模块分别进行。
- ESAT 官方结果按模块分别报告 1.0-9.0、一位小数的等级分；换算依赖当次考试 Rasch 等值和考生分布。legacy 诊断卷只能报告模块原始分和正确率，不能伪造官方等级分。
- 总览可以存在，但不能替代模块得分，也不能把 3 个模块粗暴合并成一个官方总分。

## 4. 候选题筛选

题目进入候选池必须满足：

- `target_exam_scope.target_exam == "ESAT"`。
- `target_exam_scope.status == "in_scope"`。
- `target_exam_scope.review_status == "reviewed"`。
- `target_exam_scope.primary_module` 属于当前组合。
- `target_exam_scope.primary_module_code`、`primary_module_label` 与 `esat_syllabus.json` 模块节点一致。
- `target_exam_scope.syllabus_codes` 全部是 `esat_syllabus.json` 中存在的 6 位数字代码。
- `target_exam_scope.syllabus_items` 与 `syllabus_codes` 逐项对应，且 code、label、module、parent、path 与 `esat_syllabus.json` 完全一致。
- `question_type == "multiple_choice"`。
- `is_ai_generated == false`。

默认不纳入：

- `out_of_scope`
- `partially_in_scope`
- `unknown`
- 未复核题
- 非选择题
- AI 生成题

## 5. 缺题处理

缺题时仍然组卷，不得拒绝输出。

- 全部纳入可用题。
- 在 `module_note` 中写明目标题量、实际题量和诊断限制。
- 在 `time_note` 中写明官方 27题/40分钟基准和实际题量对应的建议限时。
- 在 `syllabus_coverage` 中保留空覆盖结构，不能省略字段。
- `diagnostic_confidence` 根据缺口程度降为 `medium` 或 `low`。
- 学生报告应说明：该模块结果只能诊断已覆盖范围，不能等价于完整官方模块。

## 6. 题目过多时的挑选

题量超过目标时，不得简单取前 N 题。按以下优先级稳定挑选：

1. 覆盖更多 ESAT 考纲大类。
2. 难度分布更均衡。
3. ENGAA/NSAA 题源更平衡。
4. 避免同知识点重复堆叠。
5. 优先保留已完整解析、图形还原和来源证据完整的题。
6. 仍无法区分时按年份、来源、原题号和 code 稳定排序。

## 7. 覆盖集中与形式集中

如果题量充足但考纲大类、知识点或考查形式过于集中，仍然组卷，但必须：

- 在 `module_note` 中说明覆盖偏窄。
- 降低 `diagnostic_confidence`。
- 保留完整题目结构和解析，便于系统后续生成学生诊断解释。

## 8. 内部与最终输出

内部 `assembled_exam` 继续保存完整的选题、覆盖、计时、来源和审核信息，用于组卷计算与复验。它默认只在内存中使用；需要调试时可通过 `--canonical-output` 或 `--canonical-output-dir` 另行保存。

最终交付必须是六个独立的项目 JSON。每个文件必须包含：

- 根字段 `code`、`metadata`、`questions`。
- `metadata.paperName/year/duration/examType/paperType/totalQuestions`。
- 三个模块的全部入选题目，按模块顺序排列并从 1 连续编号。
- 字符串 `title`，且等于首个 `content_blocks` paragraph。
- 数组 `answer`，项目题型枚举和当前考纲字段。
- 自包含 SVG 或 data URI 位图，不引用本机文件路径。
- 相同来源题在不同卷中使用相同 `code`。

项目导出时进行以下确定性转换：

- canonical `title` 内容块转换为项目 `title + content_blocks`。
- canonical 标量答案转换为项目答案数组。
- canonical `multiple_choice/free_response` 转换为项目 `single_choice/multiple_choice/short_answer`。
- canonical 知识点和考纲项转换为项目 `knowledge_points/syllabus_points`。
- canonical `correct_solution` 转换为项目 `learning_analysis.solution`。

内部 coverage、module_note、diagnostic_confidence、来源 evidence 和 fingerprint 不进入项目 JSON；它们仍保留在 canonical 或分析产物中。

最终字段模板见 `references/output-template.md`，正式 Schema 为 `../exam-paper-core/schema/project-diagnostic-paper.schema.json`。
