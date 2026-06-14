#!/usr/bin/env python3
"""Validate exam question JSON for common extraction failures."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def collect_tree_labels(nodes: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    stack = list(nodes)
    while stack:
        node = stack.pop()
        code = node.get("code")
        label = node.get("label")
        if isinstance(code, str) and isinstance(label, str):
            labels[code] = label
        children = node.get("children")
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, dict))
    return labels


def load_knowledge_tree_labels() -> dict[str, str]:
    tree_path = Path(__file__).resolve().parents[1] / "references" / "esat-knowledge-tree.json"
    if not tree_path.exists():
        return {}
    tree = json.loads(tree_path.read_text(encoding="utf-8-sig"))
    if not isinstance(tree, list):
        return {}
    return collect_tree_labels(tree)


MOJIBAKE_MARKERS = (
    "�",
    "锛",
    "銆",
    "鐨",
    "绛旀",
    "璇曞",
    "寮�",
)


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def string_garbled_reasons(text: str) -> list[str]:
    reasons: list[str] = []
    if re.search(r"\?{3,}", text):
        reasons.append("contains repeated question marks")
    if any(char != "\n" and ord(char) < 32 for char in text):
        reasons.append("contains control characters")
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        reasons.append("contains common mojibake markers")
    return reasons


def validate_text_encoding(value: Any, path: str, issues: list[str]) -> None:
    if isinstance(value, str):
        reasons = string_garbled_reasons(value)
        if reasons:
            issues.append(f"{path} may be garbled: {', '.join(reasons)}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_text_encoding(item, f"{path}[{index}]", issues)
    elif isinstance(value, dict):
        for key, item in value.items():
            validate_text_encoding(item, f"{path}.{key}", issues)


def validate_learning_analysis_encoding(question: dict[str, Any], prefix: str, issues: list[str]) -> None:
    learning_analysis = question.get("learning_analysis")
    if not isinstance(learning_analysis, dict):
        return
    validate_text_encoding(learning_analysis, f"{prefix}.learning_analysis", issues)
    if learning_analysis.get("language") != "zh-CN":
        return

    checks = [
        ("exam_focus_text", learning_analysis.get("exam_focus_text")),
        ("solution.summary", learning_analysis.get("solution", {}).get("summary") if isinstance(learning_analysis.get("solution"), dict) else None),
        ("review_guidance.summary", learning_analysis.get("review_guidance", {}).get("summary") if isinstance(learning_analysis.get("review_guidance"), dict) else None),
    ]
    for field, value in checks:
        if isinstance(value, str) and value.strip() and not has_cjk(value):
            issues.append(f"{prefix}.learning_analysis.{field} is zh-CN but contains no Chinese characters")


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
    knowledge_labels = load_knowledge_tree_labels()
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
        validate_text_encoding(question, prefix, issues)
        validate_learning_analysis_encoding(question, prefix, issues)

        knowledge_points = question.get("knowledge_points")
        if knowledge_points is not None:
            if not isinstance(knowledge_points, list):
                issues.append(f"{prefix}.knowledge_points must be an array")
            else:
                for kp_index, knowledge_point in enumerate(knowledge_points):
                    kp_prefix = f"{prefix}.knowledge_points[{kp_index}]"
                    if not isinstance(knowledge_point, dict):
                        issues.append(f"{kp_prefix} must be an object")
                        continue
                    code = knowledge_point.get("code")
                    label = knowledge_point.get("label")
                    if not isinstance(code, str) or not code.strip():
                        issues.append(f"{kp_prefix}.code is missing")
                    elif knowledge_labels and code not in knowledge_labels:
                        issues.append(f"{kp_prefix}.code {code} is not in esat-knowledge-tree.json")
                    if not isinstance(label, str) or not label.strip():
                        issues.append(f"{kp_prefix}.label is missing")
                    elif isinstance(code, str) and code in knowledge_labels and label != knowledge_labels[code]:
                        issues.append(f"{kp_prefix}.label does not match esat-knowledge-tree.json for code {code}")

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
