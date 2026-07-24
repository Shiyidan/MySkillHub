from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core.fingerprint import question_fingerprint  # noqa: E402


class FingerprintCompatibilityTest(unittest.TestCase):
    def test_version_two_fingerprint_remains_stable_after_normalizer_refactor(self) -> None:
        question = {
            "title": [
                {"type": "text", "content": "  AREA  \uff21\n equals  10  "},
            ],
            "options": [
                {
                    "label": "A",
                    "content": [{"type": "latex", "content": "R^2", "mode": "inline"}],
                },
                {"label": "B", "content": [{"type": "text", "content": "  r  "}]},
            ],
            "diagram": {"semantics": "  Circle   Radius  "},
        }

        self.assertEqual(
            question_fingerprint(question),
            "603389f4039b092ac8c671d00c808ab2e4b398a7a7949f9241f29f82cdab70fe",
        )


if __name__ == "__main__":
    unittest.main()
