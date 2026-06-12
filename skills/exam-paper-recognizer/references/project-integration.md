# 项目集成

本文件说明当前项目实际使用的输出格式，以及 Markdown 上传时的解析规则。

## 默认项目 JSON

默认输出使用 `references/project-question.schema.json`。它必须保留项目现有基础字段：

```ts
export interface ParsedQuestion {
  number: number
  title: string
  options: { label: string; text: string }[]
  answer: string[]
  images: { type: string; alt: string; code?: string; src?: string }[]
}
```

同时可以扩展增强字段：

```ts
subject?: string
question_type?: string
difficulty?: { level: string; score: number | null; reason: string }
knowledge_points?: { name: string; taxonomy?: string; confidence?: number | null }[]
skills?: string[]
generation_profile?: object
source?: object
confidence?: number | null
```

图片对象可以扩展：

```json
{
  "type": "svg",
  "diagram_type": "geometry",
  "alt": "A triangle with side AB labelled 5 cm.",
  "semantic": {},
  "graph_schema": {},
  "quality": {},
  "code": "<svg viewBox='0 0 150 150' ...></svg>",
  "src": "optional/fallback/crop.png"
}
```

只要项目入库和渲染逻辑忽略未知字段，增强版 JSON 可以继续兼容现有入库和渲染。

## JSON-in-Markdown 上传格式

如果项目支持上传 `.md`，Markdown 只作为 JSON 容器。项目必须提取 fenced `json` 代码块作为数据源。

推荐格式：

````md
---
schema: project-question.schema.json
source: ENGAA_2023_S1_QuestionPaper.pdf
content_type: parsed_question_json
---

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
      "question_type": "single_choice",
      "difficulty": {"level": "medium", "score": 0.5, "reason": "..."},
      "knowledge_points": [],
      "skills": [],
      "generation_profile": {}
    }
  ]
}
```
````

解析规则：

- 只读取第一个 fenced `json` 代码块，或按项目约定读取带标记的 JSON 代码块。
- frontmatter 只用于 `schema/source/content_type/version` 等元信息。
- 正文自然语言说明不参与入库。
- 提取 JSON 后必须运行 schema 校验。
- 不要从 Markdown 标题、段落或列表反推题目结构。

## 不推荐的格式

不要把题目写成自然 Markdown 再解析入库：

```md
## Question 1
Question text...

A. Option A
B. Option B

Knowledge point: algebra
```

这种格式对人友好，但字段边界、数组关系、图形语义和生成画像都不稳定。
