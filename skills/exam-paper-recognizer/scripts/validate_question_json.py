#!/usr/bin/env python3
"""Validate exam question JSON for common extraction failures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def text_from_blocks(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") in {"paragraph", "text"}:
            parts.append(str(block.get("text", "")))
        elif block.get("type") == "formula":
            parts.append(str(block.get("latex", "")))
        elif block.get("type") == "asset":
            parts.append("[asset]")
    return " ".join(part.strip() for part in parts if part)


def question_stem_text(question: dict[str, Any]) -> str:
    if isinstance(question.get("title"), str):
        return question["title"].strip()
    stem = question.get("stem")
    if isinstance(stem, dict) and isinstance(stem.get("blocks"), list):
        return text_from_blocks(stem["blocks"]).strip()
    return ""


def option_text(option: dict[str, Any]) -> str:
    if isinstance(option.get("text"), str):
        return option["text"].strip()
    if isinstance(option.get("blocks"), list):
        return text_from_blocks(option["blocks"]).strip()
    return ""


def validate(data: Any, max_question: int | None = None) -> list[str]:
    issues: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        return ["questions must be a non-empty array"]

    seen: set[int] = set()
    numbers: list[int] = []
    for index, question in enumerate(questions):
        prefix = f"questions[{index}]"
        if not isinstance(question, dict):
            issues.append(f"{prefix} must be an object")
            continue

        number = question.get("number")
        if not isinstance(number, int) or number <= 0:
            issues.append(f"{prefix}.number must be a positive integer")
        else:
            if max_question is not None and number > max_question:
                issues.append(f"{prefix}.number {number} exceeds max question limit {max_question}")
            if number in seen:
                issues.append(f"duplicate question number {number}")
            seen.add(number)
            numbers.append(number)

        if not question_stem_text(question):
            issues.append(f"{prefix} has empty stem/title")

        options = question.get("options")
        if not isinstance(options, list):
            issues.append(f"{prefix}.options must be an array")
        elif options:
            labels: set[str] = set()
            for opt_index, option in enumerate(options):
                opt_prefix = f"{prefix}.options[{opt_index}]"
                if not isinstance(option, dict):
                    issues.append(f"{opt_prefix} must be an object")
                    continue
                label = option.get("label")
                if not isinstance(label, str) or not label.strip():
                    issues.append(f"{opt_prefix}.label is missing")
                elif label in labels:
                    issues.append(f"{prefix} has duplicate option label {label}")
                else:
                    labels.add(label)
                if not option_text(option):
                    issues.append(f"{opt_prefix} has empty text/blocks")
        else:
            q_type = question.get("type", "single_choice")
            if q_type in {"single_choice", "multiple_choice", "unknown"}:
                issues.append(f"{prefix} has no options")

        for key in ("images", "assets"):
            assets = question.get(key)
            if assets is None:
                continue
            if not isinstance(assets, list):
                issues.append(f"{prefix}.{key} must be an array")
                continue
            for asset_index, asset in enumerate(assets):
                asset_prefix = f"{prefix}.{key}[{asset_index}]"
                if not isinstance(asset, dict):
                    issues.append(f"{asset_prefix} must be an object")
                    continue
                if key == "assets" and not asset.get("id"):
                    issues.append(f"{asset_prefix}.id is missing")
                svg_code = str(asset.get("code") or asset.get("svg_code") or asset.get("display", {}).get("svg_code") or "")
                if "\n" in svg_code:
                    issues.append(f"{asset_prefix} embedded SVG contains real newlines")

    if numbers:
        sorted_numbers = sorted(numbers)
        missing = [n for n in range(sorted_numbers[0], sorted_numbers[-1] + 1) if n not in seen]
        if missing:
            issues.append(f"missing question numbers in detected range: {missing}")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file")
    parser.add_argument("--max-question", type=int, help="Fail if any question number is greater than this value")
    args = parser.parse_args()

    data = json.loads(Path(args.json_file).read_text(encoding="utf-8-sig"))
    issues = validate(data, max_question=args.max_question)
    if issues:
        print("Validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
