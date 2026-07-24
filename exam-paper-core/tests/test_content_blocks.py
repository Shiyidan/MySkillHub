from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core.content_blocks import from_structured_parts  # noqa: E402


class ContentBlockReconstructionTest(unittest.TestCase):
    def test_inline_latex_remains_inside_source_paragraph(self) -> None:
        parts = [
            {"type": "text", "content": "where "},
            {"type": "latex", "content": "a", "mode": "inline"},
            {"type": "text", "content": " is a real constant."},
        ]

        self.assertEqual(
            from_structured_parts(parts),
            [
                {
                    "type": "paragraph",
                    "text": "where \\(a\\) is a real constant.",
                }
            ],
        )

    def test_centered_display_lines_remain_separate(self) -> None:
        parts = [
            {"type": "text", "content": "Consider the simultaneous equations"},
            {
                "type": "latex",
                "content": "3x^2+2xy=4",
                "mode": "block",
                "align": "center",
            },
            {
                "type": "latex",
                "content": "x+y=a",
                "mode": "block",
                "align": "center",
            },
            {
                "type": "text",
                "content": "where ",
                "break_before": True,
            },
            {"type": "latex", "content": "a", "mode": "inline"},
            {"type": "text", "content": " is a real constant."},
        ]

        self.assertEqual(
            from_structured_parts(parts),
            [
                {
                    "type": "paragraph",
                    "text": "Consider the simultaneous equations",
                },
                {
                    "type": "paragraph",
                    "text": "\\[3x^2+2xy=4\\]",
                    "align": "center",
                },
                {
                    "type": "paragraph",
                    "text": "\\[x+y=a\\]",
                    "align": "center",
                },
                {
                    "type": "paragraph",
                    "text": "where \\(a\\) is a real constant.",
                },
            ],
        )

    def test_latex_mode_and_block_alignment_are_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "mode"):
            from_structured_parts([{"type": "latex", "content": "a"}])
        with self.assertRaisesRegex(ValueError, "alignment"):
            from_structured_parts(
                [{"type": "latex", "content": "a=1", "mode": "block"}]
            )


if __name__ == "__main__":
    unittest.main()
