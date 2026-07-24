# 提示词规则

这些规则用于指导任意视觉/多模态模型的试卷抽取提示词，不绑定具体模型服务。

## JSON 安全

要求模型直接输出 JSON 时，可以使用占位符降低解析失败率：

- `[[BS]]` 表示反斜杠 `\`
- `[[NL]]` 表示段内强制换行
- `[[PARA]]` 表示段落分隔
- `[[FIG]]` 表示复杂图片占位

原因：LaTeX 反斜杠和 JSON 字符串中的真实换行，是模型输出 JSON 时最常见的解析失败来源。

## 编码与乱码自检

- 所有学生可见中文字段必须使用正常 UTF-8 中文，不允许出现 `???`、`����`、控制字符或 mojibake。
- 重点检查 `learning_analysis.exam_focus_text`、`learning_analysis.exam_focus[].title`、`learning_analysis.exam_focus[].description`、`learning_analysis.solution.summary`、`learning_analysis.review_guidance.summary`。
- `learning_analysis.language = "zh-CN"` 时，上述中文解析字段必须包含正常中文字符；如果只剩问号、英文占位或乱码，必须重写该字段。
- 不要通过 PowerShell 内联中文字符串批量写入最终 JSON；需要批量修复时，使用 UTF-8 `.py` 脚本或 UTF-8 JSON 模板文件。
- 导出前必须运行 `scripts/validate_question_json.py <json>`。如果校验提示 `may be garbled` 或 `contains no Chinese characters`，不要交付，先重新生成对应解析字段。

## 文本抽取

- 保留英文原文，不要改写题干和选项。
- 只在影响阅读或公式布局时保留段落分隔和强制换行。
- PDF 的自动折行、OCR token 边界和字体切换不是段落边界。句内变量即使单独识别为 LaTeX，也必须与前后文字保留在同一个 paragraph 中，例如 `where $a$ is a real constant.`。
- 不要把普通英文散文包进 LaTeX 命令。
- 默认用 `$...$` 表示行内公式或独立公式，除非目标项目要求其他格式。
- 兼容字段 `title` 和 `options[].text` 也必须使用 Markdown + LaTeX。不要只在 `content_blocks[].formula` 中保存正确公式，否则旧渲染链路仍会显示错误。
- 对源题中独立居中的公式，`title` 中使用空行 + `$$...$$` + 空行保留版式，例如：`Given that\n\n$$...$$\n\nwhat is ...?`。
- 原卷中连续的多行独立公式必须逐行保存，不得用 `\qquad` 拼成一行，也不得只为减少块数量而合并为一个 `aligned` 公式。
- 根号、分式、上标、下标和希腊字母必须使用 LaTeX：`\\sqrt{}`、`\\frac{}{}`、`^{}`、`_{}`、`\\pi`。不要输出 `?`、`sqrt( )`、`^2` 或普通 `/` 分式作为最终展示文本。
- 在占位符模式下，单位建议写成 `[[BS]]mathrm{}`。

## 题目结构

模型输出只允许是 JSON 对象，不要输出解释文字或 Markdown。

## 调试范围限制

当用户要求调试模式、首轮测试、或只识别前十题时，把这段硬约束加入识别提示词：

```text
调试模式：只识别并输出前 10 道题。
仅输出题号 1 到 10 的题目；如果页面中出现第 11 题或之后的题目，忽略。
不要为了凑满 10 题而编造题目。
如果当前批次只包含部分前 10 题，只输出当前批次中实际出现的题目。
输出 JSON 中不得包含 number > 10 的题目。
```

流水线也要执行同样限制：

```text
max_questions = 10
drop questions where number > 10
stop scheduling later batches once Q10 is complete and validated
validate with scripts/validate_question_json.py <json> --max-question 10
```

项目兼容结构。调试早期可只输出基础字段；正式抽取时应尽量输出完整字段：

```json
{
  "questions": [
    {
      "number": 1,
      "title": "Question stem",
      "options": [{"label": "A", "text": "Option text"}],
      "answer": [],
      "images": [],
      "subject": "Physics",
      "subject_code": "130000",
      "topic": "Mechanics (力学)",
      "topic_code": "131000",
      "question_type": "graph_interpretation",
      "difficulty": "medium",
      "syllabus_points": [
        {"code": "131004", "label": "Energy, work & power (能量、功与功率)", "role": "primary"},
        {"code": "111001", "label": "Unit conversion (单位换算)", "role": "secondary"}
      ],
      "knowledge_points": [
        {"code": "P3.3", "label": "Force and extension (力与伸长)", "role": "primary"},
        {"code": "P3.7", "label": "Energy (能量)", "role": "secondary"},
        {"code": "M1.2", "label": "Unit conversion (单位换算)", "role": "secondary"}
      ],
      "skills": ["graph interpretation", "unit conversion"],
      "learning_analysis": {
        "exam_focus": "考查弹簧能量、图像读数与单位换算。",
        "solution": "由图得 $x^2=25$，换成米后代入 $E=\\frac12Fx$。",
        "review_guidance": "复习弹性势能公式、图像变量和单位换算。"
      },
      "generation_profile": {
        "can_generate_similar": true,
        "generation_focus": [
          "改变图像斜率",
          "改变能量或伸长量",
          "设置单位换算干扰"
        ],
        "common_distractors": [
          "误把 $x^2=25$ 当作 $x=25$",
          "忘记 cm 到 m 的换算"
        ]
      }
    }
  ]
}
```

## ESAT 考纲 code 匹配规则

- ESAT/ENGAA 风格试题必须同时使用两套考纲依赖：
  - `references/esat-knowledge-tree.json`：项目左侧简版考纲 tree，供 `syllabus_points` 使用。
  - `references/esat-medium-knowledge-tree.json`：medium/official 考纲 tree，供 `knowledge_points` 使用。
- 两份依赖都是 Element UI tree 形态，每个节点只有 `code`、`label` 和可选 `children`。
- `subject_code`、`topic`、`topic_code` 必须由 `syllabus_points` 的主考点在简版考纲树中的父级路径推导：
  - `subject_code` 对应科目节点 code，例如 `130000`。
  - `topic` 对应下一层 topic 节点 label，例如 `Mechanics (力学)`。
  - `topic_code` 对应下一层 topic 节点 code，例如 `131000`。
- 如果一道题有多个 `syllabus_points`，使用 `role: "primary"` 的点推导；没有 primary 时使用第一个点推导。
- `syllabus_points` 只能选择简版考纲 tree 的叶子节点，不要选择 exam、subject 或 topic 父节点。
- `knowledge_points` 只能选择 medium 考纲 tree 的叶子节点，不要选择父节点。
- 每个 `syllabus_points[]` 至少输出：
  ```json
  {"code": "132001", "label": "Circuits (电路)", "role": "primary"}
  ```
- 每个 `knowledge_points[]` 至少输出：
  ```json
  {"code": "P1.2", "label": "Electric circuits (电路)", "role": "primary"}
  ```
- `code` 和 `label` 必须与各自依赖文件中的节点保持一致，不要自由发明 code、缩写或新 label。
- `knowledge_points[].label` 不要重复包含 code，不要写成 `P1.2 Electric circuits (电路)`。
- 不要在 `syllabus_points[]` 或 `knowledge_points[]` 中输出 `confidence`；复核信息只写入 artifacts，不写入 final JSON。
- 一道题可以对应多个 `syllabus_points` 和多个 `knowledge_points`；主考点设置 `role: "primary"`，辅助考点设置 `role: "secondary"`。
- 如果题目涉及跨知识点综合，保留多个知识点，并将 `difficulty` 优先标为 `composite`。
- 如果无法精确匹配，选择最接近的叶子节点，并在 artifacts 中说明；不要输出不存在于考纲树的 code。

## 学生侧解析字段

- `syllabus_points` 是前端筛选标签，对应左侧简版 tree。
- `knowledge_points` 是 medium 粒度结构化知识标签，用于诊断报告、同类题生成和更细归类。
- `learning_analysis.exam_focus` 是学生可见的“考察点”，通常由 `knowledge_points` 派生，但表述应更接近前端展示文案。
- `learning_analysis.solution` 是题目解析字段；只输出短文本，不要输出 `status`、`summary`、`steps`、`final_answer`、`distractor_analysis` 等嵌套过程字段。
- `learning_analysis.review_guidance` 是复习引导字段；它可以参考 `knowledge_points`、`skills`、`difficulty` 和错因分析生成，但不等同于 `generation_profile`。
- `generation_profile` 只用于同类题生成，默认只保留 `can_generate_similar`、`generation_focus`、`common_distractors`。
- 学生侧解析默认使用中文，写给中文学生看；不要输出英文解释。
- 默认生成短版三段：`learning_analysis.exam_focus`、`learning_analysis.solution`、`learning_analysis.review_guidance`。每段不超过 50 个中文字符。
- 如果解析涉及数学或物理公式，公式仍使用 Markdown + LaTeX，例如 `$P=VI$`、`$\\sqrt{10}$`。
- 不要为了填充字段生成冗长步骤。
- `learning_analysis.exam_focus` 对应前端“考察点”，`learning_analysis.solution` 对应“题目解析”，`learning_analysis.review_guidance` 对应“复习引导”。

## 难度分层规则

- `easy` / 简单：考查基础知识、基本公式或单一步骤应用；学生主要需要识别概念并直接代入。
- `medium` / 中等：需要多步推导、公式变形、比例/单位处理或对基础公式做灵活应用，但知识点主线相对单一。
- `hard` / 困难：包含生僻考点、复杂场景变换、严谨证明、隐含条件较多或高认知负荷推理。
- `composite` / 复合：跨知识点或跨章节综合，例如图像解读 + 单位换算 + 物理公式，几何约束 + 比例 + 代数面积计算，电路拓扑 + 功率 + 并联电阻。复合题不一定比 `hard` 更难，但需要多个知识点串联。
- 如果一道题同时满足 `medium` 和 `composite`，优先标为 `composite`。不要输出难度解释、分数、rubric 或中文 label；前端负责枚举值展示。

## 答案 Key 识别规则

- 当用户同时提供 question paper 和 answer key / mark scheme / 答案 PDF 时，必须解析答案文件并按题号填入 `questions[].answer`。
- answer key 常见格式包括表格、`Q1 A`、`Question 1: A`、或题号与答案分行。解析时优先使用文本层；文本层不可靠时再用页面图像核验。
- `answer` 统一为数组，例如单选题为 `["A"]`，多选题为 `["A", "C"]`。
- 合并答案后只写入 `questions[].answer`，不要写入 `answer_source`。
- 如果答案 key 与试题 JSON 的题号范围不一致，在 artifacts 中记录，不要写入 final JSON。
- 不要根据模型推理解答覆盖 answer key；正式答案以 answer key 为准。模型推理答案只能写入解析字段或备注。

长期 canonical 结构：

```json
{
  "questions": [
    {
      "number": 1,
      "type": "single_choice",
      "stem": {"blocks": [{"type": "paragraph", "text": "Question stem"}]},
      "options": [{"label": "A", "blocks": [{"type": "text", "text": "Option text"}]}],
      "assets": []
    }
  ]
}
```

## 图片和 SVG 规则

- 只有题目确实依赖图片、图表、表格或示意图时，才添加图片资产。
- 如果图片或图表位于题干中间，必须生成 `content_blocks` 来保存原始顺序，例如：段落、段落、`image_ref`、段落。不要只把图片放入 `images` 数组末尾。
- `title` 保持向旧项目兼容的展示题干；必须保留段落换行，并用 Markdown + LaTeX 表示数学公式。精确版面顺序以 `content_blocks` 为准。
- `content_blocks` 中的独立公式必须保留源公式行数和对齐方式；项目格式支持时写入 `align: "left" | "center" | "right"`，居中依据是公式相对正文内容栏的位置。
- `content_blocks[].image_ref.image_id` 必须对应 `images[].id`，或在没有 `id` 时对应可稳定匹配的 `images[].alt`。
- 简单图优先使用 `diagram_spec` + SVG。
- 每个抽取出的图都应保留原始裁剪图作为 fallback。
- 对密集多子图、复杂表格、超过五个选项图、或 SVG 可能超过约 1500 字符的图，不要强行生成 SVG。
- 如果 JSON 内嵌 SVG，SVG 必须是单行字符串，SVG 属性优先使用单引号。
- 几何图尽量提供 coordinate system 和 constraints。
- 坐标图尽量提供轴标签、范围、点/曲线和图形类型。

### SVG 展示尺寸和观感硬规则

- 内嵌 SVG 必须设置显式 `width`、`height`、`viewBox` 和 `style`，避免前端默认把图放得过大。
- 普通题目内图建议宽度 `220-320px`；几何图默认可用 `width='260' height='230'` 左右。除非源图本身很复杂，不要超过 `width='360'`。
- SVG 根节点建议包含：`style='width:260px;max-width:100%;height:auto;display:block'`。
- 线段默认 `stroke-width='1'`，允许范围 `0.8-1.2`。禁止使用 `stroke-width >= 2`，除非源图明显是粗线。
- 线条组必须尽量使用 `vector-effect='non-scaling-stroke'`，避免前端缩放时线段变粗。
- 标签字号保持克制，几何图通常 `font-size='10'` 到 `13'`，不要生成巨大标签。
- 标签必须避让线段、顶点和阴影区域；标签与相邻线段至少保持约 `3-6` 个 SVG 单位的空隙，不能压在线上或和线段重合。
- SVG 必须保留源图的基础视觉比例：方形应接近方形，点位上下左右关系必须和源图接近。
- 几何图的 SVG 点位也必须优先满足题干给出的比例、长度、平行、垂直、中点、切点、圆心等约束；不要只在 `graph_schema` 中满足约束而在 SVG 中画错比例。
- 对标注有 `[diagram not to scale]` 的几何图，优先级为：题干明确约束 > 图形拓扑和相对位置 > 源图视觉近似。`graph_schema.coordinate_system` 保存精确数学坐标；SVG 使用这些约束生成可读、接近源图但不违背题干的展示图。
- 如果源图视觉和题干约束明显冲突，SVG 优先满足题干约束；把源图近似点位写入 `measured_visual_coordinates` 或 `quality.validation_notes`，并说明差异。

