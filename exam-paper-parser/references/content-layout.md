# 题面内容与版面恢复规范

本规范适用于所有考试类型，包括 TMUA、ESAT、ENGAA、NSAA 和 STEP。它约束
canonical `title` 内容片段以及最终项目 `contentBlocks`，不得针对单一考试另写
相互冲突的拼接规则。

## 一、先判断语义，再判断换行

- PDF 文本框、OCR token 或页面自动换行不是段落边界。
- 普通散文即使在 PDF 中换到下一物理行，只要语法仍连续，就保持同一个段落。
- 只有原卷可见的段间空白、独立公式、图片/图表或明确的新段落才建立块边界。
- 不得因为字体从正文切换为数学字体，就把行内变量拆成独立段落。
- 不得添加原卷没有的逗号、句号、正负号或连接词。

例如原卷：

```text
where a is a real constant.
```

canonical 必须表示为：

```json
[
  {"type": "text", "content": "where "},
  {"type": "latex", "content": "a", "mode": "inline"},
  {"type": "text", "content": " is a real constant."}
]
```

最终项目内容块必须是一个段落：

```json
{
  "type": "paragraph",
  "text": "where \\(a\\) is a real constant."
}
```

禁止把 `where`、`a` 和其余句子拆成三个段落。

## 二、LaTeX 模式是强制字段

所有 canonical LaTeX 片段都必须声明 `mode`：

- `mode: "inline"`：变量或公式属于当前句子。不得设置 `align`。
- `mode: "block"`：公式在原卷中独立成行。必须设置 `align`。

独立公式的 `align` 只允许：

- `left`
- `center`
- `right`

对齐依据是公式块相对正文内容栏的位置，不是相对整张页面或 OCR 裁剪框的位置。
无法可靠判断时进入人工复核，不得默认把所有公式设为居中。

## 三、独立公式逐行保存

原卷中两行独立公式必须保存为两个 block，不得用 `\qquad` 拼成一行，也不得为了
减少块数量而合并成一个 `aligned` 环境。

```json
[
  {"type": "text", "content": "Consider the simultaneous equations"},
  {
    "type": "latex",
    "content": "3x^2+2xy=4",
    "mode": "block",
    "align": "center"
  },
  {
    "type": "latex",
    "content": "x+y=a",
    "mode": "block",
    "align": "center"
  },
  {
    "type": "text",
    "content": "where ",
    "break_before": true
  },
  {"type": "latex", "content": "a", "mode": "inline"},
  {"type": "text", "content": " is a real constant."}
]
```

最终项目内容块应为：

```json
[
  {
    "type": "paragraph",
    "text": "Consider the simultaneous equations"
  },
  {
    "type": "paragraph",
    "text": "\\[3x^2+2xy=4\\]",
    "align": "center"
  },
  {
    "type": "paragraph",
    "text": "\\[x+y=a\\]",
    "align": "center"
  },
  {
    "type": "paragraph",
    "text": "where \\(a\\) is a real constant."
  }
]
```

## 四、段落边界

- 新段落的第一个 `text` 或 `inline latex` 片段设置 `break_before: true`。
- 单个换行只用于 PDF 行折返，不创建段落；双换行可作为明确段间空白的输入证据。
- `block latex` 和 `image_ref` 自身就是块边界，无需额外制造空段落。
- 选项内容只允许普通文本和 `mode: "inline"` 的 LaTeX，不允许独立公式块。

## 五、题内自检

每题提交前必须执行以下检查：

1. 不存在只含 `,`、`.`、`;`、`:`、`?`、`!` 的段落。
2. 不存在本应位于句内的单字母变量段落。
3. 不存在只含 `where`、`and`、`or` 等连接词的孤立段落。
4. 原卷每一行独立公式在输出中仍是独立块。
5. 原卷居中的独立公式具有 `align: "center"`。
6. 题干文字、标点、公式顺序和段落数量可由页面证据复验。

任一检查失败，都回滚到“题面结构恢复”步骤，只重做当前题，不得在最终导出阶段
用字符串清理脚本猜测修复。
