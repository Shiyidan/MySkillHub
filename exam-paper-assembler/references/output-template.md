# ESAT 项目诊断卷输出模板

`assemble-year` 输出六个独立 JSON。每个文件采用统一的 `metadata + sections` 结构，三个 `sections` 分别表示 Mathematics 1 和两个进一步科目。

```json
{
  "metadata": {
    "code": "ESAT_2023_M1_Biology_Physics",
    "title": "ESAT 2023 真题诊断卷：Mathematics 1 + Biology + Physics",
    "examType": "ESAT",
    "year": 2023,
    "paperType": "realPaper",
    "assemblyType": "legacy_equivalent",
    "deliveryMode": "section_sequence",
    "remarks": "管理员备注：Mathematics 1：实际 27/27 题，诊断可信度高。"
  },
  "sections": [
    {
      "code": "maths1",
      "sectionType": "subject",
      "order": 1,
      "questions": []
    },
    {
      "code": "physics",
      "sectionType": "subject",
      "order": 2,
      "questions": [
        {
          "code": "ENGAA_2023_S1_Q06",
          "number": 1,
          "title": "A spring is initially unstretched.",
          "contentBlocks": [
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
          "questionType": "single_choice",
          "difficulty": "medium",
          "classification": {
            "subject": "Physics",
            "subjectCode": "130000",
            "topic": "Mechanics (力学)",
            "topicCode": "131000",
            "knowledgePoints": [
              {"code": "P3.7", "label": "Energy (能量)", "role": "primary"}
            ]
          },
          "source": {
            "examType": "ENGAA",
            "year": 2023,
            "sectionCode": "physics",
            "questionNumber": 6
          },
          "learningAnalysis": {
            "correctSolution": "由图读出能量，再用弹簧做功关系求力。",
            "examFocus": "考查弹性势能与力的关系。",
            "commonErrorCauses": ["混淆能量与伸长量平方的关系。"],
            "reviewGuidance": "复习弹簧能量、力和伸长量的关系。"
          }
        }
      ]
    }
  ]
}
```

## 导出规则

- 六个文件分别表示六套独立试卷。
- ESAT 的 `sectionType` 固定为 `subject`；每段只输出 `code`、`sectionType`、`order`、`questions`。
- 考试时长、休息和 section 跳转由项目端配置，最终试卷 JSON 不输出相关字段。
- 完整组合卷每科目目标为 27 题；题量不足仍导出，并把提示汇总到 `metadata.remarks`。
- 科目段内 `number` 从 1 连续编号，题目分类统一放入 `classification`。
- SVG 必须内联，位图必须转换为 data URI。
- 正式 Schema 为 `../exam-paper-core/schema/project-diagnostic-paper.schema.json`。
