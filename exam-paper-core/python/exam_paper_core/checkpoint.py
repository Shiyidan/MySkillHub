"""带可验证阶段凭据的流水线检查点。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from .production import file_sha256


RECEIPT_VERSION = "3"
STATE_VERSION = "4"


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _artifact_record(item: dict[str, Any] | str | os.PathLike[str]) -> dict[str, Any]:
    if isinstance(item, (str, os.PathLike)):
        role = "阶段产物"
        path = item
    elif isinstance(item, dict):
        if set(item) != {"role", "path"}:
            raise ValueError("阶段产物必须且只能包含 role、path。")
        role = item["role"]
        path = item["path"]
    else:
        raise ValueError("阶段产物必须是路径或 {role, path} 对象。")
    if not isinstance(role, str) or not role.strip():
        raise ValueError("阶段产物 role 不能为空。")
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"阶段产物不存在：{resolved}")
    return {
        "role": role.strip(),
        "path": str(resolved),
        "sha256": file_sha256(resolved),
        "size": resolved.stat().st_size,
    }


def _validate_method(value: Any, label: str) -> None:
    required = {"objective", "procedure", "decision_basis", "result", "exceptions"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{label}必须且只能包含 objective、procedure、decision_basis、result、exceptions。")
    minimums = {
        "objective": 12,
        "procedure": 30,
        "decision_basis": 20,
        "result": 12,
        "exceptions": 1,
    }
    for field, minimum in minimums.items():
        if not isinstance(value[field], str) or len(value[field].strip()) < minimum:
            raise ValueError(f"{label}.{field}内容不足，不能支撑阶段复演。")


def _validate_artifact(record: Any, label: str) -> None:
    if not isinstance(record, dict) or set(record) != {"role", "path", "sha256", "size"}:
        raise ValueError(f"{label}结构非法。")
    path = Path(record["path"])
    if not path.is_file():
        raise ValueError(f"{label}已丢失：{path}")
    if path.stat().st_size != record["size"] or file_sha256(path) != record["sha256"]:
        raise ValueError(f"{label}在通过后被修改：{path}")


def create_stage_receipt(
    path: str | os.PathLike[str],
    *,
    pipeline: str,
    stage: str,
    method: dict[str, str],
    artifacts: Iterable[dict[str, Any] | str | os.PathLike[str]],
    transaction_receipts: Iterable[str | os.PathLike[str]] = (),
) -> Path:
    """由实际产物生成阶段凭据，不能凭空把阶段标成完成。"""

    _validate_method(method, "阶段方法记录")
    records = [_artifact_record(item) for item in artifacts]
    if not records:
        raise ValueError("阶段凭据至少登记一个可复验产物。")
    transaction_paths = [str(Path(item).resolve()) for item in transaction_receipts]
    receipt_path = Path(path).resolve()
    _write_json_atomic(
        receipt_path,
        {
            "receipt_version": RECEIPT_VERSION,
            "pipeline": pipeline,
            "stage": stage,
            "status": "通过",
            "method": {key: method[key].strip() for key in method},
            "artifacts": records,
            "transaction_receipts": transaction_paths,
        },
    )
    return receipt_path


def validate_stage_receipt(
    path: str | os.PathLike[str], *, pipeline: str, stage: str
) -> dict[str, Any]:
    receipt_path = Path(path).resolve()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if set(receipt) != {
        "receipt_version",
        "pipeline",
        "stage",
        "status",
        "method",
        "artifacts",
        "transaction_receipts",
    }:
        raise ValueError(f"阶段凭据结构非法：{receipt_path}")
    if receipt["receipt_version"] != RECEIPT_VERSION:
        raise ValueError("阶段凭据版本不受支持。")
    if receipt["pipeline"] != pipeline or receipt["stage"] != stage:
        raise ValueError("阶段凭据与当前流水线/阶段不匹配。")
    if receipt["status"] != "通过":
        raise ValueError("只有已通过的阶段凭据才能推进流水线。")
    _validate_method(receipt["method"], "阶段方法记录")
    artifacts = receipt["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("阶段凭据缺少可复验产物。")
    for index, artifact in enumerate(artifacts):
        _validate_artifact(artifact, f"阶段产物[{index}]")
    if not isinstance(receipt["transaction_receipts"], list):
        raise ValueError("transaction_receipts 必须是数组。")
    return receipt


class PipelineCheckpoint:
    def __init__(self, path: Path, data: dict[str, Any]):
        self.path = path
        self.data = data

    @classmethod
    def open_or_create(
        cls,
        path: str | os.PathLike[str],
        *,
        pipeline: str,
        input_hash: str,
        stages: Iterable[str],
        parameters: dict[str, Any] | None = None,
    ) -> "PipelineCheckpoint":
        checkpoint_path = Path(path).resolve()
        stage_list = list(stages)
        parameter_values = parameters or {}
        if not stage_list or len(stage_list) != len(set(stage_list)):
            raise ValueError("流水线阶段必须非空且不得重复。")
        if not isinstance(parameter_values, dict):
            raise ValueError("流水线参数必须是对象。")
        try:
            parameter_values = json.loads(
                json.dumps(parameter_values, ensure_ascii=False, sort_keys=True)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("流水线参数必须可以序列化为 JSON。") from exc
        if checkpoint_path.exists():
            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if data.get("state_version") != STATE_VERSION:
                raise ValueError("流水线检查点版本不受支持，必须重新建立。")
            for key, expected in {
                "pipeline": pipeline,
                "input_hash": input_hash,
                "stages": stage_list,
                "parameters": parameter_values,
            }.items():
                if data.get(key) != expected:
                    raise ValueError(f"流水线检查点身份不一致：{key}")
        else:
            data = {
                "state_version": STATE_VERSION,
                "pipeline": pipeline,
                "input_hash": input_hash,
                "stages": stage_list,
                "parameters": parameter_values,
                "completed_stages": [],
                "receipts": [],
                "status": "进行中",
            }
            _write_json_atomic(checkpoint_path, data)
        checkpoint = cls(checkpoint_path, data)
        checkpoint.validate()
        return checkpoint

    @property
    def input_hash(self) -> str:
        return self.data["input_hash"]

    @property
    def next_stage(self) -> str | None:
        count = len(self.data["completed_stages"])
        return None if count == len(self.data["stages"]) else self.data["stages"][count]

    def as_dict(self) -> dict[str, Any]:
        return dict(self.data)

    def validate(self) -> None:
        if self.data.get("state_version") != STATE_VERSION:
            raise ValueError("流水线检查点版本必须为 4。")
        if not isinstance(self.data.get("parameters"), dict):
            raise ValueError("流水线检查点 parameters 必须是对象。")
        stages = self.data.get("stages")
        completed = self.data.get("completed_stages")
        receipts = self.data.get("receipts")
        if not isinstance(stages, list) or not stages:
            raise ValueError("流水线阶段表非法。")
        if not isinstance(completed, list) or completed != stages[: len(completed)]:
            raise ValueError("流水线存在跳步或乱序。")
        if not isinstance(receipts, list) or len(receipts) != len(completed):
            raise ValueError("流水线阶段与凭据数量不一致。")
        for index, receipt_path in enumerate(receipts):
            validate_stage_receipt(
                receipt_path,
                pipeline=self.data["pipeline"],
                stage=completed[index],
            )
        finished = len(completed) == len(stages)
        expected_status = "已完成" if finished else "进行中"
        if self.data.get("status") != expected_status:
            raise ValueError("流水线状态与已完成阶段不一致。")

    def complete(self, stage: str, *, receipt_path: str | os.PathLike[str]) -> None:
        self.validate()
        expected = self.next_stage
        if expected is None:
            raise ValueError("流水线已经完成。")
        if stage != expected:
            raise ValueError(f"不得跳步：当前必须完成“{expected}”。")
        validate_stage_receipt(receipt_path, pipeline=self.data["pipeline"], stage=stage)
        self.data["completed_stages"].append(stage)
        self.data["receipts"].append(str(Path(receipt_path).resolve()))
        if self.next_stage is None:
            self.data["status"] = "已完成"
        _write_json_atomic(self.path, self.data)
        self.validate()


PipelineState = PipelineCheckpoint
