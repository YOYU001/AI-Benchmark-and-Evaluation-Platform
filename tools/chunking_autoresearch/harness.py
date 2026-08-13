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

2026-08-14 補：四方 AI coding agent（Claude Code / Codex / Antigravity /
Copilot）比較實驗中，Codex 把整份文件包成單一個 prose chunk（完全不做段落
／表格拆分），結果 content_coverage 直接等於 1.0、quality_pass_rate 也合法
過關，因為切法本身在結構上仍是合法的 chunk——這是先前 content coverage 這
道關卡沒有堵住的新漏洞：只檢查「內容有沒有保留」，沒檢查「有沒有真的做到
有意義的切分」。加了 MAX_CHUNK_SHARE_OF_DOCUMENT 這道新關卡堵住這個做法。

用法：python harness.py（或 uv run harness.py）
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
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

# 單一 chunk 不能佔同一份文件超過這個比例的字元數，否則視為硬性失敗。
# 防止「整份文件包成一個 chunk」這種沒有真正做到切分、卻能讓 content
# coverage 直接滿分的取巧做法（2026-08-14 四方 AI 比較實驗中，Codex
# 實際用這招鑽過了原本的關卡，詳見上方檔案說明）。
MAX_CHUNK_SHARE_OF_DOCUMENT = 0.5

# 單一 chunk 的絕對字元數上限，不管佔文件比例多少都不能超過。
# MAX_CHUNK_SHARE_OF_DOCUMENT 單獨存在時，還是能被「把文件無腦對半切成兩塊
# （不管段落／表格邊界）」這招繞過——兩塊各佔 50%，比例上剛好卡在門檻內，
# 但一樣沒有做到「有意義的切分」。這裡的門檻抓 baseline CHUNK_SIZE（600）
# 的約 3 倍，足以擋下「切成兩三塊超大 chunk」這種粗暴做法——本次測試文件
# 字元數是 34910～59702，對半切出來的每塊都會遠遠超過這個上限。
#
# 實際安全邊際比「3 倍」聽起來的要窄：baseline 目前最大的單一 chunk（一個
# 完整表格 chunk，因為表格不會被切開）實測是 1301 字元，離 2000 的門檻只有
# 約 35% 的餘裕，不是 600 到 2000 之間的完整空間（overlap 打包＋表格整塊不
# 拆，讓實際 chunk 大小比 CHUNK_SIZE 本身大不少）。如果之後想讓策略嘗試更大
# 的 CHUNK_SIZE（例如 900 以上），很可能會直接撞上這道門檻，屆時要重新評估
# 這個常數，不是 bug，是設計上已知的取捨。
MAX_CHUNK_CHAR_COUNT = 2000

# 切出來的內容裡，重複收錄的字元 shingle 比例不能超過這個上限，否則視為
# 硬性失敗。前兩道關卡（MAX_CHUNK_SHARE_OF_DOCUMENT／MAX_CHUNK_CHAR_COUNT）
# 擋的是「切太大」；這道關卡擋的是鏡像方向——「切太碎」：把文件切成大量
# 極小、彼此高度重疊的 chunk，一樣能通過前面所有關卡（每個 chunk 格式合法、
# 內容也都保留了），但同樣不是「有意義的切分」。redundancy_ratio 是決定性
# 指標（不受計時雜訊影響，同一個策略重跑幾次數字完全一樣），適合當硬性
# 門檻用。baseline 實測 redundancy_ratio＝0.117077，這裡抓約 3.4 倍當上限，
# 跟 MAX_CHUNK_CHAR_COUNT 的「baseline 的 3 倍」抓法一致（2026-08-14 code
# review 指出這個殘留方向，見下方「補三」）。
MAX_REDUNDANCY_RATIO = 0.4

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


def _split_table_chunk_ids(chunks: list[Chunk]) -> set[str]:
    """回傳「疑似被腰斬」的 chunk_id 集合：同一份文件裡，緊接著的兩個 chunk
    都是表格類型、且 table_title 相同，代表這其實是同一張表被硬拆成兩塊，
    不是兩張各自完整的表格。"""
    bad_ids: set[str] = set()
    for prev, cur in zip(chunks, chunks[1:]):
        if (
            prev.source_filename == cur.source_filename
            and prev.chunk_type == "table"
            and cur.chunk_type == "table"
            and prev.table_title
            and prev.table_title == cur.table_title
        ):
            bad_ids.add(prev.chunk_id)
            bad_ids.add(cur.chunk_id)
    return bad_ids


def score_chunks(chunks: list[Chunk]) -> float:
    """回傳所有 chunk 裡通過結構檢查的比例，1.0 代表全部通過。結構檢查包含
    每個 chunk 自己的格式（見 _metadata_ok）以及有沒有表格被腰斬（見
    _split_table_chunk_ids）。"""
    if not chunks:
        return 0.0
    split_ids = _split_table_chunk_ids(chunks)
    ok_count = sum(1 for c in chunks if _metadata_ok(c) and c.chunk_id not in split_ids)
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


