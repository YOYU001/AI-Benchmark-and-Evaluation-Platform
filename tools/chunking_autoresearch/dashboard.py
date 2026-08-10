"""tools/chunking_autoresearch/dashboard.py

本機即時儀表板：讀 `results.tsv`，畫出每個指標（cost_time／quality_pass_rate／
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
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

RESULTS_TSV = Path(__file__).resolve().parent / "results.tsv"
PORT = 8765
REFRESH_SECONDS = 5

# (欄位名稱, 顯示標籤, 數字越大是不是越好)
METRICS = [
    ("cost_time", "Cost Time（效能分數，數字越低越好——不是金錢單位，這階段完全零成本）", False),
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


def _step_change_pct(prev: float, cur: float, higher_is_better: bool) -> float:
    """相對「上一個 keep 點」的變化百分比，不是相對第一筆——每個點標的是
    這一步本身有沒有進步，才回答得出「哪一輪貢獻了多少」。"""
    if prev == 0:
        return 0.0
    raw = (cur - prev) / abs(prev) * 100
    return raw if higher_is_better else -raw


def _sparkline_svg(
    values: list[float], higher_is_better: bool, width: int = 560, height: int = 150
) -> str:
    if not values:
        return "<p>（還沒有資料）</p>"
    padded_top = 28  # 給點上方的百分比標籤留空間
    plot_height = height - padded_top
    display_values = values * 2 if len(values) == 1 else values  # 只有一筆資料畫水平線，避免除以零
    lo, hi = min(display_values), max(display_values)
    span = hi - lo or 1.0
    n = len(display_values)
    step = width / max(n - 1, 1)
    coords = [
        (i * step, padded_top + plot_height - ((v - lo) / span) * plot_height)
        for i, v in enumerate(display_values)
    ]
    color = "#4caf50" if higher_is_better else "#42a5f5"
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    points_svg = []
    for i, ((x, y), v) in enumerate(zip(coords, display_values)):
        if i == 0:
            label = "baseline"
        else:
            pct = _step_change_pct(display_values[i - 1], v, higher_is_better)
            label = f"{pct:+.1f}%"
        # <title> 是瀏覽器原生 hover tooltip，不需要額外的 JS 套件
        points_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}">'
            f"<title>第 {i + 1} 筆：{v:.6f}（{label}）</title>"
            f"</circle>"
            f'<text x="{x:.1f}" y="{max(y - 10, 10):.1f}" font-size="11" fill="{color}" '
            f'text-anchor="middle">{html.escape(label)}</text>'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{polyline}" />'
        f"{''.join(points_svg)}"
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
        f"<td>{html.escape(r.get('cost_time', ''))}</td>"
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
<table><tr><th>commit</th><th>status</th><th>cost_time</th><th>description</th></tr>
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
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, PORT), Handler)
    print(f"Dashboard: http://{host}:{PORT}/  (Ctrl+C 結束)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
