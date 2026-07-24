"""统一的题目内容指纹算法。"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


LAYOUT_ONLY_KEYS = {"mode", "align", "break_before"}


def _without_layout_metadata(value: Any) -> Any:
    """Remove rendering metadata from title/option identity payloads."""

    if isinstance(value, list):
        return [_without_layout_metadata(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _without_layout_metadata(item)
            for key, item in value.items()
            if key not in LAYOUT_ONLY_KEYS
        }
    return value


def normalize_fingerprint_value(value: Any) -> Any:
    """统一规范化指纹比较中的 Unicode、空白和大小写。"""

    if isinstance(value, str):
        text = unicodedata.normalize("NFKC", value)
        return re.sub(r"\s+", " ", text).strip().casefold()
    if isinstance(value, list):
        return [normalize_fingerprint_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: normalize_fingerprint_value(value[key])
            for key in sorted(value)
        }
    return value


def canonicalize_fingerprint_payload(value: Any) -> str:
    """使用共享规范化规则序列化指纹载荷。"""

    return json.dumps(
        normalize_fingerprint_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def fingerprint_payload(value: Any) -> str:
    """对业务载荷生成稳定的 SHA-256 指纹。"""

    canonical = canonicalize_fingerprint_payload(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def question_fingerprint(question: dict[str, Any]) -> str:
    """只根据题面、选项和图形语义生成稳定指纹，不混入答案或解析。"""

    diagram = question.get("diagram")
    payload = {
        "title": _without_layout_metadata(question.get("title", [])),
        "options": _without_layout_metadata(question.get("options", [])),
        "diagram_semantics": diagram.get("semantics") if isinstance(diagram, dict) else None,
    }
    return fingerprint_payload(payload)


def question_stem_fingerprint(question: dict[str, Any]) -> str:
    """Generate a stable key for the stem and diagram, ignoring option order."""

    diagram = question.get("diagram")
    payload = {
        "title": _without_layout_metadata(question.get("title", [])),
        "diagram_semantics": diagram.get("semantics") if isinstance(diagram, dict) else None,
    }
    return fingerprint_payload(payload)