### 电路图还原硬规则

- 电路图必须先恢复拓扑连接，再绘制视觉图；不要只按外观摆放元件。
- 必须明确保存并核对：电源、电阻数量、电表类型和位置、开关状态、节点、支路、串联/并联关系。
- 不要添加源图没有的极性标记、元件数值、方向箭头或说明文字；例如源图电池没有 `+/-` 时，SVG 中也不能补 `+/-`。
- 开关必须保存 `state`，例如 `open` 或 `closed`。如果题目图中开关打开，但题干要求“now closed”，图像资产仍按源图状态绘制，并在语义中同时记录题目推理状态。
- 元件端点必须连接到具体节点；不要让导线“看起来接近”但语义上没有连接。
- 对有黑点节点的电路图，SVG 中应画出连接节点，`semantic.circuit.nodes` 中也要列出这些节点。
- 电阻、电表、开关、电源的相对支路位置必须和源图一致；如果为了可读性调整尺寸，只能等比例/小幅调整，不能改变串并联拓扑。
- 导线走线必须尽量按源图的直角折线排列；除了开关刀片等源图本身的斜线，不要新增斜线、曲线或改成不同的绕线路径。
- 电路图 SVG 线宽默认 `1`，导线、元件和文字不要过粗；图宽通常控制在 `260-360px`。

