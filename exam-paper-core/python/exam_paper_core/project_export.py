"""将内部 assembled_exam 导出为按模块分组的自包含项目诊断试卷。"""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import Any

from .contract import ContractError


PROJECT_QUESTION_FIELDS = {
    "code",
    "number",
    "title",
    "content_blocks",
    "options",
    "answer",
    "images",
    "examType",
    "source_examType",
    "year",
    "topic",
    "topic_code",
    "question_type",
    "difficulty",
    "syllabus_points",
    "knowledge_points",
    "learning_analysis",
}
PROJECT_MODULE_FIELDS = {"subject", "subject_code", "duration", "items"}
PROJECT_PAPER_TYPES = {"realPaper", "mockPaper", "aiPaper"}
PROJECT_DIFFICULTIES = {"easy", "medium", "hard", "composite"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _as_year(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ContractError("项目诊断卷年份必须是数字。")


def _project_remarks(assembly: Any) -> str:
    _require(isinstance(assembly, dict), "assembled_exam.metadata.assembly 必须是对象。")
    sections = assembly.get("sections")
    _require(isinstance(sections, list) and sections, "assembled_exam 必须包含非空模块段。")
    duration = assembly.get("official_full_test_time_minutes")
    _require(isinstance(duration, int) and not isinstance(duration, bool) and duration > 0, "assembled_exam 缺少官方整卷时长。")

    confidence_labels = {"high": "高", "medium": "中", "low": "低"}
    section_notes: list[str] = []
    for index, section in enumerate(sections, 1):
        _require(isinstance(section, dict), f"assembled_exam 第 {index} 个模块段必须是对象。")
        module = section.get("module_label") or section.get("module")
        actual = section.get("actual_question_count")
        target = section.get("target_question_count")
        flags = section.get("diagnostic_flags", [])
        confidence = section.get("diagnostic_confidence")
        _require(isinstance(module, str) and module.strip(), f"assembled_exam 第 {index} 个模块段缺少名称。")
        _require(isinstance(actual, int) and not isinstance(actual, bool) and actual >= 0, f"{module} 实际题量无效。")
        _require(isinstance(target, int) and not isinstance(target, bool) and target > 0, f"{module} 目标题量无效。")
        _require(isinstance(flags, list), f"{module} diagnostic_flags 必须是数组。")
        _require(confidence in confidence_labels, f"{module} diagnostic_confidence 无效。")

        details = [f"实际 {actual}/{target} 题"]
        if actual < target:
            details.append(f"题量不足 {target - actual} 题")
        elif "overfilled" in flags:
            details.append(f"候选题超量，已筛选至 {target} 题")
        if "narrow_coverage" in flags:
            details.append("考纲覆盖偏窄")
        if "source_skewed" in flags:
            details.append("题源分布偏斜")
        details.append(f"诊断可信度{confidence_labels[confidence]}")
        section_notes.append(f"{module}：" + "，".join(details))

    return (
        f"管理员备注：各模块固定 40 分钟，本卷固定 {duration} 分钟。"
        + "；".join(section_notes)
        + "。"
    )


def _latex_text(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if (
        (text.startswith("$") and text.endswith("$"))
        or (text.startswith("\\(") and text.endswith("\\)"))
        or (text.startswith("\\[") and text.endswith("\\]"))
    ):
        return text
    return f"\\({text}\\)"


def _append_paragraphs(target: list[dict[str, str]], text: str) -> None:
    for paragraph in re.split(r"\n\s*\n", text):
        normalized = paragraph.strip()
        if normalized:
            target.append({"type": "paragraph", "text": normalized})


def _project_content_blocks(blocks: Any, *, label: str) -> list[dict[str, str]]:
    _require(isinstance(blocks, list) and blocks, f"{label}必须包含内容块。")
    result: list[dict[str, str]] = []
    text_parts: list[str] = []

    def flush_text() -> None:
        if text_parts:
            _append_paragraphs(result, "".join(text_parts))
            text_parts.clear()

    for index, block in enumerate(blocks, 1):
        _require(isinstance(block, dict), f"{label}第 {index} 个内容块必须是对象。")
        block_type = block.get("type")
        if block_type == "text":
            text_parts.append(str(block.get("content", "")))
        elif block_type == "latex":
            text_parts.append(_latex_text(str(block.get("content", ""))))
        elif block_type == "image_ref":
            flush_text()
            image_id = block.get("image_id")
            _require(isinstance(image_id, str) and image_id.strip(), f"{label}图片引用缺少 image_id。")
            result.append({"type": "image_ref", "image_id": image_id.strip()})
        else:
            raise ContractError(f"{label}包含项目不支持的内容块类型：{block_type}")
    flush_text()
    _require(result, f"{label}转换后不能为空。")
    _require(result[0].get("type") == "paragraph", f"{label}首块必须是题干段落，不能直接以图片开始。")
    return result


def _project_option(option: Any, *, label: str) -> dict[str, str]:
    _require(isinstance(option, dict), f"{label}必须是对象。")
    option_label = option.get("label")
    _require(isinstance(option_label, str) and option_label.strip(), f"{label}.label 不能为空。")
    content = option.get("content")
    _require(isinstance(content, list) and content, f"{label}.content 不能为空。")
    text_parts: list[str] = []
    image_ids: list[str] = []
    for block in content:
        block_type = block.get("type") if isinstance(block, dict) else None
        if block_type == "text":
            text_parts.append(str(block.get("content", "")))
        elif block_type == "latex":
            text_parts.append(_latex_text(str(block.get("content", ""))))
        elif block_type == "image_ref":
            image_id = block.get("image_id")
            _require(isinstance(image_id, str) and image_id.strip(), f"{label}图片引用缺少 image_id。")
            image_ids.append(image_id.strip())
        else:
            raise ContractError(f"{label}包含项目不支持的内容块类型：{block_type}")
    _require(len(image_ids) <= 1, f"{label}最多只能引用一张选项图片。")
    result = {"label": option_label.strip(), "text": "".join(text_parts).strip()}
    if image_ids:
        result["image_id"] = image_ids[0]
    return result


def _resolve_asset(asset_path: str, asset_base_dir: Path) -> Path:
    path = Path(asset_path)
    return path.resolve() if path.is_absolute() else (asset_base_dir / path).resolve()


def _project_image(image: Any, *, asset_base_dir: Path, label: str) -> dict[str, str]:
    _require(isinstance(image, dict), f"{label}必须是对象。")
    image_id = image.get("image_id")
    alt = image.get("alt_text")
    _require(isinstance(image_id, str) and image_id.strip(), f"{label}.image_id 不能为空。")
    _require(isinstance(alt, str) and alt.strip(), f"{label}.alt_text 不能为空。")
    _require(image.get("status") == "restored", f"{label}尚未恢复，不能进入自包含项目试卷。")
    asset_path = image.get("asset_path")
    _require(isinstance(asset_path, str) and asset_path.strip(), f"{label}.asset_path 不能为空。")

    if asset_path.lstrip().startswith("<svg"):
        return {"id": image_id.strip(), "type": "svg", "alt": alt.strip(), "svg": asset_path.strip()}
    if asset_path.startswith("data:image/"):
        return {"id": image_id.strip(), "type": "image", "alt": alt.strip(), "src": asset_path}

    resolved = _resolve_asset(asset_path, asset_base_dir)
    _require(resolved.is_file(), f"{label}图形资产不存在：{resolved}")
    if resolved.suffix.lower() == ".svg":
        svg = resolved.read_text(encoding="utf-8-sig").strip()
        _require("<svg" in svg and "</svg>" in svg, f"{label}不是有效的 SVG 文件。")
        return {"id": image_id.strip(), "type": "svg", "alt": alt.strip(), "svg": svg}

    mime = mimetypes.guess_type(resolved.name)[0]
    _require(mime is not None and mime.startswith("image/"), f"{label}不是受支持的图片文件：{resolved.name}")
    encoded = base64.b64encode(resolved.read_bytes()).decode("ascii")
    return {
        "id": image_id.strip(),
        "type": "image",
        "alt": alt.strip(),
        "src": f"data:{mime};base64,{encoded}",
    }


def _project_points(question: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    knowledge_points: list[dict[str, str]] = []
    primary_code: str | None = None
    for point in question["knowledge_points"]:
        role = "primary" if point["is_primary"] else "secondary"
        if role == "primary":
            primary_code = point["code"]
        knowledge_points.append({"code": point["code"], "label": point["name"], "role": role})

    items = question["target_exam_scope"]["syllabus_items"]
    syllabus_points: list[dict[str, str]] = []
    has_matching_primary = any(item["code"] == primary_code for item in items)
    for index, item in enumerate(items):
        role = "primary" if item["code"] == primary_code or (not has_matching_primary and index == 0) else "secondary"
        syllabus_points.append({"code": item["code"], "label": item["label"], "role": role})
    return syllabus_points, knowledge_points


def _project_question(
    question: dict[str, Any],
    *,
    number: int,
    year: int,
    asset_base_dir: Path,
) -> dict[str, Any]:
    content_blocks = _project_content_blocks(question["title"], label=f"第 {number} 题题干")
    title = content_blocks[0]["text"]
    options = [
        _project_option(option, label=f"第 {number} 题选项 {index}")
        for index, option in enumerate(question["options"], 1)
    ]
    raw_answer = question["answer"]
    answer = [str(item) for item in raw_answer] if isinstance(raw_answer, list) else [str(raw_answer)]
    question_type = "short_answer"
    if question["question_type"] == "multiple_choice":
        question_type = "single_choice" if len(answer) == 1 else "multiple_choice"
    syllabus_points, knowledge_points = _project_points(question)
    analysis = question["learning_analysis"]
    images = [
        _project_image(image, asset_base_dir=asset_base_dir, label=f"第 {number} 题图形 {index}")
        for index, image in enumerate(question["images"], 1)
    ]

    result = {
        "code": question["code"],
        "number": number,
        "title": title,
        "content_blocks": content_blocks,
        "options": options,
        "answer": answer,
        "images": images,
        "examType": "ESAT",
        "source_examType": question["source_examType"],
        "year": year,
        "topic": question["topic"],
        "topic_code": question["topic_code"],
        "question_type": question_type,
        "difficulty": question["difficulty"],
        "syllabus_points": syllabus_points,
        "knowledge_points": knowledge_points,
        "learning_analysis": {
            "exam_focus": analysis["exam_focus"],
            "solution": analysis["correct_solution"],
            "review_guidance": analysis["review_guidance"],
        },
    }
    _require(set(result) == PROJECT_QUESTION_FIELDS, "项目题目导出字段集合异常。")
    return result


def _project_module_groups(
    assembled_document: dict[str, Any],
    *,
    year: int,
    asset_base_dir: Path,
) -> list[dict[str, Any]]:
    assembly = assembled_document["metadata"].get("assembly")
    _require(isinstance(assembly, dict), "assembled_exam.metadata.assembly 必须是对象。")
    sections = assembly.get("sections")
    _require(isinstance(sections, list) and sections, "assembled_exam 必须包含非空模块段。")

    by_module: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for question in assembled_document["questions"]:
        assembled_section = question.get("assembled_section")
        _require(isinstance(assembled_section, dict), f"{question.get('code')} 缺少 assembled_section。")
        module = assembled_section.get("module")
        question_order = assembled_section.get("question_order")
        _require(isinstance(module, str) and module.strip(), f"{question.get('code')} 缺少组卷模块。")
        _require(isinstance(question_order, int) and not isinstance(question_order, bool) and question_order > 0, f"{question.get('code')} 模块内题号无效。")
        by_module.setdefault(module, []).append((question_order, question))

    ordered_sections: list[tuple[int, dict[str, Any]]] = []
    section_modules: set[str] = set()
    for section in sections:
        _require(isinstance(section, dict), "assembled_exam 模块段必须是对象。")
        module = section.get("module")
        section_order = section.get("section_order")
        _require(isinstance(module, str) and module.strip(), "assembled_exam 模块段缺少 module。")
        _require(module not in section_modules, f"assembled_exam 模块段重复：{module}")
        _require(isinstance(section_order, int) and not isinstance(section_order, bool) and section_order > 0, f"{module} section_order 无效。")
        section_modules.add(module)
        ordered_sections.append((section_order, section))
    _require(set(by_module) <= section_modules, f"存在未声明模块的题目：{sorted(set(by_module) - section_modules)}")

    groups: list[dict[str, Any]] = []
    for _, section in sorted(ordered_sections, key=lambda item: item[0]):
        module = section["module"]
        module_code = section.get("module_code")
        duration = section.get("official_time_minutes")
        _require(isinstance(module_code, str) and module_code.strip(), f"{module} 缺少 module_code。")
        _require(isinstance(duration, int) and not isinstance(duration, bool) and duration > 0, f"{module} 模块时长无效。")
        source_items = sorted(by_module.get(module, []), key=lambda item: item[0])
        orders = [item[0] for item in source_items]
        _require(orders == list(range(1, len(source_items) + 1)), f"{module} 模块内题号必须从 1 连续编号。")
        items = [
            _project_question(
                question,
                number=index,
                year=year,
                asset_base_dir=asset_base_dir,
            )
            for index, (_, question) in enumerate(source_items, 1)
        ]
        group = {
            "subject": module,
            "subject_code": module_code,
            "duration": duration,
            "items": items,
        }
        _require(set(group) == PROJECT_MODULE_FIELDS, f"{module} 模块导出字段集合异常。")
        groups.append(group)

    _require(sum(len(group["items"]) for group in groups) == len(assembled_document["questions"]), "模块分组后的题目总数不一致。")
    return groups


def validate_project_diagnostic_paper(document: Any) -> None:
    """校验采用模块分组结构的项目诊断卷 JSON。"""

    _require(isinstance(document, dict) and set(document) == {"code", "metadata", "questions"}, "项目诊断卷根字段必须且只能包含 code、metadata、questions。")
    _require(isinstance(document["code"], str) and document["code"].strip(), "项目诊断卷 code 不能为空。")
    metadata = document["metadata"]
    _require(isinstance(metadata, dict) and set(metadata) == {"paperName", "year", "duration", "examType", "paperType", "totalQuestions", "remarks"}, "项目诊断卷 metadata 字段不完整。")
    _require(isinstance(metadata["paperName"], str) and metadata["paperName"].strip(), "metadata.paperName 不能为空。")
    _require(isinstance(metadata["year"], int) and not isinstance(metadata["year"], bool), "metadata.year 必须是数字年份。")
    _require(isinstance(metadata["duration"], int) and metadata["duration"] > 0, "metadata.duration 必须是正整数分钟。")
    _require(metadata["examType"] == "ESAT", "metadata.examType 必须是 ESAT。")
    _require(metadata["paperType"] in PROJECT_PAPER_TYPES, "metadata.paperType 必须是 realPaper、mockPaper 或 aiPaper。")
    _require(metadata["paperType"] == "realPaper", "由真实 ENGAA/NSAA 题目组成的 ESAT 诊断卷必须是 realPaper。")
    _require(isinstance(metadata["totalQuestions"], int) and not isinstance(metadata["totalQuestions"], bool) and metadata["totalQuestions"] > 0, "metadata.totalQuestions 必须是正整数。")
    _require(isinstance(metadata["remarks"], str) and metadata["remarks"].strip(), "metadata.remarks 不能为空。")
    groups = document["questions"]
    _require(isinstance(groups, list) and groups, "questions 必须是非空模块数组。")

    codes: set[str] = set()
    subjects: set[str] = set()
    subject_codes: set[str] = set()
    total_questions = 0
    total_duration = 0
    for group_index, group in enumerate(groups, 1):
        module_label = f"questions[{group_index - 1}]"
        _require(isinstance(group, dict) and set(group) == PROJECT_MODULE_FIELDS, f"{module_label} 必须且只能包含 subject、subject_code、duration、items。")
        subject = group["subject"]
        subject_code = group["subject_code"]
        _require(isinstance(subject, str) and subject.strip(), f"{module_label}.subject 不能为空。")
        _require(isinstance(subject_code, str) and subject_code.strip(), f"{module_label}.subject_code 不能为空。")
        _require(subject not in subjects and subject_code not in subject_codes, f"{module_label} 模块重复。")
        subjects.add(subject)
        subject_codes.add(subject_code)
        _require(group["duration"] == 40, f"{module_label}.duration 必须固定为 40。")
        items = group["items"]
        _require(isinstance(items, list), f"{module_label}.items 必须是数组。")
        total_duration += group["duration"]
        total_questions += len(items)

        for index, question in enumerate(items, 1):
            label = f"{subject} 第 {index} 题"
            _require(isinstance(question, dict) and set(question) == PROJECT_QUESTION_FIELDS, f"{label}字段集合不符合项目契约。")
            _require(question["number"] == index, f"{label}.number 必须在模块内从 1 连续编号。")
            _require(question["code"] not in codes, f"{label}.code 在同一试卷中重复。")
            codes.add(question["code"])
            _require(question["examType"] == "ESAT", f"{label}.examType 必须是 ESAT。")
            _require(question["source_examType"] in {"ENGAA", "NSAA"}, f"{label}.source_examType 必须是 ENGAA 或 NSAA。")
            _require(question["year"] == metadata["year"], f"{label}.year 与试卷年份不一致。")
            _require(question["question_type"] in {"single_choice", "multiple_choice", "short_answer"}, f"{label}.question_type 不受支持。")
            _require(question["difficulty"] in PROJECT_DIFFICULTIES, f"{label}.difficulty 不受支持。")
            _require(isinstance(question["answer"], list) and question["answer"], f"{label}.answer 必须是非空数组。")
            _require(isinstance(question["content_blocks"], list) and question["content_blocks"], f"{label}.content_blocks 不能为空。")
            first = question["content_blocks"][0]
            _require(first == {"type": "paragraph", "text": question["title"]}, f"{label}.title 必须等于首个 paragraph。")
            image_ids = {item["id"] for item in question["images"]}
            referenced_ids = {
                block["image_id"]
                for block in question["content_blocks"]
                if block["type"] == "image_ref"
            }
            referenced_ids.update(option["image_id"] for option in question["options"] if "image_id" in option)
            _require(referenced_ids <= image_ids, f"{label}存在未定义的图片引用。")
            _require(all(item.get("type") in {"svg", "image"} and item.get("id") and item.get("alt") for item in question["images"]), f"{label}.images 结构无效。")
            _require(all((item["type"] == "svg" and isinstance(item.get("svg"), str)) or (item["type"] == "image" and isinstance(item.get("src"), str)) for item in question["images"]), f"{label}.images 缺少自包含资源。")

    _require(total_questions > 0, "项目诊断卷至少需要一道题。")
    _require(metadata["totalQuestions"] == total_questions, "metadata.totalQuestions 必须等于所有模块 items.length 之和。")
    _require(metadata["duration"] == total_duration, "metadata.duration 必须等于所有模块 duration 之和。")


def build_project_diagnostic_paper(
    assembled_document: dict[str, Any],
    *,
    paper_code: str,
    asset_base_dir: str | Path,
) -> dict[str, Any]:
    """把内部 assembled_exam 投影成按模块分组的项目诊断卷 JSON。"""

    _require(assembled_document.get("document_type") == "assembled_exam", "只能从 assembled_exam 导出项目诊断卷。")
    _require(assembled_document.get("validation_status") == "passed", "assembled_exam 尚未通过内部校验。")
    metadata = assembled_document["metadata"]
    year = _as_year(metadata["year"])
    assembly = metadata.get("assembly")
    remarks = _project_remarks(assembly)
    paper_type = metadata.get("paper_type", "realPaper")
    _require(paper_type == "realPaper", "真实 ENGAA/NSAA 题目重组的 ESAT 诊断卷必须导出为 realPaper。")
    groups = _project_module_groups(
        assembled_document,
        year=year,
        asset_base_dir=Path(asset_base_dir).resolve(),
    )
    total_questions = sum(len(group["items"]) for group in groups)
    document = {
        "code": paper_code,
        "metadata": {
            "paperName": metadata["title"],
            "year": year,
            "duration": assembly["official_full_test_time_minutes"],
            "examType": "ESAT",
            "paperType": paper_type,
            "totalQuestions": total_questions,
            "remarks": remarks,
        },
        "questions": groups,
    }
    validate_project_diagnostic_paper(document)
    return document
