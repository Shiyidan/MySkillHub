---
name: exam-paper-recognizer
description: 识别英文考试试卷 PDF 或页面图片，并转化为可校验、可入库的增强版项目 JSON；支持 ESAT/ENGAA 等英文试卷、题号/题干/选项/公式/图片识别、SVG 图形资产、graph_schema 图形语义结构、题型/科目/难度/知识点/生成画像、分批处理、JSON-in-Markdown 上传容器和项目格式适配。Use when Codex needs to process exam PDFs or page images, improve OCR prompts, validate extracted questions, generate JSON-in-Markdown containers, or design JSON schemas for question banks.
---

# 试卷识别专家

## 核心原则

当前默认输出是 `references/project-question.schema.json` 对应的清爽版项目 JSON。根层级只允许：

```text
questions
```

每道题保留项目入库、渲染、筛选、解析展示和后续生题真正需要的字段：

```text
number / title / content_blocks / options / answer / images
subject / subject_code / topic / topic_code / question_type / difficulty / syllabus_points / knowledge_points / skills / learning_analysis / generation_profile
```

不要把调试或处理过程信息写入 final JSON，包括：

```text
paper / extraction / rendering / answer_source / knowledge_mapping / source_pdf / skill_version / confidence / quality / difficulty.reason / difficulty.rubric
```

Markdown 只作为“结构化 JSON 的上传容器、说明书和人工审核入口”。不要从自然 Markdown 正文反推题目结构。

优先采用这条流程：

```text
PDF -> 页面检查 -> 按页/按题分批 -> 增强版项目 JSON -> 结构校验 -> 源文件对照自检 -> JSON-in-Markdown 容器 -> 项目导入
```

不要采用这条主流程：

```text
PDF -> 自然 Markdown -> Markdown 解析器 -> 数据库 JSON
```

如果需要上传 `.md`，使用 JSON-in-Markdown：Markdown 中必须包含完整解析后的 fenced `json` 代码块，项目解析时只读取该 JSON 代码块。frontmatter 和正文说明只用于来源追踪、版本标记和人工备注。

## 工作流

1. 先检查 PDF。
   - 运行 `scripts/inspect_pdf.py <pdf> --out <artifact-dir> --render-pages 1,2`。
   - 检查页数、文本层质量、页面尺寸、题号候选和渲染页面。
   - 文本层里的题号候选只能作为提示；图表数字、选项数字、说明文字里的数字都可能造成误判。
   - 如果 PDF 有文本层，优先利用文本层；但始终保留页面渲染图，用于版面判断、图形裁剪和人工核验。

2. 制定分批计划。
   - 不要让视觉模型一次处理整份试卷。
   - 先按页面窗口处理，再按识别到的题目区域或题目跨度处理。
   - 对可能跨页的题目使用重叠页面窗口。
   - 每道题保留来源证据：页码、bbox、原始裁剪图路径和置信度。
   - 调试阶段如用户要求“只识别前十题”，将 `max_questions` 设为 `10`，提示词只允许输出题号 `1-10`，后处理丢弃 `number > 10` 的题目，并用 `scripts/validate_question_json.py <json> --max-question 10` 校验。

3. 抽取增强版项目 JSON。
   - 默认使用 `references/project-question.schema.json`。
