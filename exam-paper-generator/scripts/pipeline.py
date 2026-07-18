#!/usr/bin/env python3
"""英文试卷生成 Skill 的可恢复流水线入口。"""

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


PIPELINE = "exam-paper-generator"
STAGES = [
    "input_validation",
    "generation_blueprints",
    "question_transactions",
    "novelty_review",
    "independent_review",
    "export",
]


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
    if not isinstance(constraints, dict):
        raise ContractError("约束文件必须是 JSON 对象。")
    question_count = constraints.get("question_count")
    if isinstance(question_count, bool) or not isinstance(question_count, int) or question_count <= 0:
        raise ContractError("constraints.question_count 必须是正整数。")
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
    document = build_document(
        draft,
        document_type="generated_exam",
        source_hash=state.input_hash,
        validation_status="passed",
    )
    expected_count = constraints["question_count"]
    if len(document["questions"]) != expected_count:
        raise ContractError(
            f"生成题目数不符：期望 {expected_count}，实际 {len(document['questions'])}。"
        )
    source_exam_type = source["metadata"]["exam_type"]
    if document["metadata"]["exam_type"] != source_exam_type:
        raise ContractError(
            "生成结果的 metadata.exam_type 必须与输入题库一致："
            f"{source_exam_type}。"
        )
    source_question_codes = {item["code"] for item in source["questions"]}
    unknown_references: list[str] = []
    for item in document["questions"]:
        source_question_id = item["source"]["source_question_id"]
        if source_question_id not in source_question_codes:
            unknown_references.append(f"{item['code']}→{source_question_id}")
    if unknown_references:
        raise ContractError(
            "生成题引用了输入题库中不存在的 code："
            + "、".join(unknown_references)
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
        args.handler(args)
        return 0
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
