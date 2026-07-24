#!/usr/bin/env python3
"""按 ESAT 模块组合从年度题库生成诊断性 assembled_exam。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
CORE_PYTHON = Path(__file__).resolve().parents[2] / "exam-paper-core" / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core import (  # noqa: E402
    ChineseArgumentParser,
    ContractError,
    ESAT_COMBINATIONS,
    analyze_assembly,
    build_assembled_exam,
    build_project_diagnostic_paper,
    calculate_source_hash,
    read_json,
    scan_tree,
    validate_document,
    validate_project_diagnostic_paper,
    write_json_atomic,
)
from exam_paper_core.assembly import safe_combination_name, source_name  # noqa: E402


def command_preflight(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    problems = scan_tree(root)
    if problems:
        print("预检失败：")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print(f"预检通过：{root}")


def _load_inputs(input_path: Path, constraints_path: Path) -> tuple[dict, dict, str]:
    document = read_json(input_path)
    constraints = read_json(constraints_path)
    source_hash = calculate_source_hash([input_path, constraints_path])
    return document, constraints, source_hash


def command_analyze(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    constraints_path = Path(args.constraints)
    document, constraints, _ = _load_inputs(input_path, constraints_path)
    analysis = analyze_assembly(document, constraints, source_document_name=source_name(input_path))
    write_json_atomic(Path(args.output), analysis)
    print(f"ESAT 组卷分析已导出：{Path(args.output).resolve()}")


def command_assemble(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    constraints_path = Path(args.constraints)
    document, constraints, source_hash = _load_inputs(input_path, constraints_path)
    assembled = build_assembled_exam(
        document,
        constraints,
        source_hash=source_hash,
        source_document_name=source_name(input_path),
    )
    modules = assembled["metadata"]["assembly"]["modules"]
    paper_code = f"ESAT_{assembled['metadata']['year']}_{safe_combination_name(modules)}"
    project_paper = build_project_diagnostic_paper(
        assembled,
        paper_code=paper_code,
        asset_base_dir=input_path.parent,
    )
    output = Path(args.output)
    write_json_atomic(output, project_paper)
    if args.canonical_output:
        write_json_atomic(Path(args.canonical_output), assembled)
    print(f"ESAT 诊断组合卷已导出：{output.resolve()}")
    print(f"模块组合：{' + '.join(assembled['metadata']['assembly']['modules'])}")
    for section in assembled["metadata"]["assembly"]["sections"]:
        print(f"- {section['module']}: {section['actual_question_count']} 题，可信度 {section['diagnostic_confidence']}")


def _expected_year_packages(year: int) -> dict[str, tuple[str, ...]]:
    return {
        f"ESAT_{year}_{safe_combination_name(modules)}.json": tuple(modules)
        for modules in ESAT_COMBINATIONS
    }


def _validate_year_project_package(package_dir: Path, year: int) -> list[str]:
    """Validate all six project papers as one publishable annual package."""

    section_codes = {
        "Mathematics 1": "maths1",
        "Mathematics 2": "maths2",
        "Physics": "physics",
        "Chemistry": "chemistry",
        "Biology": "biology",
    }
    expected = _expected_year_packages(year)
    actual = {path.name for path in package_dir.iterdir() if path.is_file()}
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        unexpected = sorted(actual - set(expected))
        raise ContractError(f"年度组合卷文件集合不完整：缺少 {missing}，多出 {unexpected}。")

    module_question_codes: dict[str, tuple[str, ...]] = {}
    question_owners: dict[str, str] = {}
    for filename, expected_modules in expected.items():
        paper = read_json(package_dir / filename)
        validate_project_diagnostic_paper(paper)
        expected_code = filename.removesuffix(".json")
        metadata = paper.get("metadata", {})
        if metadata.get("code") != expected_code:
            raise ContractError(f"{filename} 的 metadata.code 必须是 {expected_code}。")
        if metadata.get("year") != year:
            raise ContractError(f"{filename} 的年份与年度题库不一致。")
        if metadata.get("examType") != "ESAT":
            raise ContractError(f"{filename} 的 metadata.examType 必须是 ESAT。")
        if metadata.get("assemblyType") != "legacy_equivalent":
            raise ContractError(f"{filename} 的 metadata.assemblyType 必须是 legacy_equivalent。")
        if metadata.get("deliveryMode") != "section_sequence":
            raise ContractError(f"{filename} 的 metadata.deliveryMode 必须是 section_sequence。")

        sections = paper.get("sections", [])
        actual_section_codes = tuple(section.get("code") for section in sections if isinstance(section, dict))
        expected_section_codes = tuple(section_codes[module] for module in expected_modules)
        if actual_section_codes != expected_section_codes:
            raise ContractError(
                f"{filename} 的 section code 组合应为 {list(expected_section_codes)}，实际为 {list(actual_section_codes)}。"
            )

        paper_codes: set[str] = set()
        for module, section in zip(expected_modules, sections):
            if section.get("sectionType") != "subject":
                raise ContractError(f"{filename} 的 {module} sectionType 必须是 subject。")
            questions = section.get("questions", [])
            codes = tuple(item.get("code") for item in questions if isinstance(item, dict))
            if len(codes) != len(questions) or any(not isinstance(code, str) or not code for code in codes):
                raise ContractError(f"{filename} 的 {module} 模块存在无效题目 code。")
            if len(codes) != len(set(codes)):
                raise ContractError(f"{filename} 的 {module} 模块存在重复题目。")
            overlap = paper_codes.intersection(codes)
            if overlap:
                raise ContractError(f"{filename} 的不同模块重复使用题目：{sorted(overlap)}。")
            paper_codes.update(codes)

            previous_codes = module_question_codes.setdefault(module, codes)
            if previous_codes != codes:
                raise ContractError(f"六套卷中的 {module} 模块题目或顺序不一致。")
            for code in codes:
                previous_owner = question_owners.setdefault(code, module)
                if previous_owner != module:
                    raise ContractError(f"题目 {code} 在年度组合卷中被分配到多个模块。")

    return list(expected)


def _validate_year_canonical_package(package_dir: Path, year: int) -> None:
    expected = {
        filename.removesuffix(".json") + ".canonical.json": modules
        for filename, modules in _expected_year_packages(year).items()
    }
    actual = {path.name for path in package_dir.iterdir() if path.is_file()}
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        unexpected = sorted(actual - set(expected))
        raise ContractError(f"年度 canonical 文件集合不完整：缺少 {missing}，多出 {unexpected}。")
    for filename, expected_modules in expected.items():
        document = read_json(package_dir / filename)
        validate_document(document, expected_type="assembled_exam")
        if document.get("metadata", {}).get("year") != year:
            raise ContractError(f"{filename} 的年份与年度题库不一致。")
        modules = tuple(document.get("metadata", {}).get("assembly", {}).get("modules", []))
        if modules != expected_modules:
            raise ContractError(f"{filename} 的 canonical 模块组合不正确。")


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _publish_directories_transactionally(pairs: list[tuple[Path, Path]]) -> None:
    """Publish complete directories and restore every prior target on failure."""

    if not pairs:
        raise ContractError("没有可发布的年度组合卷目录。")
    targets = [target.resolve() for _, target in pairs]
    for index, target in enumerate(targets):
        if any(_paths_overlap(target, other) for other in targets[index + 1 :]):
            raise ContractError("项目输出目录与 canonical 输出目录不得相同或互相嵌套。")

    token = uuid.uuid4().hex
    backups: list[tuple[Path, Path]] = []
    published: list[Path] = []
    try:
        for staged, target in pairs:
            if not staged.is_dir():
                raise ContractError(f"待发布目录不存在：{staged}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not target.is_dir():
                raise ContractError(f"发布目标必须是目录：{target}")
            if target.exists():
                backup = target.parent / f".{target.name}.backup-{token}"
                os.replace(target, backup)
                backups.append((target, backup))

        for staged, target in pairs:
            os.replace(staged, target)
            published.append(target)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for target in reversed(published):
            try:
                _remove_path(target)
            except OSError as rollback_exc:
                rollback_errors.append(f"删除新目录 {target} 失败：{rollback_exc}")
        for target, backup in reversed(backups):
            try:
                if backup.exists():
                    os.replace(backup, target)
            except OSError as rollback_exc:
                rollback_errors.append(f"恢复旧目录 {target} 失败：{rollback_exc}")
        if rollback_errors:
            details = "；".join(rollback_errors)
            raise ContractError(f"年度组合卷发布失败且回滚不完整：{details}") from exc
        raise
    else:
        for _, backup in backups:
            shutil.rmtree(backup, ignore_errors=True)


def command_assemble_year(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    document = read_json(input_path)
    output_dir = Path(args.output_dir).resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    base_constraints = read_json(Path(args.constraints)) if args.constraints else {}
    if not isinstance(base_constraints, dict):
        raise ContractError("年度通用约束必须是 JSON 对象。")
    title_template = base_constraints.pop("title_template", None)
    explicit_title = base_constraints.pop("title", None)
    canonical_output_dir = Path(args.canonical_output_dir).resolve() if args.canonical_output_dir else None
    if canonical_output_dir and _paths_overlap(output_dir, canonical_output_dir):
        raise ContractError("项目输出目录与 canonical 输出目录不得相同或互相嵌套。")
    # tempfile.mkdtemp creates a private Windows ACL that follows files moved
    # into the final directory. A normal inherited directory keeps published
    # JSON readable by the desktop user while retaining isolated staging.
    run_id = uuid.uuid4().hex
    staging_root = output_dir.parent / f".{output_dir.name}.staging-{run_id}"
    staging_root.mkdir()
    staged_project_dir = staging_root / "project"
    canonical_staging_root = None
    staged_canonical_dir = None
    if canonical_output_dir:
        canonical_output_dir.parent.mkdir(parents=True, exist_ok=True)
        canonical_staging_root = canonical_output_dir.parent / f".{canonical_output_dir.name}.staging-{run_id}"
        canonical_staging_root.mkdir()
        staged_canonical_dir = canonical_staging_root / "canonical"
        staged_canonical_dir.mkdir()
    staged_constraints_dir = staging_root / "constraints"
    staged_project_dir.mkdir(parents=True)
    staged_constraints_dir.mkdir(parents=True)
    staged_names: list[str] = []
    try:
        for modules in ESAT_COMBINATIONS:
            constraints = dict(base_constraints)
            constraints["target_exam"] = "ESAT"
            constraints["modules"] = list(modules)
            constraints.setdefault("paper_mode", "diagnostic_combination_paper")
            module_text = " + ".join(modules)
            if isinstance(title_template, str) and title_template.strip():
                try:
                    constraints["title"] = title_template.format(
                        year=document["metadata"]["year"], modules=module_text
                    )
                except (KeyError, ValueError) as exc:
                    raise ContractError(
                        "title_template 只允许使用 {year} 和 {modules} 占位符。"
                    ) from exc
            elif isinstance(explicit_title, str) and explicit_title.strip():
                constraints["title"] = f"{explicit_title}: {module_text}"
            else:
                constraints["title"] = f"ESAT legacy diagnostic paper: {module_text}"
            combination_name = safe_combination_name(modules)
            constraints_path = staged_constraints_dir / f"{combination_name}.json"
            write_json_atomic(constraints_path, constraints)
            source_hash = calculate_source_hash([input_path, constraints_path])
            assembled = build_assembled_exam(
                document,
                constraints,
                source_hash=source_hash,
                source_document_name=source_name(input_path),
            )
            paper_code = f"ESAT_{document['metadata']['year']}_{combination_name}"
            project_paper = build_project_diagnostic_paper(
                assembled,
                paper_code=paper_code,
                asset_base_dir=input_path.parent,
            )
            filename = f"{paper_code}.json"
            write_json_atomic(staged_project_dir / filename, project_paper)
            if staged_canonical_dir:
                write_json_atomic(staged_canonical_dir / f"{paper_code}.canonical.json", assembled)
            staged_names.append(filename)

        staged_names = _validate_year_project_package(staged_project_dir, document["metadata"]["year"])
        publish_pairs = [(staged_project_dir, output_dir)]
        if staged_canonical_dir and canonical_output_dir:
            _validate_year_canonical_package(staged_canonical_dir, document["metadata"]["year"])
            publish_pairs.append((staged_canonical_dir, canonical_output_dir))
        _publish_directories_transactionally(publish_pairs)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        if canonical_staging_root:
            shutil.rmtree(canonical_staging_root, ignore_errors=True)

    created = [output_dir / filename for filename in staged_names]
    print(f"已生成 {len(created)} 套统一 sections 结构的 ESAT 年度诊断组合卷：{output_dir.resolve()}")
    for path in created:
        print(f"- {path.name}")


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(description="ESAT legacy 真题诊断组卷工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="只读检查 Skill 文件")
    preflight.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    preflight.set_defaults(handler=command_preflight)

    analyze = subparsers.add_parser("analyze", help="分析某一模块组合的组卷状态")
    analyze.add_argument("--input", required=True, help="已通过校验的年度 parsed_exam JSON。")
    analyze.add_argument("--constraints", required=True, help="ESAT 模块组合约束 JSON。")
    analyze.add_argument("--output", required=True, help="分析 JSON 输出路径。")
    analyze.set_defaults(handler=command_analyze)

    assemble = subparsers.add_parser("assemble", help="生成一套 ESAT 诊断组合卷")
    assemble.add_argument("--input", required=True, help="已通过校验的年度 parsed_exam JSON。")
    assemble.add_argument("--constraints", required=True, help="ESAT 模块组合约束 JSON。")
    assemble.add_argument("--output", required=True, help="统一 sections 结构诊断卷 JSON 输出路径。")
    assemble.add_argument("--canonical-output", help="可选：同时保存内部 assembled_exam canonical JSON。")
    assemble.set_defaults(handler=command_assemble)

    assemble_year = subparsers.add_parser("assemble-year", help="自动生成年度 6 套 ESAT 诊断组合卷")
    assemble_year.add_argument("--input", required=True, help="已通过校验的年度 parsed_exam JSON。")
    assemble_year.add_argument("--output-dir", required=True, help="6 套统一 sections 结构诊断卷 JSON 输出目录。")
    assemble_year.add_argument("--constraints", help="可选的年度通用约束 JSON。")
    assemble_year.add_argument("--canonical-output-dir", help="可选：保存六套内部 assembled_exam canonical JSON 的目录。")
    assemble_year.set_defaults(handler=command_assemble_year)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
        return 0
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