- 保留英文原文、选项标签、公式表达和有意义的段落换行。
- PDF 自动折行和 OCR token 边界不是段落边界。句内变量不得拆成独立段落；原卷中多行独立公式必须逐行保存，并在结构化内容块中保留 `left/center/right` 对齐语义。本规则对 ESAT、TMUA、ENGAA、NSAA 和 STEP 全局生效。
   - 数学表达式必须使用 Markdown + LaTeX：行内公式用 `$...$`，独立公式用 `$$...$$`。不要把 `π`、根号、上下标、分式退化为 `?`、`sqrt`、`^` 或普通斜杠文本。
   - 必须保留基础字段 `number/title/options/answer/images`，确保项目现有入库和渲染链路可继续工作。
   - `title` 是兼容展示字段，也必须保留段落换行和 LaTeX 公式；如果题干中有居中/独立公式，`title` 中也要用空行 + `$$...$$` 单独表示。
   - `options[].text` 是兼容展示字段，含数学符号时也必须使用 LaTeX，例如 `$R=2\\sqrt{5}r$`、`$2.5\\,\\mathrm{g\\,cm^{-3}}$`。
   - 对原题中“文字 - 图片/图表 - 文字”的排版，必须额外生成 `content_blocks` 保存原始阅读顺序；不要只依赖 `title + images`，否则图片会被渲染到题干末尾。
   - `content_blocks` 中使用 `paragraph`、`formula`、`image_ref`、`line_break` 等块；`image_ref.image_id` 必须能对应到 `images[].id` 或 `images[].alt`。
   - 尽量补充 `subject/subject_code/topic/topic_code/question_type/difficulty/syllabus_points/knowledge_points/skills/learning_analysis/generation_profile`。
   - ESAT/ENGAA 风格试题必须使用两套知识点字段，不要混用：
     - `syllabus_points` 对应 `references/esat-knowledge-tree.json`，这是项目左侧简版考纲 tree，供前端筛选使用。
     - `knowledge_points` 对应 `references/esat-medium-knowledge-tree.json`，这是 medium/official 考纲 tree，供细化知识点、诊断报告和后续生题使用。
   - `subject_code/topic/topic_code` 来自 `syllabus_points` 主考点在简版考纲树中的父级路径，用于前端定位左侧 tree 的科目和 topic 层级；不要自由填写。
   - `subject_code` 对应简版考纲 tree 的科目节点 code，例如 `110000`；`topic` 和 `topic_code` 对应下一层 topic 节点，例如 `Number & Arithmetic (算术与数)` 和 `111000`。
   - `syllabus_points[]` 必须选择简版考纲 tree 的叶子节点，必须同时输出 `code`、`label`、`role`，且 `code/label` 与 `esat-knowledge-tree.json` 一致。例如 `{"code":"132001","label":"Circuits (电路)","role":"primary"}`。
   - `knowledge_points[]` 必须选择 medium 考纲 tree 的叶子节点，必须同时输出 `code`、`label`、`role`，且 `code/label` 与 `esat-medium-knowledge-tree.json` 一致。例如 `{"code":"P1.2","label":"Electric circuits (电路)","role":"primary"}`。
   - `knowledge_points[].label` 不要重复包含 code；不要输出 `confidence`。
   - 一道题可以对应多个 `syllabus_points` 和多个 `knowledge_points`；主考点使用 `role: "primary"`，辅助考点使用 `role: "secondary"`。不要自由发明不存在于对应考纲树的 code。
   - 难度 `difficulty` 只输出一个字符串枚举：`easy`、`medium`、`hard`、`composite`、`unknown`。不要输出 `score`、`reason`、`rubric`、`label` 或 `label_zh`。
   - 难度判断规则：`easy` 为基础知识和直接公式应用；`medium` 为多步推导或基础公式灵活变形；`hard` 为生僻考点、复杂场景变换、严谨证明或高认知负荷；`composite` 为多个知识点串联，例如图像 + 单位换算 + 物理公式、几何 + 比例 + 代数面积计算。
   - `learning_analysis` 面向中文学生展示，包含 `exam_focus`、`solution`、`review_guidance`。
   - 默认生成短解析：`learning_analysis.exam_focus`、`learning_analysis.solution`、`learning_analysis.review_guidance` 每部分不超过 50 个中文字符；除非用户明确要求详细解析，不要生成长篇步骤。
   - 学生侧解析必须使用中文；涉及公式时继续使用 Markdown + LaTeX，例如 `$F=ma$`、`$\\frac{1}{2}mv^2$`。
   - `learning_analysis` 直接保存三段展示文本，不要输出 `language`、`status`、`steps`、`final_answer`、`distractor_analysis` 等过程字段。
   - `exam_focus` 可以由 `knowledge_points` 派生，但不要直接替代 `knowledge_points`：前者是可展示的“考察点”，后者是 medium 粒度结构化知识标签。
   - `solution` 保存题目解析，`review_guidance` 保存复习引导；二者不属于 `generation_profile`。
   - 图形题尽量补充 `images[].diagram_type`、`images[].semantic`、`images[].graph_schema`。图形复核分数和人工审核标记只放在 artifacts，不写入 final JSON。
   - 模型直接输出 JSON 时，必要时使用占位符降低解析失败率：`[[BS]]`、`[[NL]]`、`[[PARA]]`、`[[FIG]]`。

