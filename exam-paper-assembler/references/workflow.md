# ESAT Legacy 诊断组卷流程

组卷只消费已经完成解析、中文解析、图形还原和 ESAT 范围标注的 canonical 年度 JSON。它不修改单题质量字段。内部先构建并校验 `assembled_exam`，然后确定性投影为六个新版模块分组项目 JSON。

## 1. ESAT-only

- 仅适用于 ESAT legacy 场景。
- 输入必须来自同一年 ENGAA+NSAA 合并真题库，`metadata.paper_type=realPaper`，且 `metadata.source_exam_types` 同时包含两种来源。
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

### 批量发布规则

- 六套组合先写入隔离暂存目录，全部通过 canonical、项目 Schema 和整包一致性校验后再发布。
- 整包校验必须确认文件名与六种标准组合完全一致、每套模块及顺序正确、每段固定 40 分钟、每套固定 120 分钟、单卷无重复题，并确认同一模块在不同组合卷中的题目与顺序一致。
- 最终目录采用目录级事务替换；任一发布步骤失败时恢复完整旧目录，不允许出现新旧文件混合。
- 成功发布时以本次六套卷完整替换旧目录，自动清除旧版本遗留文件。
- 通用 `title` 会自动追加模块组合；需要自定义格式时使用含 `{year}`、`{modules}` 占位符的 `title_template`。

## 3. 模块分段与评分

- 每套卷包含 3 个模块段。
- ESAT 官方完整模块基准为 27 题/40 分钟；完整组合诊断卷必须把每个模块目标题量锁定为 27，调用方不得覆盖。
- 每段必须写入 `official_question_count=27`、`official_time_minutes=40`、`actual_question_count`、`suggested_time_minutes` 和 `time_note`。
- 每段必须写入来自 `esat_syllabus.json` 的 `module_code`、`module_label`、`coverage_summary` 和 `syllabus_coverage`。
- 无论实际题量是否不足 27，`suggested_time_minutes` 和 `official_time_minutes` 均为 40；完整三模块组合卷总时长固定为 120 分钟。
- 整卷必须写入 `official_full_test_time_minutes=120` 和 `total_suggested_time_minutes=120`，方便系统开发设置三段测试计时器。
- 每题 1 原始分，不倒扣。
- 学生测试和结果解释必须按模块分别进行。
- ESAT 官方结果按模块分别报告 1.0-9.0、一位小数的等级分；换算依赖当次考试 Rasch 等值和考生分布。legacy 诊断卷只能报告模块原始分和正确率，不能伪造官方等级分。
- 总览可以存在，但不能替代模块得分，也不能把 3 个模块粗暴合并成一个官方总分。

## 4. 候选题筛选

题目进入候选池必须满足：

- `target_exam_scope.target_exam == "ESAT"`。
- `target_exam_scope.scope_status == "in_scope"`。
- `target_exam_scope.mapping_status` 为 `auto_verified` 或 `human_verified`。
- `subject` 属于当前组合，`target_exam_scope.modules == [subject]`。
- `subject_code` 与 `esat_syllabus.json` 中该科目的模块 code 一致。
- `target_exam_scope.syllabus_codes` 全部是 `esat_syllabus.json` 中存在的 6 位数字代码。
- `target_exam_scope.syllabus_items` 与 `syllabus_codes` 逐项对应，且 code、label、module、parent、path 与 `esat_syllabus.json` 完全一致。
- `question_type == "multiple_choice"`。
- `is_ai_generated == false`。

默认不纳入：

- `out_of_scope`
- `partially_in_scope`
- `unknown`
- `mapping_status == "needs_review"` 的题目
- 非选择题
- AI 生成题

## 5. 缺题处理

缺题时仍然组卷，不得拒绝输出。

- 全部纳入可用题。
- 在 `module_note` 中写明目标题量、实际题量和诊断限制。
- 在 `time_note` 中写明官方 27 题/40 分钟基准、实际题量以及仍固定使用 40 分钟。
- 在 `syllabus_coverage` 中保留空覆盖结构，不能省略字段。
- `diagnostic_confidence` 根据缺口程度降为 `medium` 或 `low`。
- 在最终项目 JSON 的 `metadata.remarks` 中写明题量缺口、覆盖偏窄和中文可信度提示，供管理员导入前核对。
- 学生报告应说明：该模块结果只能诊断已覆盖范围，不能等价于完整官方模块。

## 6. 题目过多时的挑选

题量超过目标时，不得简单取前 N 题。先比较规范化题干、选项内容、正确答案和考纲归属：四者一致的确认重复题只保留一题，并把保留 code、排除 code、原因及来源写入内部 `module_reports[].deduplicated_questions`；选项顺序不同但正确答案所对应内容一致时也可合并。仅题干相同、视觉证据不足或高度相似的题不得自动删除；答案或考纲归属冲突必须回到 parser 复核。随后按以下优先级稳定挑选：

1. 覆盖更多具体 ESAT 考点，避免同知识点重复堆叠。
2. 覆盖更多 ESAT 考纲大类。
3. 难度分布更均衡。
4. ENGAA/NSAA 题源更平衡。
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

- 根字段 `metadata`、`sections`。
- `metadata.code/title/examType/year/paperType/assemblyType/deliveryMode/remarks`。
- `metadata.paperType=realPaper`、`assemblyType=legacy_equivalent`、`deliveryMode=section_sequence`。
- `sections[0..2]` 是三个科目段，每段只包含 `code/sectionType/order/questions`；时间、休息和跳转由项目端配置。
- 三个科目段按组合顺序排列，每段的 `questions[].number` 独立从 1 连续编号。
- 字符串 `title`，且等于首个 `contentBlocks` paragraph。
- 数组 `answer`，项目题型枚举和当前考纲字段。
- 自包含 SVG 或 data URI 位图，不引用本机文件路径。
- 相同来源题在不同卷中使用相同 `sections[].questions[].code`。

项目导出时进行以下确定性转换：

- canonical `title` 内容块转换为项目 `title + contentBlocks`。
- canonical 标量答案转换为项目答案数组。
- canonical `multiple_choice/free_response` 转换为项目 `single_choice/multiple_choice/short_answer`。
- canonical 学科、章节和知识点转换为项目 `classification`。
- canonical 来源信息转换为项目 `source`。
- canonical 学习解析转换为项目 `learningAnalysis`。
- canonical 单题 `is_ai_generated` 不进入最终项目 JSON，试卷来源统一由 `metadata.paperType` 表达。

内部 coverage、module_note、来源 evidence 和 fingerprint 不进入项目 JSON；它们仍保留在 canonical 或分析产物中。最终 `metadata.remarks` 只汇总每模块实际/目标题量、覆盖警告和 `diagnostic_confidence`，不复制整套内部分析结构。

最终字段模板见 `references/output-template.md`，正式 Schema 为 `../exam-paper-core/schema/project-diagnostic-paper.schema.json`。
