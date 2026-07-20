# 生成约束

约束文件使用 `../exam-paper-core/schema/generation-constraints.schema.json`。未知字段会被拒绝，避免拼写错误被静默忽略。

最小约束：

```json
{
  "question_count": 10
}
```

完整示例：

```json
{
  "question_count": 10,
  "exam_type": "ESAT",
  "year": 2026,
  "title": "ESAT Mathematics 1 AI practice",
  "question_type_counts": {
    "multiple_choice": 10
  },
  "difficulty_counts": {
    "easy": 2,
    "medium": 4,
    "hard": 2,
    "composite": 2
  },
  "module_counts": {
    "Mathematics 1": 10
  },
  "primary_syllabus_codes": ["110415", "110416"],
  "exclude_source_question_ids": ["ESAT_LEGACY_2023_NSAA_Q01"]
}
```

规则：

- 所有计数对象的总和必须等于 `question_count`。
- `primary_syllabus_codes` 约束每题唯一主知识点；辅助知识点可以超出该列表，但仍必须属于目标考纲。
- `exclude_source_question_ids` 中的 code 必须存在于输入题库，并且不能作为母题。
- `source_question_id`、`source_fingerprint` 和 `retained_knowledge_point` 必须与真实母题一一对应。
- `title` 和 `year` 提供时，生成结果 metadata 必须完全一致。
