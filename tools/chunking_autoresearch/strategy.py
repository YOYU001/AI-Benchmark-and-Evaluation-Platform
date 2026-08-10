"""tools/chunking_autoresearch/strategy.py

agent（Hermes）唯一能編輯的檔案。目前的內容是從 MVP_V1
spike/chunker.py 的 structured_600_100 策略簡化移植過來的 baseline
（完整版包含更多語料庫專屬的細節，例如兩種不同的表格偵測路徑，這裡刻意
簡化成一種，方便完整看懂、方便重寫）。

可以自由改寫這個檔案的任何部分：換演算法、加輔助函式、整個重寫都可以，
**但 `chunk(pages, source_filename) -> list[Chunk]` 這個函式簽名一定要保留**
——這是 harness.py／_worker.py 呼叫這個檔案的唯一介面，改掉會讓每次實驗
都直接 crash。完整規則見 program.md 的「能做／不能做」。

其他限制：
  - 不能加 requirements.txt 以外的新套件
  - STRATEGY_NAME 常數要更新成描述這次嘗試的名稱（會顯示在 harness 的輸出裡）
"""

from __future__ import annotations

import re

from schema import Chunk, PageParseResult

STRATEGY_NAME = "structured_600_100_listcomp_lines_zip_unpack"

CHUNK_SIZE = 600
OVERLAP = 100

_DATE_LINE_RE = re.compile(r"^\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*$")
_UNIT_PAREN_RE = re.compile(r"\([^()]{0,8}(kW|kWh|%|°C|Wh|V|A|Ah|SOC)\)")
_TABLE_TITLE_RE = re.compile(r"^表\s*\d+[\.．]\s*\S")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?])")


def _split_oversized(text: str, limit: int) -> list[str]:
    """把過長的文字沿句子邊界切開，切不下去才硬切。"""
    if len(text) <= limit:
        return [text]
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s]
    pieces: list[str] = []
    buf = ""
    for s in sentences:
        if buf and len(buf) + len(s) > limit:
            pieces.append(buf)
            buf = s
        else:
            buf += s
    if buf:
        pieces.append(buf)

    final: list[str] = []
    for p in pieces:
        if len(p) <= limit:
            final.append(p)
        else:
            for j in range(0, len(p), limit):
                final.append(p[j : j + limit])
    return final


def _pack_with_overlap(text: str, size: int, overlap: int) -> list[str]:
    """切完之後，讓每一段開頭重複上一段結尾的 overlap 個字元。"""
    pieces = _split_oversized(text, size)
    if overlap <= 0 or len(pieces) <= 1:
        return pieces
    packed = [pieces[0]]
    for p in pieces[1:]:
        tail = packed[-1][-overlap:]
        packed.append(tail + p)
    return packed


def chunk(pages: list[PageParseResult], source_filename: str) -> list[Chunk]:
    """段落感知 + 表格感知的 chunking，從 MVP_V1 的 structured_600_100
    簡化而來。把每頁文字拆成一行一行，用縮排判斷段落邊界，用「中文日期行
    前面有沒有帶單位的欄位名稱」判斷是不是表格區塊，段落最後用
    CHUNK_SIZE/OVERLAP 打包成大小適中的 chunk。
    """
    lines: list[tuple[str, int, int]] = [
        (raw.strip(), page.page_index, page.pdf_page_number)
        for page in pages
        for raw in page.text.splitlines()
    ]

    chunks: list[Chunk] = []
    para_buf: list[tuple[str, int, int]] = []
    table_buf: list[tuple[str, int, int]] = []
    in_table = False

    def flush_para() -> None:
        nonlocal para_buf
        if not para_buf:
            return
        text = " ".join(t for t, _, _ in para_buf)
        page_idx = [p for _, p, _ in para_buf]
        pdf_pg = [p for _, _, p in para_buf]
        for piece in _pack_with_overlap(text, CHUNK_SIZE, OVERLAP):
            chunks.append(
                Chunk(
                    chunk_id=f"{source_filename}::prose::{len(chunks):04d}",
                    source_filename=source_filename,
                    chunk_type="prose",
                    text=piece,
                    char_count=len(piece),
                    page_index_range=(min(page_idx), max(page_idx)),
                    pdf_page_number_range=(min(pdf_pg), max(pdf_pg)),
                )
            )
        para_buf = []

    def flush_table(title: str) -> None:
        nonlocal table_buf
        if not table_buf:
            return
        text = title + "\n" + "\n".join(t for t, _, _ in table_buf)
        page_idx = [p for _, p, _ in table_buf]
        pdf_pg = [p for _, _, p in table_buf]
        chunks.append(
            Chunk(
                chunk_id=f"{source_filename}::table::{len(chunks):04d}",
                source_filename=source_filename,
                chunk_type="table",
                text=text,
                char_count=len(text),
                page_index_range=(min(page_idx), max(page_idx)),
                pdf_page_number_range=(min(pdf_pg), max(pdf_pg)),
                table_title=title,
            )
        )
        table_buf = []

    i = 0
    n = len(lines)
    while i < n:
        text, page_idx, pdf_pg = lines[i]
        if not text:
            i += 1
            continue

        if not in_table and _DATE_LINE_RE.match(text):
            lookback = para_buf[-6:]
            has_unit = any(_UNIT_PAREN_RE.search(t) for t, _, _ in lookback)
            if has_unit:
                # 表頭欄位名稱（例如「日期 需量(kW) 市電(kW) ...」）原本會被
                # 從 para_buf 移除但沒有放進表格內容裡——直接遺失。現在改成
                # 移到 table_buf 開頭，內容才不會憑空消失。
                para_buf = para_buf[: max(0, len(para_buf) - len(lookback))]
                flush_para()
                in_table = True
                table_buf = list(lookback) + [(text, page_idx, pdf_pg)]
                i += 1
                continue

        if in_table:
            if _TABLE_TITLE_RE.match(text):
                flush_table(title=text)
                in_table = False
                i += 1
                continue
            table_buf.append((text, page_idx, pdf_pg))
            i += 1
            continue

        para_buf.append((text, page_idx, pdf_pg))
        i += 1

    flush_para()
    flush_table(title="(未偵測到表格標題)")
    return chunks
