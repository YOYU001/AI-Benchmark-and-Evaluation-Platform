"""tools/chunking_autoresearch/harness.py

固定、不可改的驗證程式（對應 autoresearch 的 prepare.py 角色）。
agent（Hermes）絕對不能編輯這個檔案。

這一版是四方獨立審查（qa / research / code-review / codex）之後的重寫，
修掉的核心問題：
  1. 品質檢查原本只驗證欄位格式，完全沒檢查「內容有沒有被保留下來」——
     QA 實測證明：一個把資料整個丟光的策略反而能拿到比 baseline 更低的
     cost_time。現在加了 content coverage 的硬性門檻（見 MIN_CONTENT_COVERAGE），
     沒過門檻直接给一個遠高於任何正常結果的 cost_time，不再能用「少做事」取巧。
  2. strategy.chunk() 現在透過 `_worker.py` 在獨立 subprocess 裡執行，
     父行程自己的計時器／常數碰不到，也真的有 timeout 強制中止。
  3. 計時範圍排除 PDF 解析（固定成本、策略改不動），並且跑三次取中位數，
     降低單次執行的隨機雜訊。

用法：python harness.py（或 uv run harness.py）
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Optional

from pdf_utils import parse_pdf_pages
from schema import Chunk, PageParseResult

# 只用來讀 STRATEGY_NAME 這個字串常數放進摘要輸出，不會呼叫 strategy.chunk()
# ——實際執行 chunk() 一律透過 _worker.py 的 subprocess，不在這個 process
# 裡跑，所以這裡 import 不影響計時或評分的可信度。schema.py 拆出來之後，
# strategy.py 已經不會再 import 這個檔案，不會有循環 import。
import strategy

# ---------------------------------------------------------------------------
# 固定常數——agent 可以讀，但不能改這個檔案本身
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "spike_documents"
TOOL_DIR = Path(__file__).resolve().parent

DOCUMENTS = [
    "新進人員實習表.pdf",
    "2415-1305研究報告-太陽光發電預測.pdf",
    "2415-1304研究報告-智能貨櫃屋 .pdf",
    "A 完整版本  鋰電池二次利用之電池管理系統開發研究完成報告.pdf",
]

# 每份文件的原始內容，至少要有這個比例透過 shingle 比對出現在 chunk 裡，
# 否則視為硬性失敗（見 content_coverage）。這個門檻是防呆用的，不是拿來
# 精細比較「哪個策略切得比較好」——切得好不好交給 quality_pass_rate。
MIN_CONTENT_COVERAGE = 0.90
SHINGLE_SIZE = 30

# 硬性失敗（quality 或 coverage 沒過門檻）的 cost_time 基準值，遠高於任何正常
# 執行結果，讓「投機取巧」永遠競爭不過「認真切但慢一點」。
HARD_FAILURE_BASE = 1000.0

# baseline 策略（strategy.py 目前的內容）跑出來的中位數秒數，讓
# normalized_seconds 有一個穩定的參考值。如果之後手動調整 baseline，
# 這個常數要跟著手動更新（跑 harness.py 幾次、取中位數）。
BASELINE_SECONDS = 0.11

# 每次實驗跑幾次 strategy，取中位數計時，降低單次執行的隨機雜訊。
TIMING_REPEATS = 3

# 子行程逾時秒數：卡住或跑太久的策略會被強制中止，計入 crash。
SUBPROCESS_TIMEOUT_SECONDS = 30

WORKER_SCRIPT = TOOL_DIR / "_worker.py"


# ---------------------------------------------------------------------------
# 結構品質檢查（照搬 MVP_V1 spike/run_chunking_comparison.py 的 _metadata_ok）
# ---------------------------------------------------------------------------


def _metadata_ok(chunk: Chunk) -> bool:
    if chunk.page_index_range[0] > chunk.page_index_range[1]:
        return False
    if chunk.char_count != len(chunk.text):
        return False
    if chunk.chunk_type not in ("prose", "table"):
        return False
    if chunk.chunk_type == "table" and not chunk.table_title:
        return False
    if not chunk.text.strip():
        return False
    return True


def score_chunks(chunks: list[Chunk]) -> float:
    """回傳所有 chunk 裡通過結構檢查的比例，1.0 代表全部通過。"""
    if not chunks:
        return 0.0
    ok_count = sum(1 for c in chunks if _metadata_ok(c))
    return ok_count / len(chunks)


# ---------------------------------------------------------------------------
# 內容保留率檢查（新增：這是修掉「丟光資料反而分數更高」的關鍵）
# ---------------------------------------------------------------------------


def _shingles(text: str, size: int = SHINGLE_SIZE) -> set[str]:
    normalized = "".join(text.split())
    if len(normalized) < size:
        return {normalized} if normalized else set()
    return {normalized[i : i + size] for i in range(len(normalized) - size + 1)}


def content_coverage(source_pages: list[PageParseResult], chunks: list[Chunk]) -> float:
    """用固定長度的字元 shingle 比對，估算原始文件內容有多少比例真的出現在
    切出來的 chunk 裡。切法可以重疊、可以重新排列，這些都不影響分數；
    但把內容丟掉不切，分數會明顯下降，無法靠「少做事」騙到高分。
    """
    source_text = "".join(p.text for p in source_pages)
    source_shingles = _shingles(source_text)
    if not source_shingles:
        return 1.0
    chunk_text = "".join(c.text for c in chunks)
    chunk_shingles = _shingles(chunk_text)
    covered = source_shingles & chunk_shingles
    return len(covered) / len(source_shingles)


# ---------------------------------------------------------------------------
# 透過 subprocess 執行 strategy.chunk()（隔離 + 真正的 timeout）
# ---------------------------------------------------------------------------


def _run_worker_once(payload: list[dict]) -> tuple[Optional[list[dict]], float]:
    """跑一次 _worker.py。回傳 (worker 輸出的文件/chunk 清單, 花費秒數)。
    子行程 crash 或逾時，回傳 (None, 花費秒數)。
    """
    import time

    start = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, str(WORKER_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            cwd=str(TOOL_DIR),
        )
    except subprocess.TimeoutExpired:
        return None, time.perf_counter() - start
    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return None, elapsed
    try:
        return json.loads(result.stdout), elapsed
    except json.JSONDecodeError:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None, elapsed


def _chunk_from_dict(d: dict) -> Chunk:
    d = dict(d)
    d["page_index_range"] = tuple(d["page_index_range"])
    d["pdf_page_number_range"] = tuple(d["pdf_page_number_range"])
    return Chunk(**d)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def run() -> None:
    # PDF 解析是固定成本、策略改不動它，排除在計時範圍之外。
    pages_by_doc: dict[str, list[PageParseResult]] = {
        filename: parse_pdf_pages(str(DOCS_DIR / filename)) for filename in DOCUMENTS
    }
    payload = [
        {
            "filename": filename,
            "pages": [
                {
                    "page_index": p.page_index,
                    "pdf_page_number": p.pdf_page_number,
                    "text": p.text,
                    "char_count": p.char_count,
                }
                for p in pages
            ],
        }
        for filename, pages in pages_by_doc.items()
    ]

    timings: list[float] = []
    worker_output: Optional[list[dict]] = None
    for _ in range(TIMING_REPEATS):
        result, elapsed = _run_worker_once(payload)
        timings.append(elapsed)
        if result is None:
            print("strategy.chunk() 在 subprocess 裡失敗或逾時（詳見上方 stderr）", file=sys.stderr)
            sys.exit(1)
        if worker_output is None:
            worker_output = result

    assert worker_output is not None
    all_chunks: list[Chunk] = []
    coverage_scores: list[float] = []
    for doc in worker_output:
        filename = doc["filename"]
        chunks = [_chunk_from_dict(c) for c in doc["chunks"]]
        all_chunks.extend(chunks)
        coverage_scores.append(content_coverage(pages_by_doc[filename], chunks))

    quality_pass_rate = score_chunks(all_chunks)
    avg_content_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
    median_seconds = statistics.median(timings)
    normalized_seconds = median_seconds / BASELINE_SECONDS if BASELINE_SECONDS > 0 else median_seconds

    hard_gate_passed = quality_pass_rate >= 1.0 and avg_content_coverage >= MIN_CONTENT_COVERAGE
    if hard_gate_passed:
        cost_time = normalized_seconds
    else:
        cost_time = (
            HARD_FAILURE_BASE
            + (1 - avg_content_coverage) * 100
            + (1 - quality_pass_rate) * 100
        )

    print("---")
    print(f"cost_time:         {cost_time:.6f}")
    print(f"quality_pass_rate: {quality_pass_rate:.6f}")
    print(f"content_coverage:  {avg_content_coverage:.6f}")
    print(f"hard_gate_passed:  {hard_gate_passed}")
    print(f"seconds:           {median_seconds:.6f}")
    print(f"baseline_seconds:  {BASELINE_SECONDS:.6f}")
    print(f"num_chunks:        {len(all_chunks)}")
    print(f"strategy_name:     {getattr(strategy, 'STRATEGY_NAME', 'unnamed')}")


if __name__ == "__main__":
    run()
