from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core.assembly import (  # noqa: E402
    _module_targets,
    _select_questions,
    suggested_time_minutes,
)
from exam_paper_core.contract import ContractError, _suggested_time_minutes  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
