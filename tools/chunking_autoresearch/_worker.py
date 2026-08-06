"""tools/chunking_autoresearch/_worker.py

在獨立的 subprocess 裡執行 strategy.chunk()。這是四方審查（qa／codex）都指出
的問題的修法：原本 strategy.py 是直接被 import 進 harness.py 同一個
process 執行，理論上可以 monkeypatch `time.perf_counter`、改掉 harness.py
的全域常數、或做其他越權的事，「只能改 strategy.py」在那個設計下只是文件
上的約定，不是真的技術防線。

現在 harness.py 只透過 stdin/stdout 的 JSON 跟這支 subprocess 交換資料，
父行程自己的計時器、常數、模組狀態，子行程完全碰不到；父行程也可以用
`subprocess.run(timeout=...)` 強制中止跑太久或卡住的策略。

不要手動執行這支腳本，由 harness.py 呼叫。
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

import strategy
from schema import PageParseResult


def _pages_from_json(raw_pages: list[dict]) -> list[PageParseResult]:
    return [PageParseResult(**p) for p in raw_pages]


def _chunk_to_dict(chunk) -> dict:
    d = asdict(chunk)
    d["page_index_range"] = list(chunk.page_index_range)
    d["pdf_page_number_range"] = list(chunk.pdf_page_number_range)
    return d


def main() -> None:
    payload = json.load(sys.stdin)
    output = []
    for doc in payload:
        pages = _pages_from_json(doc["pages"])
        chunks = strategy.chunk(pages, doc["filename"])
        output.append(
            {
                "filename": doc["filename"],
                "chunks": [_chunk_to_dict(c) for c in chunks],
            }
        )
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