## 图形语义规则

1. `geometry` 类型图形必须优先恢复几何约束，而不是只做视觉估计。
   - 根据题目给出的长度、比例、坐标、平行、垂直、中点、切点、圆心恢复坐标。
   - 所有几何图必须生成 `graph_schema.coordinate_system`。
   - 坐标允许约 `2%` 视觉误差，但约束关系必须优先正确。
   - 如果源图标注 `[diagram not to scale]`，`graph_schema.coordinate_system` 使用题干约束恢复出的数学坐标；SVG 点位优先使用同一约束生成展示坐标，只允许为标签避让和可读性做小幅偏移。

2. `semantic` 按图形类型保存语义：
   - `geometry`: 保存顶点、形状、比例关系、平行/垂直/圆等关系。
   - `coordinate_graph`: 保存 `x_axis`, `y_axis`, `graph_kind`。
   - `circuit`: 保存电路元件、节点、支路、开关状态、串并联关系和连接关系。
   - `force_diagram`: 保存受力对象和力。
   - `statistical_chart`: 保存统计数据描述。

3. `graph_schema` 推荐结构：

```json
{
  "coordinate_system": {"A": [0, 0], "B": [1, 0]},
  "constraints": ["AB:BC=1:2"],
  "derived_points": {"M": [0.5, 0]}
}
```

