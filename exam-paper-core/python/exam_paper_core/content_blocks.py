"""考试题干的通用内容块重建。

解析层可将题干保留为 text/latex/image_ref 片段；本模块按稳定规则
重建段落，供 ESAT、TMUA 等考试共同使用。考试专属版式判断不放在这里。
"""
from __future__ import annotations

import re


def normalize_math_text(text: str) -> str:
    """Normalize unstructured option math without changing ordinary prose.

    This conservative path only handles unmistakable OCR patterns such as
    log10 and unicode minus. Structured LaTeX remains the preferred source.
    """
    value = str(text).strip().replace("−", "-").replace("–", "-")
    if re.search(r"\blog\s*10\b", value, flags=re.I):
        value = re.sub(r"\blog\s*10\b\s*([0-9]+)", r"\\log_{10}(\1)", value, flags=re.I)
    value = re.sub(r"(?<![A-Za-z])\blog10\b", r"\\log_{10}", value, flags=re.I)
    return value


def from_structured_parts(parts: list[dict]) -> list[dict]:
    """将题干结构化片段转换为 paragraph/image_ref 内容块。

    独立公式（latex）单独成为段落；相邻普通文本合并为一个段落。
    这是确定性排版转换，不在最终导出阶段拼接整道题干。
    """
    if not isinstance(parts, list):
        raise TypeError("structured title parts must be a list")
    blocks: list[dict] = []
    text_parts: list[str] = []
    leading_images: list[dict] = []

    def flush() -> None:
        if text_parts:
            text = "".join(text_parts).strip()
            if text:
                blocks.append({"type": "paragraph", "text": text})
            text_parts.clear()
            if leading_images:
                blocks.extend(leading_images)
                leading_images.clear()

    for part in parts:
        kind = part.get("type")
        if kind == "text":
            if part.get("break_before"):
                flush()
            content = str(part.get("content", ""))
            segments = content.split("\n\n")
            for index, segment in enumerate(segments):
                if index:
                    flush()
                if segment.strip():
                    text_parts.append(segment.replace("\n", " "))
        elif kind == "latex":
            flush()
            content = str(part.get("content", "")).strip()
            if content:
                blocks.append({"type": "paragraph", "text": "\\(" + content + "\\)"})
        elif kind == "image_ref":
            block = {"type": "image_ref", "image_id": part["image_id"]}
            if part.get("alt"):
                block["alt"] = part["alt"]
            if not blocks and not text_parts:
                leading_images.append(block)
            else:
                flush()
                blocks.append(block)
        else:
            raise ValueError(f"unsupported content part type: {kind!r}")
    flush()
    if leading_images:
        # A valid question must begin with its stem paragraph.  A source image
        # preceding the printed stem is retained immediately after that stem.
        blocks.extend(leading_images)
    if not blocks:
        raise ValueError("question stem produced no content blocks")
    return blocks
