from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core import PipelineState  # noqa: E402


class CheckpointIdentityTest(unittest.TestCase):
    def test_parameters_are_part_of_checkpoint_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipeline-state.json"
            state = PipelineState.open_or_create(
                path,
                pipeline="parser",
                input_hash="a" * 64,
                stages=["inspect", "export"],
                parameters={"paper_type": "realPaper"},
            )
            self.assertEqual(state.data["parameters"], {"paper_type": "realPaper"})

            with self.assertRaisesRegex(ValueError, "parameters"):
                PipelineState.open_or_create(
                    path,
                    pipeline="parser",
                    input_hash="a" * 64,
                    stages=["inspect", "export"],
                    parameters={"paper_type": "mockPaper"},
                )


if __name__ == "__main__":
    unittest.main()
