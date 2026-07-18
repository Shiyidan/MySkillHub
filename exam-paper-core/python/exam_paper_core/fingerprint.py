"""统一的题目内容指纹算法。"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        text = unicodedata.normalize("NFKC", value)
        return re.sub(r"\s+", " ", text).strip().casefold()
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(value[key]) for key in sorted(value)}
    return value


def question_fingerprint(question: dict[str, Any]) -> str:
    """只根据题面、选项和图形语义生成稳定指纹，不混入答案或解析。"""

    diagram = question.get("diagram")
    payload = {
        "title": question.get("title", []),
        "options": question.get("options", []),
        "diagram_semantics": diagram.get("semantics") if isinstance(diagram, dict) else None,
    }
    canonical = json.dumps(_normalize(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
