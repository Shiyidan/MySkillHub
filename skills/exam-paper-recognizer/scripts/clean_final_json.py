#!/usr/bin/env python3
"""Strip extraction/debug metadata and write the clean final questions JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


KEEP_QUESTION_KEYS = [
    "number",
    "title",
    "content_blocks",
    "options",
    "answer",
    "images",
    "subject",
    "subject_code",
    "topic",
    "topic_code",
    "question_type",
    "difficulty",
    "syllabus_points",
    "knowledge_points",
    "skills",
    "learning_analysis",
    "generation_profile",
]


def clean_difficulty(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("level")
    if value in {"easy", "medium", "hard", "composite", "unknown"}:
        return str(value)
    return "unknown"


def clean_learning_analysis(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    solution = value.get("solution") if isinstance(value.get("solution"), dict) else {}
    review = value.get("review_guidance") if isinstance(value.get("review_guidance"), dict) else {}
    clean = {
        "exam_focus": value.get("exam_focus_text") or value.get("exam_focus") or "",
        "solution": solution.get("summary") if isinstance(solution, dict) else value.get("solution", ""),
        "review_guidance": review.get("summary") if isinstance(review, dict) else value.get("review_guidance", ""),
    }
    return {key: str(text) for key, text in clean.items() if text}


def clean_generation_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    clean: dict[str, Any] = {}
    if isinstance(value.get("can_generate_similar"), bool):
        clean["can_generate_similar"] = value["can_generate_similar"]
    focus = value.get("generation_focus")
    if not focus and isinstance(value.get("similarity_template"), str) and value["similarity_template"].strip():
        focus = [value["similarity_template"].strip()]
    if isinstance(focus, list) and focus:
        clean["generation_focus"] = focus
    distractors = value.get("common_distractors")
    if isinstance(distractors, list) and distractors:
        clean["common_distractors"] = distractors
    return clean


def clean_image(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    allowed = ["id", "type", "diagram_type", "alt", "code", "svg", "src", "semantic", "graph_schema"]
    return {key: value[key] for key in allowed if key in value and value[key] not in (None, [], {})}


def plain_subject(label: str) -> str:
    if " (" in label:
        return label.split(" (", 1)[0]
    return label


def build_syllabus_paths() -> dict[str, dict[str, str]]:
    tree_path = Path(__file__).resolve().parents[1] / "references" / "esat-knowledge-tree.json"
    if not tree_path.exists():
        return {}
    tree = json.loads(tree_path.read_text(encoding="utf-8-sig"))
    paths: dict[str, dict[str, str]] = {}
    if not isinstance(tree, list):
        return paths

    def walk(node: dict[str, Any], ancestors: list[dict[str, Any]]) -> None:
        code = node.get("code")
        children = node.get("children")
        if isinstance(code, str) and len(ancestors) >= 3:
            subject = ancestors[1]
            topic = ancestors[2]
            paths[code] = {
                "subject": plain_subject(str(subject.get("label", ""))),
                "subject_code": str(subject.get("code", "")),
                "topic": str(topic.get("label", "")),
                "topic_code": str(topic.get("code", "")),
            }
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    walk(child, ancestors + [node])

    for root in tree:
        if isinstance(root, dict):
            walk(root, [])
    return paths


def primary_syllabus_code(question: dict[str, Any]) -> str | None:
    points = question.get("syllabus_points")
    if not isinstance(points, list):
        return None
    for point in points:
        if isinstance(point, dict) and point.get("role") == "primary" and isinstance(point.get("code"), str):
            return point["code"]
    for point in points:
        if isinstance(point, dict) and isinstance(point.get("code"), str):
            return point["code"]
    return None


def clean_question(question: dict[str, Any], syllabus_paths: dict[str, dict[str, str]]) -> dict[str, Any]:
    clean = {key: question[key] for key in KEEP_QUESTION_KEYS if key in question and question[key] not in (None, {})}
    clean.setdefault("options", [])
    clean.setdefault("answer", [])
    clean.setdefault("images", [])
    path = syllabus_paths.get(primary_syllabus_code(clean) or "")
    if path:
        clean["subject"] = path["subject"]
        clean["subject_code"] = path["subject_code"]
        clean["topic"] = path["topic"]
        clean["topic_code"] = path["topic_code"]
    clean["difficulty"] = clean_difficulty(question.get("difficulty"))
    if "learning_analysis" in clean:
        analysis = clean_learning_analysis(clean["learning_analysis"])
        if analysis:
            clean["learning_analysis"] = analysis
        else:
            clean.pop("learning_analysis", None)
    if "generation_profile" in clean:
        profile = clean_generation_profile(clean["generation_profile"])
        if profile:
            clean["generation_profile"] = profile
        else:
            clean.pop("generation_profile", None)
    if isinstance(clean.get("images"), list):
        clean["images"] = [clean_image(image) for image in clean["images"]]
    return clean


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
    parser.add_argument("output_json")
    args = parser.parse_args()

    data = json.loads(Path(args.input_json).read_text(encoding="utf-8-sig"))
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError("input JSON must contain questions array")
    syllabus_paths = build_syllabus_paths()
    clean = {"questions": [clean_question(question, syllabus_paths) for question in questions if isinstance(question, dict)]}
    Path(args.output_json).write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
