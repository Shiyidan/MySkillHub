#!/usr/bin/env python3
"""按 ESAT 模块组合从年度题库生成诊断性 assembled_exam。"""

from __future__ import annotations

import argparse
import json
import sys
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


def command_assemble_year(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    document = read_json(input_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base_constraints = read_json(Path(args.constraints)) if args.constraints else {}
    created: list[Path] = []
    canonical_output_dir = Path(args.canonical_output_dir) if args.canonical_output_dir else None
    if canonical_output_dir:
        canonical_output_dir.mkdir(parents=True, exist_ok=True)
    for modules in ESAT_COMBINATIONS:
        constraints = dict(base_constraints)
        constraints["target_exam"] = "ESAT"
        constraints["modules"] = list(modules)
        constraints.setdefault("paper_mode", "diagnostic_combination_paper")
        constraints.setdefault("title", f"ESAT legacy diagnostic paper: {' + '.join(modules)}")
        constraints_path = output_dir / f".constraints_{safe_combination_name(modules)}.json"
        write_json_atomic(constraints_path, constraints)
        source_hash = calculate_source_hash([input_path, constraints_path])
        assembled = build_assembled_exam(
            document,
            constraints,
            source_hash=source_hash,
            source_document_name=source_name(input_path),
        )
        paper_code = f"ESAT_{document['metadata']['year']}_{safe_combination_name(modules)}"
        project_paper = build_project_diagnostic_paper(
            assembled,
            paper_code=paper_code,
            asset_base_dir=input_path.parent,
        )
        output_path = output_dir / f"{paper_code}.json"
        write_json_atomic(output_path, project_paper)
        if canonical_output_dir:
            write_json_atomic(canonical_output_dir / f"{paper_code}.canonical.json", assembled)
        constraints_path.unlink(missing_ok=True)
        created.append(output_path)
    print(f"已生成 {len(created)} 套可直接导入项目的 ESAT 年度诊断组合卷：{output_dir.resolve()}")
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
    assemble.add_argument("--output", required=True, help="可直接导入项目的完整诊断卷 JSON 输出路径。")
    assemble.add_argument("--canonical-output", help="可选：同时保存内部 assembled_exam canonical JSON。")
    assemble.set_defaults(handler=command_assemble)

    assemble_year = subparsers.add_parser("assemble-year", help="自动生成年度 6 套 ESAT 诊断组合卷")
    assemble_year.add_argument("--input", required=True, help="已通过校验的年度 parsed_exam JSON。")
    assemble_year.add_argument("--output-dir", required=True, help="6 套可直接导入项目的完整诊断卷 JSON 输出目录。")
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
