#!/usr/bin/env python3
"""Create and validate deterministic handoff manifests for the exam-paper suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
SUITE_ROOT = Path(__file__).resolve().parents[2]
CORE_PYTHON = SUITE_ROOT / "exam-paper-core" / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core import (  # noqa: E402
    ChineseArgumentParser,
    ContractError,
    read_json,
    scan_tree,
    write_json_atomic,
)
from exam_paper_core.production import file_sha256  # noqa: E402


WORKFLOW_VERSION = "1"
RAW_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
OPERATIONS = {"parse", "generate", "assemble-year"}
PAPER_TYPES = {"realPaper", "mockPaper", "aiPaper"}
FEATURE_FLAGS_PATH = Path(__file__).resolve().parents[1] / "workflow-features.json"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _resolved_files(values: list[str]) -> list[Path]:
    files = [Path(value).resolve() for value in values]
    _require(bool(files), "至少需要一个 --input 文件。")
    missing = [str(path) for path in files if not path.is_file()]
    _require(not missing, f"输入文件不存在：{missing}")
    return files


def _input_record(path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": str(path),
        "name": path.name,
        "sha256": file_sha256(path),
        "size": path.stat().st_size,
    }


def _canonical_document(path: Path) -> dict[str, Any]:
    _require(path.suffix.lower() == ".json", "canonical 输入必须是 JSON 文件。")
    document = read_json(path)
    _require(isinstance(document, dict), "canonical 输入根节点必须是对象。")
    return document


def _workflow_features() -> dict[str, Any]:
    features = read_json(FEATURE_FLAGS_PATH)
    _require(isinstance(features, dict) and set(features) == {"profile", "operations"}, "workflow-features.json 字段不完整或包含未知字段。")
    _require(isinstance(features["profile"], str) and features["profile"].strip(), "workflow-features.json.profile 不能为空。")
    operations = features["operations"]
    _require(isinstance(operations, dict) and set(operations) == OPERATIONS, "workflow-features.json.operations 必须完整声明 parse、generate、assemble-year。")
    _require(all(isinstance(enabled, bool) for enabled in operations.values()), "workflow-features.json.operations 的值必须是布尔值。")
    return features


def _require_operation_enabled(operation: str, features: dict[str, Any]) -> None:
    _require(
        features["operations"][operation],
        f"当前工作流配置 {features['profile']} 已关闭 {operation}；本轮只测试试卷解析与组卷。",
    )


def _looks_like_esat_legacy(document: dict[str, Any]) -> bool:
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        return False
    source_types = set(metadata.get("source_exam_types", []))
    return (
        document.get("document_type") == "parsed_exam"
        and metadata.get("paper_type") == "realPaper"
        and source_types == {"ENGAA", "NSAA"}
    )


def _resolve_operation(requested: str, inputs: list[Path], constraints: Path | None) -> str:
    if requested != "auto":
        return requested
    if all(path.suffix.lower() in RAW_SUFFIXES for path in inputs):
        return "parse"
    if len(inputs) == 1 and inputs[0].suffix.lower() == ".json":
        document = _canonical_document(inputs[0])
        if constraints is not None:
            constraint_data = read_json(constraints)
            if isinstance(constraint_data, dict) and "question_count" in constraint_data:
                return "generate"
        if _looks_like_esat_legacy(document):
            return "assemble-year"
    raise ContractError("无法自动判断目标；请明确指定 --operation parse、generate 或 assemble-year。")


def _task_id(records: list[dict[str, Any]], operation: str, parameters: dict[str, Any]) -> str:
    payload = {
        "workflow_version": WORKFLOW_VERSION,
        "operation": operation,
        "inputs": [
            {"role": item["role"], "name": item["name"], "sha256": item["sha256"]}
            for item in records
        ],
        "parameters": parameters,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _plan_parse(args: argparse.Namespace, inputs: list[Path], output_dir: Path) -> tuple[str, dict[str, Any], list[str], list[dict[str, str]]]:
    _require(all(path.suffix.lower() in RAW_SUFFIXES for path in inputs), "parse 只接受 PDF 或页面图片。")
    _require(args.paper_type in PAPER_TYPES, "parse 必须明确 --paper-type realPaper、mockPaper 或 aiPaper。")
    workdir = output_dir / "artifacts" / "parser-run"
    command = [
        "python",
        str(SUITE_ROOT / "exam-paper-parser" / "scripts" / "pipeline.py"),
        "init",
    ]
    for path in inputs:
        command.extend(["--source", str(path)])
    command.extend(["--paper-type", args.paper_type, "--workdir", str(workdir)])
    parameters = {"paper_type": args.paper_type, "exam_type": args.exam_type, "year": args.year}
    outputs = [
        {"role": "parsed_exam canonical JSON", "path": str(output_dir / "final" / "parsed-exam.canonical.json")},
        {"role": "跨试卷去重报告", "path": str(output_dir / "final" / "parsed-exam.canonical.deduplication-report.json")},
    ]
    return "exam-paper-parser", parameters, command, outputs


def _plan_generate(args: argparse.Namespace, inputs: list[Path], constraints: Path | None, output_dir: Path) -> tuple[str, dict[str, Any], list[str], list[dict[str, str]]]:
    _require(len(inputs) == 1, "generate 必须且只能提供一个 parsed_exam canonical JSON。")
    document = _canonical_document(inputs[0])
    _require(document.get("document_type") == "parsed_exam", "generate 输入必须是 parsed_exam。")
    _require(constraints is not None, "generate 必须提供 --constraints。")
    _require(args.paper_type in {None, "aiPaper"}, "生成新题的 paper_type 固定为 aiPaper。")
    workdir = output_dir / "artifacts" / "generator-run"
    command = [
        "python",
        str(SUITE_ROOT / "exam-paper-generator" / "scripts" / "pipeline.py"),
        "prepare",
        "--input",
        str(inputs[0]),
        "--constraints",
        str(constraints),
        "--workdir",
        str(workdir),
    ]
    parameters = {"paper_type": "aiPaper", "constraints": constraints.name}
    outputs = [{"role": "generated_exam canonical JSON", "path": str(output_dir / "final" / "generated-exam.canonical.json")}]
    return "exam-paper-generator", parameters, command, outputs


def _plan_assemble(inputs: list[Path], constraints: Path | None, output_dir: Path) -> tuple[str, dict[str, Any], list[str], list[dict[str, str]]]:
    _require(len(inputs) == 1, "assemble-year 必须且只能提供一个年度 parsed_exam canonical JSON。")
    document = _canonical_document(inputs[0])
    _require(_looks_like_esat_legacy(document), "assemble-year 输入必须是同年 ENGAA+NSAA realPaper 年度题库。")
    command = [
        "python",
        str(SUITE_ROOT / "exam-paper-assembler" / "scripts" / "assemble.py"),
        "assemble-year",
        "--input",
        str(inputs[0]),
        "--output-dir",
        str(output_dir / "final"),
    ]
    if constraints is not None:
        command.extend(["--constraints", str(constraints)])
    parameters = {"paper_type": "realPaper", "combination_count": 6, "module_minutes": 40}
    outputs = [{"role": "six ESAT diagnostic paper JSON files", "path": str(output_dir / "final")}]
    return "exam-paper-assembler", parameters, command, outputs


def command_plan(args: argparse.Namespace) -> None:
    inputs = _resolved_files(args.input)
    features = _workflow_features()
    constraints = Path(args.constraints).resolve() if args.constraints else None
    if constraints is not None:
        _require(constraints.is_file(), f"约束文件不存在：{constraints}")
    operation = _resolve_operation(args.operation, inputs, constraints)
    _require_operation_enabled(operation, features)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if operation == "parse":
        child_skill, parameters, command, outputs = _plan_parse(args, inputs, output_dir)
    elif operation == "generate":
        child_skill, parameters, command, outputs = _plan_generate(args, inputs, constraints, output_dir)
    else:
        child_skill, parameters, command, outputs = _plan_assemble(inputs, constraints, output_dir)
    parameters["workflow_profile"] = features["profile"]

    records = [_input_record(path, "source") for path in inputs]
    if constraints is not None:
        records.append(_input_record(constraints, "constraints"))
    task_id = _task_id(records, operation, parameters)
    manifest = {
        "workflow_version": WORKFLOW_VERSION,
        "task_id": task_id,
        "operation": operation,
        "status": "planned",
        "child_skill": child_skill,
        "inputs": records,
        "parameters": parameters,
        "output_dir": str(output_dir),
        "expected_outputs": outputs,
        "next_action": {"skill": child_skill, "command": command},
        "execution": {
            "isolated_workdir": True,
            "subagent_mode": "use_when_runtime_supports_it",
            "parallelizable_unit": "question_transaction" if operation in {"parse", "generate"} else "paper_export",
        },
    }
    manifest_path = Path(args.manifest).resolve() if args.manifest else output_dir / "workflow-manifest.json"
    write_json_atomic(manifest_path, manifest)
    print(f"任务清单已创建：{manifest_path}")
    print(f"task_id：{task_id}")
    print(f"工作流配置：{features['profile']}")
    print(f"路由：{child_skill}")
    print("下一步命令：" + " ".join(json.dumps(part, ensure_ascii=False) for part in command))


def command_validate(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).resolve()
    manifest = read_json(manifest_path)
    required = {
        "workflow_version", "task_id", "operation", "status", "child_skill", "inputs",
        "parameters", "output_dir", "expected_outputs", "next_action", "execution",
    }
    _require(isinstance(manifest, dict) and set(manifest) == required, "任务清单字段不完整或包含未知字段。")
    _require(manifest["workflow_version"] == WORKFLOW_VERSION, "任务清单版本不受支持。")
    _require(manifest["operation"] in OPERATIONS, "任务操作不受支持。")
    _require(manifest["status"] == "planned", "当前仅校验 planned 任务清单。")
    features = _workflow_features()
    _require_operation_enabled(manifest["operation"], features)
    _require(manifest["parameters"].get("workflow_profile") == features["profile"], "任务清单的工作流配置已改变，请重新创建任务。")
    records = manifest["inputs"]
    _require(isinstance(records, list) and records, "任务清单必须包含输入记录。")
    for index, record in enumerate(records):
        _require(isinstance(record, dict) and set(record) == {"role", "path", "name", "sha256", "size"}, f"inputs[{index}] 结构非法。")
        path = Path(record["path"])
        _require(path.is_file(), f"输入文件已丢失：{path}")
        _require(path.name == record["name"], f"输入文件名改变：{path}")
        _require(path.stat().st_size == record["size"] and file_sha256(path) == record["sha256"], f"输入文件在计划后被修改：{path}")
    expected_id = _task_id(records, manifest["operation"], manifest["parameters"])
    _require(manifest["task_id"] == expected_id, "task_id 与输入或参数不一致。")
    _require(manifest["next_action"].get("skill") == manifest["child_skill"], "next_action 与 child_skill 不一致。")
    print(f"任务清单校验通过：{manifest_path}")


def command_preflight(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    features = _workflow_features()
    problems: list[str] = []
    for name in ("exam-paper-workflow", "exam-paper-parser", "exam-paper-generator", "exam-paper-assembler", "exam-paper-core"):
        problems.extend(scan_tree(root / name))
    if problems:
        print("套件预检失败：")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print(f"套件预检通过：{root}")
    print(f"工作流配置：{features['profile']}；操作开关：{features['operations']}")


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(description="英文试卷套件工作流路由")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="检查整个试卷 Skill 套件")
    preflight.add_argument("--root", default=str(SUITE_ROOT))
    preflight.set_defaults(handler=command_preflight)

    plan = subparsers.add_parser("plan", help="创建任务清单并选择子 Skill")
    plan.add_argument("--operation", choices=["auto", *sorted(OPERATIONS)], default="auto")
    plan.add_argument("--input", action="append", required=True, help="输入文件，可重复传入。")
    plan.add_argument("--constraints", help="生成或组卷约束 JSON。")
    plan.add_argument("--paper-type", choices=sorted(PAPER_TYPES), help="解析入口的试卷类型。")
    plan.add_argument("--exam-type", help="可选考试名称，例如 ESAT、ENGAA、NSAA、TMUA。")
    plan.add_argument("--year", help="可选考试年份。")
    plan.add_argument("--output-dir", required=True, help="隔离任务输出目录。")
    plan.add_argument("--manifest", help="任务清单路径，默认写入 output-dir。")
    plan.set_defaults(handler=command_plan)

    validate = subparsers.add_parser("validate", help="校验任务清单及输入未改变")
    validate.add_argument("--manifest", required=True)
    validate.set_defaults(handler=command_validate)
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
