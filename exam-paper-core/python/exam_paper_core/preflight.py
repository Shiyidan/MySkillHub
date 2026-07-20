"""Read-only structural checks for the exam-paper skill suite."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".py", ".json", ".md", ".yaml", ".yml"}
AGENT_KEYS = {"display_name", "short_description", "default_prompt"}


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _skill_frontmatter_errors(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [f"{path}：缺少 YAML frontmatter 起始分隔线。"]
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return [f"{path}：缺少 YAML frontmatter 结束分隔线。"]
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            errors.append(f"{path}：frontmatter 行缺少冒号：{line!r}")
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key in values:
            errors.append(f"{path}：frontmatter 字段重复：{key}")
        values[key] = _unquote(raw_value)
    if set(values) != {"name", "description"}:
        errors.append(f"{path}：frontmatter 必须且只能包含 name、description。")
        return errors
    if values["name"] != path.parent.name:
        errors.append(f"{path}：name 必须与目录名一致。")
    if not values["description"].strip() or "TODO" in values["description"]:
        errors.append(f"{path}：description 不能为空或保留 TODO。")
    if "TODO" in text:
        errors.append(f"{path}：仍包含 TODO 占位内容。")
    return errors

def _agent_yaml_errors(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines or lines[0].strip() != "interface:":
        return [f"{path}：根节点必须是 interface。"]
    values: dict[str, str] = {}
    for line in lines[1:]:
        if not line.startswith("  ") or line.startswith("    ") or ":" not in line:
            errors.append(f"{path}：interface 字段必须使用两个空格缩进：{line!r}")
            continue
        key, raw_value = line.strip().split(":", 1)
        if key in values:
            errors.append(f"{path}：interface 字段重复：{key}")
        values[key] = _unquote(raw_value)
    if set(values) != AGENT_KEYS:
        errors.append(f"{path}：interface 必须且只能包含 {sorted(AGENT_KEYS)}。")
        return errors
    if any(not value.strip() or "TODO" in value for value in values.values()):
        errors.append(f"{path}：interface 字段不能为空或保留 TODO。")
    description_length = len(values["short_description"])
    if not 25 <= description_length <= 64:
        errors.append(f"{path}：short_description 长度必须为 25-64 个字符，当前为 {description_length}。")
    skill_name = path.parent.parent.name
    if f"${skill_name}" not in values["default_prompt"]:
        errors.append(f"{path}：default_prompt 必须显式引用 ${skill_name}。")
    return errors


def _schema_node_errors(node: Any, label: str) -> list[str]:
    errors: list[str] = []
    if isinstance(node, dict):
        required = node.get("required")
        properties = node.get("properties")
        if required is not None:
            if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
                errors.append(f"{label}.required 必须是字符串数组。")
            elif len(required) != len(set(required)):
                errors.append(f"{label}.required 包含重复字段。")
            elif isinstance(properties, dict):
                missing = set(required) - set(properties)
                if missing:
                    errors.append(f"{label}.required 引用了未定义 properties：{sorted(missing)}")
        enum = node.get("enum")
        if isinstance(enum, list):
            serialized = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in enum]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{label}.enum 包含重复值。")
        for key, value in node.items():
            errors.extend(_schema_node_errors(value, f"{label}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            errors.extend(_schema_node_errors(value, f"{label}[{index}]"))
    return errors


def _schema_errors(path: Path, data: Any) -> list[str]:
    if not isinstance(data, dict):
        return [f"{path}：Schema 根节点必须是对象。"]
    errors: list[str] = []
    if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append(f"{path}：必须声明 JSON Schema draft 2020-12。")
    if data.get("type") != "object":
        errors.append(f"{path}：Schema 根类型必须是 object。")
    errors.extend(_schema_node_errors(data, str(path)))
    return errors


def scan_tree(root: str | Path) -> list[str]:
    base = Path(root)
    errors: list[str] = []
    if not base.is_dir():
        return [f"目录不存在：{base}"]
    for path in sorted(base.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8-sig")
            if "\ufffd" in text:
                errors.append(f"{path}：包含 Unicode 替换字符，疑似编码损坏。")
            if path.suffix == ".py":
                ast.parse(text, filename=str(path))
            elif path.suffix == ".json":
                data = json.loads(text)
                if path.name.endswith(".schema.json"):
                    errors.extend(_schema_errors(path, data))
            elif path.name == "SKILL.md":
                errors.extend(_skill_frontmatter_errors(path, text))
            elif path.name == "openai.yaml" and path.parent.name == "agents":
                errors.extend(_agent_yaml_errors(path, text))
        except (OSError, UnicodeError, SyntaxError, json.JSONDecodeError) as error:
            errors.append(f"{path}：{error}")
    if (base / "SKILL.md").is_file() and not (base / "agents" / "openai.yaml").is_file():
        errors.append(f"{base}：缺少 agents/openai.yaml。")
    return errors
