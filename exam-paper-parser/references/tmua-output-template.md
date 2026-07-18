# TMUA parsed_exam 输出模板

本模板用于制作或审计 TMUA 真题解析 JSON。交给 `pipeline.py finalize` 的草稿根级只能包含 `metadata` 和 `questions`；`contract_version`、`document_type`、`source_hash`、`validation_status`、`question_fingerprint_version`、`locale` 和 `fingerprint` 由核心模块封装或计算。

## 草稿根节点

```json
{
  "metadata": {
    "exam_type": "TMUA",
    "year": 2023,
    "source_files": ["TMUA_2023_Paper_1.pdf", "TMUA_2023_AnswerKey.pdf"],
    "target_exam": "TMUA",
    "corpus_group": "TMUA 2023",
    "syllabus_version": "tmua_syllabus.json"
  },
  "questions": []
}
```

## TMUA Paper 1 题目片段

```json
{
  "code": "TMUA_2023_P1_Q01",
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
  "examType": "TMUA",
  "source_examType": "TMUA",
  "year": 2023,
  "questionNumber": 1,
  "subject": "Paper 1: Mathematical Thinking",
  "subject_code": "paper-1",
  "topic": "Equations and simultaneous equations",
  "topic_code": "214015",
  "question_type": "multiple_choice",
  "difficulty": "easy",
  "knowledge_points": [
    {"code": "214015", "name": "Equations and simultaneous equations", "is_primary": true}
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
    "exam_focus": "本题考查 TMUA Paper 1 中方程与代数变形的基础数学思维。",
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
  "syllabus_tags": ["214015"],
  "diagram": null,
  "target_exam_scope": {
    "target_exam": "TMUA",
    "status": "in_scope",
    "modules": ["Paper 1"],
    "primary_module": "Paper 1",
    "primary_module_code": "TMUA-P1",
    "primary_module_label": "Paper 1: Mathematical Thinking",
    "syllabus_codes": ["214015"],
    "syllabus_items": [
      {
        "code": "214015",
        "label": "Equations and simultaneous equations (方程与联立方程)",
        "module": "Mathematics 1",
        "module_code": "210000",
        "module_label": "Mathematics 1 (数学1)",
        "parent_code": "214000",
        "parent_label": "Algebra (代数)",
        "path_codes": ["200000", "210000", "214000", "214015"],
        "path_labels": [
          "TMUA (大学入学数学测试)",
          "Mathematics 1 (数学1)",
          "Algebra (代数)",
          "Equations and simultaneous equations (方程与联立方程)"
        ]
      }
    ],
    "exclusion_reasons": [],
    "evidence": "本题是代数方程选择题，属于 TMUA Paper 1 Mathematical Thinking 的 Mathematics 1 范围。",
    "review_status": "reviewed"
  },
  "source": {
    "question": {"file": "TMUA_2023_Paper_1.pdf", "page": 1},
    "answer": {"file": "TMUA_2023_AnswerKey.pdf", "page": 1},
    "solution": null,
    "evidence_packet": {"path": "evidence/TMUA_2023_P1_Q01.json", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}
  }
}
```

## TMUA Paper 2 题目范围标注片段

```json
"target_exam_scope": {
  "target_exam": "TMUA",
  "status": "in_scope",
  "modules": ["Paper 2"],
  "primary_module": "Paper 2",
  "primary_module_code": "TMUA-P2",
  "primary_module_label": "Paper 2: Mathematical Reasoning",
  "syllabus_codes": ["231001"],
  "syllabus_items": [
    {
      "code": "231001",
      "label": "Mathematical logic basics (数学逻辑基础)",
      "module": "Logic & Proof",
      "module_code": "230000",
      "module_label": "Logic & Proof (逻辑与证明)",
      "parent_code": "231000",
      "parent_label": "The Logic of Arguments (论证逻辑)",
      "path_codes": ["200000", "230000", "231000", "231001"],
      "path_labels": [
        "TMUA (大学入学数学测试)",
        "Logic & Proof (逻辑与证明)",
        "The Logic of Arguments (论证逻辑)",
        "Mathematical logic basics (数学逻辑基础)"
      ]
    }
  ],
  "exclusion_reasons": [],
  "evidence": "本题要求判断数学论证结构，属于 TMUA Paper 2 Mathematical Reasoning 的 Logic & Proof 范围。",
  "review_status": "reviewed"
}
```

## 强制检查

- `target_exam_scope.modules` 对 TMUA 表示 paper；只允许 `Paper 1`、`Paper 2`。
- `primary_module_code` 只允许 `TMUA-P1`、`TMUA-P2`，并必须与 `primary_module` 对应。
- `syllabus_codes[]`、`knowledge_points[].code`、`topic_code` 与 `syllabus_tags[]` 必须来自 `tmua_syllabus.json`。
- `syllabus_items[]` 必须与 `tmua_syllabus.json` 中的 code/label/module/parent/path 完全一致。
- Paper 1 不使用 `Logic & Proof`；Paper 2 可使用 `Mathematics 1`、`Mathematics 2`、`Logic & Proof`。
- `question_type` 必须是 `multiple_choice`；错误选项必须逐一解释。
- 题干和选项保持英文；中文只进入解析、学习分析、证据说明和复核记录。
