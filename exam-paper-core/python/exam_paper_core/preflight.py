"""不产生缓存文件的只读预检。"""

from __future__ import annotations

import ast
import json
from pathlib import Path


def scan_tree(root: str | Path) -> list[str]:
    base = Path(root)
    errors: list[str] = []
    if not base.is_dir():
        return [f"目录不存在：{base}"]
    for path in sorted(base.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            if path.suffix == ".py":
                source = path.read_text(encoding="utf-8")
                ast.parse(source, filename=str(path))
            elif path.suffix == ".json":
                with path.open("r", encoding="utf-8-sig") as handle:
                    json.load(handle)
            elif path.suffix in {".md", ".yaml", ".yml"}:
                path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, SyntaxError, json.JSONDecodeError) as error:
            errors.append(f"{path}：{error}")
    return errors
