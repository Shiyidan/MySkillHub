"""逐题生产事务：把质量设计进过程，质量门只做兜底拦截。"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .contract import validate_question_fragment


TRANSACTION_VERSION = "4"


@dataclass(frozen=True)
class StepSpec:
    name: str
    purpose: str
    output_roles: tuple[str, ...]


PARSER_STEP_SPECS = (
    StepSpec("证据充分性确认", "确认题面、选项、图形、官方答案/解析来源足以支持本题闭环。", ("证据充分性报告",)),
    StepSpec("题面结构恢复", "从原始证据恢复英文题面、选项、公式、图形引用和版面关系。", ("题面结构草稿",)),
    StepSpec("考纲映射", "按考试考纲定位学科、主题、知识点和是否属于目标考试范围。", ("考纲映射记录",)),
    StepSpec("独立求解", "在对齐官方答案前独立求解，形成可审计的推理结果。", ("独立求解记录",)),
    StepSpec("官方答案对齐", "将独立求解结果与官方答案/评分方案比对，只处理证据支持的差异。", ("答案对齐记录",)),
    StepSpec("解题轨迹构建", "把可复核推理整理为 solution_trace，逐步服务中文解析。", ("解题轨迹",)),
    StepSpec("学习分析构建", "基于本题推理和干扰项生成中文学习分析，不使用泛化模板。", ("学习分析",)),
    StepSpec("图形复原", "恢复或确认图形资产、bbox、语义和 alt 文本。", ("图形复原记录",)),
    StepSpec("题内微验证", "在单题范围内校验字段、答案、解析、图形和来源一致性。", ("单题微验证报告",)),
    StepSpec("原子提交", "提交通过本题闭环的最终 JSON 片段并锁定。", ("最终题目片段",)),
)

GENERATOR_STEP_SPECS = (
    StepSpec("唯一母题锁定", "只选定一个已验证母题，锁定来源指纹和可继承知识点。", ("母题锁定记录",)),
    StepSpec("生成蓝图", "先完成母题解剖、结构改造、图形方案、难度重估和新颖性目标。", ("生成蓝图",)),
    StepSpec("图形信息设计", "先区分题面已知、视觉已知和必须由考生推出的隐藏关系，防止图形泄露关键推理。", ("图形信息披露记录",)),
    StepSpec("推理结构重构", "生成新题时改变核心推理路径、条件组织和干扰项逻辑，避免只替换数值或语境。", ("推理结构重构记录",)),
    StepSpec("独立求解", "先解新题并确认唯一答案，再进入干扰项与解析设计。", ("独立求解记录",)),
    StepSpec("干扰项设计", "为每个错误选项设计来自本题的具体错误原因。", ("干扰项设计记录",)),
    StepSpec("解题轨迹构建", "把新题求解过程整理为 solution_trace。", ("解题轨迹",)),
    StepSpec("学习分析构建", "基于新题推理和干扰项生成中文学习分析。", ("学习分析",)),
    StepSpec("SVG排版与渲染", "根据布局计划生成正式考试风格的可编辑 SVG，渲染预览并在提交前修正裁切、碰撞、比例误导和信息泄露。", ("SVG排版与渲染记录",)),
    StepSpec("精确溯源", "记录唯一母题、来源指纹和生成蓝图，不做多母题拼接。", ("精确溯源记录",)),
    StepSpec("新颖性核验", "核验新题不是原题复写、数值替换、题干复写、图形复刻、难度照抄或近重复。", ("新颖性核验报告",)),
    StepSpec("题内微验证", "在单题范围内校验字段、答案、解析、图形、溯源和新颖性。", ("单题微验证报告",)),
    StepSpec("原子提交", "提交通过本题闭环的最终 JSON 片段并锁定。", ("最终题目片段",)),
)

PARSER_STEPS = tuple(spec.name for spec in PARSER_STEP_SPECS)
GENERATOR_STEPS = tuple(spec.name for spec in GENERATOR_STEP_SPECS)


def file_sha256(path: str | os.PathLike[str]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _step_specs(mode: str) -> tuple[StepSpec, ...]:
    if mode == "parser":
        return PARSER_STEP_SPECS
    if mode == "generator":
        return GENERATOR_STEP_SPECS
    raise ValueError(f"未知生产模式：{mode}")


def _required_steps(mode: str) -> tuple[str, ...]:
    return tuple(spec.name for spec in _step_specs(mode))


def _spec_for(mode: str, step: str) -> StepSpec:
    for spec in _step_specs(mode):
        if spec.name == step:
            return spec
    raise ValueError(f"未知步骤：{step}")


def _evidence_record(item: dict[str, Any] | str | os.PathLike[str]) -> dict[str, Any]:
    if isinstance(item, (str, os.PathLike)):
        role = "未标注证据"
        path = item
    elif isinstance(item, dict):
        if set(item) != {"role", "path"}:
            raise ValueError("证据项必须且只能包含 role、path。")
        role = item["role"]
        path = item["path"]
    else:
        raise ValueError("证据项必须是路径或 {role, path} 对象。")

    if not isinstance(role, str) or not role.strip():
        raise ValueError("证据 role 不能为空。")
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"过程证据不存在：{resolved}")
    return {
        "role": role.strip(),
        "path": str(resolved),
        "sha256": file_sha256(resolved),
        "size": resolved.stat().st_size,
    }


def _validate_evidence_record(record: Any, label: str) -> None:
    if not isinstance(record, dict) or set(record) != {"role", "path", "sha256", "size"}:
        raise ValueError(f"{label}必须且只能包含 role、path、sha256、size。")
    if not isinstance(record["role"], str) or not record["role"].strip():
        raise ValueError(f"{label}.role 不能为空。")
    path = Path(record["path"])
    if not path.is_file():
        raise ValueError(f"{label}文件已丢失：{path}")
    if not isinstance(record["size"], int) or record["size"] < 0:
        raise ValueError(f"{label}.size 非法。")
    current_size = path.stat().st_size
    current_hash = file_sha256(path)
    if current_size != record["size"] or current_hash != record["sha256"]:
        raise ValueError(f"{label}在通过后被修改；必须使本题事务失效并重新执行。")


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
        text = value[field]
        if not isinstance(text, str) or len(text.strip()) < minimum:
            raise ValueError(f"{label}.{field}内容不足，不能支撑过程复演。")


def _hashes(records: Iterable[dict[str, Any]]) -> set[str]:
    return {record["sha256"] for record in records}


@dataclass
class QuestionTransaction:
    """单题闭环事务。

    每一步都必须有结构化方法、输入证据和输出产物。后续步骤必须引用前一步输出，
    以保证质量来自生产过程本身，而不是最终质量门临时补救。
    """

    path: Path
    data: dict[str, Any]

    @classmethod
    def open_or_create(
        cls,
        path: str | os.PathLike[str],
        *,
        mode: str,
        question_id: str,
        source_fingerprint: str,
    ) -> "QuestionTransaction":
        transaction_path = Path(path).resolve()
        required_steps = list(_required_steps(mode))
        if transaction_path.exists():
            data = json.loads(transaction_path.read_text(encoding="utf-8"))
            if data.get("transaction_version") != TRANSACTION_VERSION:
                raise ValueError("逐题事务版本不受支持，必须重新建立事务。")
            expected = {
                "mode": mode,
                "question_id": question_id,
                "source_fingerprint": source_fingerprint,
                "required_steps": required_steps,
            }
            for key, value in expected.items():
                if data.get(key) != value:
                    raise ValueError(f"逐题事务身份不一致：{key}")
        else:
            data = {
                "transaction_version": TRANSACTION_VERSION,
                "mode": mode,
                "question_id": question_id,
                "source_fingerprint": source_fingerprint,
                "required_steps": required_steps,
                "completed_steps": [],
                "records": [],
                "status": "进行中",
                "final_artifact": None,
            }
            _write_json_atomic(transaction_path, data)

        instance = cls(transaction_path, data)
        instance.validate()
        return instance

    @property
    def required_steps(self) -> list[str]:
        return list(self.data["required_steps"])

    @property
    def completed_steps(self) -> list[str]:
        return list(self.data["completed_steps"])

    @property
    def next_step(self) -> str | None:
        completed_count = len(self.completed_steps)
        if completed_count == len(self.required_steps):
            return None
        return self.required_steps[completed_count]

    def validate(self) -> None:
        if self.data.get("transaction_version") != TRANSACTION_VERSION:
            raise ValueError("逐题事务版本必须为 3。")
        mode = self.data.get("mode")
        required = self.data.get("required_steps")
        if required != list(_required_steps(mode)):
            raise ValueError("逐题事务步骤表被篡改。")
        completed = self.data.get("completed_steps")
        records = self.data.get("records")
        if not isinstance(completed, list) or not isinstance(records, list):
            raise ValueError("逐题事务步骤记录格式非法。")
        if completed != required[: len(completed)]:
            raise ValueError("逐题事务存在跳步或乱序。")
        if len(records) != len(completed):
            raise ValueError("逐题事务步骤与凭据数量不一致。")

        previous_output_hashes: set[str] = set()
        for index, record in enumerate(records):
            step = completed[index]
            if not isinstance(record, dict) or set(record) != {
                "step",
                "purpose",
                "method",
                "inputs",
                "outputs",
            }:
                raise ValueError(f"步骤“{step}”的过程凭据结构非法。")
            if record["step"] != step:
                raise ValueError(f"步骤“{step}”的过程凭据错位。")
            spec = _spec_for(mode, step)
            if record["purpose"] != spec.purpose:
                raise ValueError(f"步骤“{step}”的目的说明被篡改。")
            _validate_method(record["method"], f"步骤“{step}”的方法记录")

            inputs = record["inputs"]
            outputs = record["outputs"]
            if not isinstance(inputs, list) or not inputs:
                raise ValueError(f"步骤“{step}”没有输入证据。")
            if not isinstance(outputs, list) or not outputs:
                raise ValueError(f"步骤“{step}”没有输出产物。")
            for evidence_index, item in enumerate(inputs):
                _validate_evidence_record(item, f"步骤“{step}”输入[{evidence_index}]")
            for evidence_index, item in enumerate(outputs):
                _validate_evidence_record(item, f"步骤“{step}”输出[{evidence_index}]")

            output_roles = {item["role"] for item in outputs}
            missing_roles = set(spec.output_roles) - output_roles
            if missing_roles:
                raise ValueError(f"步骤“{step}”缺少必要输出：{sorted(missing_roles)}")
            if index > 0 and not (_hashes(inputs) & previous_output_hashes):
                raise ValueError(f"步骤“{step}”没有引用上一步输出，过程链断裂。")
            previous_output_hashes = _hashes(outputs)

        committed = len(completed) == len(required)
        if committed:
            if self.data.get("status") != "已提交":
                raise ValueError("所有步骤完成后，事务状态必须为已提交。")
            artifact = self.data.get("final_artifact")
            _validate_evidence_record(artifact, "最终题目片段")
            document_type = "parsed_exam" if mode == "parser" else "generated_exam"
            artifact_data = json.loads(Path(artifact["path"]).read_text(encoding="utf-8"))
            validate_question_fragment(artifact_data, document_type=document_type)
        else:
            if self.data.get("status") != "进行中":
                raise ValueError("未完成事务状态必须为进行中。")
            if self.data.get("final_artifact") is not None:
                raise ValueError("未完成原子提交前不得登记最终题目片段。")

    def complete_step(
        self,
        step: str,
        *,
        method: dict[str, str],
        input_evidence: Iterable[dict[str, Any] | str | os.PathLike[str]],
        output_evidence: Iterable[dict[str, Any] | str | os.PathLike[str]],
        question_artifact: str | os.PathLike[str] | None = None,
    ) -> None:
        """完成一个步骤；任何一步都不能无方法、无输入、无输出或越序完成。"""

        self.validate()
        expected = self.next_step
        if expected is None:
            raise ValueError("本题已经原子提交，不得继续修改。")
        if step != expected:
            raise ValueError(f"不得跳步：当前必须执行“{expected}”，不能执行“{step}”。")
        _validate_method(method, f"步骤“{step}”的方法记录")
        inputs = [_evidence_record(item) for item in input_evidence]
        outputs = [_evidence_record(item) for item in output_evidence]
        if not inputs:
            raise ValueError(f"步骤“{step}”必须提供至少一个输入证据。")
        if not outputs:
            raise ValueError(f"步骤“{step}”必须提供至少一个输出产物。")

        spec = _spec_for(self.data["mode"], step)
        output_roles = {item["role"] for item in outputs}
        missing_roles = set(spec.output_roles) - output_roles
        if missing_roles:
            raise ValueError(f"步骤“{step}”缺少必要输出：{sorted(missing_roles)}")

        is_final_step = step == self.required_steps[-1]
        if is_final_step and question_artifact is None:
            raise ValueError("原子提交步骤必须提供最终单题 JSON 片段。")
        if not is_final_step and question_artifact is not None:
            raise ValueError("只有原子提交步骤可以登记最终题目片段。")

        if self.data["records"]:
            previous_outputs = self.data["records"][-1]["outputs"]
            if not (_hashes(inputs) & _hashes(previous_outputs)):
                raise ValueError(f"步骤“{step}”必须引用上一步输出作为输入。")

        self.data["completed_steps"].append(step)
        self.data["records"].append(
            {
                "step": step,
                "purpose": spec.purpose,
                "method": {key: method[key].strip() for key in method},
                "inputs": inputs,
                "outputs": outputs,
            }
        )
        if is_final_step:
            artifact = _evidence_record({"role": "最终题目片段", "path": question_artifact})
            artifact_data = json.loads(Path(artifact["path"]).read_text(encoding="utf-8"))
            artifact_id = artifact_data.get("code") or artifact_data.get("question_id")
            if artifact_id != self.data["question_id"]:
                raise ValueError("最终题目片段的题目标识与逐题事务不一致。")
            document_type = "parsed_exam" if self.data["mode"] == "parser" else "generated_exam"
            validate_question_fragment(artifact_data, document_type=document_type)
            self.data["final_artifact"] = artifact
            self.data["status"] = "已提交"

        _write_json_atomic(self.path, self.data)
        self.validate()


def validate_committed_transaction(path: str | os.PathLike[str]) -> dict[str, Any]:
    transaction_path = Path(path).resolve()
    data = json.loads(transaction_path.read_text(encoding="utf-8"))
    transaction = QuestionTransaction(transaction_path, data)
    transaction.validate()
    if transaction.data["status"] != "已提交":
        raise ValueError(f"逐题事务尚未提交：{transaction_path}")
    return transaction.data