def max_chunk_share(source_pages: list[PageParseResult], chunks: list[Chunk]) -> float:
    """回傳這份文件裡，單一 chunk 的字元數佔原始文件總字元數的最高比例。

    用比例而非絕對字數，是因為四份測試文件長短差很多，固定字數上限對短文件
    太寬鬆、對長文件太嚴格；用比例才能公平地套用在不同大小的文件上。
    """
    source_char_count = sum(p.char_count for p in source_pages)
    if source_char_count == 0 or not chunks:
        return 0.0
    return max(c.char_count for c in chunks) / source_char_count


def redundancy_ratio(chunks: list[Chunk]) -> float:
    """估算切出來的內容裡，有多少比例是「重複收錄」的。做法：把每個 chunk
    的字元 shingle 攤平算出現次數，總出現次數扣掉「不重複的 shingle 種類數」，
    再除以總出現次數——分子就是「超過第一次出現、算重複」的部分。

    不跟固定字數的重疊量（例如 baseline 目前用的 100 字）比較，因為那只是
    baseline 自己選的參數，不是放諸四海皆準的標準；agent 之後可能用完全不同
    的切法。這裡只回傳「這次切出來的原始重複比例」這個數字本身，交給
    dashboard 拿去跟 baseline 自己的第一筆結果比較（跟 cost_time 的處理方式
    一樣），不在這裡預設「多少重複才算正常」。
    """
    all_shingles: list[str] = []
    for c in chunks:
        all_shingles.extend(_shingles(c.text))
    if not all_shingles:
        return 0.0
    unique_count = len(set(all_shingles))
    return (len(all_shingles) - unique_count) / len(all_shingles)


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
    chunk_share_scores: list[float] = []
    for doc in worker_output:
        filename = doc["filename"]
        chunks = [_chunk_from_dict(c) for c in doc["chunks"]]
        all_chunks.extend(chunks)
        coverage_scores.append(content_coverage(pages_by_doc[filename], chunks))
        chunk_share_scores.append(max_chunk_share(pages_by_doc[filename], chunks))

    quality_pass_rate = score_chunks(all_chunks)
    avg_content_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
    avg_redundancy_ratio = redundancy_ratio(all_chunks)
    worst_chunk_share = max(chunk_share_scores) if chunk_share_scores else 0.0
    worst_chunk_char_count = max((c.char_count for c in all_chunks), default=0)
    median_seconds = statistics.median(timings)
    normalized_seconds = median_seconds / BASELINE_SECONDS if BASELINE_SECONDS > 0 else median_seconds

    hard_gate_passed = (
        quality_pass_rate >= 1.0
        and avg_content_coverage >= MIN_CONTENT_COVERAGE
        and worst_chunk_share <= MAX_CHUNK_SHARE_OF_DOCUMENT
        and worst_chunk_char_count <= MAX_CHUNK_CHAR_COUNT
        and avg_redundancy_ratio <= MAX_REDUNDANCY_RATIO
    )
    if hard_gate_passed:
        cost_time = normalized_seconds
    else:
        cost_time = (
            HARD_FAILURE_BASE
            + (1 - avg_content_coverage) * 100
            + (1 - quality_pass_rate) * 100
            + max(0.0, worst_chunk_share - MAX_CHUNK_SHARE_OF_DOCUMENT) * 100
            + max(0.0, (worst_chunk_char_count - MAX_CHUNK_CHAR_COUNT) / MAX_CHUNK_CHAR_COUNT) * 100
            + max(0.0, avg_redundancy_ratio - MAX_REDUNDANCY_RATIO) * 100
        )

    print("---")
    print(f"cost_time:         {cost_time:.6f}")
    print(f"quality_pass_rate: {quality_pass_rate:.6f}")
    print(f"content_coverage:  {avg_content_coverage:.6f}")
    print(f"redundancy_ratio:  {avg_redundancy_ratio:.6f}")
    print(f"max_chunk_share:   {worst_chunk_share:.6f}")
    print(f"max_chunk_chars:   {worst_chunk_char_count}")
    print(f"hard_gate_passed:  {hard_gate_passed}")
    print(f"seconds:           {median_seconds:.6f}")
    print(f"baseline_seconds:  {BASELINE_SECONDS:.6f}")
    print(f"num_chunks:        {len(all_chunks)}")
    print(f"strategy_name:     {getattr(strategy, 'STRATEGY_NAME', 'unnamed')}")
    # 放在摘要最後一行，方便之後接新欄位到 results.tsv 時直接接在既有欄位後面，
    # 不用重排前面欄位順序（dashboard 的日期篩選功能要用這個）。
    print(f"timestamp:         {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    run()
