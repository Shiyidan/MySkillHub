#!/usr/bin/env python3
"""Build the TMUA annual import JSON directly from canonical question objects.

This exporter is intentionally strict: it does not repair missing question data
or infer fields from display strings.  A failed transaction must be corrected in
the parser output before annual assembly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CORE_ROOT = Path(r"C:\Users\SW\.codex\skills\exam-paper-core\python")
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))
from exam_paper_core.content_blocks import from_structured_parts, normalize_math_text


CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
LABELS = tuple("ABCDEFGH")


def recover_source_layout(q: dict, year: int) -> dict:
    """Apply source-page semantic recovery before block construction.

    The 2022 Paper 1 Q14 PDF text layer splits mathematical glyphs into
    unrelated characters; its source-page reconstruction is deterministic.
    """
    if year == 2022 and q.get("code") == "TMUA_2022_P1_Q14":
        q = dict(q)
        q["title"] = [
            {"type": "text", "content": "A circle has centre O and radius 6."},
            {"type": "text", "break_before": True, "content": r"P, Q and R are points on the circumference with angle $POQ \geq \frac{\pi}{2}$."},
            {"type": "text", "break_before": True, "content": r"The area of the triangle $POQ$ is $9\sqrt{3}$."},
            {"type": "text", "break_before": True, "content": "What is the greatest possible area of triangle PRQ?"},
        ]
        values = [r"18+9\sqrt{3}", r"18\sqrt{3}", r"27+9\sqrt{3}", r"27\sqrt{3}", r"36+9\sqrt{3}", r"36\sqrt{3}"]
        q["options"] = [{"label": label, "content": [{"type": "latex", "content": value}]} for label, value in zip("ABCDEF", values)]
        return q
    return q


def clean(value: str) -> str:
    return CONTROL.sub("", value)


def inline_content(parts) -> str:
    if not isinstance(parts, list) or not parts:
        raise ValueError("structured content is required")
    out = []
    for part in parts:
        if not isinstance(part, dict):
            raise ValueError(f"unsupported structured content part: {part!r}")
        if part.get("type") == "image_ref":
            continue
        if part.get("type") not in {"text", "latex"}:
            raise ValueError(f"unsupported structured content part: {part!r}")
        content = part.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty structured content part")
        out.append(content if part["type"] == "text" else "\\(" + content + "\\)")
    return clean("".join(out)).strip()


def question_obj(q: dict, module_code: str, number: int, year: int, subject: str, subject_code: str, asset_root: Path) -> dict:
    q = recover_source_layout(q, year)
    title_parts = q.get("title")
    if not isinstance(title_parts, list):
        raise ValueError(f"{q.get('id', '<question>')}: title must be structured")
    blocks = from_structured_parts(title_parts)
    title = next(b["text"] for b in blocks if b["type"] == "paragraph")
    options = q.get("options")
    if not isinstance(options, list) or not options:
        raise ValueError(f"{q.get('id', '<question>')}: options are required")
    final_options = []
    for opt in options:
        label = opt.get("label")
        if label not in LABELS:
            raise ValueError(f"{q.get('id')}: invalid option label {label!r}")
        option = {"label": label, "text": normalize_math_text(inline_content(opt.get("content")))}
        if opt.get("image_id"):
            option["image_id"] = opt["image_id"]
        final_options.append(option)
    answer = q.get("answer")
    if not isinstance(answer, str) or answer not in [x["label"] for x in final_options]:
        raise ValueError(f"{q.get('id')}: answer must be one option label")

    # The parser/core has already established paragraph boundaries.  Exporting
    # must preserve them and never flatten the stem back into one string.
    images = []
    for image in q.get("images", []) or []:
        image_id = image.get("id") or image.get("image_id")
        rel = image.get("asset_path")
        if not image_id or not rel:
            raise ValueError(f"{q.get('id')}: image id and asset_path are required")
        path = asset_root / rel
        if path.suffix.lower() != ".svg" or not path.exists():
            raise ValueError(f"{q.get('id')}: required SVG asset missing: {path}")
        svg = clean(path.read_text(encoding="utf-8"))
        if "<svg" not in svg:
            raise ValueError(f"{q.get('id')}: asset is not SVG: {path}")
        if not any(b.get("type") == "image_ref" and b.get("image_id") == image_id for b in blocks):
            blocks.append({"type": "image_ref", "image_id": image_id, "alt": clean(str(image.get("alt", image.get("alt_text", ""))))})
        images.append({"id": image_id, "type": "svg", "svg": svg, "alt": clean(str(image.get("alt", image.get("alt_text", ""))))})

    return {
        "code": q.get("code") or q.get("id") or (_ for _ in ()).throw(ValueError("question code/id is required")),
        "number": number,
        "examType": "TMUA",
        "source_examType": q.get("source_examType") or q.get("source_examType".lower()) or "TMUA",
        "year": year,
        "subject": subject,
        "subject_code": subject_code,
        "question_type": "single_choice",
        "difficulty": q.get("difficulty", ""),
        "is_ai_generated": bool(q.get("is_ai_generated", False)),
        "title": title,
        "content_blocks": blocks,
        "options": final_options,
        "answer": [answer],
        "images": images,
        "topic_code": q.get("topic_code", ""),
        "topic": q.get("topic", ""),
        "knowledge_points": q.get("knowledge_points", []),
        "learning_analysis": q.get("learning_analysis", {}),
    }


def build(canonical: dict, asset_root: Path) -> dict:
    year = int(canonical.get("year") or canonical.get("metadata", {}).get("year", 0))
    all_questions = canonical.get("questions")
    if not isinstance(all_questions, list):
        raise ValueError("canonical questions list is required")
    modules = []
    module_specs = [("paper1", 1, "Paper 1: Applications of Mathematical Knowledge", "TMUA-P1"),
                    ("paper2", 2, "Paper 2: Mathematical Reasoning", "TMUA-P2")]
    for code, order, subject, subject_code in module_specs:
        prefix = "P1" if code == "paper1" else "P2"
        qs = [q for q in all_questions if f"_{prefix}_" in str(q.get("code", ""))]
        if not qs:
            qs = [q for q in all_questions if str(q.get("id", "")).find(f"_{prefix}_") >= 0]
        if not isinstance(qs, list) or len(qs) != 20:
            raise ValueError(f"{code}: exactly 20 questions are required")
        modules.append({
            "code": code, "order": order, "subject": subject, "subject_code": subject_code,
            "duration": 75, "totalQuestions": 20,
            "questions": [question_obj(q, code, i, year, subject, subject_code, asset_root) for i, q in enumerate(qs, 1)],
        })
    return {
        "schemaVersion": "diagnostic-paper-v2",
        "code": f"TMUA-{year}",
        "metadata": {
            "paperName": f"TMUA {year} Full Paper",
            "year": year, "duration": 150, "examType": "TMUA", "paperType": "realPaper",
            "totalQuestions": 40, "deliveryMode": "module_sequence",
            "breakPolicy": {"durationSeconds": 0, "skippable": False},
            "assemblyType": "original", "sourceExamTypes": ["TMUA"],
            "remarks": "Annual TMUA paper; Paper 1 and Paper 2 are delivered as two scored modules.",
        },
        "modules": modules,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("canonical", type=Path)
    ap.add_argument("asset_root", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    data = json.loads(args.canonical.read_text(encoding="utf-8-sig"))
    result = build(data, args.asset_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
