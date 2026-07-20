#!/usr/bin/env python3
"""英文试卷生成 Skill 的可恢复流水线入口。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
SUITE_ROOT = Path(__file__).resolve().parents[2]
CORE_PYTHON = SUITE_ROOT / "exam-paper-core" / "python"
FEATURE_FLAGS_PATH = SUITE_ROOT / "exam-paper-workflow" / "workflow-features.json"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core import (  # noqa: E402
    ChineseArgumentParser,
    ContractError,
    PipelineState,
    build_document,
    calculate_source_hash,
    create_stage_receipt,
    read_json,
    scan_tree,
    validate_committed_transaction,
    validate_document,
    write_json_atomic,
)
from exam_paper_core.fingerprint import question_stem_fingerprint  # noqa: E402


PIPELINE = "exam-paper-generator"
STAGES = [
    "input_validation",
    "generation_blueprints",
    "question_transactions",
    "novelty_review",
    "independent_review",
    "export",
]
GENERATION_CONSTRAINT_FIELDS = {
    "question_count",
    "exam_type",
    "year",
    "title",
    "question_type_counts",
    "difficulty_counts",
    "module_counts",
    "primary_syllabus_codes",
    "exclude_source_question_ids",
}
QUESTION_TYPES = {"multiple_choice", "free_response"}
DIFFICULTIES = {"easy", "medium", "hard", "composite"}


def _require_generation_enabled() -> None:
    features = read_json(FEATURE_FLAGS_PATH)
    operations = features.get("operations") if isinstance(features, dict) else None
    enabled = isinstance(operations, dict) and operations.get("generate") is True
    profile = features.get("profile", "unknown") if isinstance(features, dict) else "unknown"
    if not enabled:
        raise ContractError(f"当前工作流配置 {profile} 已关闭生题；本轮只测试试卷解析与组卷。")


def _state_path(workdir: Path) -> Path:
    return workdir / "pipeline-state.json"


def _load_inputs(args: argparse.Namespace) -> tuple[dict, dict, str]:
    input_path = Path(args.input)
    constraints_path = Path(args.constraints)
    source = read_json(input_path)
    validate_document(source, expected_type="parsed_exam")
    if source["validation_status"] != "passed":
        raise ContractError("输入解析结果尚未通过质量校验。")
    constraints = read_json(constraints_path)
    _validate_generation_constraints(constraints)
    exam_type = constraints.get("exam_type")
    if exam_type is not None:
        if not isinstance(exam_type, str) or not exam_type.strip():
            raise ContractError("constraints.exam_type 必须是非空字符串。")
        source_exam_type = source["metadata"]["exam_type"]
        if exam_type != source_exam_type:
            raise ContractError(
                f"考试类型不一致：约束为 {exam_type}，输入题库为 {source_exam_type}。"
            )
    return source, constraints, calculate_source_hash([input_path, constraints_path])


def _validate_count_map(
    constraints: dict,
    field: str,
    *,
    question_count: int,
    allowed_keys: set[str] | None = None,
) -> None:
    if field not in constraints:
        return
    value = constraints[field]
    if not isinstance(value, dict) or not value:
        raise ContractError(f"constraints.{field} 必须是非空计数对象。")
    if not all(isinstance(key, str) and key.strip() for key in value):
        raise ContractError(f"constraints.{field} 的键必须是非空字符串。")
    if allowed_keys is not None and not set(value) <= allowed_keys:
        raise ContractError(
            f"constraints.{field} 包含不受支持的键：{sorted(set(value) - allowed_keys)}"
        )
    if not all(isinstance(count, int) and not isinstance(count, bool) and count > 0 for count in value.values()):
        raise ContractError(f"constraints.{field} 的计数必须是正整数。")
    if sum(value.values()) != question_count:
        raise ContractError(
            f"constraints.{field} 的计数总和必须等于 question_count={question_count}。"
        )


def _validate_unique_text_list(constraints: dict, field: str) -> None:
    if field not in constraints:
        return
    value = constraints[field]
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
        or len(value) != len(set(value))
    ):
        raise ContractError(f"constraints.{field} 必须是非空且不重复的字符串数组。")


def _validate_generation_constraints(constraints: object) -> None:
    if not isinstance(constraints, dict):
        raise ContractError("约束文件必须是 JSON 对象。")
    unknown = set(constraints) - GENERATION_CONSTRAINT_FIELDS
    if unknown:
        raise ContractError(f"约束文件包含未知字段：{sorted(unknown)}")
    question_count = constraints.get("question_count")
    if isinstance(question_count, bool) or not isinstance(question_count, int) or question_count <= 0:
        raise ContractError("constraints.question_count 必须是正整数。")
    for field in ("exam_type", "title"):
        if field in constraints and (
            not isinstance(constraints[field], str) or not constraints[field].strip()
        ):
            raise ContractError(f"constraints.{field} 必须是非空字符串。")
    if "year" in constraints and (
        isinstance(constraints["year"], bool)
        or not isinstance(constraints["year"], (str, int))
    ):
        raise ContractError("constraints.year 必须是字符串或整数年份。")
    _validate_count_map(
        constraints,
        "question_type_counts",
        question_count=question_count,
        allowed_keys=QUESTION_TYPES,
    )
    _validate_count_map(
        constraints,
        "difficulty_counts",
        question_count=question_count,
        allowed_keys=DIFFICULTIES,
    )
    _validate_count_map(
        constraints,
        "module_counts",
        question_count=question_count,
    )
    _validate_unique_text_list(constraints, "primary_syllabus_codes")
    _validate_unique_text_list(constraints, "exclude_source_question_ids")


def _primary_knowledge_code(question: dict) -> str:
    primary = [
        point["code"]
        for point in question["knowledge_points"]
        if point.get("is_primary") is True
    ]
    if len(primary) != 1:
        raise ContractError(f"{question.get('code', '未知题目')} 必须且只能有一个主知识点。")
    return primary[0]


def _validate_generated_output(source: dict, document: dict, constraints: dict) -> None:
    questions = document["questions"]
    source_by_code = {item["code"]: item for item in source["questions"]}
    excluded_sources = set(constraints.get("exclude_source_question_ids", []))
    unknown_exclusions = excluded_sources - set(source_by_code)
    if unknown_exclusions:
        raise ContractError(f"exclude_source_question_ids 包含不存在的母题：{sorted(unknown_exclusions)}")

    source_stems = {
        question_stem_fingerprint(item): item["code"] for item in source["questions"]
    }
    generated_stems: dict[str, str] = {}
    binding_errors: list[str] = []
    stem_collisions: list[str] = []
    for item in questions:
        source_info = item["source"]
        source_id = source_info["source_question_id"]
        source_question = source_by_code.get(source_id)
        if source_question is None:
            binding_errors.append(f"{item['code']} 引用了不存在的母题 {source_id}")
            continue
        if source_id in excluded_sources:
            binding_errors.append(f"{item['code']} 使用了被排除的母题 {source_id}")
        if source_info["source_fingerprint"] != source_question["fingerprint"]:
            binding_errors.append(f"{item['code']} 的母题 ID 与 source_fingerprint 不匹配")
        retained = source_info["generation_blueprint"]["retained_knowledge_point"]
        source_codes = {point["code"] for point in source_question["knowledge_points"]}
        generated_codes = {point["code"] for point in item["knowledge_points"]}
        if retained not in source_codes or retained not in generated_codes:
            binding_errors.append(f"{item['code']} 的 retained_knowledge_point 未同时存在于母题和新题")
        stem = question_stem_fingerprint(item)
        if stem in source_stems:
            stem_collisions.append(f"{item['code']} 与母题 {source_stems[stem]} 题干相同")
        if stem in generated_stems:
            stem_collisions.append(f"{item['code']} 与同批题 {generated_stems[stem]} 题干相同")
        generated_stems[stem] = item["code"]
    if binding_errors:
        raise ContractError("生成题母题绑定失败：" + "；".join(binding_errors))
    if stem_collisions:
        raise ContractError("生成题题干近重复：" + "；".join(stem_collisions))

    expected_count = constraints["question_count"]
    count_specs = {
        "question_type_counts": Counter(item["question_type"] for item in questions),
        "difficulty_counts": Counter(item["difficulty"] for item in questions),
        "module_counts": Counter(item["subject"] for item in questions),
    }
    for field, actual in count_specs.items():
        if field in constraints and dict(actual) != constraints[field]:
            raise ContractError(
                f"生成结果不满足 constraints.{field}：期望 {constraints[field]}，实际 {dict(actual)}。"
            )
    allowed_primary = set(constraints.get("primary_syllabus_codes", []))
    if allowed_primary:
        invalid = [
            item["code"]
            for item in questions
            if _primary_knowledge_code(item) not in allowed_primary
        ]
        if invalid:
            raise ContractError(f"生成题主知识点超出 primary_syllabus_codes：{invalid}")
    metadata = document["metadata"]
    if "year" in constraints and str(metadata["year"]) != str(constraints["year"]):
        raise ContractError("生成结果 metadata.year 不满足 constraints.year。")
    if "title" in constraints and metadata.get("title") != constraints["title"]:
        raise ContractError("生成结果 metadata.title 不满足 constraints.title。")
    if len(questions) != expected_count:
        raise ContractError(f"生成题目数不符：期望 {expected_count}，实际 {len(questions)}。")


def _open_state(args: argparse.Namespace) -> tuple[PipelineState, dict, dict]:
    source, constraints, input_hash = _load_inputs(args)
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    state = PipelineState.open_or_create(
        _state_path(workdir),
        pipeline=PIPELINE,
        input_hash=input_hash,
        stages=STAGES,
    )
    return state, source, constraints


def command_preflight(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    problems = scan_tree(root)
    if problems:
        print("预检失败：")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print(f"预检通过：{root}")


def command_prepare(args: argparse.Namespace) -> None:
    state, source, constraints = _open_state(args)
    if state.next_stage == "input_validation":
        receipt = create_stage_receipt(
            Path(args.workdir) / "receipts" / "input_validation.json",
            pipeline=PIPELINE,
            stage="input_validation",
            method=_fixed_method(
                "校验输入契约",
                "读取 parsed_exam 与生成约束，校验契约版本、考试类型、题目数量和约束一致性。",
                "输入题库和生成约束均已通过校验。",
            ),
            artifacts=[
                {"role": "已校验 parsed_exam 输入", "path": args.input},
                {"role": "已校验生成约束", "path": args.constraints},
            ],
        )
        state.complete("input_validation", receipt_path=receipt)
    print("生成任务已准备，输入契约校验通过。")
    print(f"输入题目数：{len(source['questions'])}")
    print(f"计划生成数：{constraints['question_count']}")
    print(f"下一阶段：{state.next_stage or '全部完成'}")


def command_status(args: argparse.Namespace) -> None:
    state, _, _ = _open_state(args)
    print(json.dumps(state.as_dict(), ensure_ascii=False, indent=2))


def command_complete(args: argparse.Namespace) -> None:
    state, _, _ = _open_state(args)
    receipt = create_stage_receipt(
        Path(args.workdir) / "receipts" / f"{args.stage}.json",
        pipeline=PIPELINE,
        stage=args.stage,
        method=_method_from_args(args),
        artifacts=[{"role": "阶段产物", "path": item} for item in args.artifact],
        transaction_receipts=args.transaction_receipt or (),
    )
    state.complete(args.stage, receipt_path=receipt)
    print(f"阶段已完成：{args.stage}")
    print(f"下一阶段：{state.next_stage or '全部完成'}")


def command_finalize(args: argparse.Namespace) -> None:
    state, source, constraints = _open_state(args)
    if state.next_stage != "export":
        raise ContractError(
            "尚不能导出；必须先依次完成 generation_blueprints、question_transactions、"
            "novelty_review、independent_review。"
        )
    draft = read_json(Path(args.draft))
    _validate_question_transactions(state, draft)
    metadata = draft.get("metadata")
    if not isinstance(metadata, dict):
        raise ContractError("生成草稿必须包含 metadata 对象。")
    if metadata.get("paper_type") not in {None, "aiPaper"}:
        raise ContractError("AI 生成试卷的 metadata.paper_type 必须是 aiPaper。")
    metadata["paper_type"] = "aiPaper"
    document = build_document(
        draft,
        document_type="generated_exam",
        source_hash=state.input_hash,
        validation_status="passed",
    )
    expected_count = constraints["question_count"]
    _validate_generated_output(source, document, constraints)
    source_exam_type = source["metadata"]["exam_type"]
    if document["metadata"]["exam_type"] != source_exam_type:
        raise ContractError(
            "生成结果的 metadata.exam_type 必须与输入题库一致："
            f"{source_exam_type}。"
        )
    source_fingerprints = {item["fingerprint"] for item in source["questions"]}
    collisions = [
        item["code"]
        for item in document["questions"]
        if item["fingerprint"] in source_fingerprints
    ]
    if collisions:
        raise ContractError("生成题与输入原题重复：" + "、".join(collisions))
    output = Path(args.output)
    write_json_atomic(output, document)
    receipt = create_stage_receipt(
        Path(args.workdir) / "receipts" / "export.json",
        pipeline=PIPELINE,
        stage="export",
        method=_fixed_method("封装导出", "用已提交逐题片段封装标准 generated_exam 文档并写入最终 JSON。", f"导出到 {output.resolve()}"),
        artifacts=[{"role": "最终 generated_exam JSON", "path": output}],
    )
    state.complete("export", receipt_path=receipt)
    print(f"生成结果已导出：{output.resolve()}")


def _method_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "objective": args.method_objective,
        "procedure": args.method_procedure,
        "decision_basis": args.method_decision_basis,
        "result": args.method_result,
        "exceptions": args.method_exceptions,
    }


def _fixed_method(objective: str, procedure: str, result: str) -> dict[str, str]:
    return {
        "objective": f"完成当前流水线阶段目标：{objective}",
        "procedure": procedure,
        "decision_basis": "依据已完成的阶段凭据、逐题事务凭据和标准数据契约进行处理。",
        "result": result,
        "exceptions": "无",
    }


def _validate_question_transactions(state: PipelineState, draft: dict) -> None:
    if not isinstance(draft, dict) or not isinstance(draft.get("questions"), list):
        raise ContractError("草稿必须包含 questions 数组。")
    try:
        stage_index = state.data["completed_stages"].index("question_transactions")
    except ValueError as exc:
        raise ContractError("缺少 question_transactions 阶段凭据。") from exc
    receipt = read_json(Path(state.data["receipts"][stage_index]))
    transaction_paths = receipt.get("transaction_receipts")
    if not isinstance(transaction_paths, list) or not transaction_paths:
        raise ContractError("question_transactions 阶段必须登记逐题事务凭据。")
    committed = [validate_committed_transaction(path) for path in transaction_paths]
    committed_ids = {item["question_id"] for item in committed}
    draft_ids = {item.get("code") or item.get("question_id") for item in draft["questions"]}
    if committed_ids != draft_ids:
        raise ContractError(
            "草稿题目与已提交逐题事务不一致："
            f"草稿={sorted(draft_ids)}，事务={sorted(committed_ids)}。"
        )


def add_task_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, help="已通过校验的 parsed_exam JSON。")
    parser.add_argument("--constraints", required=True, help="生成约束 JSON。")
    parser.add_argument("--workdir", required=True, help="任务工作目录。")


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(description="英文试卷生成流水线")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="只读检查 Skill 文件")
    preflight.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    preflight.set_defaults(handler=command_preflight)

    prepare = subparsers.add_parser("prepare", help="校验输入并初始化或恢复任务")
    add_task_arguments(prepare)
    prepare.set_defaults(handler=command_prepare)

    status = subparsers.add_parser("status", help="查看任务状态")
    add_task_arguments(status)
    status.set_defaults(handler=command_status)

    complete = subparsers.add_parser("complete", help="确认一个阶段完成")
    add_task_arguments(complete)
    complete.add_argument("--stage", required=True, choices=STAGES[1:-1])
    complete.add_argument("--artifact", action="append", required=True, help="本阶段真实产物，可重复传入。")
    complete.add_argument("--transaction-receipt", action="append", help="逐题事务 JSON，可重复传入。")
    complete.add_argument("--method-objective", required=True, help="本阶段目标。")
    complete.add_argument("--method-procedure", required=True, help="实际执行过程。")
    complete.add_argument("--method-decision-basis", required=True, help="判断依据。")
    complete.add_argument("--method-result", required=True, help="阶段结果。")
    complete.add_argument("--method-exceptions", default="无", help="例外与遗留问题；没有则填“无”。")
    complete.set_defaults(handler=command_complete)

    finalize = subparsers.add_parser("finalize", help="校验并原子导出最终 JSON")
    add_task_arguments(finalize)
    finalize.add_argument("--draft", required=True, help="待封装的生成草稿 JSON。")
    finalize.add_argument("--output", required=True, help="最终 JSON 输出路径。")
    finalize.set_defaults(handler=command_finalize)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command != "preflight":
            _require_generation_enabled()
        args.handler(args)
        return 0
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
