from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SUITE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SUITE_ROOT / "exam-paper-generator" / "scripts" / "pipeline.py"
SPEC = importlib.util.spec_from_file_location("exam_paper_generator_pipeline", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class GenerationConstraintsTest(unittest.TestCase):
    def test_count_maps_must_sum_to_question_count(self) -> None:
        with self.assertRaisesRegex(GENERATOR.ContractError, "计数总和"):
            GENERATOR._validate_generation_constraints(
                {
                    "question_count": 3,
                    "difficulty_counts": {"easy": 1, "medium": 1},
                }
            )

    def test_unknown_constraint_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(GENERATOR.ContractError, "未知字段"):
            GENERATOR._validate_generation_constraints(
                {"question_count": 1, "difficulty_distribution": {"easy": 1}}
            )

    def test_source_id_fingerprint_and_retained_point_are_bound(self) -> None:
        source_question = {
            "code": "S1",
            "fingerprint": "a" * 64,
            "title": [{"type": "text", "content": "What is x?"}],
            "diagram": None,
            "knowledge_points": [{"code": "K1", "is_primary": True}],
        }
        generated_question = {
            "code": "G1",
            "title": [{"type": "text", "content": "Find the value of y."}],
            "diagram": None,
            "question_type": "multiple_choice",
            "difficulty": "medium",
            "subject": "Mathematics 1",
            "knowledge_points": [{"code": "K1", "is_primary": True}],
            "source": {
                "source_question_id": "S1",
                "source_fingerprint": "b" * 64,
                "generation_blueprint": {"retained_knowledge_point": "K1"},
            },
        }
        source = {"questions": [source_question]}
        document = {
            "metadata": {"year": 2026},
            "questions": [generated_question],
        }
        constraints = {"question_count": 1}

        with self.assertRaisesRegex(GENERATOR.ContractError, "ID 与 source_fingerprint"):
            GENERATOR._validate_generated_output(source, document, constraints)

        generated_question["source"]["source_fingerprint"] = "a" * 64
        GENERATOR._validate_generated_output(source, document, constraints)

    def test_output_count_constraints_are_enforced(self) -> None:
        source_question = {
            "code": "S1",
            "fingerprint": "a" * 64,
            "title": [{"type": "text", "content": "What is x?"}],
            "diagram": None,
            "knowledge_points": [{"code": "K1", "is_primary": True}],
        }
        generated_question = {
            "code": "G1",
            "title": [{"type": "text", "content": "Find the value of y."}],
            "diagram": None,
            "question_type": "multiple_choice",
            "difficulty": "medium",
            "subject": "Mathematics 1",
            "knowledge_points": [{"code": "K1", "is_primary": True}],
            "source": {
                "source_question_id": "S1",
                "source_fingerprint": "a" * 64,
                "generation_blueprint": {"retained_knowledge_point": "K1"},
            },
        }
        constraints = {
            "question_count": 1,
            "difficulty_counts": {"hard": 1},
        }

        with self.assertRaisesRegex(GENERATOR.ContractError, "difficulty_counts"):
            GENERATOR._validate_generated_output(
                {"questions": [source_question]},
                {"metadata": {"year": 2026}, "questions": [generated_question]},
                constraints,
            )


if __name__ == "__main__":
    unittest.main()
