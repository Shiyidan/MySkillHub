#!/usr/bin/env python3
"""Inspect an exam PDF and optionally render selected pages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


QUESTION_RE = re.compile(r"^\s*(\d{1,3})(?:[\).]|\s{1,})(?=\S)")


def parse_pages(value: str, page_count: int) -> list[int]:
    if not value:
        return []
    pages: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = max(1, int(start_s))
            end = min(page_count, int(end_s))
            pages.update(range(start, end + 1))
        else:
            n = int(part)
            if 1 <= n <= page_count:
                pages.add(n)
    return sorted(pages)


def question_candidates(text: str) -> list[int]:
    found: list[int] = []
    for line in text.splitlines():
        match = QUESTION_RE.match(line)
        if match:
            found.append(int(match.group(1)))
    return found


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="Path to the source PDF")
    parser.add_argument("--out", help="Artifact directory for manifest, text, and rendered pages")
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--render-pages", default="", help="Pages/ranges to render, e.g. 1,2,5-7")
    parser.add_argument("--render-all", action="store_true")
    args = parser.parse_args()

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise SystemExit("PyMuPDF is required. Install package 'pymupdf'.") from exc

    pdf_path = Path(args.pdf).expanduser().resolve()
    doc = fitz.open(pdf_path)

    out_dir = Path(args.out).expanduser().resolve() if args.out else None
    if out_dir:
        (out_dir / "pages").mkdir(parents=True, exist_ok=True)
        (out_dir / "page-text").mkdir(parents=True, exist_ok=True)

    render_pages = list(range(1, doc.page_count + 1)) if args.render_all else parse_pages(args.render_pages, doc.page_count)
    zoom = args.dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    pages = []
    for index, page in enumerate(doc, start=1):
        rect = page.rect
        text = page.get_text("text")
        page_info = {
            "page": index,
            "width": round(rect.width, 2),
            "height": round(rect.height, 2),
            "text_length": len(text),
            "question_number_candidates": question_candidates(text),
            "rendered_image": None,
            "text_path": None,
        }

        if out_dir:
            text_path = out_dir / "page-text" / f"page-{index:03d}.txt"
            text_path.write_text(text, encoding="utf-8")
            page_info["text_path"] = str(text_path)

        if out_dir and index in render_pages:
            image_path = out_dir / "pages" / f"page-{index:03d}.png"
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(image_path)
            page_info["rendered_image"] = str(image_path)

        pages.append(page_info)

    manifest = {
        "source_pdf": str(pdf_path),
        "page_count": doc.page_count,
        "metadata": doc.metadata,
        "dpi": args.dpi,
        "pages": pages,
    }

    if out_dir:
        manifest_path = out_dir / "page_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["manifest_path"] = str(manifest_path)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
