# 试卷处理共享核心

此目录是 `exam-paper-parser`、`exam-paper-generator` 与 `exam-paper-assembler` 的共享资源，不是可直接触发的 Skill。

它统一维护：

- `schema/exam-document.schema.json`：解析、生成与组卷共用的唯一正式数据契约；
- `syllabus/`：ESAT、TMUA、STEP 的考纲数据；
- `python/exam_paper_core/`：契约验证、题目指纹、跨试卷保守去重、断点状态、ESAT 组卷和只读预检。

约定：用户界面、日志、报告与提示词使用简体中文；题目正文和选项保留英文；字段名、枚举、命令参数及错误码保持英文，以保证机器接口稳定。

正式文档契约版本为 `3.3.0`。解析、生成与组卷草稿均只允许根字段 `metadata` 和 `questions`，最终导出必须经共享验证器构建，禁止由模型直接拼装正式根字段。
