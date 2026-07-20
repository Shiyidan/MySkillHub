# ESAT 项目诊断卷输出模板

`assemble-year` 默认输出六个独立 JSON。每个文件包含 Mathematics 1 和两个进一步模块；根 `questions[0]`、`questions[1]`、`questions[2]` 分别表示三个模块，模块内题目放在 `items`。

```json
{
  "code": "ESAT_2023_M1_Biology_Physics",
  "metadata": {
    "paperName": "ESAT 2023 真题诊断卷：Mathematics 1 + Biology + Physics",
    "year": 2023,
    "duration": 120,
    "examType": "ESAT",
    "paperType": "realPaper",
    "totalQuestions": 1,
    "remarks": "管理员备注：各模块固定 40 分钟，本卷固定 120 分钟。Mathematics 1：实际 0/27 题，题量不足 27 题，诊断可信度低；Biology：实际 0/27 题，题量不足 27 题，诊断可信度低；Physics：实际 1/27 题，题量不足 26 题，考纲覆盖偏窄，诊断可信度低。"
  },
  "questions": [
    {
      "subject": "Mathematics 1",
      "subject_code": "110000",
      "duration": 40,
      "items": []
    },
    {
      "subject": "Biology",
      "subject_code": "150000",
      "duration": 40,
      "items": []
    },
    {
      "subject": "Physics",
      "subject_code": "130000",
      "duration": 40,
      "items": [
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
          "learning_analysis": {
            "exam_focus": "考查弹性势能与力的关系。",
            "solution": "由图读出能量，再用弹簧做功关系求力。",
            "review_guidance": "复习弹簧能量、力和伸长量的关系。"
          }
        }
      ]
    }
  ]
}
```

## 导出规则

- 六个文件分别表示六套独立试卷。
- 真题及真题诊断卷使用 `paperType=realPaper`；普通模考卷使用 `mockPaper`；AI 生成练习卷使用 `aiPaper`。
- 三个模块按数组顺序排列，不再输出 `order`、题号起止范围、实际题量、可信度或 warnings 等模块字段。
- 模块实际题量等于 `items.length`；完整组合卷的目标题量固定为每模块 27 题。
- 模块内 `number` 从 1 重新连续编号；单题继承所在模块的 `subject` 和 `subject_code`。
- 最终单题不输出 `is_ai_generated`，试卷来源由 `metadata.paperType` 统一表达。
- SVG 必须内联，位图必须转换为 data URI。
- 当前 QuizTestDemo 导入器仍使用旧的扁平 `questions` 契约；项目端完成模块分组适配后才能直接导入此新版结构。
