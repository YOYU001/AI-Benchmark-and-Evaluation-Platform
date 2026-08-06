"""tools/chunking_autoresearch/mcp_server.py

小型 stdio MCP server，把 chunking-autoresearch 的實驗紀錄
（results.tsv）暴露給 Claude Code 查詢。

註冊方式：
    claude mcp add chunking-research -- python "<repo 絕對路徑>/tools/chunking_autoresearch/mcp_server.py"
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

RESULTS_TSV = Path(__file__).resolve().parent / "results.tsv"

mcp = FastMCP("chunking-research")


def _read_rows() -> list[dict]:
    if not RESULTS_TSV.exists():
        return []
    with RESULTS_TSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def _safe_float(value: Optional[str]) -> Optional[float]:
    """轉型失敗（例如 results.tsv 被手動編輯、欄位壞掉）回傳 None 而不是讓
    例外往外炸——這個檔案是 Hermes 的實驗迴圈自己在寫，欄位髒掉的機率不算低。
    """
    try:
        return float(value) if value else None
    except (TypeError, ValueError):
        return None


@mcp.tool()
def list_chunking_experiments(limit: int = 20) -> list[dict]:
    """列出最近的 chunking-autoresearch 實驗紀錄（最新的排最前面）。"""
    rows = _read_rows()
    return list(reversed(rows))[:limit]


@mcp.tool()
def get_best_chunking_strategy() -> Optional[dict]:
    """回傳目前 status 為 keep、cost 最低的那筆實驗紀錄。"""
    scored = [(r, _safe_float(r.get("cost"))) for r in _read_rows() if r.get("status") == "keep"]
    scored = [(r, cost) for r, cost in scored if cost is not None]
    if not scored:
        return None
    return min(scored, key=lambda pair: pair[1])[0]


@mcp.tool()
def get_chunking_experiment_summary() -> dict:
    """回傳實驗統計：keep/discard/crash 各幾筆、目前最好的 cost、最後一筆的說明。"""
    rows = _read_rows()
    kept = [r for r in rows if r.get("status") == "keep"]
    discarded = [r for r in rows if r.get("status") == "discard"]
    crashed = [r for r in rows if r.get("status") == "crash"]
    kept_costs = [c for c in (_safe_float(r.get("cost")) for r in kept) if c is not None]
    return {
        "total_experiments": len(rows),
        "kept": len(kept),
        "discarded": len(discarded),
        "crashed": len(crashed),
        "best_cost": min(kept_costs) if kept_costs else None,
        "latest_description": rows[-1]["description"] if rows else None,
    }


if __name__ == "__main__":
    mcp.run()
