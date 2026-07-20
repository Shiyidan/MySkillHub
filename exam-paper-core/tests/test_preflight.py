from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core import scan_tree  # noqa: E402


class PreflightTest(unittest.TestCase):
    def test_valid_skill_and_schema_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "sample-skill"
            (root / "agents").mkdir(parents=True)
            (root / "schema").mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: sample-skill\ndescription: A complete sample skill used for structural validation.\n---\n\n# Sample\n",
                encoding="utf-8",
            )
            (root / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "Sample"\n  short_description: "A sufficiently descriptive sample skill summary"\n  default_prompt: "Use $sample-skill for this task."\n',
                encoding="utf-8",
            )
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
            }
            (root / "schema" / "sample.schema.json").write_text(
                json.dumps(schema), encoding="utf-8"
            )

            self.assertEqual(scan_tree(root), [])

    def test_preflight_rejects_placeholders_and_broken_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "broken-skill"
            (root / "agents").mkdir(parents=True)
            (root / "schema").mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: broken-skill\ndescription: TODO\n---\n",
                encoding="utf-8",
            )
            (root / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "Broken"\n  short_description: "too short"\n  default_prompt: "Use this skill."\n',
                encoding="utf-8",
            )
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["missing"],
                "properties": {},
            }
            (root / "schema" / "broken.schema.json").write_text(
                json.dumps(schema), encoding="utf-8"
            )

            errors = "\n".join(scan_tree(root))
            self.assertIn("TODO", errors)
            self.assertIn("short_description", errors)
            self.assertIn("未定义 properties", errors)


if __name__ == "__main__":
    unittest.main()