4. 公式和图形分开处理。
   - 公式尽量存为文本或 LaTeX，不要优先作为图片。
   - 图形资产使用三层结构：原始裁剪图 + 可选 SVG + `semantic/graph_schema`。
   - 在设计或修改图片/SVG 策略前，读取 `references/diagram-assets.md`。
   - 几何图必须优先恢复题干给出的约束关系；坐标允许约 2% 视觉误差，但比例、平行、垂直、中点、切点、圆心等约束必须优先正确。
   - SVG 必须显式控制展示尺寸、线宽和 viewBox。普通几何图默认宽度控制在 220-320px，线宽约 1px，不允许生成占满页面或粗线条的 SVG。
   - 几何 SVG 的点位也必须优先满足题干约束，不能只在 `graph_schema` 中保存正确比例而让 SVG 展示比例错误。
   - 标签必须避让线段、顶点和阴影区域；如果标签与线段重合，优先移动标签。
   - 对标注 `[diagram not to scale]` 的图，优先级为：题干明确约束 > 图形拓扑和相对位置 > 源图视觉近似。`graph_schema` 保存精确数学比例和几何约束；SVG 用这些约束生成可读展示图，并在不违背题干时贴近源图视觉。

5. 结构校验。
   - 如果用户同时提供 answer key / mark scheme / 答案 PDF，先运行 `scripts/parse_answer_key.py <answer-key.pdf> --out <artifact-dir>/answer_key.json`。
   - 如果已经有试题 JSON，运行 `scripts/parse_answer_key.py <answer-key.pdf> --question-json <questions.json> --out-question-json <merged.json>`，按题号把答案写入 `questions[].answer`。
   - 合并答案时只把答案写入 `questions[].answer`。答案 PDF 路径、匹配方式和置信度只能写入 artifacts，不要写入 final JSON。
   - 如果答案 key 中缺少某题、题号重复、答案超出选项范围，必须在 artifacts 中标记，不能静默忽略。
   - 运行 `scripts/validate_question_json.py <json>`。
   - 校验基础字段、题号范围、选项、题干、图片字段、SVG XML 结构、考纲 `code/label` 对应关系，以及中文解析字段编码。
   - 如果 `learning_analysis.exam_focus`、`learning_analysis.solution`、`learning_analysis.review_guidance` 或其他学生可见文本出现 `???`、`����`、控制字符、典型 mojibake 字符，必须重写对应字段并重新校验；不要交付乱码 JSON。
   - 短解析字段必须包含正常中文字符；如果只剩问号、拼音、乱码或空文本，视为解析失败。
   - 结构校验失败时，先修复 JSON，不要进入最终导出。

6. 源文件对照自检。
   - 对每道题使用源 PDF 文本层、页面渲染图、题目区域截图或图形裁剪图进行对照。
   - 文本准确度：检查题号、题干、选项数量、选项文本、公式、单位、上下标是否和源文件一致。
   - 图形准确度：检查 SVG/semantic/graph_schema 是否和源图一致，包括图形类型、标签、关键点、线段/曲线、坐标轴、表格、元件、连接关系。
   - 几何图必须检查 `graph_schema.coordinate_system`、`constraints`、`derived_points` 是否符合题干给出的比例、长度、平行、垂直、中点、切点、圆心等约束。
   - 坐标图必须检查 `x_label/y_label/points/curve` 是否和源图一致。
   - 电路图必须先检查拓扑连接，再检查视觉还原；必须核对元件、节点、支路、串并联关系、开关状态、电表、电阻、电源和连接关系是否完整。
   - 电路题中如果源图状态和题目推理状态不同，例如图中开关打开但题干说“now closed”，必须分别写入 `diagram_state` 和 `reasoning_state`。
   - 电路 SVG 不得添加源图没有的 `+/-`、元件值、方向箭头或说明文字；导线路由必须尽量按源图折线结构还原，不要重新排版。
   - 自检结果写入 artifacts 中的审核记录，不要写入 final JSON。低置信度内容应进入人工复核队列。
   - 如果无法可靠比较 SVG 和源图，保留 SVG，但在 artifacts 中标记人工复核；不要在 final JSON 中写视觉相似度等调试字段。

