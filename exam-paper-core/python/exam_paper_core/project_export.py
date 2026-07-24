"""Export canonical assembled exams to the project diagnostic-paper format."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .content_blocks import from_structured_parts, inline_latex
from .contract import ContractError


PROJECT_METADATA_FIELDS = {
    "code",
    "title",
    "examType",
    "year",
    "paperType",
    "assemblyType",
    "deliveryMode",
    "remarks",
}
PROJECT_SECTION_FIELDS = {
    "code",
    "sectionType",
    "order",
    "questions",
}
PROJECT_QUESTION_FIELDS = {
    "code",
    "number",
    "title",
    "contentBlocks",
    "options",
    "answer",
    "images",
    "questionType",
    "difficulty",
    "classification",
    "source",
    "learningAnalysis",
}
PROJECT_PAPER_TYPES = {"realPaper", "mockPaper", "aiPaper"}
PROJECT_DIFFICULTIES = {"easy", "medium", "hard", "composite"}
ESAT_SECTION_CODES = {
    "Mathematics 1": "maths1",
    "Mathematics 2": "maths2",
    "Physics": "physics",
    "Chemistry": "chemistry",
    "Biology": "biology",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _as_year(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ContractError("Project paper year must be an integer.")


def _project_remarks(assembly: Any) -> str:
    _require(isinstance(assembly, dict), "assembled_exam.metadata.assembly must be an object.")
    sections = assembly.get("sections")
    _require(isinstance(sections, list) and sections, "assembled_exam must contain sections.")

    notes: list[str] = []
    for index, section in enumerate(sections, 1):
        _require(isinstance(section, dict), f"assembly.sections[{index - 1}] must be an object.")
        module = section.get("module_label") or section.get("module")
        actual = section.get("actual_question_count")
        target = section.get("target_question_count")
        flags = section.get("diagnostic_flags", [])
        confidence = section.get("diagnostic_confidence")
        _require(isinstance(module, str) and module.strip(), f"Section {index} has no module name.")
        _require(isinstance(actual, int) and not isinstance(actual, bool) and actual >= 0, f"{module} has invalid actual count.")
        _require(isinstance(target, int) and not isinstance(target, bool) and target > 0, f"{module} has invalid target count.")
        _require(isinstance(flags, list), f"{module}.diagnostic_flags must be an array.")
        _require(confidence in {"high", "medium", "low"}, f"{module} has invalid diagnostic confidence.")

        confidence_label = {"high": "高", "medium": "中", "low": "低"}[confidence]
        details = [f"实际 {actual}/{target} 题"]
        if actual < target:
            details.append(f"题量不足 {target - actual} 题")
        if "narrow_coverage" in flags:
            details.append("考纲覆盖偏窄")
        if "source_skewed" in flags:
            details.append("题源分布偏斜")
        details.append(f"诊断可信度{confidence_label}")
        notes.append(f"{module}：" + "，".join(details))

    return "管理员备注：" + "；".join(notes) + "。"


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
    return inline_latex(text)


def _project_content_blocks(blocks: Any, *, label: str) -> list[dict[str, Any]]:
    _require(isinstance(blocks, list) and blocks, f"{label} must contain structured content.")
    try:
        result = from_structured_parts(blocks)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{label} has invalid layout semantics: {exc}") from exc
    _require(result, f"{label} cannot be empty.")
    _require(result[0].get("type") == "paragraph", f"{label} must begin with a paragraph.")
    return result


def _project_option(option: Any, *, label: str) -> dict[str, str]:
    _require(isinstance(option, dict), f"{label} must be an object.")
    option_label = option.get("label")
    _require(isinstance(option_label, str) and option_label.strip(), f"{label}.label cannot be empty.")
    content = option.get("content")
    _require(isinstance(content, list) and content, f"{label}.content cannot be empty.")
    text_parts: list[str] = []
    image_ids: list[str] = []
    for block in content:
        block_type = block.get("type") if isinstance(block, dict) else None
        if block_type == "text":
            text_parts.append(str(block.get("content", "")))
        elif block_type == "latex":
            _require(block.get("mode") == "inline", f"{label} option math must be inline.")
            text_parts.append(_latex_text(str(block.get("content", ""))))
        elif block_type == "image_ref":
            image_id = block.get("image_id")
            _require(isinstance(image_id, str) and image_id.strip(), f"{label} image reference has no image_id.")
            image_ids.append(image_id.strip())
        else:
            raise ContractError(f"{label} contains unsupported block type: {block_type}")
    _require(len(image_ids) <= 1, f"{label} may reference at most one image.")
    result = {"label": option_label.strip(), "text": "".join(text_parts).strip()}
    if image_ids:
        result["image_id"] = image_ids[0]
    return result


def _resolve_asset(asset_path: str, asset_base_dir: Path) -> Path:
    path = Path(asset_path)
    return path.resolve() if path.is_absolute() else (asset_base_dir / path).resolve()


def _project_image(image: Any, *, asset_base_dir: Path, label: str) -> dict[str, str]:
    _require(isinstance(image, dict), f"{label} must be an object.")
    image_id = image.get("image_id")
    alt = image.get("alt_text")
    _require(isinstance(image_id, str) and image_id.strip(), f"{label}.image_id cannot be empty.")
    _require(isinstance(alt, str) and alt.strip(), f"{label}.alt_text cannot be empty.")
    _require(image.get("status") == "restored", f"{label} is not restored.")
    asset_path = image.get("asset_path")
    _require(isinstance(asset_path, str) and asset_path.strip(), f"{label}.asset_path cannot be empty.")

    if asset_path.lstrip().startswith("<svg"):
        return {"id": image_id.strip(), "type": "svg", "alt": alt.strip(), "svg": asset_path.strip()}
    if asset_path.startswith("data:image/"):
        return {"id": image_id.strip(), "type": "image", "alt": alt.strip(), "src": asset_path}

    resolved = _resolve_asset(asset_path, asset_base_dir)
    _require(resolved.is_file(), f"{label} asset does not exist: {resolved}")
    if resolved.suffix.lower() == ".svg":
        svg = resolved.read_text(encoding="utf-8-sig").strip()
        _require("<svg" in svg and "</svg>" in svg, f"{label} is not valid SVG.")
        return {"id": image_id.strip(), "type": "svg", "alt": alt.strip(), "svg": svg}

    mime = mimetypes.guess_type(resolved.name)[0]
    _require(mime is not None and mime.startswith("image/"), f"{label} is not a supported image.")
    encoded = base64.b64encode(resolved.read_bytes()).decode("ascii")
    return {
        "id": image_id.strip(),
        "type": "image",
        "alt": alt.strip(),
        "src": f"data:{mime};base64,{encoded}",
    }


def _project_knowledge_points(question: dict[str, Any]) -> list[dict[str, str]]:
    points: list[dict[str, str]] = []
    for point in question["knowledge_points"]:
        points.append(
            {
                "code": point["code"],
                "label": point["name"],
                "role": "primary" if point["is_primary"] else "secondary",
            }
        )
    return points


def _project_question(
    question: dict[str, Any],
    *,
    number: int,
    year: int,
    section_code: str,
    asset_base_dir: Path,
) -> dict[str, Any]:
    content_blocks = _project_content_blocks(question["title"], label=f"Question {number} title")
    title = content_blocks[0]["text"]
    options = [
        _project_option(option, label=f"Question {number} option {index}")
        for index, option in enumerate(question["options"], 1)
    ]
    raw_answer = question["answer"]
    answer = [str(item) for item in raw_answer] if isinstance(raw_answer, list) else [str(raw_answer)]
    question_type = "short_answer"
    if question["question_type"] == "multiple_choice":
        question_type = "single_choice" if len(answer) == 1 else "multiple_choice"
    analysis = question["learning_analysis"]
    images = [
        _project_image(image, asset_base_dir=asset_base_dir, label=f"Question {number} image {index}")
        for index, image in enumerate(question["images"], 1)
    ]

    result = {
        "code": question["code"],
        "number": number,
        "title": title,
        "contentBlocks": content_blocks,
        "options": options,
        "answer": answer,
        "images": images,
        "questionType": question_type,
        "difficulty": question["difficulty"],
        "classification": {
            "subject": question["subject"],
            "subjectCode": question["subject_code"],
            "topic": question["topic"],
            "topicCode": question["topic_code"],
            "knowledgePoints": _project_knowledge_points(question),
        },
        "source": {
            "examType": question["source_examType"],
            "year": year,
            "sectionCode": section_code,
            "questionNumber": question["questionNumber"],
        },
        "learningAnalysis": {
            "correctSolution": analysis["correct_solution"],
            "examFocus": analysis["exam_focus"],
            "commonErrorCauses": analysis["common_error_causes"],
            "reviewGuidance": analysis["review_guidance"],
        },
    }
    _require(set(result) == PROJECT_QUESTION_FIELDS, "Unexpected project question fields.")
    return result


def _project_sections(
    assembled_document: dict[str, Any],
    *,
    year: int,
    asset_base_dir: Path,
) -> list[dict[str, Any]]:
    assembly = assembled_document["metadata"].get("assembly")
    _require(isinstance(assembly, dict), "assembled_exam.metadata.assembly must be an object.")
    source_sections = assembly.get("sections")
    _require(isinstance(source_sections, list) and source_sections, "assembled_exam must contain sections.")

    by_module: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for question in assembled_document["questions"]:
        assembled_section = question.get("assembled_section")
        _require(isinstance(assembled_section, dict), f"{question.get('code')} has no assembled_section.")
        module = assembled_section.get("module")
        question_order = assembled_section.get("question_order")
        _require(isinstance(module, str) and module.strip(), f"{question.get('code')} has no module.")
        _require(isinstance(question_order, int) and question_order > 0, f"{question.get('code')} has invalid module order.")
        by_module.setdefault(module, []).append((question_order, question))

    ordered_sections: list[tuple[int, dict[str, Any]]] = []
    seen_modules: set[str] = set()
    for section in source_sections:
        _require(isinstance(section, dict), "Assembly section must be an object.")
        module = section.get("module")
        order = section.get("section_order")
        _require(isinstance(module, str) and module.strip(), "Assembly section has no module.")
        _require(module not in seen_modules, f"Duplicate assembly section: {module}")
        _require(isinstance(order, int) and order > 0, f"{module} has invalid section_order.")
        seen_modules.add(module)
        ordered_sections.append((order, section))
    _require(set(by_module) <= seen_modules, "Questions reference undeclared modules.")

    sections: list[dict[str, Any]] = []
    sorted_sections = sorted(ordered_sections, key=lambda item: item[0])
    for position, (_, source_section) in enumerate(sorted_sections, 1):
        module = source_section["module"]
        section_code = ESAT_SECTION_CODES.get(module)
        _require(section_code is not None, f"Unsupported ESAT section: {module}")
        source_items = sorted(by_module.get(module, []), key=lambda item: item[0])
        orders = [item[0] for item in source_items]
        _require(orders == list(range(1, len(source_items) + 1)), f"{module} question order must be contiguous.")
        questions = [
            _project_question(
                question,
                number=index,
                year=year,
                section_code=section_code,
                asset_base_dir=asset_base_dir,
            )
            for index, (_, question) in enumerate(source_items, 1)
        ]
        section = {
            "code": section_code,
            "sectionType": "subject",
            "order": position,
            "questions": questions,
        }
        _require(set(section) == PROJECT_SECTION_FIELDS, f"{module} has unexpected section fields.")
        sections.append(section)

    _require(sum(len(section["questions"]) for section in sections) == len(assembled_document["questions"]), "Exported question count mismatch.")
    return sections


def validate_project_diagnostic_paper(document: Any) -> None:
    """Validate the unified metadata + sections project import format."""

    _require(isinstance(document, dict) and set(document) == {"metadata", "sections"}, "Root fields must be metadata and sections.")
    metadata = document["metadata"]
    _require(isinstance(metadata, dict) and set(metadata) == PROJECT_METADATA_FIELDS, "Invalid metadata fields.")
    _require(isinstance(metadata["code"], str) and metadata["code"].strip(), "metadata.code cannot be empty.")
    _require(isinstance(metadata["title"], str) and metadata["title"].strip(), "metadata.title cannot be empty.")
    _require(metadata["examType"] in {"ESAT", "TMUA"}, "metadata.examType must be ESAT or TMUA.")
    _require(isinstance(metadata["year"], int) and not isinstance(metadata["year"], bool), "metadata.year must be an integer.")
    _require(metadata["paperType"] in PROJECT_PAPER_TYPES, "Unsupported metadata.paperType.")
    _require(metadata["deliveryMode"] == "section_sequence", "metadata.deliveryMode must be section_sequence.")
    _require(
        metadata["assemblyType"] == ("legacy_equivalent" if metadata["examType"] == "ESAT" else "original"),
        "metadata.assemblyType does not match examType.",
    )
    _require(isinstance(metadata["remarks"], str) and metadata["remarks"].strip(), "metadata.remarks cannot be empty.")

    sections = document["sections"]
    _require(isinstance(sections, list) and sections, "sections must be a non-empty array.")
    expected_section_type = "subject" if metadata["examType"] == "ESAT" else "paper"
    codes: set[str] = set()
    section_codes: set[str] = set()
    total_questions = 0
    for section_index, section in enumerate(sections, 1):
        label = f"sections[{section_index - 1}]"
        _require(isinstance(section, dict) and set(section) == PROJECT_SECTION_FIELDS, f"{label} has invalid fields.")
        _require(isinstance(section["code"], str) and section["code"].strip(), f"{label}.code cannot be empty.")
        _require(section["code"] not in section_codes, f"{label}.code is duplicated.")
        section_codes.add(section["code"])
        _require(section["sectionType"] == expected_section_type, f"{label}.sectionType is invalid.")
        _require(section["order"] == section_index, f"{label}.order must be contiguous.")
        questions = section["questions"]
        _require(isinstance(questions, list), f"{label}.questions must be an array.")
        total_questions += len(questions)
        for number, question in enumerate(questions, 1):
            question_label = f"{label}.questions[{number - 1}]"
            _require(isinstance(question, dict) and set(question) == PROJECT_QUESTION_FIELDS, f"{question_label} has invalid fields.")
            _require(question["number"] == number, f"{question_label}.number must be contiguous.")
            _require(isinstance(question["code"], str) and question["code"] not in codes, f"{question_label}.code is invalid or duplicated.")
            codes.add(question["code"])
            _require(question["questionType"] in {"single_choice", "multiple_choice", "short_answer"}, f"{question_label}.questionType is invalid.")
            _require(question["difficulty"] in PROJECT_DIFFICULTIES, f"{question_label}.difficulty is invalid.")
            _require(isinstance(question["answer"], list) and question["answer"], f"{question_label}.answer cannot be empty.")
            blocks = question["contentBlocks"]
            _require(isinstance(blocks, list) and blocks, f"{question_label}.contentBlocks cannot be empty.")
            for block_index, block in enumerate(blocks):
                block_label = f"{question_label}.contentBlocks[{block_index}]"
                _require(isinstance(block, dict), f"{block_label} must be an object.")
                if block.get("type") == "paragraph":
                    expected = {"type", "text"}
                    if "align" in block:
                        expected.add("align")
                        _require(block["align"] in {"left", "center", "right"}, f"{block_label}.align is invalid.")
                    _require(set(block) == expected, f"{block_label} has invalid fields.")
                    text = block.get("text")
                    _require(isinstance(text, str) and text.strip(), f"{block_label}.text cannot be empty.")
                    _require(text.strip() not in {".", ",", "?", "!", ":", ";"}, f"{block_label} cannot contain punctuation only.")
                elif block.get("type") == "image_ref":
                    _require(
                        isinstance(block.get("image_id"), str) and block["image_id"].strip(),
                        f"{block_label}.image_id cannot be empty.",
                    )
                else:
                    raise ContractError(f"{block_label}.type is invalid.")
            _require(blocks[0] == {"type": "paragraph", "text": question["title"]}, f"{question_label}.title must equal the first paragraph.")
            classification = question["classification"]
            _require(
                isinstance(classification, dict)
                and set(classification) == {"subject", "subjectCode", "topic", "topicCode", "knowledgePoints"},
                f"{question_label}.classification is invalid.",
            )
            source = question["source"]
            _require(
                isinstance(source, dict)
                and set(source) == {"examType", "year", "sectionCode", "questionNumber"}
                and source["year"] == metadata["year"]
                and source["sectionCode"] == section["code"],
                f"{question_label}.source is invalid.",
            )
            analysis = question["learningAnalysis"]
            _require(
                isinstance(analysis, dict)
                and set(analysis) == {"correctSolution", "examFocus", "commonErrorCauses", "reviewGuidance"}
                and isinstance(analysis["commonErrorCauses"], list),
                f"{question_label}.learningAnalysis is invalid.",
            )
            image_ids = {item["id"] for item in question["images"]}
            referenced_ids = {
                block["image_id"]
                for block in blocks
                if block.get("type") == "image_ref"
            }
            referenced_ids.update(option["image_id"] for option in question["options"] if "image_id" in option)
            _require(referenced_ids <= image_ids, f"{question_label} references undefined images.")
    _require(total_questions > 0, "Project paper must contain at least one question.")


def build_project_diagnostic_paper(
    assembled_document: dict[str, Any],
    *,
    paper_code: str,
    asset_base_dir: str | Path,
) -> dict[str, Any]:
    """Project an internal ESAT assembled_exam into the unified import format."""

    _require(assembled_document.get("document_type") == "assembled_exam", "Only assembled_exam can be exported.")
    _require(assembled_document.get("validation_status") == "passed", "assembled_exam has not passed validation.")
    metadata = assembled_document["metadata"]
    year = _as_year(metadata["year"])
    assembly = metadata.get("assembly")
    paper_type = metadata.get("paper_type", "realPaper")
    _require(paper_type == "realPaper", "Legacy ENGAA/NSAA diagnostic papers must be realPaper.")
    sections = _project_sections(
        assembled_document,
        year=year,
        asset_base_dir=Path(asset_base_dir).resolve(),
    )
    document = {
        "metadata": {
            "code": paper_code,
            "title": metadata["title"],
            "examType": "ESAT",
            "year": year,
            "paperType": paper_type,
            "assemblyType": "legacy_equivalent",
            "deliveryMode": "section_sequence",
            "remarks": _project_remarks(assembly),
        },
        "sections": sections,
    }
    validate_project_diagnostic_paper(document)
    return document
