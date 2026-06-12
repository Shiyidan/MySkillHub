#!/usr/bin/env python3
"""Render extracted question JSON as Markdown.

Default mode writes a JSON-in-Markdown container. Use --mode review for a
natural-language review draft.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def decode_placeholders(text: str) -> str:
    text = re.sub(r"\[{1,4}[^a-zA-Z\[\]]*BS[^a-zA-Z\[\]]*\]{1,4}", r"\\", text)
    text = re.sub(r"\[{1,4}[^a-zA-Z\[\]]*PARA[^a-zA-Z\[\]]*\]{1,4}", "\n\n", text)
    text = re.sub(r"\[{1,4}[^a-zA-Z\[\]]*NL[^a-zA-Z\[\]]*\]{1,4}", "\n", text)
    text = re.sub(r"\[{1,4}[^a-zA-Z\[\]]*FIG[^a-zA-Z\[\]]*\]{1,4}", "[Figure]", text)
    return text


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        if block_type in {"paragraph", "text"}:
            lines.append(decode_placeholders(str(block.get("text", ""))))
        elif block_type == "formula":
            lines.append(f"${block.get('latex', '')}$")
        elif block_type == "asset":
            lines.append(f"[[FIG:{block.get('asset_id', '')}]]")
        elif block_type == "line_break":
            lines.append("")
        elif block_type == "table":
            lines.append("[Table]")
    return "\n\n".join(line for line in lines if line is not None).strip()


def stem_markdown(question: dict[str, Any]) -> str:
    if isinstance(question.get("title"), str):
        return decode_placeholders(question["title"]).strip()
    stem = question.get("stem")
    if isinstance(stem, dict) and isinstance(stem.get("blocks"), list):
        return blocks_to_markdown(stem["blocks"])
    return ""


def option_markdown(option: dict[str, Any]) -> str:
    if isinstance(option.get("text"), str):
        return decode_placeholders(option["text"]).strip()
    if isinstance(option.get("blocks"), list):
        return blocks_to_markdown(option["blocks"])
    return ""


def asset_lines(question: dict[str, Any]) -> list[str]:
    assets = []
    if isinstance(question.get("assets"), list):
        assets.extend(question["assets"])
    if isinstance(question.get("images"), list):
        assets.extend(question["images"])
    lines: list[str] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_id = asset.get("id") or asset.get("alt") or "figure"
        display = asset.get("display") if isinstance(asset.get("display"), dict) else {}
        src = display.get("fallback_image_path") or display.get("source_crop_path") or asset.get("src")
        svg = display.get("svg_path")
        if src:
            lines.append(f"![{asset_id}]({src})")
        elif svg:
            lines.append(f"![{asset_id}]({svg})")
        elif asset.get("code"):
            lines.append(f"`{asset_id}`: embedded SVG")
    return lines


def render_json_container(data: dict[str, Any], source: str, schema: str) -> str:
    frontmatter = [
        "---",
        f"schema: {schema}",
        f"source: {source}",
        "content_type: parsed_question_json",
        "---",
        "",
        "```json",
        json.dumps(data, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(frontmatter)


def render_natural_review(data: dict[str, Any]) -> str:
    questions = data.get("questions", [])
    lines: list[str] = []
    paper = data.get("paper", {})
    if isinstance(paper, dict) and paper:
        title = " ".join(str(paper.get(k, "")).strip() for k in ("exam", "year", "section") if paper.get(k))
        if title:
            lines.append(f"# {title}")
            lines.append("")

    for question in questions:
        if not isinstance(question, dict):
            continue
        lines.append(f"## Question {question.get('number', '?')}")
        lines.append("")
        stem = stem_markdown(question)
        if stem:
            lines.append(stem)
            lines.append("")
        for asset_line in asset_lines(question):
            lines.append(asset_line)
            lines.append("")
        options = question.get("options", [])
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict):
                    lines.append(f"{option.get('label', '')}. {option_markdown(option)}")
            lines.append("")
        answer = question.get("answer")
        if answer:
            lines.append(f"Answer: {', '.join(map(str, answer))}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file")
    parser.add_argument("output_md")
    parser.add_argument("--mode", choices=["json-container", "review"], default="json-container")
    parser.add_argument("--source", default="")
    parser.add_argument("--schema", default="project-question.schema.json")
    args = parser.parse_args()

    data = json.loads(Path(args.json_file).read_text(encoding="utf-8-sig"))
    if args.mode == "review":
        text = render_natural_review(data)
    else:
        source = args.source
        if not source and isinstance(data.get("paper"), dict):
            source = str(data["paper"].get("source_pdf") or "")
        text = render_json_container(data, source=source, schema=args.schema)

    Path(args.output_md).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
