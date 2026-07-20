"""ESAT legacy 年度题库的诊断性组卷工具。"""

from __future__ import annotations

import copy
import itertools
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .contract import ContractError, build_document, validate_document
from .esat_syllabus import esat_root, module_descriptor, syllabus_items_for_codes
from .deduplication import deduplicate_questions


ESAT_MODULES = ("Mathematics 1", "Biology", "Chemistry", "Physics", "Mathematics 2")
FURTHER_MODULES = ("Biology", "Chemistry", "Physics", "Mathematics 2")
ESAT_COMBINATIONS = tuple(("Mathematics 1", *pair) for pair in itertools.combinations(FURTHER_MODULES, 2))
DEFAULT_MODULE_QUESTION_COUNT = 27
MODULE_TIME_MINUTES = 40


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def source_name(path: str | Path) -> str:
    return Path(path).resolve().name


def safe_combination_name(modules: list[str] | tuple[str, ...]) -> str:
    parts = ["M1" if item == "Mathematics 1" else "Math2" if item == "Mathematics 2" else item for item in modules]
    return "_".join(re.sub(r"[^A-Za-z0-9]+", "", item) for item in parts)


def _validate_modules(modules: Any, *, allow_single_module: bool = False) -> list[str]:
    _require(isinstance(modules, list) and modules, "constraints.modules 必须是非空数组。")
    _require(all(isinstance(item, str) and item in ESAT_MODULES for item in modules), "constraints.modules 必须全部是 ESAT 模块。")
    _require(len(modules) == len(set(modules)), "constraints.modules 不得重复。")
    _require("Mathematics 1" in modules, "ESAT 组卷必须包含必选模块 Mathematics 1。")
    if not allow_single_module:
        _require(len(modules) == 3, "ESAT 组合诊断卷必须包含 Mathematics 1 和两个进一步模块。")
        _require(len(set(modules) & set(FURTHER_MODULES)) == 2, "ESAT 组合诊断卷必须包含两个进一步模块。")
    return list(modules)


def _module_targets(constraints: dict[str, Any], modules: list[str], *, paper_mode: str) -> dict[str, int]:
    counts = constraints.get("target_question_counts") or constraints.get("per_module_counts")
    if paper_mode in {"diagnostic_combination_paper", "full_mock_like_paper"}:
        if counts is not None:
            _require(isinstance(counts, dict), "constraints.target_question_counts 必须是对象。")
            invalid = {
                module: counts.get(module)
                for module in modules
                if counts.get(module, DEFAULT_MODULE_QUESTION_COUNT) != DEFAULT_MODULE_QUESTION_COUNT
            }
            _require(not invalid, f"完整 ESAT 组合诊断卷每个模块必须固定为 27 题，不得覆盖：{invalid}")
            extra = set(counts) - set(modules)
            _require(not extra, f"target_question_counts 包含不在本次组合中的模块：{sorted(extra)}")
        return {module: DEFAULT_MODULE_QUESTION_COUNT for module in modules}
    if counts is None:
        return {module: DEFAULT_MODULE_QUESTION_COUNT for module in modules}
    _require(isinstance(counts, dict), "constraints.target_question_counts 必须是对象。")
    result: dict[str, int] = {}
    for module in modules:
        value = counts.get(module, DEFAULT_MODULE_QUESTION_COUNT)
        _require(isinstance(value, int) and not isinstance(value, bool) and value > 0, f"{module} 目标题量必须是正整数。")
        result[module] = value
    extra = set(counts) - set(modules)
    _require(not extra, f"target_question_counts 包含不在本次组合中的模块：{sorted(extra)}")
    return result


def _family_code(code: str) -> str:
    if len(code) >= 4 and code[:4].isdigit():
        return code[:4] + "00"
    return code


