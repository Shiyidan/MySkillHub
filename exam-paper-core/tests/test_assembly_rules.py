from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core.assembly import (  # noqa: E402
    ESAT_COMBINATIONS,
    _deduplicate_candidates,
    _module_targets,
    _select_questions,
    suggested_time_minutes,
)
from exam_paper_core.contract import ContractError, DIFFICULTIES, _suggested_time_minutes  # noqa: E402


class AssemblyRulesTest(unittest.TestCase):
    def test_combination_paper_locks_each_module_to_27_questions(self) -> None:
        modules = ["Mathematics 1", "Physics", "Mathematics 2"]
        expected = {module: 27 for module in modules}

        self.assertEqual(
            _module_targets({}, modules, paper_mode="diagnostic_combination_paper"),
            expected,
        )
        with self.assertRaises(ContractError):
            _module_targets(
                {"target_question_counts": {"Physics": 20}},
                modules,
                paper_mode="diagnostic_combination_paper",
            )

    def test_single_module_paper_can_override_target_count(self) -> None:
        self.assertEqual(
            _module_targets(
                {"target_question_counts": {"Mathematics 1": 12}},
                ["Mathematics 1"],
                paper_mode="diagnostic_module_paper",
            ),
            {"Mathematics 1": 12},
        )

    def test_module_time_remains_40_minutes_when_underfilled(self) -> None:
        self.assertEqual(suggested_time_minutes(0), 40)
        self.assertEqual(suggested_time_minutes(12), 40)
        self.assertEqual(suggested_time_minutes(27), 40)
        self.assertEqual(_suggested_time_minutes(0), 40)
        self.assertEqual(_suggested_time_minutes(12), 40)

    def test_overfilled_module_is_selected_down_to_27(self) -> None:
        candidates = [
            {
                "code": f"Q{index:02d}",
                "questionNumber": index,
                "difficulty": ("easy", "medium", "hard")[index % 3],
                "source_examType": ("ENGAA", "NSAA")[index % 2],
                "target_exam_scope": {"syllabus_codes": [f"13{index % 5 + 1}001"]},
            }
            for index in range(1, 31)
        ]

        selected = _select_questions(candidates, 27)

        self.assertEqual(len(selected), 27)
        self.assertEqual(len({item["code"] for item in selected}), 27)

    def test_exact_and_equivalent_content_duplicates_are_removed(self) -> None:
        base = {
            "code": "Q01",
            "fingerprint": "a" * 64,
            "title": [{"type": "text", "content": "What is x?"}],
            "options": [],
            "diagram": None,
            "questionNumber": 1,
            "difficulty": "easy",
            "source_examType": "ENGAA",
            "target_exam_scope": {"syllabus_codes": ["110415"]},
        }
        exact_duplicate = dict(base, code="Q02", questionNumber=2)
        same_stem = dict(base, code="Q03", fingerprint="b" * 64, questionNumber=3)
        different = dict(
            base,
            code="Q04",
            fingerprint="c" * 64,
            questionNumber=4,
            title=[{"type": "text", "content": "What is y?"}],
        )

        unique, duplicates = _deduplicate_candidates(
            [base, exact_duplicate, same_stem, different]
        )

        self.assertEqual([item["code"] for item in unique], ["Q01", "Q04"])
        self.assertEqual(
            [(item["excluded_code"], item["reason"]) for item in duplicates],
            [("Q02", "exact_fingerprint"), ("Q03", "equivalent_content")],
        )
        self.assertEqual(
            [item["code"] for item in _select_questions([base, exact_duplicate, same_stem, different], 27)],
            ["Q01", "Q04"],
        )

    def test_esat_year_has_six_unique_three_module_combinations(self) -> None:
        self.assertEqual(len(ESAT_COMBINATIONS), 6)
        self.assertEqual(len(set(ESAT_COMBINATIONS)), 6)
        self.assertTrue(all(len(item) == 3 for item in ESAT_COMBINATIONS))
        self.assertTrue(all(item[0] == "Mathematics 1" for item in ESAT_COMBINATIONS))

    def test_project_difficulty_vocabulary_includes_composite(self) -> None:
        self.assertEqual(DIFFICULTIES, {"easy", "medium", "hard", "composite"})


if __name__ == "__main__":
    unittest.main()
