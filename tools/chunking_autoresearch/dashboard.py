"""tools/chunking_autoresearch/dashboard.py

本機即時儀表板：讀 `results.tsv`，畫出每個指標（cost／quality_pass_rate／
content_coverage／seconds）隨時間變化的趨勢圖，以及相對第一筆 keep 紀錄的
成長百分比。純標準函式庫實作，不加新的相依套件——圖表用 inline SVG 手動畫，
不需要 matplotlib。

用瀏覽器打開 http://127.0.0.1:8765/ 看，頁面每 5 秒自動重新整理一次
（`results.tsv` 每次都重新讀取，Hermes 一直在背景寫新的實驗結果，頁面就會
一直更新）。

`results.tsv` 裡的每一筆紀錄都會保留（包含 discard／crash），只有失敗嘗試
的 `strategy.py` 程式碼本身會被 `program.md` 的流程用 `git reset` 丟掉——
log 保留完整歷史，才能在儀表板上看到「失敗過幾次、後來怎麼找到對的方向」
的完整趨勢，不是只看到一路向上的成功曲線。

用法：python dashboard.py
"""

from __future__ import annotations

import csv
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

RESULTS_TSV = Path(__file__).resolve().parent / "results.tsv"
PORT = 8765
REFRESH_SECONDS = 5

# (欄位名稱, 顯示標籤, 數字越大是不是越好)
METRICS = [
    ("cost", "Cost（越低越好）", False),
    ("quality_pass_rate", "Quality Pass Rate（越高越好）", True),
    ("content_coverage", "Content Coverage（越高越好）", True),
    ("seconds", "Seconds（越低越好）", False),
]


def _read_rows() -> list[dict]:
    if not RESULTS_TSV.exists():
        return []
    with RESULTS_TSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _safe_float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value else None
    except (TypeError, ValueError):
        return None


def _sparkline_svg(values: list[float], higher_is_better: bool, width: int = 560, height: int = 120) -> str:
    if not values:
        return "<p>（還沒有資料）</p>"
    if len(values) == 1:
        values = values * 2  # 只有一筆資料時畫一條水平線，避免除以零
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    n = len(values)
    step = width / max(n - 1, 1)
    coords = [(i * step, height - ((v - lo) / span) * height) for i, v in enumerate(values)]
    color = "#4caf50" if higher_is_better else "#42a5f5"
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    circles = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}" />' for x, y in coords)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{polyline}" />'
        f"{circles}"
        f"</svg>"
    )


def _growth_pct(first: float, last: float, higher_is_better: bool) -> float:
    if first == 0:
        return 0.0
    raw = (last - first) / abs(first) * 100
    return raw if higher_is_better else -raw


def render_page() -> str:
    rows = _read_rows()
    kept = [r for r in rows if r.get("status") == "keep"]

    sections = []
    for key, label, higher_is_better in METRICS:
        values = [v for v in (_safe_float(r.get(key)) for r in kept) if v is not None]
        chart = _sparkline_svg(values, higher_is_better)
        if len(values) >= 2:
            growth = _growth_pct(values[0], values[-1], higher_is_better)
            growth_str = f"{growth:+.1f}%"
        else:
            growth_str = "（還沒有足夠資料）"
        sections.append(
            f"<section><h2>{html.escape(label)}</h2>"
            f"<p>相對第一筆 keep 紀錄的成長：<strong>{growth_str}</strong></p>"
            f"{chart}</section>"
        )

    total = len(rows)
    kept_n = len(kept)
    discarded_n = sum(1 for r in rows if r.get("status") == "discard")
    crashed_n = sum(1 for r in rows if r.get("status") == "crash")

    history_rows = "".join(
        f"<tr><td>{html.escape(r.get('commit', ''))}</td>"
        f"<td>{html.escape(r.get('status', ''))}</td>"
        f"<td>{html.escape(r.get('cost', ''))}</td>"
        f"<td>{html.escape(r.get('description', ''))}</td></tr>"
        for r in reversed(rows[-30:])
    )

    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<title>chunking-autoresearch 儀表板</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background:#0b0f14; color:#e6edf3; }}
h1 {{ font-size: 1.4rem; }}
section {{ margin-bottom: 1.5rem; padding: 1rem; background:#111820; border-radius: 8px; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border-bottom: 1px solid #263140; padding: 4px 8px; text-align: left; font-size: 0.85rem; }}
.stats {{ display:flex; gap:1.5rem; margin-bottom:1.5rem; flex-wrap: wrap; }}
.stats div {{ background:#111820; padding:0.75rem 1rem; border-radius:8px; }}
</style></head>
<body>
<h1>chunking-autoresearch 儀表板</h1>
<div class="stats">
<div>總實驗數：{total}</div>
<div>keep：{kept_n}</div>
<div>discard：{discarded_n}</div>
<div>crash：{crashed_n}</div>
</div>
{"".join(sections)}
<section><h2>最近 30 筆紀錄</h2>
<table><tr><th>commit</th><th>status</th><th>cost</th><th>description</th></tr>
{history_rows}
</table></section>
<p style="opacity:.5">每 {REFRESH_SECONDS} 秒自動重新整理。資料來源：results.tsv</p>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        body = render_page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        pass  # 不用把每次 request 都印到 console


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Dashboard: http://127.0.0.1:{PORT}/  (Ctrl+C 結束)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
