#!/usr/bin/env python3
"""Parse an exam answer-key PDF and optionally merge it into question JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PAIR_RE = re.compile(r"\bQ(?:uestion)?\s*(\d{1,3})\b\s*[:.\-]?\s*([A-Z](?:\s*[,/]\s*[A-Z])*)\b", re.IGNORECASE)
QUESTION_RE = re.compile(r"^Q(?:uestion)?\s*(\d{1,3})$", re.IGNORECASE)
ANSWER_RE = re.compile(r"^[A-Z](?:\s*[,/]\s*[A-Z])*$")


def normalise_answer(value: str) -> list[str]:
    return [part.strip().upper() for part in re.split(r"[,/]", value) if part.strip()]


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise SystemExit("PyMuPDF is required. Install package 'pymupdf'.") from exc

    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text("text") for page in doc)


def parse_answer_key_text(text: str) -> dict[int, list[str]]:
    answers: dict[int, list[str]] = {}

    for match in PAIR_RE.finditer(text):
        number = int(match.group(1))
        answers[number] = normalise_answer(match.group(2))

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    pending_question: int | None = None
    for line in lines:
        q_match = QUESTION_RE.match(line)
        if q_match:
            pending_question = int(q_match.group(1))
            continue
        if pending_question is not None and ANSWER_RE.match(line):
            answers[pending_question] = normalise_answer(line)
            pending_question = None

    return dict(sorted(answers.items()))


def merge_answers(question_data: dict[str, Any], answers: dict[int, list[str]], source_pdf: str) -> dict[str, Any]:
    missing: list[int] = []
    for question in question_data.get("questions", []):
        if not isinstance(question, dict):
            continue
        number = question.get("number")
        if not isinstance(number, int):
            continue
        answer = answers.get(number)
        if answer:
            question["answer"] = answer
            question["answer_source"] = {
                "type": "answer_key_pdf",
                "source_pdf": source_pdf,
                "confidence": 0.99,
                "matched_by": "question_number",
            }
        else:
            missing.append(number)

    question_data.setdefault("answer_key", {})
    question_data["answer_key"].update(
        {
            "source_pdf": source_pdf,
            "parsed_count": len(answers),
            "missing_question_numbers_in_json": missing,
        }
    )
    return question_data


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("answer_key_pdf")
    parser.add_argument("--out", help="Write parsed answer-key JSON here")
    parser.add_argument("--question-json", help="Existing question JSON to update")
    parser.add_argument("--out-question-json", help="Path for merged question JSON")
    parser.add_argument("--max-question", type=int, help="Only keep answers up to this question number")
    args = parser.parse_args()

    pdf_path = Path(args.answer_key_pdf).expanduser().resolve()
    text = extract_pdf_text(pdf_path)
    answers = parse_answer_key_text(text)
    if args.max_question is not None:
        answers = {number: answer for number, answer in answers.items() if number <= args.max_question}

    parsed = {
        "source_pdf": str(pdf_path),
        "answer_count": len(answers),
        "answers": {str(number): answer for number, answer in answers.items()},
    }

    if args.out:
        Path(args.out).expanduser().resolve().write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.question_json:
        question_path = Path(args.question_json).expanduser().resolve()
        data = json.loads(question_path.read_text(encoding="utf-8-sig"))
        merged = merge_answers(data, answers, str(pdf_path))
        output_path = Path(args.out_question_json).expanduser().resolve() if args.out_question_json else question_path
        output_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(parsed, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