def _candidate_buckets(source_document: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for question in source_document["questions"]:
        scope = question["target_exam_scope"]
        subject = question["subject"]
        if subject not in ESAT_MODULES:
            continue
        descriptor = module_descriptor(subject)
        if (
            scope["target_exam"] == "ESAT"
            and scope["scope_status"] == "in_scope"
            and scope["mapping_status"] in {"auto_verified", "human_verified"}
            and scope["modules"] == [subject]
            and question["subject_code"] == descriptor["module_code"]
            and question["question_type"] == "multiple_choice"
            and not question["is_ai_generated"]
        ):
            buckets[subject].append(question)
    for module in buckets:
        buckets[module].sort(key=lambda item: (str(item["year"]), str(item["source_examType"]), int(item["questionNumber"]) if isinstance(item["questionNumber"], int) else str(item["questionNumber"]), item["code"]))
    return buckets


def _question_features(question: dict[str, Any]) -> tuple[str, str, str]:
    scope = question["target_exam_scope"]
    family = _family_code(scope["syllabus_codes"][0]) if scope["syllabus_codes"] else "unknown"
    return family, question["difficulty"], question["source_examType"]


def _deduplicate_candidates(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Remove confirmed duplicates while retaining ambiguous same-stem questions."""

    unique, report = deduplicate_questions(candidates)
    if report["blocking_conflicts"]:
        codes = [item["codes"] for item in report["blocking_conflicts"]]
        raise ContractError(f"候选题存在重复题答案或考纲归属冲突，必须先复核：{codes}")
    return unique, report["confirmed_duplicates"]


def suggested_time_minutes(actual_question_count: int) -> int:
    """组合诊断卷始终保留 ESAT 官方每模块 40 分钟时长。"""

    return MODULE_TIME_MINUTES


def _select_questions(candidates: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    unique_candidates, _ = _deduplicate_candidates(candidates)
    return _select_from_unique_candidates(unique_candidates, target_count)


def _select_from_unique_candidates(
    unique_candidates: list[dict[str, Any]],
    target_count: int,
) -> list[dict[str, Any]]:
    """从已经去重的候选池中执行覆盖度与题源平衡选择。"""

    if len(unique_candidates) <= target_count:
        return list(unique_candidates)
    selected: list[dict[str, Any]] = []
    used_codes: set[str] = set()
    syllabus_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    difficulty_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    while len(selected) < target_count:
        best: dict[str, Any] | None = None
        best_score: tuple[int, int, int, int, int, str] | None = None
        for question in unique_candidates:
            if question["code"] in used_codes:
                continue
            family, difficulty, source = _question_features(question)
            syllabus_codes = question["target_exam_scope"].get("syllabus_codes", [])
            score = (
                sum(syllabus_counts[code] for code in syllabus_codes),
                family_counts[family],
                difficulty_counts[difficulty],
                source_counts[source],
                int(question["questionNumber"]) if isinstance(question["questionNumber"], int) else 9999,
                question["code"],
            )
            if best_score is None or score < best_score:
                best = question
                best_score = score
        if best is None:
            break
        selected.append(best)
        used_codes.add(best["code"])
        family, difficulty, source = _question_features(best)
        family_counts[family] += 1
        difficulty_counts[difficulty] += 1
        source_counts[source] += 1
        for code in best["target_exam_scope"].get("syllabus_codes", []):
            syllabus_counts[code] += 1
    return selected


def _module_summary(
    module: str,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    target_count: int,
    *,
    raw_candidate_count: int | None = None,
    duplicate_records: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    descriptor = module_descriptor(module)
    selected_codes = [item["code"] for item in selected]
    syllabus_codes = sorted({code for item in selected for code in item["target_exam_scope"]["syllabus_codes"]})
    syllabus_items, unmatched_syllabus_codes = syllabus_items_for_codes(syllabus_codes)
    family_codes = sorted({_family_code(code) for code in syllabus_codes})
    difficulty = Counter(item["difficulty"] for item in selected)
    sources = Counter(item["source_examType"] for item in selected)
    suggested_minutes = suggested_time_minutes(len(selected))
    status_parts: list[str] = []
    if len(selected) < target_count:
        status_parts.append("underfilled")
    elif len(candidates) > target_count:
        status_parts.append("overfilled")
    if len(family_codes) <= 1 and selected:
        status_parts.append("narrow_coverage")
    if sources and max(sources.values()) / max(sum(sources.values()), 1) >= 0.8:
        status_parts.append("source_skewed")
    diagnostic_status = "sufficient" if not status_parts else status_parts[0] if len(status_parts) == 1 else "mixed"
    confidence = "high"
    if len(selected) < max(8, target_count // 2) or not selected:
        confidence = "low"
    elif len(selected) < target_count or len(family_codes) <= 1:
        confidence = "medium"
    notes: list[str] = []
    duplicate_records = duplicate_records or []
    raw_candidate_count = len(candidates) if raw_candidate_count is None else raw_candidate_count
    if duplicate_records:
        notes.append(f"候选题中识别并排除 {len(duplicate_records)} 道重复题。")
    if len(selected) < target_count:
        notes.append(f"题量不足：目标 {target_count} 题，实际 {len(selected)} 题。")
    elif len(candidates) > target_count:
        notes.append(f"候选题 {len(candidates)} 题，已按考纲覆盖、难度和题源平衡挑选 {target_count} 题。")
    else:
        notes.append(f"候选题量与目标一致：{len(selected)} 题。")
    if len(family_codes) <= 1 and selected:
        notes.append("考纲大类覆盖偏窄，诊断结果更适合反映已覆盖知识点。")
    coverage_note = "本模块未选入题目，无法形成考纲覆盖诊断。"
    if selected:
        coverage_note = f"本模块覆盖 {len(family_codes)} 个 ESAT 考纲大类、{len(syllabus_items)} 个标准考纲点。"
    if sources:
        notes.append("题源分布：" + "，".join(f"{key} {value} 题" for key, value in sorted(sources.items())) + "。")
    notes.append(f"官方完整模块基准为 {DEFAULT_MODULE_QUESTION_COUNT} 题/{MODULE_TIME_MINUTES} 分钟；本模块实际 {len(selected)} 题，仍固定限时 {suggested_minutes} 分钟。")
    notes.append("按模块单独评分，诊断结果不等同于官方完整模块换算分。")
    return {
        "module": module,
        "module_code": descriptor["module_code"],
        "module_label": descriptor["module_label"],
        "official_question_count": DEFAULT_MODULE_QUESTION_COUNT,
        "official_time_minutes": MODULE_TIME_MINUTES,
        "suggested_time_minutes": suggested_minutes,
        "time_note": f"官方 ESAT 完整模块为 {DEFAULT_MODULE_QUESTION_COUNT} 题/{MODULE_TIME_MINUTES} 分钟；本 legacy 诊断模块实际 {len(selected)} 题，仍使用固定 {suggested_minutes} 分钟。",
        "target_question_count": target_count,
        "actual_question_count": len(selected),
        "available_question_count": len(candidates),
        "raw_available_question_count": raw_candidate_count,
        "duplicate_question_count": len(duplicate_records),
        "deduplicated_questions": duplicate_records,
        "diagnostic_status": diagnostic_status,
        "diagnostic_flags": status_parts,
        "diagnostic_confidence": confidence,
        "selected_question_codes": selected_codes,
        "syllabus_codes": syllabus_codes,
        "syllabus_items": syllabus_items,
        "unmatched_syllabus_codes": unmatched_syllabus_codes,
        "syllabus_families": family_codes,
        "difficulty_distribution": dict(difficulty),
        "source_exam_types": dict(sources),
        "coverage_note": coverage_note,
        "module_note": "".join(notes),
    }


def analyze_assembly(source_document: dict[str, Any], constraints: dict[str, Any], *, source_document_name: str) -> dict[str, Any]:
    """分析并规划 ESAT legacy 诊断卷；不会因缺题而拒绝。"""

    validate_document(source_document, expected_type="parsed_exam")
    source_paper_type = source_document["metadata"]["paper_type"]
    _require(source_paper_type == "realPaper", "ESAT legacy 诊断组卷只能使用 realPaper 真题题库。")
    source_types = set(source_document["metadata"].get("source_exam_types", []))
    _require(source_types == {"ENGAA", "NSAA"}, "ESAT legacy 年度题库必须且只能合并同年 ENGAA 与 NSAA 来源。")
    source_year = source_document["metadata"]["year"]
    mixed_year_questions = [
        item["code"]
        for item in source_document["questions"]
        if str(item["year"]) != str(source_year)
    ]
    _require(not mixed_year_questions, f"ESAT legacy 年度题库不得跨年份混合：{mixed_year_questions}")
    invalid_source_questions = [
        item["code"]
        for item in source_document["questions"]
        if item["source_examType"] not in source_types
    ]
    _require(not invalid_source_questions, f"题目来源必须是 ENGAA 或 NSAA：{invalid_source_questions}")
    _require(isinstance(constraints, dict), "组卷约束必须是 JSON 对象。")
    _require(constraints.get("target_exam", "ESAT") == "ESAT", "exam-paper-assembler 仅支持 ESAT。")
    paper_mode = constraints.get("paper_mode", "diagnostic_combination_paper")
    _require(paper_mode in {"diagnostic_combination_paper", "diagnostic_module_paper", "full_mock_like_paper"}, "paper_mode 不受支持。")
    modules = _validate_modules(constraints.get("modules"), allow_single_module=paper_mode == "diagnostic_module_paper")
    targets = _module_targets(constraints, modules, paper_mode=paper_mode)
    buckets = _candidate_buckets(source_document)
    selected_by_module: dict[str, list[dict[str, Any]]] = {}
    module_reports: dict[str, Any] = {}
    for module in modules:
        raw_candidates = buckets.get(module, [])
        candidates, duplicate_records = _deduplicate_candidates(raw_candidates)
        selected = _select_from_unique_candidates(candidates, targets[module])
        selected_by_module[module] = selected
        module_reports[module] = _module_summary(
            module,
            candidates,
            selected,
            targets[module],
            raw_candidate_count=len(raw_candidates),
            duplicate_records=duplicate_records,
        )

    invalid_or_excluded = [
        {
            "code": item["code"],
            "subject": item["subject"],
            "scope_status": item["target_exam_scope"]["scope_status"],
            "mapping_status": item["target_exam_scope"]["mapping_status"],
            "mapping_reason": item["target_exam_scope"].get("mapping_reason"),
        }
        for item in source_document["questions"]
        if item["target_exam_scope"]["scope_status"] != "in_scope"
        or item["target_exam_scope"]["mapping_status"] not in {"auto_verified", "human_verified"}
        or item["target_exam_scope"]["modules"] != [item["subject"]]
        or item["question_type"] != "multiple_choice"
        or item["is_ai_generated"]
    ]
    paper_notes = [
        f"本卷由 {source_document_name} 按 ESAT 当前考纲重组，用于诊断性测试。",
        "题干、LaTeX、SVG/图形资产、中文解析、来源证据均继承自已校验解析结果。",
        f"每个模块固定限时 {MODULE_TIME_MINUTES} 分钟，整卷固定限时 {len(modules) * MODULE_TIME_MINUTES} 分钟；分数按模块分别解释，题量不足、覆盖偏窄和诊断可信度会在模块说明中标出。",
    ]
    if paper_mode == "full_mock_like_paper" and any(report["actual_question_count"] < report["target_question_count"] for report in module_reports.values()):
        paper_notes.append("本卷未达到完整官方模拟题量，因此作为 legacy diagnostic paper 使用。")
    return {
        "analysis_version": "2",
        "target_exam": "ESAT",
        "paper_mode": paper_mode,
        "source_document": source_document_name,
        "modules": modules,
        "module_reports": module_reports,
        "selected_by_module": {module: [item["code"] for item in selected] for module, selected in selected_by_module.items()},
        "paper_note": "".join(paper_notes),
        "invalid_or_excluded_questions": invalid_or_excluded,
        "source_summary": {
            "question_count": len(source_document["questions"]),
            "scope_statuses": dict(Counter(item["target_exam_scope"]["scope_status"] for item in source_document["questions"])),
            "source_exam_types": list(source_document["metadata"].get("source_exam_types", [])),
        },
    }


def _section_metadata(modules: list[str], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for section_order, module in enumerate(modules, 1):
        report = analysis["module_reports"][module]
        sections.append(
            {
                "module": module,
                "module_code": report["module_code"],
                "module_label": report["module_label"],
                "section_order": section_order,
                "official_question_count": report["official_question_count"],
                "official_time_minutes": report["official_time_minutes"],
                "suggested_time_minutes": report["suggested_time_minutes"],
                "target_question_count": report["target_question_count"],
                "actual_question_count": report["actual_question_count"],
                "scoring_group": module,
                "diagnostic_status": report["diagnostic_status"],
                "diagnostic_flags": report["diagnostic_flags"],
                "diagnostic_confidence": report["diagnostic_confidence"],
                "coverage_summary": {
                    "available_question_count": report["available_question_count"],
                    "selected_question_count": report["actual_question_count"],
                    "syllabus_families": report["syllabus_families"],
                    "difficulty_distribution": report["difficulty_distribution"],
                    "source_exam_types": report["source_exam_types"],
                },
                "syllabus_coverage": {
                    "selected_question_codes": report["selected_question_codes"],
                    "syllabus_codes": report["syllabus_codes"],
                    "syllabus_items": report["syllabus_items"],
                    "unmatched_syllabus_codes": report["unmatched_syllabus_codes"],
                    "coverage_note": report["coverage_note"],
                },
                "time_note": report["time_note"],
                "module_note": report["module_note"],
            }
        )
    return sections


def build_assembled_exam(source_document: dict[str, Any], constraints: dict[str, Any], *, source_hash: str, source_document_name: str) -> dict[str, Any]:
    """从同年 legacy parsed_exam 中生成 ESAT 诊断性组合卷。"""

    analysis = analyze_assembly(source_document, constraints, source_document_name=source_document_name)
    modules = analysis["modules"]
    by_code = {question["code"]: question for question in source_document["questions"]}
    selected: list[dict[str, Any]] = []
    for section_order, module in enumerate(modules, 1):
        descriptor = module_descriptor(module)
        for question_order, code in enumerate(analysis["selected_by_module"][module], 1):
            item = copy.deepcopy(by_code[code])
            item["assembled_section"] = {
                "module": module,
                "module_code": descriptor["module_code"],
                "module_label": descriptor["module_label"],
                "section_order": section_order,
                "question_order": question_order,
                "scoring_group": module,
                "syllabus_items": copy.deepcopy(item["target_exam_scope"]["syllabus_items"]),
            }
            selected.append(item)
    _require(selected, "没有题目符合当前 ESAT 模块组合。")
    metadata = {
        "exam_type": "ESAT",
        "paper_type": "realPaper",
        "year": source_document["metadata"]["year"],
        "source_files": list(source_document["metadata"]["source_files"]),
        "target_exam": "ESAT",
        "source_exam_types": list(source_document["metadata"].get("source_exam_types", [])),
        "title": constraints.get("title", f"ESAT {' + '.join(modules)} legacy diagnostic paper"),
        "assembly": {
            "target_exam": "ESAT",
            "modules": modules,
            "required_module": "Mathematics 1",
            "source_document": source_document_name,
            "assembly_rule": "ESAT-only；自动保留 Mathematics 1 并选择两个进一步模块；不足 27 题仍组卷并写入模块说明，超量时按考纲覆盖、难度和题源平衡稳定挑选。",
            "paper_note": analysis["paper_note"],
            "syllabus_root": esat_root(),
            "official_full_test_time_minutes": len(modules) * MODULE_TIME_MINUTES,
            "total_suggested_time_minutes": 0,
            "sections": [],
            "scoring": {},
        },
    }
    if "syllabus_version" in source_document["metadata"]:
        metadata["syllabus_version"] = source_document["metadata"]["syllabus_version"]
    if "corpus_group" in source_document["metadata"]:
        metadata["corpus_group"] = source_document["metadata"]["corpus_group"]
    sections = _section_metadata(modules, analysis)
    metadata["assembly"]["sections"] = sections
    metadata["assembly"]["official_full_test_time_minutes"] = len(modules) * MODULE_TIME_MINUTES
    metadata["assembly"]["total_suggested_time_minutes"] = sum(section["suggested_time_minutes"] for section in sections)
    metadata["assembly"]["scoring"] = {
        "mode": "by_module",
        "raw_per_question_score": 1,
        "negative_marking": False,
        "raw_score_reporting": "raw_and_percentage_by_module",
        "official_reported_scale": "1.0-9.0",
        "official_decimal_places": 1,
        "official_scaling_method": "Rasch IRT equating by module",
        "official_scaled_score_available": False,
        "diagnostic_score_note": "ESAT 官方按模块报告 1.0-9.0 等级分，换算依赖当次考试 Rasch 等值；legacy 诊断卷只报告模块原始分和正确率，不伪造官方等级分。",
    }
    return build_document(
        {"metadata": metadata, "questions": selected},
        document_type="assembled_exam",
        source_hash=source_hash,
        validation_status="passed",
    )
