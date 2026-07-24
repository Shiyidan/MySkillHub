---
name: exam-paper-generator
description: 基于已经通过校验的英文试卷标准 JSON，按考试、考纲、难度和题型约束生成新的英文题目或试卷，并配套中文解析。适用于 ESAT、TMUA、STEP 等考试的仿真命题、变式题生成、组卷、去重和质量检查；不用于直接识别 PDF、图片或官方答案。
---

# 英文试卷生成

开始前读取 `../exam-paper-workflow/workflow-features.json`。当 `operations.generate=false` 时立即停止，不生成蓝图、不创建事务、不输出新题；当前 `parse_assemble_test` 配置处于关闭状态。

本 Skill 只从已通过校验的 canonical `parsed_exam` 生成新题，并输出 `metadata.paper_type=aiPaper` 的内部 canonical `generated_exam`。生成题默认不进入由 ENGAA+NSAA 真题构成的六套 legacy 诊断卷。质量来自逐题蓝图、唯一母题、推理结构重构、独立求解和新颖性复核；最终质量门只负责兜底拦截。所有面向用户的说明、日志、错误和解析使用中文；新题题干、选项和作答内容保持英文。

## 必须遵守

1. 先检查工作流功能开关；只有 `operations.generate=true` 时才继续读取 `references/workflow.md`。
2. 输入只能是 `exam-paper-parser` 生成且校验通过的 `parsed_exam` JSON；遇到原始 PDF 或图片时先调用解析 Skill。
3. 每道生成题必须且只能锁定一个母题，使用 `source.source_question_id`、`source.source_fingerprint` 和 `source.generation_blueprint` 精确溯源。
4. 生成前先写增强蓝图：母题解剖、结构改造、改变推理结构、改变语境和值、图形生成规格、难度重估和新颖性依据。不得只换数字、换名字、复写题干或轻改选项。
5. 每道题必须建立逐题生产事务：唯一母题锁定、生成蓝图、图形信息设计、推理结构重构、独立求解、干扰项设计、解题轨迹、学习分析、SVG 排版与渲染、精确溯源、新颖性核验、题内微验证、原子提交。
6. 生成 TMUA 新题时必须读取 `references/tmua-generation-constraints.md` 和 `../exam-paper-core/syllabus/tmua_syllabus.json`：先确定 Paper 1/2，再确定 TMUA syllabus code/path；不得套用 ESAT 模块。
7. 中文解析必须从新题的独立 `solution_trace` 生成，逐一解释所有错误选项。
8. 输出草稿前阅读 `references/output-contract.md`、`references/quality-rules.md` 和 `../exam-paper-parser/references/content-layout.md`；所有新题也必须使用共享的行内/独立公式与对齐语义，最终输出必须通过共享契约、逐题事务和新颖性校验。
9. 只执行生成流程，不承担证据提取、答案配对或原卷解析；输出试卷类型固定为 `aiPaper`，不得标记为 `realPaper` 或 `mockPaper`。

## 标准流程

流程分为六个可恢复阶段：

`input_validation → generation_blueprints → question_transactions → novelty_review → independent_review → export`

`prepare` 会完成输入契约校验并登记阶段凭据。其他阶段完成时都必须提供真实产物和结构化方法记录；`question_transactions` 阶段还必须登记每道生成题已经提交的逐题事务 JSON。

```powershell
python scripts/pipeline.py preflight
python scripts/pipeline.py prepare --input parsed-exam.json --constraints constraints.json --workdir run
python scripts/pipeline.py status --input parsed-exam.json --constraints constraints.json --workdir run
python scripts/pipeline.py complete --input parsed-exam.json --constraints constraints.json --workdir run --stage generation_blueprints --artifact run/generation-blueprints.json --method-objective "完成生成蓝图" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py complete --input parsed-exam.json --constraints constraints.json --workdir run --stage question_transactions --artifact run/question-transactions.json --transaction-receipt run/GQ1.transaction.json --method-objective "完成逐题生成闭环" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py complete --input parsed-exam.json --constraints constraints.json --workdir run --stage novelty_review --artifact run/novelty-review.json --method-objective "完成新颖性复核" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py complete --input parsed-exam.json --constraints constraints.json --workdir run --stage independent_review --artifact run/independent-review.json --method-objective "完成独立复核" --method-procedure "..." --method-decision-basis "..." --method-result "..."
python scripts/pipeline.py finalize --draft run/draft.json --input parsed-exam.json --constraints constraints.json --workdir run --output run/generated-exam.json
```

约束文件至少包含正整数 `question_count`，可按需指定考试、年份、标题、模块计数、题型计数、四档难度计数、主考纲代码和排除母题。制作约束时读取 `references/generation-constraints.md`；未知字段和计数总和不一致会直接拒绝。`finalize` 会重新校验输入、题量、母题 ID/指纹/保留知识点绑定、约束分布、完整指纹和题干近重复，但不会替生成草稿补写质量字段。

逐题事务统一使用共享命令，不手写事务 JSON：

```powershell
python ../exam-paper-core/scripts/question_transaction.py init --transaction run/GQ1.transaction.json --mode generator --question-id GQ1 --source-fingerprint <source-question-fingerprint>
python ../exam-paper-core/scripts/question_transaction.py status --transaction run/GQ1.transaction.json
python ../exam-paper-core/scripts/question_transaction.py prepare-fragment --mode generator --input run/GQ1/draft.json --output run/GQ1/final.json
python ../exam-paper-core/scripts/question_transaction.py rollback --transaction run/GQ1.transaction.json --step "生成蓝图" --reason "新颖性复核发现推理结构与母题过近，需要重新设计生成蓝图。"
```

每个步骤用 `complete` 登记真实输入、必要输出角色和方法记录；具体参数与解析流程相同。只有“原子提交”步骤可以传入 `--question-artifact`。

## 资源按需加载

- `references/workflow.md`：始终读取，包含阶段门禁、返工规则和交付标准。
- `references/generation-prompt.md`：制定约束、蓝图和生成题目时读取。
- `references/generation-constraints.md`：创建或校验生成约束 JSON 时读取。
- `references/generation-quality-blueprint.md`：始终用于设计生成蓝图、图形方案、难度重估和新颖性复核。
- `references/diagram-generation-standard.md`：新题包含图形时必须读取，用于控制信息披露、考试版式、SVG 布局和提交前渲染。
- `references/tmua-generation-constraints.md`：生成或审计 TMUA 新题时读取。
- `references/output-contract.md`：制作或修订 JSON 时读取。
- `../exam-paper-parser/references/content-layout.md`：制作题干内容块时读取，生成题与解析题共用同一版面契约。
- `references/quality-rules.md`：新颖性、去重与质检时读取。
- `../exam-paper-core/syllabus/*.json`：仅加载当前考试对应考纲。

## 完成条件

- 输入是校验通过的 `parsed_exam`，输出的 `document_type` 为 `generated_exam`。
- 每道生成题都有唯一母题、增强生成蓝图、图形方案、难度重估、独立求解、逐题事务和新颖性记录。
- 新题保持英文，中文解析非空，答案可由题目独立推出。
- 题量与约束一致，不与输入题库或同批题目重复。
