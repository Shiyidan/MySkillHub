# parsed_exam 输出模板

本模板用于制作或审计解析草稿。交给 `pipeline.py finalize` 的草稿根级只能包含 `metadata` 和 `questions`；`contract_version`、`document_type`、`source_hash`、`validation_status`、`question_fingerprint_version`、`locale` 和 `fingerprint` 由核心模块封装或计算。

## 草稿根节点

```json
{
  "metadata": {
    "exam_type": "ESAT",
    "year": 2023,
    "source_files": ["ENGAA_2023.pdf", "NSAA_2023.pdf"],
    "target_exam": "ESAT",
    "source_exam_types": ["ENGAA", "NSAA"],
    "corpus_group": "ESAT legacy 2023",
    "syllabus_version": "esat_syllabus.json"
  },
  "questions": []
}
```

## ESAT in_scope 题目片段

```json
{
  "code": "ESAT_LEGACY_2023_NSAA_Q01",
  "number": 1,
  "title": [
    {"type": "text", "content": "If "},
    {"type": "latex", "content": "x + 2 = 5"},
    {"type": "text", "content": ", what is x?"}
  ],
  "options": [
    {"label": "A", "content": [{"type": "text", "content": "1"}]},
    {"label": "B", "content": [{"type": "text", "content": "2"}]},
    {"label": "C", "content": [{"type": "text", "content": "3"}]},
    {"label": "D", "content": [{"type": "text", "content": "4"}]}
  ],
  "answer": "C",
  "images": [],
  "examType": "ESAT",
  "source_examType": "NSAA",
  "year": 2023,
  "questionNumber": 1,
  "subject": "Mathematics 1",
  "subject_code": "math1",
  "topic": "Equations and simultaneous equations",
  "topic_code": "110415",
  "question_type": "multiple_choice",
  "difficulty": "easy",
  "knowledge_points": [
    {"code": "110415", "name": "Equations and simultaneous equations", "is_primary": true}
  ],
  "is_ai_generated": false,
  "learning_analysis": {
    "solution_trace": {
      "trace_source": "official_answer",
      "knowns": ["x + 2 = 5", "需要求 x 的值"],
      "method": "利用等式性质，两边同时减去二，直接求出未知数。",
      "steps": ["两边同时减去 2。", "左边只剩 x。", "右边 5 - 2 = 3。"],
      "final_value": "x = 3",
      "correct_answer": "C",
      "distractors": [
        {"option": "A", "reason": "把常数项处理成无依据的反向运算，导致结果过小。"},
        {"option": "B", "reason": "只看到了题面中的 2，没有完成等式两边同减的步骤。"},
        {"option": "D", "reason": "把减去 2 误处理成其他运算，导致结果偏大。"}
      ]
    },
    "exam_focus": "本题考查 ESAT Mathematics 1 中一元一次方程和等式性质的基础运用。",
    "correct_solution": "目标：求出满足方程的 x。步骤 1：观察 x + 2 = 5，未知数左边多了 2。步骤 2：根据等式性质，两边同时减去 2。步骤 3：得到 x = 3，所以选择 C。复核：把 3 代回原式，3 + 2 = 5，成立。",
    "common_error_causes": [
      "只记住题面中的数字二，没有把它作为需要移去的常数项处理。",
      "把等式两边同减二误写成同加二，导致答案方向完全相反。",
      "没有把算出的数代回原方程复核，因此不能发现错误选项不满足题意。"
    ],
    "review_guidance": "复习时要把移项理解为等式两边做相同操作，并养成代回复核的习惯。",
    "answer_feedback_mode": "option_specific"
  },
  "explanation": "目标：求出满足方程的 x。步骤 1：观察方程 x + 2 = 5，左边比 x 多了 2。步骤 2：两边同时减去 2，保持等式成立。步骤 3：得到 x = 3，因此答案是 C。复核：把 3 代入，3 + 2 = 5，与题干一致。",
  "syllabus_tags": ["110415"],
  "diagram": null,
  "target_exam_scope": {
    "target_exam": "ESAT",
    "status": "in_scope",
    "modules": ["Mathematics 1"],
    "primary_module": "Mathematics 1",
    "primary_module_code": "110000",
    "primary_module_label": "Mathematics 1 (数学1)",
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
    ],
    "exclusion_reasons": [],
    "evidence": "本题是一元一次方程，落在 ESAT Mathematics 1 的代数与方程范围内。",
    "review_status": "reviewed"
  },
  "source": {
    "question": {"file": "NSAA_2023.pdf", "page": 1},
    "answer": {"file": "NSAA_2023_answers.pdf", "page": 1},
    "solution": null,
    "evidence_packet": {"path": "evidence/ESAT_LEGACY_2023_NSAA_Q01.json", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}
  }
}
```

## ESAT out_of_scope 题目片段

```json
"target_exam_scope": {
  "target_exam": "ESAT",
  "status": "out_of_scope",
  "modules": [],
  "primary_module": null,
  "primary_module_code": null,
  "primary_module_label": null,
  "syllabus_codes": [],
  "syllabus_items": [],
  "exclusion_reasons": ["本题考查逻辑门真值表，不属于 ESAT Mathematics 1/Biology/Chemistry/Physics/Mathematics 2 当前考纲。"],
  "evidence": "按 esat_syllabus.json 的模块和考纲项核对，逻辑门内容无对应 ESAT 标准考纲代码。",
  "review_status": "reviewed"
}
```

## ESAT partially_in_scope 题目片段

```json
"target_exam_scope": {
  "target_exam": "ESAT",
  "status": "partially_in_scope",
  "modules": ["Physics"],
  "primary_module": "Physics",
  "primary_module_code": "130000",
  "primary_module_label": "Physics (物理)",
  "syllabus_codes": ["130304"],
  "syllabus_items": [
    {
      "code": "130304",
      "label": "Newton's laws (牛顿定律)",
      "module": "Physics",
      "module_code": "130000",
      "module_label": "Physics (物理)",
      "parent_code": "130300",
      "parent_label": "Mechanics (力学)",
      "path_codes": ["100000", "130000", "130300", "130304"],
      "path_labels": ["ESAT (工程与科学入学测试)", "Physics (物理)", "Mechanics (力学)", "Newton's laws (牛顿定律)"]
    }
  ],
  "exclusion_reasons": ["题目主体涉及牛顿定律，但另含超出 ESAT 当前 Physics 范围的实验装置细节。"],
  "evidence": "力学主干可映射到 130304，但题目部分设问依赖不在 ESAT 当前考纲内的实验细节。",
  "review_status": "reviewed"
}
```

## images[] 图形资产模板

```json
"images": [
  {
    "image_id": "q01_svg",
    "role": "question",
    "source_page": 1,
    "bbox": [72.0, 120.0, 280.0, 240.0],
    "restore_method": "redraw_svg",
    "asset_path": "assets/ESAT_LEGACY_2023_NSAA_Q01.svg",
    "alt_text": "A labelled geometry diagram used in the question.",
    "status": "restored"
  }
]
```

## 强制检查

- `knowledge_points[].code`、`syllabus_tags[]`、`topic_code`、`target_exam_scope.syllabus_codes[]` 对 ESAT 题目应统一使用 `esat_syllabus.json` 中存在的 6 位数字代码。
- `title` 和 `options[].content` 必须保留英文原题；中文只进入解析和学习分析字段。
- 选择题必须逐一解释所有错误选项，不能只解释主要干扰项。
- 图形题必须同时保留 `image_ref`、`images[]`、`diagram` 或说明 `diagram=null` 的理由；已恢复图形必须有非空 `asset_path`。
