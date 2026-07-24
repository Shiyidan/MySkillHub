from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SUITE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SUITE_ROOT / "exam-paper-assembler" / "scripts" / "assemble.py"
SPEC = importlib.util.spec_from_file_location("exam_paper_assemble_script", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
ASSEMBLE_SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSEMBLE_SCRIPT)


class AssembleYearAtomicTest(unittest.TestCase):
    def _args(self, root: Path) -> SimpleNamespace:
        input_path = root / "annual.json"
        input_path.write_text(json.dumps({"placeholder": True}), encoding="utf-8")
        return SimpleNamespace(
            input=str(input_path),
            output_dir=str(root / "final"),
            constraints=None,
            canonical_output_dir=None,
        )

    def _project_paper(self, year: int, modules: tuple[str, ...] | list[str]) -> dict:
        module_codes = {
            "Mathematics 1": "110000",
            "Biology": "150000",
            "Chemistry": "140000",
            "Physics": "130000",
            "Mathematics 2": "120000",
        }
        combination_name = ASSEMBLE_SCRIPT.safe_combination_name(modules)
        code = f"ESAT_{year}_{combination_name}"
        section_codes = {
            "Mathematics 1": "maths1",
            "Biology": "biology",
            "Chemistry": "chemistry",
            "Physics": "physics",
            "Mathematics 2": "maths2",
        }
        sections = [
            {
                "code": section_codes[module],
                "sectionType": "subject",
                "order": index,
                "questions": [{"code": f"{module_codes[module]}_Q01"}],
            }
            for index, module in enumerate(modules, 1)
        ]
        return {
            "metadata": {
                "code": code,
                "title": code,
                "examType": "ESAT",
                "year": year,
                "paperType": "realPaper",
                "assemblyType": "legacy_equivalent",
                "deliveryMode": "section_sequence",
                "remarks": "test",
            },
            "sections": sections,
        }

    def _write_project_package(self, package_dir: Path, year: int = 2023) -> None:
        package_dir.mkdir(parents=True)
        for modules in ASSEMBLE_SCRIPT.ESAT_COMBINATIONS:
            paper = self._project_paper(year, modules)
            (package_dir / f"{paper['metadata']['code']}.json").write_text(
                json.dumps(paper, ensure_ascii=False),
                encoding="utf-8",
            )

    def _read_json_side_effect(self, args: SimpleNamespace, document: dict):
        input_path = Path(args.input).resolve()

        def read(path: str | Path) -> dict:
            resolved = Path(path).resolve()
            if resolved == input_path:
                return document
            return json.loads(resolved.read_text(encoding="utf-8"))

        return read

    def _assembled_side_effect(self, document: dict, constraints: dict, **_kwargs: object) -> dict:
        return {
            "metadata": {
                "year": document["metadata"]["year"],
                "assembly": {"modules": list(constraints["modules"])},
            }
        }

    def _project_side_effect(self, assembled: dict, *, paper_code: str, **_kwargs: object) -> dict:
        paper = self._project_paper(
            assembled["metadata"]["year"],
            assembled["metadata"]["assembly"]["modules"],
        )
        self.assertEqual(paper["metadata"]["code"], paper_code)
        return paper

    def test_failure_does_not_publish_partial_year(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self._args(root)
            document = {"metadata": {"year": 2023}}
            calls = 0

            def fail_on_third(*_args: object, **_kwargs: object) -> dict:
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise ValueError("synthetic assembly failure")
                return {"metadata": {"year": 2023}}

            with (
                patch.object(ASSEMBLE_SCRIPT, "read_json", return_value=document),
                patch.object(ASSEMBLE_SCRIPT, "build_assembled_exam", side_effect=fail_on_third),
                patch.object(ASSEMBLE_SCRIPT, "build_project_diagnostic_paper", return_value={"ok": True}),
            ):
                with self.assertRaisesRegex(ValueError, "synthetic"):
                    ASSEMBLE_SCRIPT.command_assemble_year(args)

            self.assertFalse((root / "final").exists())
            self.assertEqual(list(root.glob(".final.staging-*")), [])

    def test_success_publishes_exactly_six_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self._args(root)
            document = {"metadata": {"year": 2023}}
            final_dir = root / "final"
            final_dir.mkdir()
            (final_dir / "stale.json").write_text("old", encoding="utf-8")

            with (
                patch.object(ASSEMBLE_SCRIPT, "read_json", side_effect=self._read_json_side_effect(args, document)),
                patch.object(ASSEMBLE_SCRIPT, "build_assembled_exam", side_effect=self._assembled_side_effect),
                patch.object(ASSEMBLE_SCRIPT, "build_project_diagnostic_paper", side_effect=self._project_side_effect),
                patch.object(ASSEMBLE_SCRIPT, "validate_project_diagnostic_paper"),
            ):
                ASSEMBLE_SCRIPT.command_assemble_year(args)

            files = sorted((root / "final").glob("*.json"))
            self.assertEqual(len(files), 6)
            self.assertFalse((root / "final" / "stale.json").exists())
            self.assertEqual(list(root.glob(".final.staging-*")), [])
            self.assertEqual(list(root.glob(".final.backup-*")), [])

    def test_project_package_rejects_wrong_module_combination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_dir = Path(directory) / "package"
            self._write_project_package(package_dir)
            modules = ASSEMBLE_SCRIPT.ESAT_COMBINATIONS[1]
            path = package_dir / f"ESAT_2023_{ASSEMBLE_SCRIPT.safe_combination_name(modules)}.json"
            paper = json.loads(path.read_text(encoding="utf-8"))
            paper["sections"][1], paper["sections"][2] = paper["sections"][2], paper["sections"][1]
            path.write_text(json.dumps(paper, ensure_ascii=False), encoding="utf-8")

            with (
                patch.object(ASSEMBLE_SCRIPT, "validate_project_diagnostic_paper"),
                self.assertRaisesRegex(ASSEMBLE_SCRIPT.ContractError, "section code 组合"),
            ):
                ASSEMBLE_SCRIPT._validate_year_project_package(package_dir, 2023)

    def test_project_package_rejects_module_question_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_dir = Path(directory) / "package"
            self._write_project_package(package_dir)
            modules = ("Mathematics 1", "Chemistry", "Physics")
            path = package_dir / f"ESAT_2023_{ASSEMBLE_SCRIPT.safe_combination_name(modules)}.json"
            paper = json.loads(path.read_text(encoding="utf-8"))
            paper["sections"][2]["questions"][0]["code"] = "130000_Q_DIFFERENT"
            path.write_text(json.dumps(paper, ensure_ascii=False), encoding="utf-8")

            with (
                patch.object(ASSEMBLE_SCRIPT, "validate_project_diagnostic_paper"),
                self.assertRaisesRegex(ASSEMBLE_SCRIPT.ContractError, "模块题目或顺序不一致"),
            ):
                ASSEMBLE_SCRIPT._validate_year_project_package(package_dir, 2023)

    def test_publish_failure_restores_existing_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self._args(root)
            document = {"metadata": {"year": 2023}}
            final_dir = root / "final"
            final_dir.mkdir()
            (final_dir / "old.json").write_text("old package", encoding="utf-8")
            real_replace = os.replace

            def fail_project_publish(source: str | Path, destination: str | Path) -> None:
                if Path(source).name == "project" and Path(destination).resolve() == final_dir.resolve():
                    raise OSError("synthetic project publish failure")
                real_replace(source, destination)

            with (
                patch.object(ASSEMBLE_SCRIPT, "read_json", side_effect=self._read_json_side_effect(args, document)),
                patch.object(ASSEMBLE_SCRIPT, "build_assembled_exam", side_effect=self._assembled_side_effect),
                patch.object(ASSEMBLE_SCRIPT, "build_project_diagnostic_paper", side_effect=self._project_side_effect),
                patch.object(ASSEMBLE_SCRIPT, "validate_project_diagnostic_paper"),
                patch.object(ASSEMBLE_SCRIPT.os, "replace", side_effect=fail_project_publish),
                self.assertRaisesRegex(OSError, "synthetic project"),
            ):
                ASSEMBLE_SCRIPT.command_assemble_year(args)

            self.assertEqual((final_dir / "old.json").read_text(encoding="utf-8"), "old package")
            self.assertEqual(sorted(path.name for path in final_dir.iterdir()), ["old.json"])
            self.assertEqual(list(root.glob(".final.staging-*")), [])
            self.assertEqual(list(root.glob(".final.backup-*")), [])

    def test_canonical_publish_failure_rolls_back_both_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self._args(root)
            args.canonical_output_dir = str(root / "canonical-final")
            document = {"metadata": {"year": 2023}}
            final_dir = root / "final"
            canonical_dir = root / "canonical-final"
            final_dir.mkdir()
            canonical_dir.mkdir()
            (final_dir / "old-project.json").write_text("old project", encoding="utf-8")
            (canonical_dir / "old-canonical.json").write_text("old canonical", encoding="utf-8")
            real_replace = os.replace

            def fail_canonical_publish(source: str | Path, destination: str | Path) -> None:
                if Path(source).name == "canonical" and Path(destination).resolve() == canonical_dir.resolve():
                    raise OSError("synthetic canonical publish failure")
                real_replace(source, destination)

            with (
                patch.object(ASSEMBLE_SCRIPT, "read_json", side_effect=self._read_json_side_effect(args, document)),
                patch.object(ASSEMBLE_SCRIPT, "build_assembled_exam", side_effect=self._assembled_side_effect),
                patch.object(ASSEMBLE_SCRIPT, "build_project_diagnostic_paper", side_effect=self._project_side_effect),
                patch.object(ASSEMBLE_SCRIPT, "validate_project_diagnostic_paper"),
                patch.object(ASSEMBLE_SCRIPT, "validate_document"),
                patch.object(ASSEMBLE_SCRIPT.os, "replace", side_effect=fail_canonical_publish),
                self.assertRaisesRegex(OSError, "synthetic canonical"),
            ):
                ASSEMBLE_SCRIPT.command_assemble_year(args)

            self.assertEqual((final_dir / "old-project.json").read_text(encoding="utf-8"), "old project")
            self.assertEqual(
                (canonical_dir / "old-canonical.json").read_text(encoding="utf-8"),
                "old canonical",
            )
            self.assertEqual(list(root.glob(".final.staging-*")), [])
            self.assertEqual(list(root.glob(".final.backup-*")), [])
            self.assertEqual(list(root.glob(".canonical-final.staging-*")), [])
            self.assertEqual(list(root.glob(".canonical-final.backup-*")), [])


if __name__ == "__main__":
    unittest.main()