坐标图推荐结构：

```json
{
  "x_label": "x axis description",
  "y_label": "y axis description",
  "points": [[0, 0], [25, 0.015]],
  "curve": "line"
}
```

## 校验清单

- JSON 可以解析。
- 题号存在且大于 0。
- 题号不重复。
- 选择题有选项。
- 选项标签已规范化。
- 题干不为空。
- 文本中出现图片占位时，存在对应 asset 或 `[[FIG]]`。
- 内嵌 SVG 不包含真实换行。
- 占位符是有意使用且可解码的。

## 源文件对照自检

抽取完成后，必须把输出结果和源 PDF 文本层/页面截图/图形裁剪图进行对照。

文本自检：

- 题号是否和源文件一致。
- 题干是否漏句、漏条件或多出内容。
- 选项数量是否一致。
- 每个选项标签和文本是否一致。
- 数学公式、上下标、根号、分数、单位是否等价。
- 段落换行是否保留了影响阅读或公式布局的信息。

图形自检：

- 输出 SVG 或图片类型是否和源图一致。
- 标签是否完整且没有编造。
- 关键线段、曲线、坐标轴、元件、表格结构是否缺失。
- `semantic` 是否描述了源图中的核心关系。
- `graph_schema` 是否足以支持后续重绘和同类题生成。

按图形类型检查：

- `geometry`: 必须有 `graph_schema.coordinate_system`，并检查比例、平行、垂直、中点、切点、圆心等约束。
- `coordinate_graph`: 必须检查 `x_label`, `y_label`, `points`, `curve`。
- `circuit`: 必须检查电源、电阻、电表、开关状态和连接关系。
- `force_diagram`: 必须检查受力对象、力的方向和标签。
- `statistical_chart`: 必须检查数据系列、坐标/类别标签和图形类型。

自检结果只写入 artifacts 中的审核记录，不要写入 final JSON。建议 artifacts 中使用类似结构：

```json
{
  "quality": {
    "text_match_confidence": 0.96,
    "option_match_confidence": 0.98,
    "formula_match_confidence": 0.92,
    "visual_similarity": 0.88,
    "semantic_confidence": 0.94,
    "needs_human_review": false
  }
}
```

如果某项无法确认，不要给高置信度；设置 `needs_human_review: true`，并在 `validation_notes` 中说明原因。
