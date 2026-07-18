---
name: exam-paper-parser
description: 将英文考试的试题 PDF、图片、官方答案或评分方案解析为经过校验的标准 JSON，并生成中文解析。适用于 ESAT、TMUA、STEP 等真题识别、题目与答案配对、图形还原、考纲标注和解析质检；不用于基于题库生成新题。
---

# 英文试卷解析

本 Skill 的质量来自过程设计：先把来源、证据、逐题推理和解析闭环做扎实，最终质量门只负责兜底拦截。解析结果 `parsed_exam` 是供组卷、生题和审计使用的内部 canonical 主数据，不直接作为 QuizTestDemo 项目导入文件。所有面向用户的说明、日志、错误和解析使用中文；原题题干和选项保持英文。

## 必须遵守

1. 开始任务时完整阅读 `references/workflow.md`。
2. 解析前必须完成来源盘点、同卷材料配对和证据包制作；不得凭空补写缺失题干、答案或图形。
3. 每道题必须建立逐题生产事务：证据充分性确认、题面结构恢复、考纲映射、独立求解、官方答案对齐、解题轨迹、学习分析、图形复原、题内微验证、原子提交。
4. 独立求解必须先于官方答案对齐。官方材料只能用于比对和纠偏，不能替代推理过程。
5. 解析 ESAT legacy 真题时，同一年 ENGAA 与 NSAA 必须进入同一个年度 JSON，并为每题写入 3.2.0 `target_exam_scope`，标明是否在 ESAT 范围内，同时包含 ESAT syllabus 的模块代码、模块标签和 `syllabus_items`。
6. 解析 TMUA 真题时必须读取 `references/tmua-output-template.md` 和 `../exam-paper-core/syllabus/tmua_syllabus.json`：每题必须标明 Paper 1/2、`TMUA-P1/TMUA-P2`、TMUA syllabus code/path、选择题属性和中文解析；不得套用 ESAT 模块。
7. 中文解析必须从 `solution_trace` 生成，包含“目标”“步骤 1/STEP 1”“复核”，并逐一解释所有错误选项。
8. 图形题同时阅读 `references/visual-restoration.md`，优先保留可编辑矢量信息和可复验 bbox。
9. 输出草稿前阅读 `references/output-contract.md`；最终输出必须通过共享契约校验和逐题事务校验。
10. 只执行解析流程，不调用生成新题流程；按 ESAT 模块组合拆卷交给 `exam-paper-assembler`。

## 标准流程

流程分为六个可恢复阶段：

`source_inventory → source_inspection → evidence_packets → question_transactions → independent_review → export`

每个阶段完成时都必须提供真实产物、结构化方法记录和阶段凭据。`question_transactions` 阶段还必须登记每道题已经提交的逐题事务 JSON。

```powershell
python scripts/pipeline.py preflight
python scripts/pipeline.py init --source question.pdf --source answer.pdf --workdir run
python scripts/pipeline.py status --source question.pdf --source answer.pdf --workdir run
python scripts/pipeline.py complete --source question.pdf --source answer.pdf --workdir run --stage source_inventory --artifact run/source-manifest.json --method-objective "完成来源盘点" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py complete --source question.pdf --source answer.pdf --workdir run --stage source_inspection --artifact run/source-inspection.json --method-objective "完成材料检查" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py complete --source question.pdf --source answer.pdf --workdir run --stage evidence_packets --artifact run/evidence-packets.json --method-objective "完成证据包制作" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py complete --source question.pdf --source answer.pdf --workdir run --stage question_transactions --artifact run/question-transactions.json --transaction-receipt run/Q1.transaction.json --method-objective "完成逐题闭环" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py complete --source question.pdf --source answer.pdf --workdir run --stage independent_review --artifact run/independent-review.json --method-objective "完成独立复核" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py finalize --draft run/draft.json --source question.pdf --source answer.pdf --workdir run --output run/parsed-exam.json
```

`finalize` 只接受严格草稿：根级仅含 `metadata` 与 `questions`。脚本会补齐契约版本、来源哈希、语言环境、验证状态和题目指纹，但不会补写任何质量字段。

## 资源按需加载

- `references/workflow.md`：始终读取，包含阶段门禁、返工规则和交付标准。
- `references/output-contract.md`：制作或修订 JSON 时读取。
- `references/parsed-output-template.md`：需要核对 3.2.0 字段、ESAT scope、out_of_scope/partially_in_scope 或图形字段时读取。
- `references/tmua-output-template.md`：解析 TMUA 或审计 TMUA JSON 字段时读取。
- `references/explanation-prompt.md`：撰写中文解析时读取。
- `references/visual-restoration.md`：题目含图、表、坐标系或几何示意时读取。
- `../exam-paper-core/syllabus/*.json`：仅加载当前考试对应考纲。
- `exam-paper-assembler`：需要把年度 JSON 拆成 ESAT 模块组合卷时使用。

## 完成条件

- 标准 JSON 的 `document_type` 为 `parsed_exam`，`validation_status` 为 `passed`。
- 每道题都有已提交逐题事务，最终片段与草稿题目一一对应。
- 英文题面、选项、答案、图形引用、来源页码、当前考试考纲 code/label/path、目标考试范围标注和中文解析均可复验。
- 质量问题回到对应步骤局部返工；不得用占位词或末端补写通过校验。
