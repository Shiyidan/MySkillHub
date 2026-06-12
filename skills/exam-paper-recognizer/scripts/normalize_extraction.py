#!/usr/bin/env python3
"""Normalize raw model extraction output into parseable JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def decode_placeholders(value: str) -> str:
    result = value
    result = re.sub(r"\[{1,4}[^a-zA-Z\[\]]*BS[^a-zA-Z\[\]]*\]{1,4}", r"\\", result)
    result = re.sub(r"\[{1,4}[^a-zA-Z\[\]]*PARA[^a-zA-Z\[\]]*\]{1,4}", "\n\n", result)
    result = re.sub(r"\[{1,4}[^a-zA-Z\[\]]*NL[^a-zA-Z\[\]]*\]{1,4}", "\n", result)
    result = re.sub(r"\[{1,4}[^a-zA-Z\[\]]*FIG[^a-zA-Z\[\]]*\]{1,4}", "[Figure]", result)
    result = result.replace(r"\(", "$").replace(r"\)", "$")
    result = result.replace(r"\[", "$$").replace(r"\]", "$$")
    result = re.sub(r"\\text\{([^{}]*[\^_][^{}]*)\}", r"\\mathrm{\1}", result)
    return result


def walk_decode(obj: Any) -> Any:
    if isinstance(obj, str):
        return decode_placeholders(obj)
    if isinstance(obj, list):
        return [walk_decode(item) for item in obj]
    if isinstance(obj, dict):
        return {key: walk_decode(value) for key, value in obj.items()}
    return obj


def extract_json_object(text: str) -> str:
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        text = code_block.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1].strip()
    return text.strip()


def repair_invalid_escapes(text: str) -> str:
    return re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r"\\\\", text)


def repair_numeric_expressions(text: str) -> str:
    pattern = re.compile(r"([\[:,]\s*)(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)(?=\s*[\],])")

    def replace(match: re.Match[str]) -> str:
        denominator = float(match.group(3))
        if denominator == 0:
            return match.group(0)
        value = round(float(match.group(2)) / denominator, 6)
        return f"{match.group(1)}{value}"

    return pattern.sub(replace, text)


def parse_json(raw: str) -> Any:
    candidates = []
    base = extract_json_object(raw)
    candidates.extend([base, repair_invalid_escapes(base), repair_numeric_expressions(repair_invalid_escapes(base))])
    for candidate in dict.fromkeys(candidates):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise SystemExit("Could not parse JSON from input.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Raw model text or JSON file")
    parser.add_argument("output", nargs="?", help="Output JSON file")
    parser.add_argument("--decode-placeholders", action="store_true")
    args = parser.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8-sig")
    data = parse_json(raw)
    if args.decode_placeholders:
        data = walk_decode(data)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