7. 导出。
   - 进入 final 前，先运行 `scripts/clean_final_json.py <raw-or-merged.json> <final.project.json>`，移除调试字段并生成清爽版 `{"questions":[...]}`。
   - 默认用 `scripts/render_review_markdown.py <final.project.json> <out.md>` 生成 JSON-in-Markdown 容器。
   - 如果确实需要自然语言审核稿，使用 `scripts/render_review_markdown.py <json> <out.md> --mode review`。
   - 项目导入 `.md` 时，只提取 fenced `json` 代码块并校验 JSON。
   - 校验失败、题号缺失、题干为空、选项缺失、内容对照不一致、图形置信度低的题目，都应该进入重试或人工复核队列。

## 默认输出位置

除非用户另行指定，所有输出都放到桌面 `output` 目录下，并按“当前上传的试卷文件名”再建一层目录。不要把试卷处理中间产物写入 `.skill-build`。

```text
C:\Users\daguan\Desktop\output\<试卷文件名>\
  final\
    <试卷文件名>.project.json
    <试卷文件名>.json.md
    <试卷文件名>.review.md
  artifacts\
    page_manifest.json
    page-text\
    pages\
    crops\
```

目录名使用 PDF 文件名去掉扩展名后的名称。例如 `ENGAA_2023_S1_QuestionPaper.pdf` 的默认输出目录为：

```text
C:\Users\daguan\Desktop\output\ENGAA_2023_S1_QuestionPaper
```

`final` 放可交付文件：清爽版项目 JSON、JSON-in-Markdown 容器、可选自然语言审核 Markdown。`artifacts` 放调试中间产物和审核记录：页面文本层、渲染页图、页面清单、裁剪图、来源信息、答案匹配日志、taxonomy 说明和质量检查结果。

## 输出要求

默认输出清爽版项目 JSON：

```json
{
  "questions": [
    {
      "number": 1,
      "title": "Question text",
      "options": [{"label": "A", "text": "Option"}],
      "answer": [],
      "images": [],
      "subject": "Mathematics",
      "subject_code": "110000",
      "topic": "Algebra (代数)",
      "topic_code": "112000",
      "question_type": "single_choice",
      "difficulty": "medium",
      "syllabus_points": [
        {"code": "112004", "label": "Formula rearrangement (公式变换)", "role": "primary"}
      ],
      "knowledge_points": [
        {"code": "M4.7", "label": "Rearranging formulae (公式变形)", "role": "primary"}
      ],
      "skills": ["formula manipulation"],
      "learning_analysis": {
        "exam_focus": "考查公式变形与代数化简。",
        "solution": "先移项再交叉相乘，注意符号。",
        "review_guidance": "复习分式方程和变形符号。"
      },
      "generation_profile": {
        "can_generate_similar": true,
        "generation_focus": ["改变变量位置或分式结构"]
      }
    }
  ]
}
```

JSON-in-Markdown 输出使用以下容器格式：

````md
---
schema: project-question.schema.json
source: ENGAA_2023_S1_QuestionPaper.pdf
content_type: parsed_question_json
---

```json
{
  "questions": []
}
```
````

项目导入 `.md` 时，只提取 `json` 代码块作为数据源；frontmatter 和正文说明不参与入库。

## 资源说明

- `references/project-question.schema.json`：当前项目实际使用的增强版 JSON schema。
- `references/esat-knowledge-tree.json`：项目左侧简版考纲 tree，供 `syllabus_points[].code/label` 匹配和前端筛选。
- `references/esat-medium-knowledge-tree.json`：medium/official 考纲 tree，供 `knowledge_points[].code/label` 匹配、诊断报告和后续生题。
- `references/question-paper.schema.json`：长期通用内容库 schema 参考，不作为当前默认输出。
- `references/diagram-assets.md`：图片、SVG 和 `graph_schema` 的处理策略。
- `references/prompt-rules.md`：通用抽取提示词规则。
- `references/project-integration.md`：项目字段兼容和 JSON-in-Markdown 规则。
- `scripts/inspect_pdf.py`：检查 PDF 文本层、页面元数据，并渲染页面图片。
- `scripts/validate_question_json.py`：校验抽取后的 JSON，输出结构问题。
- `scripts/render_review_markdown.py`：默认生成 JSON-in-Markdown；可选生成自然语言审核稿。
- `scripts/normalize_extraction.py`：从模型原始输出中提取 JSON、修复常见 JSON 问题，并解码占位符。
- `scripts/clean_final_json.py`：把中间 JSON 压缩为 final 可入库清爽 JSON，只保留 `questions`。
