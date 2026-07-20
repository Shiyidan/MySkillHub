#!/usr/bin/env python3
"""Operate parser/generator per-question transactions from the command line."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core import (  # noqa: E402
    ChineseArgumentParser,
    ContractError,
    QuestionTransaction,
    question_fingerprint,
    read_json,
    validate_committed_transaction,
    validate_question_fragment,
    write_json_atomic,
)
from exam_paper_core.production import GENERATOR_STEP_SPECS, PARSER_STEP_SPECS  # noqa: E402


def _load(path: str) -> QuestionTransaction:
    transaction_path = Path(path).resolve()
    data = read_json(transaction_path)
    transaction = QuestionTransaction(transaction_path, data)
    transaction.validate()
    return transaction


def _evidence(values: list[str] | None) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for value in values or []:
        if "=" not in value:
            raise ValueError("证据参数格式必须是 角色=文件路径。")
        role, path = value.split("=", 1)
        if not role.strip() or not path.strip():
            raise ValueError("证据角色和文件路径都不能为空。")
        result.append({"role": role.strip(), "path": path.strip()})
    return result


def _method(args: argparse.Namespace) -> dict[str, str]:
    return {
        "objective": args.method_objective,
        "procedure": args.method_procedure,
        "decision_basis": args.method_decision_basis,
        "result": args.method_result,
        "exceptions": args.method_exceptions,
    }


def _next_step_payload(transaction: QuestionTransaction) -> dict[str, object] | None:
    next_step = transaction.next_step
    if next_step is None:
        return None
    specs = PARSER_STEP_SPECS if transaction.data["mode"] == "parser" else GENERATOR_STEP_SPECS
    spec = next(item for item in specs if item.name == next_step)
    return {
        "name": spec.name,
        "purpose": spec.purpose,
        "required_output_roles": list(spec.output_roles),
    }


def command_init(args: argparse.Namespace) -> None:
    transaction = QuestionTransaction.open_or_create(
        args.transaction,
        mode=args.mode,
        question_id=args.question_id,
        source_fingerprint=args.source_fingerprint,
    )
    print(json.dumps({"transaction": str(transaction.path), "next_step": _next_step_payload(transaction)}, ensure_ascii=False, indent=2))


def command_status(args: argparse.Namespace) -> None:
    transaction = _load(args.transaction)
    print(
        json.dumps(
            {
                "transaction": str(transaction.path),
                "question_id": transaction.data["question_id"],
                "mode": transaction.data["mode"],
                "status": transaction.data["status"],
                "completed_steps": transaction.completed_steps,
                "next_step": _next_step_payload(transaction),
                "rollback_history": transaction.data["rollback_history"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_complete(args: argparse.Namespace) -> None:
    transaction = _load(args.transaction)
    transaction.complete_step(
        args.step,
        method=_method(args),
        input_evidence=_evidence(args.input_evidence),
        output_evidence=_evidence(args.output_evidence),
        question_artifact=args.question_artifact,
    )
    print(f"逐题步骤已完成：{args.step}")
    print(json.dumps({"status": transaction.data["status"], "next_step": _next_step_payload(transaction)}, ensure_ascii=False, indent=2))


def command_rollback(args: argparse.Namespace) -> None:
    transaction = _load(args.transaction)
    transaction.rollback_to(args.step, reason=args.reason)
    print(f"逐题事务已回退到：{args.step}")
    print(json.dumps({"status": transaction.data["status"], "next_step": _next_step_payload(transaction)}, ensure_ascii=False, indent=2))


def command_prepare_fragment(args: argparse.Namespace) -> None:
    raw = read_json(Path(args.input))
    if not isinstance(raw, dict):
        raise ContractError("单题草稿根节点必须是对象。")
    fragment = copy.deepcopy(raw)
    fragment["fingerprint"] = question_fingerprint(fragment)
    document_type = "parsed_exam" if args.mode == "parser" else "generated_exam"
    validate_question_fragment(fragment, document_type=document_type)
    write_json_atomic(Path(args.output), fragment)
    print(f"已生成可提交单题片段：{Path(args.output).resolve()}")


def command_validate(args: argparse.Namespace) -> None:
    data = validate_committed_transaction(args.transaction)
    print(f"逐题事务校验通过：{data['question_id']}")


def _add_method_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--method-objective", required=True)
    parser.add_argument("--method-procedure", required=True)
    parser.add_argument("--method-decision-basis", required=True)
    parser.add_argument("--method-result", required=True)
    parser.add_argument("--method-exceptions", default="无")


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(description="逐题生产事务工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser("init", help="创建或恢复逐题事务")
    initialize.add_argument("--transaction", required=True)
    initialize.add_argument("--mode", choices=["parser", "generator"], required=True)
    initialize.add_argument("--question-id", required=True)
    initialize.add_argument("--source-fingerprint", required=True, help="证据包或唯一母题的 SHA-256。")
    initialize.set_defaults(handler=command_init)

    status = subparsers.add_parser("status", help="查看下一步骤和必要输出角色")
    status.add_argument("--transaction", required=True)
    status.set_defaults(handler=command_status)

    complete = subparsers.add_parser("complete", help="完成当前逐题步骤")
    complete.add_argument("--transaction", required=True)
    complete.add_argument("--step", required=True)
    complete.add_argument("--input-evidence", action="append", required=True, help="角色=文件路径，可重复传入。")
    complete.add_argument("--output-evidence", action="append", required=True, help="角色=文件路径，可重复传入。")
    complete.add_argument("--question-artifact", help="仅原子提交步骤传入已校验的单题 JSON。")
    _add_method_arguments(complete)
    complete.set_defaults(handler=command_complete)

    rollback = subparsers.add_parser("rollback", help="使某步骤及其后续记录失效")
    rollback.add_argument("--transaction", required=True)
    rollback.add_argument("--step", required=True)
    rollback.add_argument("--reason", required=True)
    rollback.set_defaults(handler=command_rollback)

    prepare = subparsers.add_parser("prepare-fragment", help="计算指纹并校验可提交单题片段")
    prepare.add_argument("--mode", choices=["parser", "generator"], required=True)
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--output", required=True)
    prepare.set_defaults(handler=command_prepare_fragment)

    validate = subparsers.add_parser("validate", help="校验事务已经原子提交")
    validate.add_argument("--transaction", required=True)
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
