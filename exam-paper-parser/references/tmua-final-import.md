# TMUA 最终导入生产契约

生产实现：`scripts/export_tmua_final.py`。它是 TMUA 年度最终导出唯一入口；旧版 `export_standard_json.py` 不得用于 TMUA。
题干段落由 Core 的 `exam_paper_core.content_blocks.from_structured_parts` 在题目事务阶段重建；导出器只保留既有 `content_blocks`，不得重新拼接题干。

TMUA 最终导入文件必须直接由逐题事务生成的最终题目对象组装，不得经过旧版 `standard.json` 转换器或从字符串字段反推题干、选项、答案和图形。

## 逐题事务必须直接产出

- `title` 为首段题干文本；`content_blocks` 按原始段落逐块保存，公式使用 LaTeX 文本块。
- `options[].text` 在逐题阶段完成；不得留空，图像选项必须同时保留 `text: ""` 和 `image_id`。
- `question_type` 为 `single_choice` 时，`answer` 必须立即规范化为恰好一个选项标签的数组。
- SVG 在逐题阶段以内联对象写入 `images`，题干通过 `image_ref` 引用；不得把 `asset_path` 留给最终导出阶段解析。
- 逐题事务完成后才允许进入模块组装；模块组装不得修改题目内容。

## 年度组装

最终文件使用 `schemaVersion: "diagnostic-paper-v2"`、顶层 `code`、`metadata` 和 `modules`。TMUA 必须包含 `paper1`、`paper2` 两个模块，每个模块 20 题、75 分钟，年度总计 40 题、150 分钟。模块代码、科目名称和科目代码使用开发约定的固定值。

最终序列化只负责写出已完成对象和 UTF-8 JSON，不负责补答案、重建题干、寻找 SVG、清理业务字段或修复乱码。任何字段错误必须回退到对应逐题事务步骤修复。
