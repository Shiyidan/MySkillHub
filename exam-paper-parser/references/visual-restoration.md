# 视觉内容恢复规则

## 优先级

1. 可准确转写的公式、表格和坐标值使用文本或 LaTeX。
2. 简单几何图、函数图或电路图使用结构化 `diagram` 描述。
3. 复杂且无法可靠重建的图形保留源页引用，并在质量检查中标记人工复核。

## images[] 必填结构

题目依赖图形、表格、坐标系、电路图、几何示意或选项图时，必须在 `title` 或选项内容中放置 `image_ref`，并在 `images[]` 中登记对应资产：

```json
{
  "image_id": "q01_svg",
  "role": "question",
  "source_page": 1,
  "bbox": [72.0, 120.0, 280.0, 240.0],
  "restore_method": "redraw_svg",
  "asset_path": "assets/ESAT_LEGACY_2023_NSAA_Q01.svg",
  "alt_text": "A labelled geometry diagram used in the question.",
  "status": "restored"
}
```

- `image_id` 必须与内容块中的 `image_ref.image_id` 一致。
- `bbox` 必须对应源页可打印题面区域，不包含页眉、脚注、水印或相邻题。
- 已恢复图形必须设置 `status="restored"`，且 `restore_method` 为 `vector_extract`、`render_crop` 或 `redraw_svg` 之一，`asset_path` 不得为空。
- 无需图形时 `images` 使用空数组，`diagram` 使用 `null`。
- SVG 或重绘图形必须高保真保留标签、单位、箭头、比例关系和阴影区域；无法确认的元素不得凭常识补全。

## 禁止行为

- 不凭常识补全被裁切的数值、标签、箭头或比例。
- 不把示意图默认视为按比例绘制。
- 不用 OCR 推测替代视觉核验。
- 不丢失图注、坐标轴单位、方向标记和阴影区域。

`diagram` 为 `null` 表示题目不依赖图形；存在图形时应给出足以重建题意的英文结构化描述，使题目语言保持英文。
