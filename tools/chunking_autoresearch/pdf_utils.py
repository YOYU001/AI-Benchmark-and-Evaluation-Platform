"""tools/chunking_autoresearch/pdf_utils.py

固定、不可改的 PDF 解析工具。只讀文字層，不做 OCR（已知落差，見 README.md）。
從 harness.py 拆出來，方便 harness.py 跟 _worker.py 共用，也讓 harness.py
本身更專注在「orchestration + 計分」這件事上。
"""

from __future__ import annotations

import fitz  # PyMuPDF

from schema import PageParseResult


def parse_pdf_pages(pdf_path: str) -> list[PageParseResult]:
    results: list[PageParseResult] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            text = page.get_text("text") or ""
            results.append(
                PageParseResult(
                    page_index=page_index,
                    pdf_page_number=page_index + 1,
                    text=text,
                    char_count=len(text.strip()),
                )
            )
    return results
