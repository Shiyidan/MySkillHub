from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core.project_export import build_project_diagnostic_paper  # noqa: E402


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
                    "title": "ESAT legacy diagnostic paper: Mathematics 1 + Biology + Physics",
                    "assembly": {"total_suggested_time_minutes": 72},
                },
                "questions": [
                    {
                        "code": "ENGAA_2023_S1_Q06",
                        "title": [
                            {"type": "text", "content": "A force "},
                            {"type": "latex", "content": "F"},
                            {"type": "text", "content": " acts."},
                            {"type": "image_ref", "image_id": "q6-graph"},
                            {"type": "text", "content": "What is F?"},
                        ],
                        "options": [
                            {"label": "A", "content": [{"type": "text", "content": "1 N"}]},
                            {"label": "B", "content": [{"type": "latex", "content": "2\\,\\mathrm{N}"}]},
                        ],
                        "answer": "B",
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
                            "review_guidance": "复习力、功和能量关系。",
                        },
                    }
                ],
            }

            result = build_project_diagnostic_paper(
                assembled,
                paper_code="ESAT_2023_M1_Biology_Physics",
                asset_base_dir=root,
            )

        self.assertEqual(result["metadata"]["paperType"], "mockPaper")
        self.assertEqual(result["metadata"]["totalQuestions"], 1)
        question = result["questions"][0]
        self.assertEqual(question["number"], 1)
        self.assertEqual(question["answer"], ["B"])
        self.assertEqual(question["title"], "A force \\(F\\) acts.")
        self.assertEqual(question["content_blocks"][1], {"type": "image_ref", "image_id": "q6-graph"})
        self.assertEqual(question["syllabus_points"][0]["role"], "primary")
        self.assertIn("<svg", question["images"][0]["svg"])
        self.assertTrue(question["images"][1]["src"].startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
