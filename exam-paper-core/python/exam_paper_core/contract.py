"""试卷解析与生成共用的严格生产契约。

本模块只验证“过程已经正确执行后应当自然产生的结果”。它不补写质量字段，
也不把缺失内容自动修成可通过状态；低质量草稿必须回到对应生产步骤局部返工。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import copy
from pathlib import Path
from typing import Any, Iterable

from .esat_syllabus import esat_root, module_descriptor, syllabus_item, syllabus_items_for_codes
from .fingerprint import question_fingerprint
from .syllabus_index import syllabus_item_for_exam, syllabus_items_for_exam_codes

CONTRACT_VERSION = "3.2.0"
FINGERPRINT_VERSION = "2"
DOCUMENT_TYPES = {"parsed_exam", "generated_exam", "assembled_exam"}
VALIDATION_STATUSES = {"draft", "passed", "failed"}
ROOT_FIELDS = {
    "contract_version", "document_type", "source_hash", "validation_status",
    "question_fingerprint_version", "locale", "metadata", "questions",
}
METADATA_REQUIRED = {"exam_type", "year", "source_files"}
METADATA_OPTIONAL = {
    "title", "subject", "corpus_group", "syllabus_version",
    "source_exam_types", "target_exam", "assembly",
}
QUESTION_FIELDS = {
    "code", "number", "title", "options", "answer", "images", "examType",
    "source_examType", "year", "questionNumber", "subject", "subject_code",
    "topic", "topic_code", "question_type", "difficulty", "knowledge_points",
    "is_ai_generated", "learning_analysis", "explanation", "fingerprint",
    "syllabus_tags", "diagram", "source", "target_exam_scope",
}
ASSEMBLED_QUESTION_FIELDS = QUESTION_FIELDS | {"assembled_section"}
BLOCK_TYPES = {"text", "latex", "image_ref"}
QUESTION_TYPES = {"multiple_choice", "free_response"}
DIFFICULTIES = {"easy", "medium", "hard"}
IMAGE_ROLES = {"question", "option", "explanation"}
RESTORE_METHODS = {"vector_extract", "render_crop", "redraw_svg", "not_applicable"}
IMAGE_STATUSES = {"restored", "not_applicable"}
TRACE_SOURCES = {"official_solution", "official_answer", "independent_derivation"}
TARGET_SCOPE_STATUSES = {"in_scope", "out_of_scope", "partially_in_scope", "unknown"}
TARGET_SCOPE_REVIEWS = {"unchecked", "reviewed", "needs_review"}
ESAT_MODULES = {"Mathematics 1", "Biology", "Chemistry", "Physics", "Mathematics 2"}
ESAT_OFFICIAL_MODULE_QUESTION_COUNT = 27
ESAT_OFFICIAL_MODULE_TIME_MINUTES = 40
TMUA_PAPERS = {"Paper 1", "Paper 2"}
TMUA_PAPER_DESCRIPTORS = {
    "Paper 1": {"code": "TMUA-P1", "label": "Paper 1: Mathematical Thinking"},
    "Paper 2": {"code": "TMUA-P2", "label": "Paper 2: Mathematical Reasoning"},
}
TMUA_PAPER_ALLOWED_SYLLABUS_MODULES = {
    "Paper 1": {"Mathematics 1", "Mathematics 2"},
    "Paper 2": {"Mathematics 1", "Mathematics 2", "Logic & Proof"},
}
TMUA_OFFICIAL_PAPER_QUESTION_COUNT = 20
TMUA_OFFICIAL_PAPER_TIME_MINUTES = 75
ASSEMBLY_DIAGNOSTIC_STATUSES = {"sufficient", "underfilled", "overfilled", "narrow_coverage", "source_skewed", "mixed"}
ASSEMBLY_CONFIDENCE_LEVELS = {"high", "medium", "low"}
ZH_RE = re.compile(r"[\u3400-\u9fff]")
STEP_ONE_RE = re.compile(r"(?:步骤|STEP)\s*1", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """标准数据不符合生产契约。"""


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json_atomic(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary_name, target)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def calculate_source_hash(paths: Iterable[str | Path]) -> str:
    digest = hashlib.sha256()
    resolved = sorted(Path(path).resolve() for path in paths)
    if not resolved:
        raise ContractError("至少需要一个源文件。")
    for ordinal, path in enumerate(resolved):
        if not path.is_file():
            raise ContractError(f"源文件不存在：{path}")
        digest.update(str(ordinal).encode("ascii"))
        digest.update(b"\0")
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _suggested_time_minutes(actual_question_count: int) -> int:
    if actual_question_count <= 0:
        return 0
    return (
        actual_question_count * ESAT_OFFICIAL_MODULE_TIME_MINUTES
        + ESAT_OFFICIAL_MODULE_QUESTION_COUNT
        - 1
    ) // ESAT_OFFICIAL_MODULE_QUESTION_COUNT


def _nonempty_text(value: Any, message: str, minimum: int = 1) -> str:
    _require(isinstance(value, str) and len(value.strip()) >= minimum, message)
    return value.strip()


def _exact_fields(value: Any, required: set[str], label: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{label}必须是对象。")
    missing = required - set(value)
    unknown = set(value) - required
    _require(not missing, f"{label}缺少字段：{sorted(missing)}")
    _require(not unknown, f"{label}包含未知字段：{sorted(unknown)}")
    return value


def _validate_syllabus_item(value: Any, label: str, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    item = _exact_fields(
        value,
        {
            "code",
            "label",
            "module",
            "module_code",
            "module_label",
            "parent_code",
            "parent_label",
            "path_codes",
            "path_labels",
        },
        label,
    )
    _nonempty_text(item["code"], f"{label}.code 不能为空。")
    _nonempty_text(item["label"], f"{label}.label 不能为空。")
    _require(item["module"] in ESAT_MODULES, f"{label}.module 必须是 ESAT 模块。")
    descriptor = module_descriptor(item["module"])
    _require(item["module_code"] == descriptor["module_code"], f"{label}.module_code 与 ESAT syllabus 不一致。")
    _require(item["module_label"] == descriptor["module_label"], f"{label}.module_label 与 ESAT syllabus 不一致。")
    _nonempty_text(item["parent_code"], f"{label}.parent_code 不能为空。")
    _nonempty_text(item["parent_label"], f"{label}.parent_label 不能为空。")
    _require(
        isinstance(item["path_codes"], list) and bool(item["path_codes"])
        and all(isinstance(code, str) and code.strip() for code in item["path_codes"]),
        f"{label}.path_codes 必须是非空字符串数组。",
    )
    _require(
        isinstance(item["path_labels"], list) and len(item["path_labels"]) == len(item["path_codes"])
        and all(isinstance(text, str) and text.strip() for text in item["path_labels"]),
        f"{label}.path_labels 必须与 path_codes 一一对应。",
    )
    canonical = syllabus_item(item["code"])
    _require(canonical is not None, f"{label}.code 不存在于 esat_syllabus.json。")
    _require(item == canonical, f"{label} 必须与 esat_syllabus.json 中的标准 code/label/path 完全一致。")
    if expected is not None:
        _require(item == expected, f"{label} 与 syllabus_codes 对应的标准条目不一致。")
    return item


def _validate_syllabus_item_list(value: Any, label: str, expected_items: list[dict[str, Any]]) -> None:
    _require(isinstance(value, list), f"{label} 必须是数组。")
    _require(len(value) == len(expected_items), f"{label} 必须与 syllabus_codes 去重后逐项对应。")
    for offset, (item, expected) in enumerate(zip(value, expected_items), 1):
        _validate_syllabus_item(item, f"{label}[{offset}]", expected)


def _validate_tmua_syllabus_item(value: Any, label: str, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    item = _exact_fields(
        value,
        {
            "code",
            "label",
            "module",
            "module_code",
            "module_label",
            "parent_code",
            "parent_label",
            "path_codes",
            "path_labels",
        },
        label,
    )
    _nonempty_text(item["code"], f"{label}.code 不能为空。")
    _nonempty_text(item["label"], f"{label}.label 不能为空。")
    _require(item["module"] in {"Mathematics 1", "Mathematics 2", "Logic & Proof"}, f"{label}.module 必须是 TMUA 知识域。")
    _require(isinstance(item["module_code"], str) and item["module_code"].startswith("2"), f"{label}.module_code 必须来自 TMUA syllabus。")
    _nonempty_text(item["module_label"], f"{label}.module_label 不能为空。")
    _nonempty_text(item["parent_code"], f"{label}.parent_code 不能为空。")
    _nonempty_text(item["parent_label"], f"{label}.parent_label 不能为空。")
    _require(
        isinstance(item["path_codes"], list) and bool(item["path_codes"])
        and all(isinstance(code, str) and code.strip() for code in item["path_codes"]),
        f"{label}.path_codes 必须是非空字符串数组。",
    )
    _require(
        isinstance(item["path_labels"], list) and len(item["path_labels"]) == len(item["path_codes"])
        and all(isinstance(text, str) and text.strip() for text in item["path_labels"]),
        f"{label}.path_labels 必须与 path_codes 一一对应。",
    )
    canonical = syllabus_item_for_exam("TMUA", item["code"])
    _require(canonical is not None, f"{label}.code 不存在于 tmua_syllabus.json。")
    _require(item == canonical, f"{label} 必须与 tmua_syllabus.json 中的标准 code/label/path 完全一致。")
    if expected is not None:
        _require(item == expected, f"{label} 与 syllabus_codes 对应的标准条目不一致。")
    return item


def _validate_tmua_syllabus_item_list(value: Any, label: str, expected_items: list[dict[str, Any]]) -> None:
    _require(isinstance(value, list), f"{label} 必须是数组。")
    _require(len(value) == len(expected_items), f"{label} 必须与 syllabus_codes 去重后逐项对应。")
    for offset, (item, expected) in enumerate(zip(value, expected_items), 1):
        _validate_tmua_syllabus_item(item, f"{label}[{offset}]", expected)


def _validate_blocks(value: Any, label: str, *, allow_empty: bool = False) -> None:
    _require(isinstance(value, list), f"{label}必须是内容块数组。")
    if not allow_empty:
        _require(bool(value), f"{label}不能为空。")
    for offset, block in enumerate(value, 1):
        block_label = f"{label}第 {offset} 个内容块"
        _require(isinstance(block, dict), f"{block_label}必须是对象。")
        block_type = block.get("type")
        _require(block_type in BLOCK_TYPES, f"{block_label}.type 不受支持。")
        expected = {"type", "image_id"} if block_type == "image_ref" else {"type", "content"}
        _exact_fields(block, expected, block_label)
        key = "image_id" if block_type == "image_ref" else "content"
        _nonempty_text(block[key], f"{block_label}.{key}不能为空。")


def _validate_options(question: dict[str, Any], label: str) -> list[str]:
    options = question["options"]
    _require(isinstance(options, list), f"{label}.options 必须是数组。")
    if question["question_type"] == "multiple_choice":
        _require(len(options) >= 2, f"{label}选择题至少需要两个选项。")
    else:
        _require(not options, f"{label}非选择题的 options 必须为空数组。")
    labels: list[str] = []
    for offset, option in enumerate(options, 1):
        option_label = f"{label}第 {offset} 个选项"
        _exact_fields(option, {"label", "content"}, option_label)
        labels.append(_nonempty_text(option["label"], f"{option_label}.label 不能为空。"))
        _validate_blocks(option["content"], f"{option_label}.content")
    _require(len(labels) == len(set(labels)), f"{label}选项标签不得重复。")
    if question["question_type"] == "multiple_choice":
        _require(question["answer"] in labels, f"{label}答案必须匹配一个选项标签。")
    return labels


def _validate_images(question: dict[str, Any], label: str) -> set[str]:
    images = question["images"]
    _require(isinstance(images, list), f"{label}.images 必须是数组。")
    image_ids: set[str] = set()
    fields = {
        "image_id", "role", "source_page", "bbox", "restore_method",
        "asset_path", "alt_text", "status",
    }
    for offset, item in enumerate(images, 1):
        image_label = f"{label}第 {offset} 个图形"
        _exact_fields(item, fields, image_label)
        image_id = _nonempty_text(item["image_id"], f"{image_label}.image_id 不能为空。")
        _require(image_id not in image_ids, f"{label}的 image_id 不得重复。")
        image_ids.add(image_id)
        _require(item["role"] in IMAGE_ROLES, f"{image_label}.role 不受支持。")
        _require(
            isinstance(item["source_page"], int) and not isinstance(item["source_page"], bool)
            and item["source_page"] > 0,
            f"{image_label}.source_page 必须是正整数。",
        )
        bbox = item["bbox"]
        _require(
            bbox is None or (
                isinstance(bbox, list) and len(bbox) == 4
                and all(isinstance(point, (int, float)) and not isinstance(point, bool) for point in bbox)
            ),
            f"{image_label}.bbox 必须是四个数值或 null。",
        )
        _require(item["restore_method"] in RESTORE_METHODS, f"{image_label}.restore_method 不受支持。")
        _require(item["status"] in IMAGE_STATUSES, f"{image_label}.status 不受支持。")
        _nonempty_text(item["alt_text"], f"{image_label}.alt_text 不能为空。")
        _require(isinstance(item["asset_path"], str), f"{image_label}.asset_path 必须是字符串。")
        if item["status"] == "restored":
            _require(item["restore_method"] != "not_applicable", f"{image_label}已恢复却没有恢复方法。")
            _nonempty_text(item["asset_path"], f"{image_label}已恢复却缺少 asset_path。")
        else:
            _require(item["restore_method"] == "not_applicable", f"{image_label}不适用时恢复方法必须为 not_applicable。")
    return image_ids


def _validate_knowledge_points(question: dict[str, Any], label: str) -> str:
    points = question["knowledge_points"]
    _require(isinstance(points, list) and points, f"{label}.knowledge_points 必须是非空数组。")
    primary: list[str] = []
    codes: set[str] = set()
    for offset, point in enumerate(points, 1):
        point_label = f"{label}第 {offset} 个知识点"
        _exact_fields(point, {"code", "name", "is_primary"}, point_label)
        code = _nonempty_text(point["code"], f"{point_label}.code 不能为空。")
        _nonempty_text(point["name"], f"{point_label}.name 不能为空。")
        _require(isinstance(point["is_primary"], bool), f"{point_label}.is_primary 必须是布尔值。")
        _require(code not in codes, f"{label}知识点代码不得重复。")
        codes.add(code)
        if point["is_primary"]:
            primary.append(code)
    _require(len(primary) == 1, f"{label}必须且只能有一个主知识点。")
    tags = question["syllabus_tags"]
    _require(
        isinstance(tags, list) and bool(tags)
        and all(isinstance(tag, str) and tag.strip() for tag in tags),
        f"{label}.syllabus_tags 必须是非空字符串数组。",
    )
    _require(primary[0] in tags, f"{label}.syllabus_tags 必须包含主知识点代码。")
    return primary[0]


def _validate_learning_analysis(question: dict[str, Any], label: str, option_labels: list[str]) -> None:
    analysis = _exact_fields(
        question["learning_analysis"],
        {"solution_trace", "exam_focus", "correct_solution", "common_error_causes", "review_guidance", "answer_feedback_mode"},
        f"{label}.learning_analysis",
    )
    trace = _exact_fields(
        analysis["solution_trace"],
        {"trace_source", "knowns", "method", "steps", "final_value", "correct_answer", "distractors"},
        f"{label}.solution_trace",
    )
    _require(trace["trace_source"] in TRACE_SOURCES, f"{label}.trace_source 不受支持。")
    _require(
        isinstance(trace["knowns"], list) and bool(trace["knowns"])
        and all(isinstance(item, str) and item.strip() for item in trace["knowns"]),
        f"{label}.knowns 必须是非空字符串数组。",
    )
    _nonempty_text(trace["method"], f"{label}.method 至少需要 20 个字符。", 20)
    _require(
        isinstance(trace["steps"], list) and len(trace["steps"]) >= 3
        and all(isinstance(step, str) and step.strip() for step in trace["steps"]),
        f"{label}.steps 至少需要三个非空步骤。",
    )
    _require(trace["final_value"] not in (None, ""), f"{label}.final_value 不能为空。")
    _require(str(trace["correct_answer"]) == str(question["answer"]), f"{label}.correct_answer 与答案不一致。")
    distractors = trace["distractors"]
    _require(isinstance(distractors, list), f"{label}.distractors 必须是数组。")
    distractor_labels: list[str] = []
    for offset, item in enumerate(distractors, 1):
        item_label = f"{label}第 {offset} 个干扰项分析"
        _exact_fields(item, {"option", "reason"}, item_label)
        distractor_labels.append(_nonempty_text(item["option"], f"{item_label}.option 不能为空。"))
        reason = _nonempty_text(item["reason"], f"{item_label}.reason 至少需要 15 个字符。", 15)
        _require(bool(ZH_RE.search(reason)), f"{item_label}.reason 必须使用中文。")
    if question["question_type"] == "multiple_choice":
        expected = set(option_labels) - {str(question["answer"])}
        _require(set(distractor_labels) == expected, f"{label}必须逐一解释所有错误选项。")
    else:
        _require(not distractors, f"{label}非选择题的 distractors 必须为空数组。")
    for field, minimum in (("exam_focus", 20), ("correct_solution", 80), ("review_guidance", 30)):
        value = _nonempty_text(analysis[field], f"{label}.{field}内容不足。", minimum)
        _require(bool(ZH_RE.search(value)), f"{label}.{field}必须使用中文。")
    errors = analysis["common_error_causes"]
    _require(
        isinstance(errors, list) and len(errors) >= 3
        and all(isinstance(item, str) and len(item.strip()) >= 15 and ZH_RE.search(item) for item in errors),
        f"{label}.common_error_causes 至少需要三条、每条至少 15 个字符的本题错误原因。",
    )
    expected_mode = "option_specific" if question["question_type"] == "multiple_choice" else "free_response"
    _require(analysis["answer_feedback_mode"] == expected_mode, f"{label}.answer_feedback_mode 与题型不一致。")


def _validate_diagram(value: Any, label: str) -> None:
    if value is None:
        return
    _exact_fields(value, {"description", "semantics", "asset_path"}, f"{label}.diagram")
    _nonempty_text(value["description"], f"{label}.diagram.description 不能为空。")
    _nonempty_text(value["semantics"], f"{label}.diagram.semantics 不能为空。")
    _require(isinstance(value["asset_path"], str), f"{label}.diagram.asset_path 必须是字符串。")


def _validate_locator(value: Any, label: str) -> None:
    _exact_fields(value, {"file", "page"}, label)
    _nonempty_text(value["file"], f"{label}.file 不能为空。")
    _require(
        isinstance(value["page"], int) and not isinstance(value["page"], bool) and value["page"] > 0,
        f"{label}.page 必须是正整数。",
    )


def _validate_parsed_source(question: dict[str, Any], label: str) -> None:
    source = _exact_fields(question["source"], {"question", "answer", "solution", "evidence_packet"}, f"{label}.source")
    _validate_locator(source["question"], f"{label}.source.question")
    _validate_locator(source["answer"], f"{label}.source.answer")
    if source["solution"] is not None:
        _validate_locator(source["solution"], f"{label}.source.solution")
    packet = _exact_fields(source["evidence_packet"], {"path", "sha256"}, f"{label}.source.evidence_packet")
    _nonempty_text(packet["path"], f"{label}.source.evidence_packet.path 不能为空。")
    _require(isinstance(packet["sha256"], str) and SHA256_RE.fullmatch(packet["sha256"]), f"{label}证据包哈希无效。")


def _validate_generated_source(question: dict[str, Any], label: str) -> None:
    source = _exact_fields(
        question["source"],
        {"source_question_id", "source_fingerprint", "generation_blueprint"},
        f"{label}.source",
    )
    _nonempty_text(source["source_question_id"], f"{label}.source_question_id 不能为空。")
    _require(isinstance(source["source_fingerprint"], str) and SHA256_RE.fullmatch(source["source_fingerprint"]), f"{label}.source_fingerprint 必须是 SHA-256。")
    blueprint = _exact_fields(
        source["generation_blueprint"],
        {
            "retained_knowledge_point",
            "source_deconstruction",
            "structural_transformation",
            "changed_reasoning_structure",
            "changed_context",
            "changed_values",
            "difficulty_reassessment",
            "diagram_generation_spec",
            "novelty_rationale",
        },
        f"{label}.generation_blueprint",
    )
    for field in blueprint:
        minimum = 40 if field in {
            "source_deconstruction",
            "structural_transformation",
            "changed_reasoning_structure",
            "difficulty_reassessment",
            "diagram_generation_spec",
            "novelty_rationale",
        } else 1
        _nonempty_text(blueprint[field], f"{label}.generation_blueprint.{field}内容不足。", minimum)


def _validate_target_exam_scope(question: dict[str, Any], label: str) -> None:
    scope = _exact_fields(
        question["target_exam_scope"],
        {
            "target_exam",
            "status",
            "modules",
            "primary_module",
            "primary_module_code",
            "primary_module_label",
            "syllabus_codes",
            "syllabus_items",
            "exclusion_reasons",
            "evidence",
            "review_status",
        },
        f"{label}.target_exam_scope",
    )
    target_exam = _nonempty_text(scope["target_exam"], f"{label}.target_exam_scope.target_exam 不能为空。")
    _require(scope["status"] in TARGET_SCOPE_STATUSES, f"{label}.target_exam_scope.status 不受支持。")
    _require(scope["review_status"] in TARGET_SCOPE_REVIEWS, f"{label}.target_exam_scope.review_status 不受支持。")
    _require(isinstance(scope["modules"], list), f"{label}.target_exam_scope.modules 必须是数组。")
    _require(isinstance(scope["syllabus_codes"], list), f"{label}.target_exam_scope.syllabus_codes 必须是数组。")
    _require(isinstance(scope["syllabus_items"], list), f"{label}.target_exam_scope.syllabus_items 必须是数组。")
    _require(isinstance(scope["exclusion_reasons"], list), f"{label}.target_exam_scope.exclusion_reasons 必须是数组。")
    _require(isinstance(scope["evidence"], str) and len(scope["evidence"].strip()) >= 10, f"{label}.target_exam_scope.evidence 必须说明判断依据。")
    _require(all(isinstance(item, str) and item.strip() for item in scope["modules"]), f"{label}.target_exam_scope.modules 必须是非空字符串数组。")
    _require(all(isinstance(item, str) and item.strip() for item in scope["syllabus_codes"]), f"{label}.target_exam_scope.syllabus_codes 必须是字符串数组。")
    _require(all(isinstance(item, str) and item.strip() for item in scope["exclusion_reasons"]), f"{label}.target_exam_scope.exclusion_reasons 必须是字符串数组。")
    if target_exam == "ESAT":
        unknown_modules = set(scope["modules"]) - ESAT_MODULES
        _require(not unknown_modules, f"{label}.target_exam_scope.modules 包含非 ESAT 模块：{sorted(unknown_modules)}")
        primary = scope["primary_module"]
        _require(primary is None or primary in ESAT_MODULES, f"{label}.target_exam_scope.primary_module 不是 ESAT 模块。")
        if primary is None:
            _require(scope["primary_module_code"] is None, f"{label}.target_exam_scope.primary_module_code 必须为 null。")
            _require(scope["primary_module_label"] is None, f"{label}.target_exam_scope.primary_module_label 必须为 null。")
        else:
            descriptor = module_descriptor(primary)
            _require(scope["primary_module_code"] == descriptor["module_code"], f"{label}.target_exam_scope.primary_module_code 与 esat_syllabus 不一致。")
            _require(scope["primary_module_label"] == descriptor["module_label"], f"{label}.target_exam_scope.primary_module_label 与 esat_syllabus 不一致。")
        expected_items, unmatched = syllabus_items_for_codes(scope["syllabus_codes"])
        _require(not unmatched, f"{label}.target_exam_scope.syllabus_codes 包含非 ESAT syllabus code：{unmatched}")
        _validate_syllabus_item_list(scope["syllabus_items"], f"{label}.target_exam_scope.syllabus_items", expected_items)
        for item in expected_items:
            _require(item["module"] in scope["modules"], f"{label}.target_exam_scope.syllabus_items 包含不属于 modules 的考纲项：{item['code']}")
        if scope["status"] == "in_scope":
            _require(bool(scope["modules"]), f"{label}标为 ESAT in_scope 时必须给出模块。")
            _require(primary in scope["modules"], f"{label}.primary_module 必须属于 modules。")
            _require(bool(scope["syllabus_codes"]), f"{label}标为 ESAT in_scope 时必须给出考纲代码。")
            _require(bool(scope["syllabus_items"]), f"{label}标为 ESAT in_scope 时必须给出 syllabus_items。")
            _require(not scope["exclusion_reasons"], f"{label}标为 ESAT in_scope 时不得写排除原因。")
        elif scope["status"] == "out_of_scope":
            _require(not scope["modules"], f"{label}标为 ESAT out_of_scope 时 modules 必须为空。")
            _require(primary is None, f"{label}标为 ESAT out_of_scope 时 primary_module 必须为 null。")
            _require(not scope["syllabus_codes"], f"{label}标为 ESAT out_of_scope 时 syllabus_codes 必须为空。")
            _require(not scope["syllabus_items"], f"{label}标为 ESAT out_of_scope 时 syllabus_items 必须为空。")
            _require(bool(scope["exclusion_reasons"]), f"{label}标为 ESAT out_of_scope 时必须写明排除原因。")
        elif scope["status"] == "partially_in_scope":
            _require(bool(scope["modules"]), f"{label}标为 ESAT partially_in_scope 时必须给出可用模块。")
            _require(primary in scope["modules"], f"{label}.primary_module 必须属于 modules。")
            _require(bool(scope["syllabus_codes"]), f"{label}标为 ESAT partially_in_scope 时必须给出可用考纲代码。")
            _require(bool(scope["syllabus_items"]), f"{label}标为 ESAT partially_in_scope 时必须给出可用 syllabus_items。")
            _require(bool(scope["exclusion_reasons"]), f"{label}标为 ESAT partially_in_scope 时必须说明排除或部分超纲原因。")
    elif target_exam == "TMUA":
        unknown_papers = set(scope["modules"]) - TMUA_PAPERS
        _require(not unknown_papers, f"{label}.target_exam_scope.modules 包含非 TMUA paper：{sorted(unknown_papers)}")
        primary = scope["primary_module"]
        _require(primary is None or primary in TMUA_PAPERS, f"{label}.target_exam_scope.primary_module 不是 TMUA paper。")
        if primary is None:
            _require(scope["primary_module_code"] is None, f"{label}.target_exam_scope.primary_module_code 必须为 null。")
            _require(scope["primary_module_label"] is None, f"{label}.target_exam_scope.primary_module_label 必须为 null。")
        else:
            descriptor = TMUA_PAPER_DESCRIPTORS[primary]
            _require(scope["primary_module_code"] == descriptor["code"], f"{label}.target_exam_scope.primary_module_code 与 TMUA paper 不一致。")
            _require(scope["primary_module_label"] == descriptor["label"], f"{label}.target_exam_scope.primary_module_label 与 TMUA paper 不一致。")
        expected_items, unmatched = syllabus_items_for_exam_codes("TMUA", scope["syllabus_codes"])
        _require(not unmatched, f"{label}.target_exam_scope.syllabus_codes 包含非 TMUA syllabus code：{unmatched}")
        _validate_tmua_syllabus_item_list(scope["syllabus_items"], f"{label}.target_exam_scope.syllabus_items", expected_items)
        if primary is not None:
            allowed_modules = TMUA_PAPER_ALLOWED_SYLLABUS_MODULES[primary]
            disallowed = [item["code"] for item in expected_items if item["module"] not in allowed_modules]
            _require(not disallowed, f"{label}.target_exam_scope.syllabus_items 不属于 {primary} 可用范围：{disallowed}")
        if scope["status"] == "in_scope":
            _require(bool(scope["modules"]), f"{label}标为 TMUA in_scope 时必须给出 paper。")
            _require(primary in scope["modules"], f"{label}.primary_module 必须属于 modules。")
            _require(bool(scope["syllabus_codes"]), f"{label}标为 TMUA in_scope 时必须给出考纲代码。")
            _require(bool(scope["syllabus_items"]), f"{label}标为 TMUA in_scope 时必须给出 syllabus_items。")
            _require(not scope["exclusion_reasons"], f"{label}标为 TMUA in_scope 时不得写排除原因。")
        elif scope["status"] == "out_of_scope":
            _require(not scope["modules"], f"{label}标为 TMUA out_of_scope 时 modules 必须为空。")
            _require(primary is None, f"{label}标为 TMUA out_of_scope 时 primary_module 必须为 null。")
            _require(not scope["syllabus_codes"], f"{label}标为 TMUA out_of_scope 时 syllabus_codes 必须为空。")
            _require(not scope["syllabus_items"], f"{label}标为 TMUA out_of_scope 时 syllabus_items 必须为空。")
            _require(bool(scope["exclusion_reasons"]), f"{label}标为 TMUA out_of_scope 时必须写明排除原因。")
        elif scope["status"] == "partially_in_scope":
            _require(bool(scope["modules"]), f"{label}标为 TMUA partially_in_scope 时必须给出可用 paper。")
            _require(primary in scope["modules"], f"{label}.primary_module 必须属于 modules。")
            _require(bool(scope["syllabus_codes"]), f"{label}标为 TMUA partially_in_scope 时必须给出可用考纲代码。")
            _require(bool(scope["syllabus_items"]), f"{label}标为 TMUA partially_in_scope 时必须给出可用 syllabus_items。")
            _require(bool(scope["exclusion_reasons"]), f"{label}标为 TMUA partially_in_scope 时必须说明排除或部分超纲原因。")


def _validate_assembled_section(question: dict[str, Any], label: str) -> None:
    section = _exact_fields(
        question["assembled_section"],
        {"module", "module_code", "module_label", "section_order", "question_order", "scoring_group", "syllabus_items"},
        f"{label}.assembled_section",
    )
    module = section["module"]
    _require(module in ESAT_MODULES, f"{label}.assembled_section.module 必须是 ESAT 模块。")
    descriptor = module_descriptor(module)
    _require(section["module_code"] == descriptor["module_code"], f"{label}.assembled_section.module_code 与 esat_syllabus 不一致。")
    _require(section["module_label"] == descriptor["module_label"], f"{label}.assembled_section.module_label 与 esat_syllabus 不一致。")
    _require(section["scoring_group"] == module, f"{label}.assembled_section.scoring_group 必须与 module 一致。")
    _require(isinstance(section["section_order"], int) and not isinstance(section["section_order"], bool) and section["section_order"] > 0, f"{label}.assembled_section.section_order 必须是正整数。")
    _require(isinstance(section["question_order"], int) and not isinstance(section["question_order"], bool) and section["question_order"] > 0, f"{label}.assembled_section.question_order 必须是正整数。")
    _require(question["target_exam_scope"]["primary_module"] == module, f"{label}.assembled_section.module 必须与 target_exam_scope.primary_module 一致。")
    _validate_syllabus_item_list(section["syllabus_items"], f"{label}.assembled_section.syllabus_items", question["target_exam_scope"]["syllabus_items"])


def _validate_question(question: Any, index: int, document_type: str) -> None:
    label = f"第 {index + 1} 题"
    expected_fields = ASSEMBLED_QUESTION_FIELDS if document_type == "assembled_exam" else QUESTION_FIELDS
    _exact_fields(question, expected_fields, label)
    for field in ("code", "examType", "source_examType", "subject", "subject_code", "topic", "topic_code"):
        _nonempty_text(question[field], f"{label}.{field}不能为空。")
    _require(isinstance(question["number"], (str, int)) and not isinstance(question["number"], bool), f"{label}.number 必须是字符串或整数。")
    _require(isinstance(question["questionNumber"], (str, int)) and not isinstance(question["questionNumber"], bool), f"{label}.questionNumber 必须是字符串或整数。")
    _require(str(question["number"]) == str(question["questionNumber"]), f"{label}.number 与 questionNumber 必须一致。")
    _require(isinstance(question["year"], (str, int)) and not isinstance(question["year"], bool), f"{label}.year 必须是年份。")
    _require(question["question_type"] in QUESTION_TYPES, f"{label}.question_type 不受支持。")
    _require(question["difficulty"] in DIFFICULTIES, f"{label}.difficulty 不受支持。")
    _validate_blocks(question["title"], f"{label}.title")
    _require(question["answer"] not in (None, ""), f"{label}.answer 不能为空。")
    option_labels = _validate_options(question, label)
    image_ids = _validate_images(question, label)
    referenced_ids: set[str] = set()
    for block in question["title"]:
        if block["type"] == "image_ref": referenced_ids.add(block["image_id"])
    for option in question["options"]:
        for block in option["content"]:
            if block["type"] == "image_ref": referenced_ids.add(block["image_id"])
    _require(referenced_ids <= image_ids, f"{label}包含未定义的 image_ref。")
    _validate_knowledge_points(question, label)
    _validate_target_exam_scope(question, label)
    if question["target_exam_scope"]["target_exam"] == "TMUA":
        _require(question["question_type"] == "multiple_choice", f"{label}TMUA 题目必须是 multiple_choice。")
    if document_type == "assembled_exam":
        _validate_assembled_section(question, label)
    _validate_learning_analysis(question, label, option_labels)
    explanation = _nonempty_text(question["explanation"], f"{label}.explanation 至少需要 80 个字符。", 80)
    _require(bool(ZH_RE.search(explanation)), f"{label}.explanation 必须使用中文。")
    _require("目标" in explanation and STEP_ONE_RE.search(explanation) and "复核" in explanation, f"{label}.explanation 必须包含目标、步骤 1 和复核。")
    _validate_diagram(question["diagram"], label)
    _require(isinstance(question["is_ai_generated"], bool), f"{label}.is_ai_generated 必须是布尔值。")
    if document_type in {"parsed_exam", "assembled_exam"}:
        _require(not question["is_ai_generated"], f"{label}真题或组卷题不得标为 AI 生成。")
        _validate_parsed_source(question, label)
    else:
        _require(question["is_ai_generated"], f"{label}生成题必须标为 AI 生成。")
        _validate_generated_source(question, label)
    fingerprint = question["fingerprint"]
    _require(isinstance(fingerprint, str) and SHA256_RE.fullmatch(fingerprint), f"{label}.fingerprint 必须是 SHA-256。")
    _require(fingerprint == question_fingerprint(question), f"{label}题目指纹不一致。")


def validate_question_fragment(question: Any, *, document_type: str) -> None:
    """校验已经完成逐题生产闭环的单题片段。

    这个入口只做兜底拦截，不补写字段、不修复质量问题。若失败，必须回到对应
    的单题生产步骤局部返工。
    """

    _require(document_type in DOCUMENT_TYPES, "文档类型不受支持。")
    _validate_question(question, 0, document_type)


def _validate_assembly_metadata(metadata: dict[str, Any], document_type: str) -> None:
    if "assembly" not in metadata:
        _require(document_type != "assembled_exam", "assembled_exam 必须包含 metadata.assembly。")
        return
    assembly = _exact_fields(
        metadata["assembly"],
        {
            "target_exam",
            "modules",
            "required_module",
            "source_document",
            "assembly_rule",
            "paper_note",
            "syllabus_root",
            "official_full_test_time_minutes",
            "total_suggested_time_minutes",
            "sections",
            "scoring",
        },
        "metadata.assembly",
    )
    _require(assembly["target_exam"] == "ESAT", "metadata.assembly.target_exam 目前仅支持 ESAT。")
    _require(isinstance(assembly["modules"], list) and bool(assembly["modules"]), "metadata.assembly.modules 必须是非空数组。")
    _require(all(isinstance(item, str) and item in ESAT_MODULES for item in assembly["modules"]), "metadata.assembly.modules 必须全部是 ESAT 模块。")
    _require(len(assembly["modules"]) == len(set(assembly["modules"])), "metadata.assembly.modules 不得重复。")
    _require(assembly["required_module"] == "Mathematics 1", "ESAT 组卷必须以 Mathematics 1 为必选模块。")
    _require("Mathematics 1" in assembly["modules"], "ESAT 组卷 modules 必须包含 Mathematics 1。")
    _nonempty_text(assembly["source_document"], "metadata.assembly.source_document 不能为空。")
    _nonempty_text(assembly["assembly_rule"], "metadata.assembly.assembly_rule 不能为空。", 10)
    _nonempty_text(assembly["paper_note"], "metadata.assembly.paper_note 不能为空。", 20)
    _require(assembly["syllabus_root"] == esat_root(), "metadata.assembly.syllabus_root 必须与 esat_syllabus.json 根节点一致。")
    _require(
        assembly["official_full_test_time_minutes"] == len(assembly["modules"]) * ESAT_OFFICIAL_MODULE_TIME_MINUTES,
        "metadata.assembly.official_full_test_time_minutes 必须等于模块数 × 官方 40 分钟。",
    )
    _require(
        isinstance(assembly["total_suggested_time_minutes"], int)
        and not isinstance(assembly["total_suggested_time_minutes"], bool)
        and assembly["total_suggested_time_minutes"] >= 0,
        "metadata.assembly.total_suggested_time_minutes 必须是非负整数。",
    )
    scoring = _exact_fields(
        assembly["scoring"],
        {
            "mode",
            "raw_per_question_score",
            "negative_marking",
            "raw_score_reporting",
            "official_reported_scale",
            "official_decimal_places",
            "official_scaling_method",
            "official_scaled_score_available",
            "diagnostic_score_note",
        },
        "metadata.assembly.scoring",
    )
    _require(scoring["mode"] == "by_module", "ESAT 组卷必须按模块评分。")
    _require(scoring["raw_per_question_score"] == 1, "ESAT legacy 诊断卷每题 1 原始分。")
    _require(scoring["negative_marking"] is False, "ESAT legacy 诊断卷不得设置倒扣分。")
    _require(scoring["raw_score_reporting"] == "raw_and_percentage_by_module", "raw_score_reporting 必须按模块报告原始分和正确率。")
    _require(scoring["official_reported_scale"] == "1.0-9.0", "ESAT 官方报告分数应标注为 1.0-9.0。")
    _require(scoring["official_decimal_places"] == 1, "ESAT 官方报告分数应保留 1 位小数。")
    _nonempty_text(scoring["official_scaling_method"], "metadata.assembly.scoring.official_scaling_method 不能为空。", 10)
    _require(scoring["official_scaled_score_available"] is False, "legacy 诊断卷不得声称可直接计算官方 ESAT 等级分。")
    _nonempty_text(scoring["diagnostic_score_note"], "metadata.assembly.scoring.diagnostic_score_note 不能为空。", 30)
    sections = assembly["sections"]
    _require(isinstance(sections, list) and len(sections) == len(assembly["modules"]), "metadata.assembly.sections 必须与 modules 一一对应。")
    seen_modules: set[str] = set()
    seen_orders: set[int] = set()
    total_suggested = 0
    for offset, section in enumerate(sections, 1):
        section_data = _exact_fields(
            section,
            {
                "module",
                "module_code",
                "module_label",
                "section_order",
                "official_question_count",
                "official_time_minutes",
                "suggested_time_minutes",
                "target_question_count",
                "actual_question_count",
                "scoring_group",
                "diagnostic_status",
                "diagnostic_flags",
                "diagnostic_confidence",
                "coverage_summary",
                "syllabus_coverage",
                "time_note",
                "module_note",
            },
            f"metadata.assembly.sections[{offset}]",
        )
        module = section_data["module"]
        _require(module in assembly["modules"], f"metadata.assembly.sections[{offset}].module 不属于 modules。")
        descriptor = module_descriptor(module)
        _require(section_data["module_code"] == descriptor["module_code"], f"metadata.assembly.sections[{offset}].module_code 与 esat_syllabus 不一致。")
        _require(section_data["module_label"] == descriptor["module_label"], f"metadata.assembly.sections[{offset}].module_label 与 esat_syllabus 不一致。")
        _require(module not in seen_modules, f"metadata.assembly.sections[{offset}].module 重复。")
        seen_modules.add(module)
        order = section_data["section_order"]
        _require(isinstance(order, int) and not isinstance(order, bool) and order > 0, f"metadata.assembly.sections[{offset}].section_order 必须是正整数。")
        _require(order not in seen_orders, f"metadata.assembly.sections[{offset}].section_order 重复。")
        seen_orders.add(order)
        _require(section_data["official_question_count"] == ESAT_OFFICIAL_MODULE_QUESTION_COUNT, f"metadata.assembly.sections[{offset}].official_question_count 必须为 27。")
        _require(section_data["official_time_minutes"] == ESAT_OFFICIAL_MODULE_TIME_MINUTES, f"metadata.assembly.sections[{offset}].official_time_minutes 必须为 40。")
        for field in ("target_question_count", "actual_question_count"):
            _require(isinstance(section_data[field], int) and not isinstance(section_data[field], bool) and section_data[field] >= 0, f"metadata.assembly.sections[{offset}].{field} 必须是非负整数。")
        expected_suggested = _suggested_time_minutes(section_data["actual_question_count"])
        _require(section_data["suggested_time_minutes"] == expected_suggested, f"metadata.assembly.sections[{offset}].suggested_time_minutes 必须按实际题数由 27题/40分钟折算。")
        total_suggested += section_data["suggested_time_minutes"]
        _require(section_data["scoring_group"] == module, f"metadata.assembly.sections[{offset}].scoring_group 必须与模块一致。")
        _require(section_data["diagnostic_status"] in ASSEMBLY_DIAGNOSTIC_STATUSES, f"metadata.assembly.sections[{offset}].diagnostic_status 不受支持。")
        flags = section_data["diagnostic_flags"]
        _require(
            isinstance(flags, list)
            and all(isinstance(flag, str) and flag in ASSEMBLY_DIAGNOSTIC_STATUSES - {"sufficient"} for flag in flags),
            f"metadata.assembly.sections[{offset}].diagnostic_flags 必须是诊断状态数组。",
        )
        _require(section_data["diagnostic_confidence"] in ASSEMBLY_CONFIDENCE_LEVELS, f"metadata.assembly.sections[{offset}].diagnostic_confidence 不受支持。")
        coverage_summary = _exact_fields(
            section_data["coverage_summary"],
            {"available_question_count", "selected_question_count", "syllabus_families", "difficulty_distribution", "source_exam_types"},
            f"metadata.assembly.sections[{offset}].coverage_summary",
        )
        for field in ("available_question_count", "selected_question_count"):
            _require(
                isinstance(coverage_summary[field], int) and not isinstance(coverage_summary[field], bool)
                and coverage_summary[field] >= 0,
                f"metadata.assembly.sections[{offset}].coverage_summary.{field} 必须是非负整数。",
            )
        _require(coverage_summary["available_question_count"] >= section_data["actual_question_count"], f"metadata.assembly.sections[{offset}].coverage_summary.available_question_count 不能小于 actual_question_count。")
        _require(coverage_summary["selected_question_count"] == section_data["actual_question_count"], f"metadata.assembly.sections[{offset}].coverage_summary.selected_question_count 必须等于 actual_question_count。")
        _require(isinstance(coverage_summary["syllabus_families"], list) and all(isinstance(item, str) and item.strip() for item in coverage_summary["syllabus_families"]), f"metadata.assembly.sections[{offset}].coverage_summary.syllabus_families 必须是字符串数组。")
        _require(isinstance(coverage_summary["difficulty_distribution"], dict), f"metadata.assembly.sections[{offset}].coverage_summary.difficulty_distribution 必须是对象。")
        _require(isinstance(coverage_summary["source_exam_types"], dict), f"metadata.assembly.sections[{offset}].coverage_summary.source_exam_types 必须是对象。")
        syllabus_coverage = _exact_fields(
            section_data["syllabus_coverage"],
            {"selected_question_codes", "syllabus_codes", "syllabus_items", "unmatched_syllabus_codes", "coverage_note"},
            f"metadata.assembly.sections[{offset}].syllabus_coverage",
        )
        _require(
            isinstance(syllabus_coverage["selected_question_codes"], list)
            and len(syllabus_coverage["selected_question_codes"]) == section_data["actual_question_count"]
            and all(isinstance(code, str) and code.strip() for code in syllabus_coverage["selected_question_codes"]),
            f"metadata.assembly.sections[{offset}].syllabus_coverage.selected_question_codes 必须与实际题量一致。",
        )
        _require(isinstance(syllabus_coverage["syllabus_codes"], list) and all(isinstance(code, str) and code.strip() for code in syllabus_coverage["syllabus_codes"]), f"metadata.assembly.sections[{offset}].syllabus_coverage.syllabus_codes 必须是字符串数组。")
        _require(isinstance(syllabus_coverage["unmatched_syllabus_codes"], list) and all(isinstance(code, str) and code.strip() for code in syllabus_coverage["unmatched_syllabus_codes"]), f"metadata.assembly.sections[{offset}].syllabus_coverage.unmatched_syllabus_codes 必须是字符串数组。")
        expected_items, unmatched = syllabus_items_for_codes(syllabus_coverage["syllabus_codes"])
        _require(syllabus_coverage["unmatched_syllabus_codes"] == unmatched, f"metadata.assembly.sections[{offset}].syllabus_coverage.unmatched_syllabus_codes 与 syllabus code 解析结果不一致。")
        _require(not unmatched, f"metadata.assembly.sections[{offset}].syllabus_coverage 包含非 ESAT syllabus code：{unmatched}")
        _validate_syllabus_item_list(syllabus_coverage["syllabus_items"], f"metadata.assembly.sections[{offset}].syllabus_coverage.syllabus_items", expected_items)
        _require(all(item["module"] == module for item in syllabus_coverage["syllabus_items"]), f"metadata.assembly.sections[{offset}].syllabus_coverage.syllabus_items 必须全部属于本模块。")
        _nonempty_text(syllabus_coverage["coverage_note"], f"metadata.assembly.sections[{offset}].syllabus_coverage.coverage_note 不能为空。", 10)
        _nonempty_text(section_data["time_note"], f"metadata.assembly.sections[{offset}].time_note 不能为空。", 20)
        _nonempty_text(section_data["module_note"], f"metadata.assembly.sections[{offset}].module_note 不能为空。", 20)
    _require(seen_modules == set(assembly["modules"]), "metadata.assembly.sections 必须覆盖所有 modules。")
    _require(seen_orders == set(range(1, len(sections) + 1)), "metadata.assembly.sections.section_order 必须从 1 连续编号。")
    _require(total_suggested == assembly["total_suggested_time_minutes"], "metadata.assembly.total_suggested_time_minutes 必须等于各模块 suggested_time_minutes 之和。")


def validate_document(document: Any, expected_type: str | None = None) -> None:
    _exact_fields(document, ROOT_FIELDS, "文档根节点")
    _require(document["contract_version"] == CONTRACT_VERSION, "契约版本不受支持。")
    document_type = document["document_type"]
    _require(document_type in DOCUMENT_TYPES, "document_type 不受支持。")
    if expected_type is not None:
        _require(document_type == expected_type, "文档类型与当前流程不匹配。")
    _require(isinstance(document["source_hash"], str) and SHA256_RE.fullmatch(document["source_hash"]), "source_hash 必须是 SHA-256。")
    _require(document["validation_status"] in VALIDATION_STATUSES, "validation_status 不受支持。")
    _require(document["question_fingerprint_version"] == FINGERPRINT_VERSION, "题目指纹版本不受支持。")
    _require(document["locale"] == {"interface_language": "zh-CN", "question_language": "en", "explanation_language": "zh-CN"}, "locale 必须为中文工作环境、英文题目、中文解析。")
    metadata = document["metadata"]
    _require(isinstance(metadata, dict), "metadata 必须是对象。")
    missing = METADATA_REQUIRED - set(metadata)
    unknown = set(metadata) - METADATA_REQUIRED - METADATA_OPTIONAL
    _require(not missing, f"metadata 缺少字段：{sorted(missing)}")
    _require(not unknown, f"metadata 包含未知字段：{sorted(unknown)}")
    _nonempty_text(metadata["exam_type"], "metadata.exam_type 不能为空。")
    _require(isinstance(metadata["year"], (str, int)) and not isinstance(metadata["year"], bool), "metadata.year 必须是年份。")
    _require(isinstance(metadata["source_files"], list) and bool(metadata["source_files"]) and all(isinstance(item, str) and item.strip() for item in metadata["source_files"]), "metadata.source_files 必须是非空字符串数组。")
    if "source_exam_types" in metadata:
        _require(isinstance(metadata["source_exam_types"], list) and bool(metadata["source_exam_types"]) and all(isinstance(item, str) and item.strip() for item in metadata["source_exam_types"]), "metadata.source_exam_types 必须是非空字符串数组。")
    if metadata.get("target_exam") == "ESAT" and "source_exam_types" in metadata:
        source_types = set(metadata["source_exam_types"])
        if source_types & {"ENGAA", "NSAA"}:
            _require({"ENGAA", "NSAA"} <= source_types, "ESAT legacy 年度合并库必须同时包含 ENGAA 与 NSAA 来源。")
    _validate_assembly_metadata(metadata, document_type)
    questions = document["questions"]
    _require(isinstance(questions, list) and questions, "questions 必须是非空数组。")
    seen_codes: set[str] = set()
    seen_fingerprints: set[str] = set()
    assembled_counts: dict[str, int] = {}
    assembled_orders: dict[str, set[int]] = {}
    expected_target_exam = metadata.get("target_exam") or metadata.get("exam_type")
    for index, question in enumerate(questions):
        _validate_question(question, index, document_type)
        if expected_target_exam in {"ESAT", "TMUA"} or document_type == "assembled_exam":
            _require(
                question["target_exam_scope"]["target_exam"] == expected_target_exam,
                f"{expected_target_exam} 文档中的每题都必须包含 {expected_target_exam} 范围标注。",
            )
        if document_type == "assembled_exam":
            assembly_modules = set(metadata["assembly"]["modules"])
            scope = question["target_exam_scope"]
            _require(scope["status"] == "in_scope", f"{question['code']} 未标为 ESAT in_scope，不能进入组卷。")
            _require(set(scope["modules"]) <= assembly_modules, f"{question['code']} 的模块不属于当前组卷组合。")
            section = question["assembled_section"]
            module = section["module"]
            assembled_counts[module] = assembled_counts.get(module, 0) + 1
            assembled_orders.setdefault(module, set()).add(section["question_order"])
        _require(question["code"] not in seen_codes, "code 不得重复。")
        _require(question["fingerprint"] not in seen_fingerprints, "文档内题目不得重复。")
        seen_codes.add(question["code"])
        seen_fingerprints.add(question["fingerprint"])
    if document_type == "assembled_exam":
        for section in metadata["assembly"]["sections"]:
            module = section["module"]
            actual = assembled_counts.get(module, 0)
            _require(actual == section["actual_question_count"], f"{module} 实际题数与 metadata.assembly.sections 不一致。")
            _require(assembled_orders.get(module, set()) == set(range(1, actual + 1)), f"{module} 模块内题号必须从 1 连续编号。")


def build_document(draft: dict[str, Any], *, document_type: str, source_hash: str, validation_status: str = "passed") -> dict[str, Any]:
    """只封装并计算指纹；绝不为草稿补写任何质量字段。"""

    _require(document_type in DOCUMENT_TYPES, "文档类型不受支持。")
    _require(isinstance(source_hash, str), "source_hash 必须是字符串。")
    _require(validation_status in VALIDATION_STATUSES, "validation_status 不受支持。")
    _exact_fields(draft, {"metadata", "questions"}, "草稿根节点")
    _require(isinstance(draft["questions"], list), "草稿 questions 必须是数组。")
    questions: list[dict[str, Any]] = []
    for index, raw in enumerate(draft["questions"]):
        _require(isinstance(raw, dict), f"第 {index + 1} 题必须是对象。")
        question = copy.deepcopy(raw)
        question["fingerprint"] = question_fingerprint(question)
        questions.append(question)
    document = {
        "contract_version": CONTRACT_VERSION,
        "document_type": document_type,
        "source_hash": source_hash,
        "validation_status": validation_status,
        "question_fingerprint_version": FINGERPRINT_VERSION,
        "locale": {"interface_language": "zh-CN", "question_language": "en", "explanation_language": "zh-CN"},
        "metadata": draft["metadata"],
        "questions": questions,
    }
    validate_document(document, document_type)
    return document
