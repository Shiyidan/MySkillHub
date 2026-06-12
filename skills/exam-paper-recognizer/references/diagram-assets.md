# 图形资产

使用三层图形资产模型：

```text
source_crop -> display SVG/image -> diagram_spec
```

## 三层含义

- `source_crop`: 从 PDF 页面裁剪出的原始图片。作为证据和视觉 fallback，建议长期保留。
- `svg`: 当图形足够简单、可重绘时，作为优先展示资产。
- `diagram_spec`: 图形的语义 JSON 描述。用于生成解析、提取知识点、生成同类题和重绘图形。

SVG 是绘图格式，不一定可靠表达语义；`diagram_spec` 才负责表达“图中有什么、关系是什么”。

## 资产策略

1. 每个图都保存或引用原始裁剪图。
2. 简单线图、几何图、坐标图、受力图、简单电路图、简单统计图优先生成 SVG。
3. 照片、复杂实验装置、多子图、复杂表格、噪声扫描图、需要很长 SVG 的图，回退到原始裁剪图。
4. 公式尽量使用 LaTeX，不作为图片资产。
5. 表格优先使用 table JSON，除非表格本身只是视觉图。

## 高还原度规则

区分视觉还原度和语义还原度：

- 前端展示优先选择视觉上最接近原图的资产。
- 解析、知识点和同类题生成优先使用 `diagram_spec`。
- 如果 SVG 无法核验或可能不准确，展示层回退到原始裁剪图，但仍可保留语义结构。

## SVG 与源图对照自检

生成 SVG 后必须和源图裁剪图或页面截图进行对照：

- 视觉对照：整体布局、关键点位置、线段方向、曲线走势、标签位置、坐标轴和表格结构。
- 语义对照：题干中给出的长度、比例、坐标、平行、垂直、中点、切点、圆心、元件连接等约束是否被保留。
- 一致性对照：`SVG code`、`semantic`、`graph_schema` 三者不能互相矛盾。

推荐评分：

```json
{
  "quality": {
    "visual_similarity": 0.88,
    "semantic_confidence": 0.94,
    "needs_human_review": false
  }
}
```

评分含义：

- `visual_similarity`: SVG 看起来和源图有多接近。
- `semantic_confidence`: 图形语义、约束和关系是否正确。
- `needs_human_review`: 是否需要人工复核。

如果只能确认语义但视觉还原一般，可以保留 SVG 用于生成题目，但前端展示应优先使用 source crop 或标记人工复核。

推荐质量字段：

```json
{
  "quality": {
    "visual_similarity": 0.94,
    "semantic_confidence": 0.88,
    "needs_human_review": false
  }
}
```

## Diagram Spec 结构

几何图：

```json
{
  "type": "geometry",
  "coordinate_system": {"A": [10, 120], "B": [120, 120], "C": [80, 20]},
  "objects": [
    {"type": "point", "id": "A", "label": "A"},
    {"type": "segment", "from": "A", "to": "B", "label": "5 cm"},
    {"type": "angle", "vertex": "C", "label": "60 degrees"}
  ],
  "constraints": ["AB is horizontal", "AC = BC"]
}
```

坐标图：

```json
{
  "type": "coordinate_graph",
  "axes": {
    "x_label": "time / s",
    "y_label": "velocity / m s^-1",
    "x_range": [0, 10],
    "y_range": [0, 20]
  },
  "curves": [
    {"type": "line", "points": [[0, 0], [10, 20]]}
  ]
}
```

电路图：

```json
{
  "type": "circuit",
  "components": [
    {"id": "B1", "type": "battery"},
    {"id": "R1", "type": "resistor", "label": "4 ohm"}
  ],
  "connections": [["B1.positive", "R1.left"], ["R1.right", "B1.negative"]]
}
```

电路图还原要求：

- 先抽取拓扑，再生成 SVG。拓扑包括节点、支路、元件端点和串并联关系。
- `components` 至少记录 `battery`、`resistor`、`ammeter/voltmeter`、`switch` 等元件；开关必须有 `state`。
- `nodes` 用稳定 id 表示黑点、分叉点和等电势导线段，例如 `N_left`, `N_right`。
- `branches` 描述每条支路经过的元件顺序，例如 `N_left -> A1 -> R1 -> N_right`。
- `connections` 描述元件端点与节点的连接，不能只依赖 SVG 外观。
- 如果题干中有“switch is open/closed/now closed”，语义中同时记录 `diagram_state` 和 `reasoning_state`，避免把源图状态和题目要求混淆。
- SVG 的导线和元件应保持细线风格，默认 `stroke-width='1'`；黑点节点、电池极板、开关触点必须清楚可见。
- SVG 不得补充源图没有的 `+/-`、电阻值、电流箭头或文字标签。电池极性只有在源图明确标出时才绘制。
- 导线路由应按源图的可见折线结构还原，保留上支路、下支路、左右竖线和节点的相对位置；不要为了美观把电路重新排版。

## SVG 提示词规则

- JSON 内嵌 SVG 时使用单行字符串。
- SVG 属性优先使用单引号，减少 JSON 转义。
- 使用简单线条和填充，避免渐变、阴影、滤镜和无关装饰。
- 标签尽量放在线外，不要压线或遮挡关键结构。
- 标签必须避让相邻线段、顶点和填充区域；如果标签与线段重合，优先移动标签，不要移动题干约束决定的点位。
- 不要编造原图没有的标签、长度或测量值。
- 复杂图不要强行生成 SVG，使用 `[[FIG]]` 或指向原始裁剪图的 asset。

## SVG 展示规范

- SVG 根节点必须包含显式 `width`、`height`、`viewBox`。
- SVG 根节点必须包含类似 `style='width:260px;max-width:100%;height:auto;display:block'` 的尺寸控制，避免在前端撑满页面。
- 普通几何图建议尺寸为 `width='240-300'`、`height='200-260'`。只有复杂图才允许更大。
- 默认线宽为 `stroke-width='1'`，允许 `0.8-1.2`；不要使用粗线模拟原图。
- 线条 group 建议加 `vector-effect='non-scaling-stroke'`，减少前端缩放造成的线宽失真。
- 文本标签字号保持在 `10-13`；标签位置应接近源图，但不能遮挡关键线条。
- 方形、坐标轴、电路结构等基础比例必须和源图视觉接近，不能只根据想象重新排版。
- 对几何题，SVG 展示点位也必须优先满足题干明确给出的比例、长度、坐标、平行、垂直、中点、切点、圆心等约束。
- 对 `[diagram not to scale]` 的几何题，`graph_schema` 保存精确数学约束，SVG 使用这些约束生成展示图；只有在不违背题干约束的前提下才贴近源图视觉。源图视觉点位可另存为 `measured_visual_coordinates`。

## 推荐展示决策

```text
简单语义图且视觉置信度高 -> SVG
简单语义图但视觉不确定 -> 原始裁剪图展示 + diagram_spec
复杂图或照片类图 -> 原始裁剪图 + alt text
公式 -> LaTeX
表格 -> table JSON
```
