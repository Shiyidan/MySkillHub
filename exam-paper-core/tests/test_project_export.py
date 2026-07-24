from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core.contract import ContractError  # noqa: E402
from exam_paper_core.project_export import (  # noqa: E402
    build_project_diagnostic_paper,
    validate_project_diagnostic_paper,
)


class ProjectExportTest(unittest.TestCase):
    def test_exports_self_contained_project_paper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            svg_path = root / "graph.svg"
            svg_path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"></svg>',
                encoding="utf-8",
            )
            png_path = root / "crop.png"
            png_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            assembled = {
                "document_type": "assembled_exam",
                "validation_status": "passed",
                "metadata": {
                    "year": 2023,
                    "paper_type": "realPaper",
                    "title": "ESAT legacy diagnostic paper: Mathematics 1 + Biology + Physics",
                    "assembly": {
                        "official_full_test_time_minutes": 120,
                        "total_suggested_time_minutes": 120,
                        "sections": [
                            {
                                "module": "Mathematics 1",
                                "module_code": "110000",
                                "section_order": 1,
                                "official_time_minutes": 40,
                                "actual_question_count": 0,
                                "target_question_count": 27,
                                "diagnostic_flags": ["underfilled"],
                                "diagnostic_confidence": "low",
                            },
                            {
                                "module": "Biology",
                                "module_code": "150000",
                                "section_order": 2,
                                "official_time_minutes": 40,
                                "actual_question_count": 0,
                                "target_question_count": 27,
                                "diagnostic_flags": ["underfilled"],
                                "diagnostic_confidence": "low",
                            },
                            {
                                "module": "Physics",
                                "module_code": "130000",
                                "section_order": 3,
                                "official_time_minutes": 40,
                                "actual_question_count": 1,
                                "target_question_count": 27,
                                "diagnostic_flags": ["underfilled", "narrow_coverage"],
                                "diagnostic_confidence": "low",
                            },
                        ],
                    },
                },
                "questions": [
                    {
                        "code": "ENGAA_2023_S1_Q06",
                        "title": [
                            {"type": "text", "content": "A force "},
                            {"type": "latex", "content": "F", "mode": "inline"},
                            {"type": "text", "content": " acts."},
                            {"type": "image_ref", "image_id": "q6-graph"},
                            {"type": "text", "content": "What is F?"},
                        ],
                        "options": [
                            {"label": "A", "content": [{"type": "text", "content": "1 N"}]},
                            {
                                "label": "B",
                                "content": [
                                    {
                                        "type": "latex",
                                        "content": "2\\,\\mathrm{N}",
                                        "mode": "inline",
                                    }
                                ],
                            },
                        ],
                        "answer": "B",
                        "questionNumber": 6,
                        "images": [
                            {
                                "image_id": "q6-graph",
                                "alt_text": "Force graph",
                                "status": "restored",
                                "asset_path": "graph.svg",
                            },
                            {
                                "image_id": "q6-crop",
                                "alt_text": "Source crop",
                                "status": "restored",
                                "asset_path": "crop.png",
                            }
                        ],
                        "source_examType": "ENGAA",
                        "subject": "Physics",
                        "subject_code": "130000",
                        "topic": "Mechanics (力学)",
                        "topic_code": "131000",
                        "question_type": "multiple_choice",
                        "difficulty": "medium",
                        "knowledge_points": [
                            {"code": "P3.7", "name": "Energy (能量)", "is_primary": True}
                        ],
                        "target_exam_scope": {
                            "syllabus_items": [
                                {"code": "131004", "label": "Energy, work & power (能量、功和功率)"}
                            ]
                        },
                        "learning_analysis": {
                            "exam_focus": "考查力与能量关系。",
                            "correct_solution": "根据题目条件计算并选择 B。",
                            "common_error_causes": ["误读图像关系。"],
                            "review_guidance": "复习力、功和能量关系。",
                        },
                        "assembled_section": {
                            "module": "Physics",
                            "question_order": 1,
                        },
                    }
                ],
            }

            result = build_project_diagnostic_paper(
                assembled,
                paper_code="ESAT_2023_M1_Biology_Physics",
                asset_base_dir=root,
            )

        self.assertEqual(result["metadata"]["paperType"], "realPaper")
        self.assertEqual(result["metadata"]["deliveryMode"], "section_sequence")
        self.assertEqual(result["metadata"]["assemblyType"], "legacy_equivalent")
        self.assertEqual(sum(len(section["questions"]) for section in result["sections"]), 1)
        self.assertIn("Physics：实际 1/27 题", result["metadata"]["remarks"])
        self.assertIn("题量不足 26 题", result["metadata"]["remarks"])
        self.assertIn("考纲覆盖偏窄", result["metadata"]["remarks"])
        self.assertIn("诊断可信度低", result["metadata"]["remarks"])
        self.assertEqual(len(result["sections"]), 3)
        self.assertEqual(
            [section["code"] for section in result["sections"]],
            ["maths1", "biology", "physics"],
        )
        self.assertEqual(result["sections"][2]["sectionType"], "subject")
        self.assertEqual(
            set(result["sections"][2]),
            {"code", "sectionType", "order", "questions"},
        )
        question = result["sections"][2]["questions"][0]
        self.assertEqual(question["number"], 1)
        self.assertEqual(question["answer"], ["B"])
        self.assertEqual(question["title"], "A force \\(F\\) acts.")
        self.assertEqual(question["contentBlocks"][1], {"type": "image_ref", "image_id": "q6-graph"})
        self.assertEqual(question["classification"]["knowledgePoints"][0]["role"], "primary")
        self.assertEqual(question["source"]["sectionCode"], "physics")
        self.assertIn("<svg", question["images"][0]["svg"])
        self.assertTrue(question["images"][1]["src"].startswith("data:image/png;base64,"))
        self.assertNotIn("examType", question)
        self.assertNotIn("subject_code", question)
        self.assertNotIn("is_ai_generated", question)

        invalid = copy.deepcopy(result)
        invalid["metadata"]["deliveryMode"] = "module_sequence"
        with self.assertRaises(ContractError):
            validate_project_diagnostic_paper(invalid)

        invalid = copy.deepcopy(result)
        invalid["sections"][2]["questions"][0]["contentBlocks"].insert(
            1,
            {"type": "paragraph", "text": ","},
        )
        with self.assertRaises(ContractError):
            validate_project_diagnostic_paper(invalid)


if __name__ == "__main__":
    unittest.main()
