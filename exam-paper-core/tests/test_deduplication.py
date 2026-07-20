from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core.deduplication import deduplicate_questions  # noqa: E402


def _option(label: str, content: str) -> dict:
    return {"label": label, "content": [{"type": "text", "content": content}]}


def _question(
    code: str,
    source_exam_type: str,
    *,
    answer: str = "A",
    options: list[dict] | None = None,
    title: str = "The surface areas are equal. Which expression is correct?",
    syllabus_code: str = "110603",
) -> dict:
    return {
        "code": code,
        "title": [{"type": "text", "content": title}],
        "options": options or [_option("A", "R = 5r"), _option("B", "R = 10r")],
        "answer": answer,
        "images": [],
        "source_examType": source_exam_type,
        "questionNumber": 1,
        "subject": "Mathematics 1",
        "subject_code": "110000",
        "topic_code": syllabus_code,
        "question_type": "multiple_choice",
        "knowledge_points": [{"code": syllabus_code}],
        "syllabus_tags": [syllabus_code],
        "target_exam_scope": {
            "target_exam": "ESAT",
            "scope_status": "in_scope",
            "mapping_status": "human_verified",
            "modules": ["Mathematics 1"],
            "syllabus_codes": [syllabus_code],
        },
        "diagram": None,
        "explanation": "目标：比较两个表面积表达式并求出半径关系。",
        "source": {
            "question": {"file": f"{source_exam_type}_2023.pdf", "page": 1},
            "answer": {"file": f"{source_exam_type}_2023_answers.pdf", "page": 1},
            "solution": None,
            "evidence_packet": {"path": f"evidence/{code}.json", "sha256": "0" * 64},
        },
    }


class DeduplicationTest(unittest.TestCase):
    def test_cross_paper_exact_duplicate_is_merged_and_sources_are_audited(self) -> None:
        engaa = _question("ENGAA_Q01", "ENGAA")
        nsaa = _question("NSAA_Q01", "NSAA")

        unique, report = deduplicate_questions([nsaa, engaa])

        self.assertEqual([item["code"] for item in unique], ["ENGAA_Q01"])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["confirmed_duplicate_count"], 1)
        duplicate = report["confirmed_duplicates"][0]
        self.assertEqual(duplicate["kept_code"], "ENGAA_Q01")
        self.assertEqual(duplicate["excluded_code"], "NSAA_Q01")
        self.assertEqual(duplicate["excluded_occurrence"]["question_source"]["file"], "NSAA_2023.pdf")

    def test_reordered_options_are_merged_when_correct_content_matches(self) -> None:
        original = _question("ENGAA_Q01", "ENGAA", answer="A")
        reordered = _question(
            "NSAA_Q01",
            "NSAA",
            answer="B",
            options=[_option("A", "R = 10r"), _option("B", "R = 5r")],
        )

        unique, report = deduplicate_questions([original, reordered])

        self.assertEqual(len(unique), 1)
        self.assertEqual(report["confirmed_duplicates"][0]["reason"], "equivalent_content")

    def test_answer_conflict_blocks_silent_merge(self) -> None:
        original = _question("ENGAA_Q01", "ENGAA", answer="A")
        conflicting = _question("NSAA_Q01", "NSAA", answer="B")

        unique, report = deduplicate_questions([original, conflicting])

        self.assertEqual(len(unique), 2)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["blocking_conflict_count"], 1)
        self.assertEqual(report["blocking_conflicts"][0]["checks"]["answer"], "conflict")

    def test_syllabus_conflict_blocks_silent_merge(self) -> None:
        original = _question("ENGAA_Q01", "ENGAA")
        conflicting = _question("NSAA_Q01", "NSAA", syllabus_code="110415")

        unique, report = deduplicate_questions([original, conflicting])

        self.assertEqual(len(unique), 2)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["blocking_conflicts"][0]["checks"]["classification"], "conflict")

    def test_same_stem_with_different_options_is_retained_for_review(self) -> None:
        original = _question("ENGAA_Q01", "ENGAA")
        variant = _question(
            "NSAA_Q01",
            "NSAA",
            options=[_option("A", "R = 4r"), _option("B", "R = 8r")],
        )

        unique, report = deduplicate_questions([original, variant])

        self.assertEqual(len(unique), 2)
        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["review_candidate_count"], 1)
        self.assertEqual(report["review_candidates"][0]["reason"], "same_stem_requires_review")


if __name__ == "__main__":
    unittest.main()
