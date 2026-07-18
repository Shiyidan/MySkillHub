#!/usr/bin/env python3
"""英文试卷解析 Skill 的可恢复流水线入口。"""

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
    write_json_atomic,
)


PIPELINE = "exam-paper-parser"
STAGES = [
    "source_inventory",
    "source_inspection",
    "evidence_packets",
    "question_transactions",
    "independent_review",
    "export",
]


def _state_path(workdir: Path) -> Path:
    return workdir / "pipeline-state.json"


def _source_hash(source_paths: list[str]) -> str:
    if not source_paths:
        raise ContractError("至少需要一个 --source 输入文件。")
    return calculate_source_hash([Path(item) for item in source_paths])


def _open_state(args: argparse.Namespace) -> PipelineState:
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    return PipelineState.open_or_create(
        _state_path(workdir),
        pipeline=PIPELINE,
        input_hash=_source_hash(args.source),
        stages=STAGES,
    )


def command_preflight(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve()
    problems = scan_tree(root)
    if problems:
        print("预检失败：")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print(f"预检通过：{root}")


def command_init(args: argparse.Namespace) -> None:
    state = _open_state(args)
    print("解析任务已初始化。")
    print(json.dumps(state.as_dict(), ensure_ascii=False, indent=2))


def command_status(args: argparse.Namespace) -> None:
    state = _open_state(args)
    print(json.dumps(state.as_dict(), ensure_ascii=False, indent=2))


def command_complete(args: argparse.Namespace) -> None:
    state = _open_state(args)
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
    state = _open_state(args)
    if state.next_stage != "export":
        raise ContractError(
            "尚不能导出；必须先依次完成 source_inventory、source_inspection、"
            "evidence_packets、question_transactions、independent_review。"
        )
    draft = read_json(Path(args.draft))
    _validate_question_transactions(state, draft)
    document = build_document(
        draft,
        document_type="parsed_exam",
        source_hash=state.input_hash,
        validation_status="passed",
    )
    output = Path(args.output)
    write_json_atomic(output, document)
    receipt = create_stage_receipt(
        Path(args.workdir) / "receipts" / "export.json",
        pipeline=PIPELINE,
        stage="export",
        method=_fixed_method("封装导出", "用已提交逐题片段封装标准 parsed_exam 文档并写入最终 JSON。", f"导出到 {output.resolve()}"),
        artifacts=[{"role": "最终 parsed_exam JSON", "path": output}],
    )
    state.complete("export", receipt_path=receipt)
    print(f"解析结果已导出：{output.resolve()}")


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
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        help="源文件路径；题卷、答卷、评分方案等可重复传入。",
    )
    parser.add_argument("--workdir", required=True, help="任务工作目录。")


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(description="英文试卷解析流水线")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="只读检查 Skill 文件")
    preflight.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    preflight.set_defaults(handler=command_preflight)

    initialize = subparsers.add_parser("init", help="初始化或恢复解析任务")
    add_task_arguments(initialize)
    initialize.set_defaults(handler=command_init)

    status = subparsers.add_parser("status", help="查看任务状态")
    add_task_arguments(status)
    status.set_defaults(handler=command_status)

    complete = subparsers.add_parser("complete", help="确认一个阶段完成")
    add_task_arguments(complete)
    complete.add_argument("--stage", required=True, choices=STAGES[:-1])
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
    finalize.add_argument("--draft", required=True, help="待封装的草稿 JSON。")
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
