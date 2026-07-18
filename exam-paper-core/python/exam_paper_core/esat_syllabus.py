"""ESAT 考纲树的标准字段映射。"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


SYLLABUS_FILENAME = "esat_syllabus.json"


def _syllabus_path() -> Path:
    return Path(__file__).resolve().parents[2] / "syllabus" / SYLLABUS_FILENAME


def _module_name_from_label(label: str) -> str:
    return label.split(" (", 1)[0]


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    with _syllabus_path().open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    root = data[0]
    root_info = {"code": root["code"], "label": root["label"], "source_file": SYLLABUS_FILENAME}
    modules_by_name: dict[str, dict[str, str]] = {}
    modules_by_code: dict[str, dict[str, str]] = {}
    items_by_code: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any], *, module: dict[str, str] | None, path: list[dict[str, str]]) -> None:
        code = str(node["code"])
        label = str(node["label"])
        current_path = [*path, {"code": code, "label": label}]
        if module is None and code != root["code"]:
            module_name = _module_name_from_label(label)
            module = {"module": module_name, "module_code": code, "module_label": label}
            modules_by_name[module_name] = copy.deepcopy(module)
            modules_by_code[code] = copy.deepcopy(module)
        elif module is not None:
            parent = path[-1] if path else {"code": root["code"], "label": root["label"]}
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


def esat_root() -> dict[str, str]:
    return copy.deepcopy(_index()["root"])


def esat_module_names() -> set[str]:
    return set(_index()["modules_by_name"])


def module_descriptor(module: str) -> dict[str, str]:
    item = _index()["modules_by_name"].get(module)
    if item is None:
        raise KeyError(module)
    return copy.deepcopy(item)


def syllabus_item(code: str) -> dict[str, Any] | None:
    item = _index()["items_by_code"].get(str(code))
    return copy.deepcopy(item) if item is not None else None


def syllabus_items_for_codes(codes: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for raw in codes:
        code = str(raw)
        if code in seen:
            continue
        seen.add(code)
        item = syllabus_item(code)
        if item is None:
            unmatched.append(code)
        else:
            items.append(item)
    return items, unmatched
