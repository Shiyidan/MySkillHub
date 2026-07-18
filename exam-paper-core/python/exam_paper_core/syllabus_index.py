"""多考试考纲树的标准字段索引。

本模块只负责把各考试的 syllabus JSON 转成稳定的机器字段：
root、一级模块/知识域、以及每个考纲节点的 code/label/path。
考试规则仍由 contract.py 决定，避免把 ESAT、TMUA 的业务规则混在索引层。
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


SYLLABUS_FILES = {
    "ESAT": "esat_syllabus.json",
    "TMUA": "tmua_syllabus.json",
    "STEP": "step_syllabus.json",
}


def _syllabus_path(exam: str) -> Path:
    normalized = exam.upper()
    if normalized not in SYLLABUS_FILES:
        raise KeyError(exam)
    return Path(__file__).resolve().parents[2] / "syllabus" / SYLLABUS_FILES[normalized]


def _module_name_from_label(label: str) -> str:
    return label.split(" (", 1)[0]


@lru_cache(maxsize=None)
def _index(exam: str) -> dict[str, Any]:
    normalized = exam.upper()
    with _syllabus_path(normalized).open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    root = data[0]
    source_file = SYLLABUS_FILES[normalized]
    root_info = {"code": str(root["code"]), "label": str(root["label"]), "source_file": source_file}
    modules_by_name: dict[str, dict[str, str]] = {}
    modules_by_code: dict[str, dict[str, str]] = {}
    items_by_code: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any], *, module: dict[str, str] | None, path: list[dict[str, str]]) -> None:
        code = str(node["code"])
        label = str(node["label"])
        current_path = [*path, {"code": code, "label": label}]
        if module is None and code != root_info["code"]:
            module_name = _module_name_from_label(label)
            module = {"module": module_name, "module_code": code, "module_label": label}
            modules_by_name[module_name] = copy.deepcopy(module)
            modules_by_code[code] = copy.deepcopy(module)
        elif module is not None:
            parent = path[-1] if path else {"code": root_info["code"], "label": root_info["label"]}
            items_by_code[code] = {
                "code": code,
                "label": label,
                "module": module["module"],
                "module_code": module["module_code"],
                "module_label": module["module_label"],
                "parent_code": parent["code"],
                "parent_label": parent["label"],
                "path_codes": [item["code"] for item in current_path],
                "path_labels": [item["label"] for item in current_path],
            }
        for child in node.get("children", []):
            walk(child, module=module, path=current_path)

    walk(root, module=None, path=[])
    return {
        "root": root_info,
        "modules_by_name": modules_by_name,
        "modules_by_code": modules_by_code,
        "items_by_code": items_by_code,
    }


def syllabus_root(exam: str) -> dict[str, str]:
    return copy.deepcopy(_index(exam)["root"])


def syllabus_module_names(exam: str) -> set[str]:
    return set(_index(exam)["modules_by_name"])


def syllabus_module_descriptor(exam: str, module: str) -> dict[str, str]:
    item = _index(exam)["modules_by_name"].get(module)
    if item is None:
        raise KeyError(module)
    return copy.deepcopy(item)


def syllabus_item_for_exam(exam: str, code: str) -> dict[str, Any] | None:
    item = _index(exam)["items_by_code"].get(str(code))
    return copy.deepcopy(item) if item is not None else None


def syllabus_items_for_exam_codes(exam: str, codes: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for raw in codes:
        code = str(raw)
        if code in seen:
            continue
        seen.add(code)
        item = syllabus_item_for_exam(exam, code)
        if item is None:
            unmatched.append(code)
        else:
            items.append(item)
    return items, unmatched
