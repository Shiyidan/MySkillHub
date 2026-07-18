---
name: exam-paper-assembler
description: 基于已经通过校验的 ESAT legacy 年度英文真题 JSON，按 Mathematics 1 必选和 Biology/Chemistry/Physics/Mathematics 2 四选二规则生成 6 套诊断性 ESAT 组合卷。适用于同一年 ENGAA+NSAA 合并题库、ESAT 备考诊断测试、模块分段测试和按模块评分；不用于 TMUA/STEP，不解析 PDF，也不生成新题。
---

# ESAT Legacy 诊断组卷

本 Skill 只服务 ESAT。它从 `exam-paper-parser` 产出的同一年 ENGAA+NSAA canonical 年度题库中，按 ESAT 考纲生成诊断性测试卷。它不解析原始 PDF，不补写题目质量字段，也不生成新题。默认交付物是 6 个各自包含完整题目的项目 JSON，每个文件可独立提交到 QuizTestDemo 的 `/api/papers/import-json`。

## 必须遵守

1. 开始任务时阅读 `references/workflow.md`。
2. 输入必须是 `document_type=parsed_exam` 且 `validation_status=passed` 的 ESAT canonical 年度 JSON；`metadata.source_exam_types` 必须同时包含 `ENGAA` 与 `NSAA`，且不得跨年份混合。
3. 每道候选题必须已有 `target_exam_scope`；不得用 `subject` 字符串临时猜模块。
4. 年度组卷必须自动生成 6 套组合：Mathematics 1 + 四个进一步模块中任意两个。
5. 每套卷必须按 3 个模块分段；官方完整模块基准为 27 题/40 分钟，但 legacy 诊断卷必须按实际入卷题数写入模块建议限时和整卷总建议限时，模块仍独立评分。
6. 题目不足 27 仍然组卷，但必须在 `module_note` 中说明缺题、覆盖和诊断可信度。
7. 题目过多时必须按考纲覆盖、难度、题源和重复度稳定挑选，不得简单截断。
8. 内部 `assembled_exam` 必须保留 parser 的完整 canonical 结构；最终项目 JSON 只输出项目入库和渲染需要的字段。
9. 最终项目 JSON 的根字段必须为 `code`、`metadata`、`questions`；每套卷使用 `examType=ESAT`、`paperType=mockPaper`，并把 SVG 或位图资源内联为自包含内容。
10. `out_of_scope`、`partially_in_scope`、`unknown` 默认不得进入诊断卷。
11. 同一道来源题进入不同组合卷时必须保留相同 `questions[].code`；每套卷内题号按三个模块的顺序重新连续编号。

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
  "modules": ["Mathematics 1", "Physics", "Mathematics 2"],
  "target_question_counts": {
    "Mathematics 1": 27,
    "Physics": 27,
    "Mathematics 2": 27
  }
}
```

如果题量不足，仍输出；如果题量超过目标，按 Skill 流程挑选。

## 资源按需加载

- `references/workflow.md`：始终读取，包含 ESAT-only、6 套组合、选题逻辑和输出要求。
- `references/output-template.md`：需要核对最终 JSON 字段或给开发侧说明结构时读取，包含可直接导入项目的单套诊断卷模板。
- `../exam-paper-core/schema/project-diagnostic-paper.schema.json`：六套最终项目 JSON 的正式 Schema。
- `../exam-paper-core/syllabus/esat_syllabus.json`：需要核查模块代码或考纲标注时读取。

## 完成条件

- 每年输出 6 个可独立导入项目的完整 JSON，不输出一个六卷合并包。
- 每套 JSON 的 `metadata.totalQuestions` 与 `questions.length` 一致，`metadata.duration` 等于三个模块建议时长之和。
- 每套卷按 Mathematics 1、进一步模块一、进一步模块二的顺序排列题目，并连续编号。
- 每题使用项目标准的字符串 `title`、`content_blocks`、数组 `answer`、`syllabus_points`、`knowledge_points` 和 `learning_analysis`。
- 所有 SVG 以内联字符串交付，位图以 data URI 交付，不允许最终 JSON 引用本机绝对路径。
- 内部 coverage、module_note、diagnostic_confidence、来源证据和指纹保留在 canonical/分析产物中，不写入项目 JSON。
