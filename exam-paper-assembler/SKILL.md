---
name: exam-paper-assembler
description: 基于已经通过校验的 ESAT legacy 年度英文真题 JSON，按 Mathematics 1 必选和 Biology/Chemistry/Physics/Mathematics 2 四选二规则生成 6 套诊断性 ESAT 组合卷。适用于同一年 ENGAA+NSAA 合并题库、ESAT 备考诊断测试、模块分段测试和按模块评分；不用于 TMUA/STEP，不解析 PDF，也不生成新题。
---

# ESAT Legacy 诊断组卷

本 Skill 只服务 ESAT。它从 `exam-paper-parser` 产出的同一年 ENGAA+NSAA canonical 年度真题库中，按 ESAT 考纲生成诊断性测试卷。它不解析原始 PDF，不补写题目质量字段，也不生成新题。默认交付物是 6 个各自包含完整题目的模块分组项目 JSON；QuizTestDemo 需要先适配新版分组契约才能导入。

## 必须遵守

1. 开始任务时阅读 `references/workflow.md`。
2. 输入必须是 `document_type=parsed_exam`、`validation_status=passed` 且 `metadata.paper_type=realPaper` 的 ESAT canonical 年度 JSON；`metadata.source_exam_types` 必须同时包含 `ENGAA` 与 `NSAA`，且不得跨年份混合。
3. 每道候选题必须已有 `target_exam_scope`；不得用 `subject` 字符串临时猜模块。
4. 年度组卷必须自动生成 6 套组合：Mathematics 1 + 四个进一步模块中任意两个。
5. 六套卷必须先在隔离暂存目录全部生成，并通过单卷 Schema 与整包一致性校验，再以目录级事务发布；任一生成、校验或发布步骤失败时必须恢复完整旧目录，不得留下新旧混合结果。
6. 每套完整组合卷必须按 3 个模块分段，并把每个模块目标题量锁定为 27；调用方不得用 `target_question_counts` 修改。每个模块固定 40 分钟，整卷固定 120 分钟，模块仍独立评分。
7. 题目不足 27 仍然组卷，时间不缩短；必须在内部 `module_note` 和最终 `metadata.remarks` 中说明缺题、覆盖和诊断可信度。
8. 题目过多时先排除已经确认的重复题，再按具体考点覆盖、考纲大类、难度和题源稳定挑选，不得简单截断。只允许在题干、选项、正确答案和考纲归属一致时自动去重；仅题干相同不得删除。
9. 内部 `assembled_exam` 必须保留 parser 的完整 canonical 结构；最终项目 JSON 只输出项目入库和渲染需要的字段。
10. 最终项目 JSON 的根字段必须为 `code`、`metadata`、`questions`；真题诊断卷使用 `examType=ESAT`、`paperType=realPaper`。`questions[0..2]` 是三个模块，每个模块只含 `subject`、`subject_code`、`duration`、`items`。
11. `out_of_scope`、`partially_in_scope`、`unknown` 默认不得进入诊断卷。
12. 同一道来源题进入不同组合卷时必须保留相同 `questions[].items[].code`；每个模块内题号从 1 重新连续编号。最终单题不输出 `subject`、`subject_code` 或 `is_ai_generated`，这些信息从模块和 `metadata.paperType` 继承。

## 标准命令

生成某一年 6 套 ESAT 组合诊断卷：

```powershell
python scripts/assemble.py assemble-year --input annual-legacy.canonical.json --output-dir ESAT_2023_diagnostic_papers
```

生成单套组合卷：

```powershell
python scripts/assemble.py assemble --input annual-legacy.canonical.json --constraints esat-combination.json --output paper.json
```

轻量分析某个组合：

```powershell
python scripts/assemble.py analyze --input annual-legacy.json --constraints esat-combination.json --output analysis.json
```

约束文件示例：

```json
{
  "target_exam": "ESAT",
  "paper_mode": "diagnostic_combination_paper",
  "title": "ESAT legacy diagnostic paper: Mathematics 1 + Physics + Mathematics 2",
  "modules": ["Mathematics 1", "Physics", "Mathematics 2"]
}
```

完整组合卷自动锁定为每模块 27 题。`target_question_counts` 只允许用于 `diagnostic_module_paper` 等单科/局部流程；如果题量不足，仍输出；如果题量超过目标，先排除确认重复题，再按具体考点覆盖、考纲大类、难度和题源筛选到 27 题。仅题干相同或高度相似的题保留待复核，答案或考纲归属冲突会阻止静默组卷。被排除的题目及原因保留在内部分析报告，不进入最终项目 JSON。

## 资源按需加载

- `references/workflow.md`：始终读取，包含 ESAT-only、6 套组合、选题逻辑和输出要求。
- `references/output-template.md`：需要核对最终 JSON 字段或给开发侧说明结构时读取，包含模块分组的单套诊断卷模板。
- `../exam-paper-core/schema/project-diagnostic-paper.schema.json`：六套最终项目 JSON 的正式 Schema。
- `../exam-paper-core/syllabus/esat_syllabus.json`：需要核查模块代码或考纲标注时读取。

## 完成条件

- 每年输出 6 个独立完整 JSON，不输出一个六卷合并包。
- 每套 JSON 的 `questions` 必须包含三个模块对象；`metadata.totalQuestions` 等于三个模块 `items.length` 之和，`metadata.duration=120`。
- 每套 JSON 的 `metadata.remarks` 必须逐模块写明实际/目标题量、覆盖警告和诊断可信度，供管理员导入前核对。
- 每套卷按 Mathematics 1、进一步模块一、进一步模块二排列模块；模块内题目从 1 连续编号。
- 每题使用项目标准的字符串 `title`、`content_blocks`、数组 `answer`、`syllabus_points`、`knowledge_points` 和 `learning_analysis`。
- 所有 SVG 以内联字符串交付，位图以 data URI 交付，不允许最终 JSON 引用本机绝对路径。
- 内部 coverage、module_note、来源证据和指纹保留在 canonical/分析产物中；最终项目 JSON 只通过 `metadata.remarks` 汇总题量、覆盖和 diagnostic_confidence 警告。
