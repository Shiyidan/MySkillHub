"""跨试卷重复题检测、保守合并和审计报告。"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from .fingerprint import (
    canonicalize_fingerprint_payload,
    fingerprint_payload,
    normalize_fingerprint_value,
    question_fingerprint,
)


REPORT_VERSION = "1"
NEAR_DUPLICATE_THRESHOLD = 0.96


def _image_index(question: dict[str, Any]) -> dict[str, dict[str, Any]]:
    images = question.get("images")
    if not isinstance(images, list):
        return {}
    return {
        item["image_id"]: item
        for item in images
        if isinstance(item, dict) and isinstance(item.get("image_id"), str)
    }


def _blocks_payload(
    blocks: Any,
    image_index: dict[str, dict[str, Any]],
) -> tuple[list[Any], bool]:
    if not isinstance(blocks, list):
        return [], False
    payload: list[Any] = []
    unresolved_visual = False
    for block in blocks:
        if not isinstance(block, dict):
            payload.append(block)
            continue
        block_type = block.get("type")
        if block_type != "image_ref":
            payload.append({"type": block_type, "content": block.get("content")})
            continue
        unresolved_visual = True
        image = image_index.get(str(block.get("image_id")), {})
        alt_text = image.get("alt_text") if isinstance(image, dict) else None
        payload.append(
            {
                "type": "image_ref",
                "role": image.get("role") if isinstance(image, dict) else None,
                "alt_text": alt_text,
            }
        )
    return payload, unresolved_visual


def _content_keys(question: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    title = question.get("title")
    options = question.get("options")
    if not isinstance(title, list) or not title or not isinstance(options, list):
        return None, None, False

    images = _image_index(question)
    title_payload, unresolved_visual = _blocks_payload(title, images)
    option_payloads: list[Any] = []
    for option in options:
        content = option.get("content") if isinstance(option, dict) else option
        option_payload, option_unresolved = _blocks_payload(content, images)
        unresolved_visual = unresolved_visual or option_unresolved
        option_payloads.append(option_payload)

    diagram = question.get("diagram")
    diagram_semantics = diagram.get("semantics") if isinstance(diagram, dict) else None
    if unresolved_visual and isinstance(diagram_semantics, str) and diagram_semantics.strip():
        unresolved_visual = False
    stem_payload = {
        "title": title_payload,
        "diagram_semantics": diagram_semantics,
    }
    content_payload = {
        "stem": stem_payload,
        "options": sorted(
            canonicalize_fingerprint_payload(option) for option in option_payloads
        ),
    }
    return (
        fingerprint_payload(stem_payload),
        fingerprint_payload(content_payload),
        unresolved_visual,
    )


def _computed_fingerprint(question: dict[str, Any]) -> str | None:
    fingerprint = question.get("fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return fingerprint
    if isinstance(question.get("title"), list) and isinstance(question.get("options"), list):
        return question_fingerprint(question)
    return None


def _answer_payload(question: dict[str, Any]) -> Any:
    answer = question.get("answer")
    options = question.get("options")
    if isinstance(options, list):
        images = _image_index(question)
        for option in options:
            if isinstance(option, dict) and option.get("label") == answer:
                content, _ = _blocks_payload(option.get("content"), images)
                return {"kind": "option_content", "content": content}
    return {"kind": "literal", "answer": answer}


def _classification_payload(question: dict[str, Any]) -> Any:
    scope = question.get("target_exam_scope")
    normalized_scope = None
    if isinstance(scope, dict):
        normalized_scope = {
            "target_exam": scope.get("target_exam"),
            "scope_status": scope.get("scope_status"),
            "modules": scope.get("modules"),
            "syllabus_codes": scope.get("syllabus_codes"),
        }
    knowledge_points = question.get("knowledge_points")
    knowledge_codes = []
    if isinstance(knowledge_points, list):
        knowledge_codes = sorted(
            str(item.get("code"))
            for item in knowledge_points
            if isinstance(item, dict) and item.get("code") is not None
        )
    return {
        "question_type": question.get("question_type"),
        "subject": question.get("subject"),
        "subject_code": question.get("subject_code"),
        "topic_code": question.get("topic_code"),
        "syllabus_tags": sorted(str(item) for item in question.get("syllabus_tags", []) or []),
        "knowledge_codes": knowledge_codes,
        "target_exam_scope": normalized_scope,
    }


def _occurrence(question: dict[str, Any]) -> dict[str, Any]:
    source = question.get("source")
    parsed_source = source if isinstance(source, dict) and "question" in source else {}
    return {
        "code": str(question.get("code") or question.get("question_id") or "unknown"),
        "source_exam_type": question.get("source_examType"),
        "question_number": question.get("questionNumber") or question.get("number"),
        "question_source": parsed_source.get("question"),
        "answer_source": parsed_source.get("answer"),
        "evidence_packet": parsed_source.get("evidence_packet"),
    }


def _keeper_sort_key(question: dict[str, Any]) -> tuple[int, int, int, int, str]:
    scope = question.get("target_exam_scope")
    mapping_status = scope.get("mapping_status") if isinstance(scope, dict) else None
    mapping_rank = {"human_verified": 3, "auto_verified": 2, "needs_review": 1}.get(mapping_status, 0)
    source = question.get("source")
    has_solution = int(isinstance(source, dict) and source.get("solution") is not None)
    has_diagram = int(isinstance(question.get("diagram"), dict))
    explanation_length = len(str(question.get("explanation") or ""))
    code = str(question.get("code") or question.get("question_id") or "")
    return (-mapping_rank, -has_solution, -has_diagram, -explanation_length, code)


def _stem_text(question: dict[str, Any]) -> str:
    parts: list[str] = []
    title = question.get("title")
    if not isinstance(title, list):
        return ""
    for block in title:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "image_ref":
            parts.append("<image>")
        else:
            parts.append(str(block.get("content") or ""))
    return str(normalize_fingerprint_value(" ".join(parts)))


def _conflict_record(group: list[dict[str, Any]], *, answer_match: bool, classification_match: bool) -> dict[str, Any]:
    reasons: list[str] = []
    if not answer_match:
        reasons.append("answer_mismatch")
    if not classification_match:
        reasons.append("classification_mismatch")
    return {
        "reason": "+".join(reasons),
        "codes": [str(item.get("code") or item.get("question_id")) for item in group],
        "occurrences": [_occurrence(item) for item in group],
        "checks": {
            "stem_and_options": "matched",
            "answer": "matched" if answer_match else "conflict",
            "classification": "matched" if classification_match else "conflict",
        },
    }


def deduplicate_questions(
    questions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """只合并证据一致的重复题；疑似题保留，冲突题交由人工处理。"""

    stem_keys: dict[str, str | None] = {}
    content_keys: dict[str, str | None] = {}
    unresolved_visuals: dict[str, bool] = {}
    fingerprints: dict[str, str | None] = {}
    question_by_code: dict[str, dict[str, Any]] = {}
    parent = list(range(len(questions)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    key_owner: dict[str, int] = {}

    for index, question in enumerate(questions):
        code = str(question.get("code") or question.get("question_id") or f"index:{index}")
        question_by_code[code] = question
        stem_key, content_key, unresolved_visual = _content_keys(question)
        fingerprint = _computed_fingerprint(question)
        stem_keys[code] = stem_key
        content_keys[code] = content_key
        unresolved_visuals[code] = unresolved_visual
        fingerprints[code] = fingerprint
        keys: list[str] = []
        if content_key is not None:
            keys.append(f"content:{content_key}")
        if fingerprint is not None:
            keys.append(f"fingerprint:{fingerprint}")
        for key in keys:
            owner = key_owner.get(key)
            if owner is None:
                key_owner[key] = index
            else:
                union(owner, index)

    groups: dict[int, list[dict[str, Any]]] = {}
    for index, question in enumerate(questions):
        groups.setdefault(find(index), []).append(question)

    excluded_codes: set[str] = set()
    confirmed_duplicates: list[dict[str, Any]] = []
    blocking_conflicts: list[dict[str, Any]] = []

    for group in groups.values():
        if len(group) < 2:
            continue
        group_codes = [str(item.get("code") or item.get("question_id")) for item in group]
        answer_match = len(
            {
                canonicalize_fingerprint_payload(_answer_payload(item))
                for item in group
            }
        ) == 1
        classification_match = len(
            {
                canonicalize_fingerprint_payload(_classification_payload(item))
                for item in group
            }
        ) == 1
        exact_fingerprints = {fingerprints[code] for code in group_codes}
        exact_match = len(exact_fingerprints) == 1 and None not in exact_fingerprints
        unresolved_visual = any(unresolved_visuals[code] for code in group_codes)

        if not answer_match or not classification_match:
            blocking_conflicts.append(
                _conflict_record(
                    group,
                    answer_match=answer_match,
                    classification_match=classification_match,
                )
            )
            continue
        if unresolved_visual and not exact_match:
            continue

        keeper = sorted(group, key=_keeper_sort_key)[0]
        keeper_code = str(keeper.get("code") or keeper.get("question_id"))
        for duplicate in group:
            duplicate_code = str(duplicate.get("code") or duplicate.get("question_id"))
            if duplicate_code == keeper_code:
                continue
            excluded_codes.add(duplicate_code)
            confirmed_duplicates.append(
                {
                    "excluded_code": duplicate_code,
                    "kept_code": keeper_code,
                    "reason": "exact_fingerprint" if fingerprints[duplicate_code] == fingerprints[keeper_code] else "equivalent_content",
                    "kept_occurrence": _occurrence(keeper),
                    "excluded_occurrence": _occurrence(duplicate),
                    "checks": {
                        "stem_and_options": "matched",
                        "answer": "matched",
                        "classification": "matched",
                    },
                }
            )

    unique = [
        question
        for question in questions
        if str(question.get("code") or question.get("question_id")) not in excluded_codes
    ]

    review_candidates: list[dict[str, Any]] = []
    review_pairs: set[tuple[str, str]] = set()

    def add_review_pair(left: dict[str, Any], right: dict[str, Any], reason: str, similarity: float | None = None) -> None:
        left_code = str(left.get("code") or left.get("question_id"))
        right_code = str(right.get("code") or right.get("question_id"))
        pair = tuple(sorted((left_code, right_code)))
        if pair in review_pairs:
            return
        review_pairs.add(pair)
        record: dict[str, Any] = {
            "reason": reason,
            "codes": list(pair),
            "occurrences": [_occurrence(question_by_code[code]) for code in pair],
            "action": "retained_for_review",
        }
        if similarity is not None:
            record["stem_similarity"] = round(similarity, 4)
        review_candidates.append(record)

    stem_groups: dict[str, list[dict[str, Any]]] = {}
    for question in unique:
        code = str(question.get("code") or question.get("question_id"))
        stem_key = stem_keys.get(code)
        if stem_key is not None:
            stem_groups.setdefault(stem_key, []).append(question)
    for group in stem_groups.values():
        if len(group) < 2:
            continue
        for left_index, left in enumerate(group):
            for right in group[left_index + 1 :]:
                left_code = str(left.get("code") or left.get("question_id"))
                right_code = str(right.get("code") or right.get("question_id"))
                if content_keys.get(left_code) != content_keys.get(right_code) or any(
                    unresolved_visuals.get(code, False) for code in (left_code, right_code)
                ):
                    add_review_pair(left, right, "same_stem_requires_review")

    for left_index, left in enumerate(unique):
        left_text = _stem_text(left)
        if len(left_text) < 40:
            continue
        for right in unique[left_index + 1 :]:
            if left.get("source_examType") == right.get("source_examType"):
                continue
            if left.get("subject") != right.get("subject"):
                continue
            left_code = str(left.get("code") or left.get("question_id"))
            right_code = str(right.get("code") or right.get("question_id"))
            if content_keys.get(left_code) == content_keys.get(right_code):
                continue
            right_text = _stem_text(right)
            if len(right_text) < 40:
                continue
            similarity = SequenceMatcher(None, left_text, right_text).ratio()
            if similarity >= NEAR_DUPLICATE_THRESHOLD:
                add_review_pair(left, right, "near_duplicate_stem", similarity)

    if blocking_conflicts:
        status = "blocked"
    elif review_candidates:
        status = "review_required"
    else:
        status = "passed"
    report = {
        "report_version": REPORT_VERSION,
        "status": status,
        "policy": {
            "auto_merge": "题干、选项、正确答案和考纲归属一致时，只保留质量更完整且标识稳定的一题。",
            "retain_for_review": "同题干但选项不同、视觉证据不足或仅高度相似时不自动删除。",
            "block_on_conflict": "同题面出现答案或考纲归属冲突时阻止导出，必须回到对应逐题事务复核。",
        },
        "input_question_count": len(questions),
        "output_question_count": len(unique),
        "confirmed_duplicate_count": len(confirmed_duplicates),
        "confirmed_duplicates": confirmed_duplicates,
        "blocking_conflict_count": len(blocking_conflicts),
        "blocking_conflicts": blocking_conflicts,
        "review_candidate_count": len(review_candidates),
        "review_candidates": review_candidates,
    }
    return unique, report
