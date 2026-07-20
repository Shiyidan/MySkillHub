# 输出契约

正式输出统一使用共享契约 `exam-paper-core/schema/exam-document.schema.json`，解析结果的 `document_type` 固定为 `parsed_exam`，当前契约版本为 `3.3.0`。

完整字段示例见 `references/parsed-output-template.md`。制作 ESAT legacy 年度 JSON 时，必须同时对照该模板和 `../exam-paper-core/syllabus/esat_syllabus.json`。制作 TMUA JSON 时，必须同时对照 `references/tmua-output-template.md` 和 `../exam-paper-core/syllabus/tmua_syllabus.json`。

交给 `finalize` 的草稿根级只能是：

```json
{
  "metadata": {
    "exam_type": "ESAT",
    "paper_type": "realPaper",
    "year": 2026,
    "source_files": ["ENGAA_2023.pdf", "NSAA_2023.pdf"],
    "target_exam": "ESAT",
    "source_exam_types": ["ENGAA", "NSAA"]
  },
  "questions": []
}
```

`metadata.paper_type` 是所有 canonical 文档的必填字段，必须来自入口确认：真题或真题诊断卷使用 `realPaper`，普通模考卷使用 `mockPaper`，AI 生成练习卷使用 `aiPaper`。

每道题必须已经在逐题事务中完成，并包含：

- 标准题目标识：`code`、`number`、`questionNumber`、`examType`、`source_examType`、`year`。
- 英文题面内容块：`title`，选项内容块：`options`。
- 官方答案、题型、难度、学科、主题、唯一主知识点和 `syllabus_tags`。难度只允许 `easy`、`medium`、`hard`、`composite`；`composite` 至少需要两个实际参与求解的知识点。
- `target_exam_scope`：目标考试范围标注。ESAT legacy 年度库必须标明模块、模块代码、模块标签、6 位 ESAT 考纲代码、`syllabus_items`、范围状态和排除原因。
- 完整中文 `learning_analysis`，其中 `solution_trace.steps` 至少三步，错误选项逐一解释。
- 中文 `explanation`，必须包含“目标”“步骤 1/STEP 1”“复核”。
- 精确来源：

```json
"source": {
  "question": {"file": "NSAA_2023.pdf", "page": 1},
  "answer": {"file": "NSAA_2023_answers.pdf", "page": 1},
  "solution": null,
  "evidence_packet": {"path": "evidence/Q1.json", "sha256": "64位sha256"}
}
```

ESAT 范围标注示例：

```json
"target_exam_scope": {
  "target_exam": "ESAT",
  "scope_status": "in_scope",
  "mapping_status": "human_verified",
  "modules": ["Mathematics 1"],
  "syllabus_codes": ["110415"],
  "syllabus_items": [
    {
      "code": "110415",
      "label": "Equations and simultaneous equations (方程与联立方程)",
      "module": "Mathematics 1",
      "module_code": "110000",
      "module_label": "Mathematics 1 (数学1)",
      "parent_code": "110400",
      "parent_label": "Algebra (代数)",
      "path_codes": ["100000", "110000", "110400", "110415"],
      "path_labels": [
        "ESAT (工程与科学入学测试)",
        "Mathematics 1 (数学1)",
        "Algebra (代数)",
        "Equations and simultaneous equations (方程与联立方程)"
      ]
    }
  ]
}
```

ESAT 字段硬规则：

- `syllabus_codes` 必须全部来自 `esat_syllabus.json`，且必须是 6 位数字代码。
- 不得使用 `algebra.linear-equations`、`physics.mechanics` 等自由文本旧代码作为 ESAT syllabus code。
- `syllabus_items` 必须与 `syllabus_codes` 逐项对应，且 `code`、`label`、`module`、`module_code`、`module_label`、`parent_code`、`parent_label`、`path_codes`、`path_labels` 均与 `esat_syllabus.json` 一致。
- `in_scope` 与 `partially_in_scope` 题目必须只归属一个 ESAT 科目；`modules` 必须等于 `[subject]`，`subject_code` 必须等于该科目在 `esat_syllabus.json` 中的模块 code。
- `mapping_status` 只允许 `auto_verified`、`human_verified`、`needs_review`；后续组卷只接收前两种。
- `out_of_scope` 与 `unknown` 题目必须保留在年度 JSON 中，但 `modules`、`syllabus_codes`、`syllabus_items` 必须为空，并写明 `mapping_reason`。
- `partially_in_scope` 或 `mapping_status: needs_review` 必须写 `mapping_reason`，说明部分超纲或待复核原因。

TMUA 字段硬规则：

- `metadata.exam_type` 和 `metadata.target_exam` 均使用 `TMUA`，`metadata.syllabus_version` 使用 `tmua_syllabus.json`。
- `target_exam_scope.modules` 对 TMUA 表示 paper，必须且只能包含 `Paper 1` 或 `Paper 2` 之一；不得写 ESAT 模块。
- `syllabus_codes` 必须全部来自 `tmua_syllabus.json`，且 `syllabus_items` 必须与 code 对应的 label、module、parent、path 完全一致。
- `syllabus_items[].module` 对 TMUA 表示知识域：`Mathematics 1`、`Mathematics 2` 或 `Logic & Proof`；这不是 ESAT 模块。
- Paper 1 不得映射到 `Logic & Proof`；Paper 2 可映射 Mathematics 1、Mathematics 2 和 Logic & Proof。
- TMUA 题目必须为 `multiple_choice`，中文解析必须逐一解释所有错误选项。
- TMUA 成绩字段如需出现，只能描述原始分、正确率或诊断性表现；不得声称可直接计算官方 1.0–9.0 scaled score，除非另有官方转换表作为来源。

`fingerprint` 可省略，由核心模块统一计算；其他质量字段不得省略。未知字段、空题面、答案不匹配、非中文解析或重复 code 都会拒绝导出。跨试卷重复题由 `finalize` 在封装前处理：题干、选项、正确答案和考纲归属一致时只保留一题；题干相同但选项不同或仅高度相似时保留并写入待复核列表；同题面出现答案或考纲归属冲突时写出报告并拒绝导出。最终 canonical 仍不得包含重复指纹。

去重报告默认写为最终 JSON 同目录的 `*.deduplication-report.json`，包含确认重复、阻断冲突和待复核候选。它是内部审计产物，不写入项目题目 JSON；被合并的 ENGAA/NSAA 来源页和答案页不得丢失。

正式输出自动补入：

- `contract_version: "3.3.0"`
- `document_type: "parsed_exam"`
- 来源文件共同计算的 `source_hash`
- `validation_status: "passed"`
- `question_fingerprint_version: "2"`
- 固定中英语言配置 `locale`

字段名、枚举和版本号保持英文以保证机器接口稳定；操作说明、日志、错误和报告使用中文。
