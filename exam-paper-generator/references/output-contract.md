# 输出契约

正式输出统一使用共享契约 `exam-paper-core/schema/exam-document.schema.json`，生成结果的 `document_type` 固定为 `generated_exam`。

交给 `finalize` 的草稿根级只能是：

```json
{
  "metadata": {
    "exam_type": "ESAT",
    "year": 2026,
    "source_files": ["parsed-exam.json"]
  },
  "questions": []
}
```

每道题必须已经在逐题事务中完成，并包含：

- 标准题目标识：`code`、`number`、`questionNumber`、`examType`、`source_examType`、`year`。
- 英文题面内容块：`title`，选项内容块：`options`。
- 唯一答案、题型、难度、学科、主题、唯一主知识点和 `syllabus_tags`。
- `target_exam_scope`：新题目标考试范围标注，ESAT 新题必须明确模块、考纲代码和判断依据；TMUA 新题必须明确 Paper 1/2、`TMUA-P1/TMUA-P2`、TMUA syllabus code/path 和判断依据。
- 完整中文 `learning_analysis`，其中 `solution_trace.steps` 至少三步，错误选项逐一解释。
- 中文 `explanation`，必须包含“目标”“步骤 1/STEP 1”“复核”。
- 生成来源：

```json
"source": {
  "source_question_id": "Q1",
  "source_fingerprint": "64位sha256",
  "generation_blueprint": {
    "retained_knowledge_point": "algebra.linear-equations",
    "source_deconstruction": "说明母题的知识点、推理骨架、表层元素、图形元素、选项陷阱和真实难度来源",
    "structural_transformation": "说明新题在条件组织、推理路径、变量关系、作答判断或干扰项逻辑上的结构性变化",
    "changed_reasoning_structure": "说明推理结构如何改变",
    "changed_context": "说明语境如何改变",
    "changed_values": "说明数值如何改变",
    "difficulty_reassessment": "说明新题难度的独立判断依据，不能复制母题 difficulty",
    "diagram_generation_spec": "说明是否需要图形；若需要，写清图形语义、标签、单位、坐标/比例和 SVG/矢量规格",
    "novelty_rationale": "说明为什么不是近重复"
  }
}
```

`fingerprint` 可省略，由核心模块统一计算；其他质量字段不得省略。未知字段、题量不符、重复指纹、引用不存在母题、与输入原题碰撞或语言不符都会拒绝导出。

TMUA 生成字段硬规则：

- `metadata.exam_type` 和 `metadata.target_exam` 均使用 `TMUA`，`metadata.syllabus_version` 使用 `tmua_syllabus.json`。
- 每题 `question_type` 必须为 `multiple_choice`。
- `target_exam_scope.modules` 对 TMUA 表示 paper，只允许 `Paper 1` 或 `Paper 2`；不得写 ESAT 模块。
- `primary_module_code` 必须为 `TMUA-P1` 或 `TMUA-P2`，并与 `primary_module` 对应。
- `syllabus_codes`、`syllabus_items`、`knowledge_points[].code`、`topic_code` 与 `syllabus_tags` 必须来自 `tmua_syllabus.json`。
- Paper 1 不得使用 `Logic & Proof`；Paper 2 可使用 Mathematics 1、Mathematics 2 和 Logic & Proof。
- `source.generation_blueprint.retained_knowledge_point` 应使用 TMUA syllabus code，不使用旧自由文本标签。
- `source.generation_blueprint` 必须包含母题解剖、结构改造、难度重估和图形规格；缺任一项或内容空泛都会拒绝导出。
- 不得输出或暗示可直接计算官方 scaled score；没有官方转换表时只给原始分/正确率/诊断性说明。

正式输出自动补入：

- `contract_version: "3.2.0"`
- `document_type: "generated_exam"`
- 输入与约束共同计算的 `source_hash`
- `validation_status: "passed"`
- `question_fingerprint_version: "2"`
- 固定中英语言配置 `locale`
