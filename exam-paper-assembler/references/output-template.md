# ESAT 项目诊断卷输出模板

`assemble-year` 默认输出六个独立 JSON。每个文件包含一套 Mathematics 1 加两个进一步模块的完整试卷，可直接提交到 QuizTestDemo `/api/papers/import-json`。

```json
{
  "code": "ESAT_2023_M1_Physics_Math2",
  "metadata": {
    "paperName": "ESAT legacy diagnostic paper: Mathematics 1 + Physics + Mathematics 2",
    "year": 2023,
    "duration": 2,
    "examType": "ESAT",
    "paperType": "mockPaper",
    "totalQuestions": 1
  },
  "questions": [
    {
      "code": "ENGAA_2023_S1_Q06",
      "number": 1,
      "title": "A spring is initially unstretched.",
      "content_blocks": [
        {"type": "paragraph", "text": "A spring is initially unstretched."},
        {"type": "image_ref", "image_id": "q6-graph"},
        {"type": "paragraph", "text": "What is the magnitude of \\(F\\)?"}
      ],
      "options": [
        {"label": "A", "text": "0.30 N"},
        {"label": "B", "text": "0.60 N"}
      ],
      "answer": ["B"],
      "images": [
        {
          "id": "q6-graph",
          "type": "svg",
          "alt": "Energy against extension squared graph",
          "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\">...</svg>"
        }
      ],
      "examType": "ESAT",
      "source_examType": "ENGAA",
      "year": 2023,
      "subject": "Physics",
      "subject_code": "130000",
      "topic": "Mechanics (力学)",
      "topic_code": "131000",
      "question_type": "single_choice",
      "difficulty": "medium",
      "syllabus_points": [
        {"code": "131004", "label": "Energy, work & power (能量、功和功率)", "role": "primary"}
      ],
      "knowledge_points": [
        {"code": "P3.7", "label": "Energy (能量)", "role": "primary"}
      ],
      "is_ai_generated": false,
      "learning_analysis": {
        "exam_focus": "考查弹性势能与力的关系。",
        "solution": "由图读出能量，再用弹簧做功关系求力。",
        "review_guidance": "复习弹簧能量、力和伸长量的关系。"
      }
    }
  ]
}
```

## 导出规则

- 六个文件分别导入，项目会创建六张独立 `Paper`。
- `paperType` 使用 `mockPaper`：题目来自真题，但组合卷不是官方原始试卷。
- 同一道来源题在多套卷中保持相同 `code`；项目当前仍会按 `paperId + number` 创建独立 Question 记录。
- Mathematics 1 题目排在最前，随后按组合中的两个进一步模块依次排列。
- SVG 必须内联；位图必须转换为 data URI，保证单个 JSON 自包含。
- 内部组卷分析、来源证据和质量凭据不写入项目 JSON。
