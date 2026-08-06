"""tools/chunking_autoresearch/schema.py

共用資料結構，被 harness.py、strategy.py、_worker.py 三邊 import。
獨立成這個檔案是為了修掉原本 harness.py <-> strategy.py 互相 import 造成的
循環 import 問題（QA 審查實測證實：用 `python harness.py` 直接執行時，
Python 會把 harness 用 `__main__` 跟 `harness` 兩個名字各載入一次，
`strategy.py` 拿到的 `Chunk` 跟 `__main__.Chunk` 會是兩個不同的 class）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PageParseResult:
    page_index: int  # 0-based
    pdf_page_number: int  # 1-based
    text: str
    char_count: int


@dataclass
class Chunk:
    chunk_id: str
    source_filename: str
    chunk_type: str  # "prose" | "table"
    text: str
    char_count: int
    page_index_range: tuple
    pdf_page_number_range: tuple
    table_title: Optional[str] = None
