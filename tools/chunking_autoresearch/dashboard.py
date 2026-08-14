"""tools/chunking_autoresearch/dashboard.py

NAS 上常駐的即時儀表板：讀 `results.tsv`，畫出四個指標（速度提升度／組裝正確率／
內容保留率／內容擷取範圍精確度）隨時間變化的趨勢圖，外加距離 20% 通知門檻還差多少
的進度條。純標準函式庫實作，不加新的相依套件——圖表用 inline SVG 手動畫，不需要
matplotlib，日期篩選、指標切換都靠 GET query string 讓伺服器重新算，瀏覽器端只有
搜尋歷史紀錄跟亮暗模式切換兩個小功能用原生 JS，沒有任何前端框架或建置流程。

用瀏覽器打開 http://127.0.0.1:8765/ 看。原本是每 5 秒自動整頁重新整理，但圖表變寬、
變複雜之後這樣會很明顯地閃爍，改成不自動整理——`results.tsv` 每次請求都會重新讀取，
用瀏覽器自己的重新整理（會保留目前的 URL query string，包含篩選中的日期範圍跟選定
的指標）就能看到 Hermes 背景寫入的最新結果，不用另外做一個按鈕。

`results.tsv` 裡的每一筆紀錄都會保留（包含 discard／crash），只有失敗嘗試的
`strategy.py` 程式碼本身會被 `program.md` 的流程用 `git reset` 丟掉——log 保留
完整歷史，才能在儀表板上看到「失敗過幾次、後來怎麼找到對的方向」的完整趨勢，不是
只看到一路向上的成功曲線。

四個指標的實際定義（跟 `harness.py` 對齊，避免望文生義；命名跟拆分方式參考了
`docs/rag_chunking_evaluation_metrics_research.md` 的研究整理）：
- 速度提升度（來自 `cost_time`）：跟 baseline 比，這次跑得快了幾 %。原始
  `cost_time` 數字是「越低越好」，這裡換算成「提升 %」用正向、越高越好的方式呈現。
- 組裝正確率（來自 `quality_pass_rate`）：每個 chunk 自己的格式對不對（分頁範圍、
  字數、表格標題等），加上表格有沒有被腰斬（同一張表被硬拆成兩個 chunk）的檢查。
  kept 紀錄規定一定要 100% 過關才留得下來，所以這條線幾乎都是一直線 100%，是正常
  現象，不代表沒資料或圖表壞掉。
- 內容保留率（來自 `content_coverage`）：測的是程式邏輯錯誤誤丟的資料比例——原始
  文件的內容有多少比例還留在切出來的 chunk 裡，誤丟越多這個數字越低。只抓「有沒有
  丟資料」，不抓「有沒有拿太多、重複、灌水」，那是下面內容擷取範圍精確度的工作。
- 內容擷取範圍精確度（來自 `redundancy_ratio`）：跟 baseline 比，chunk 之間重複／
  灌水的內容減少了幾 %。原始 `redundancy_ratio` 只是「這次切出來的重複比例」，沒有
  固定門檻，因為切法不同、正常重疊量本來就不一樣，只跟 baseline 自己的數字比高低，
  跟速度提升度是同一套處理邏輯。

用法：python dashboard.py
"""

from __future__ import annotations

import csv
import html
import os
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlsplit

TAIWAN_TZ = timezone(timedelta(hours=8))
RESULTS_TSV = Path(__file__).resolve().parent / "results.tsv"
PORT = 8765
NOTIFY_THRESHOLD_PCT = 20.0  # 要跟 notify.py 的 IMPROVEMENT_THRESHOLD_PCT 對齊
HISTORY_ROW_LIMIT = 500  # 歷史紀錄表最多顯示幾筆（防呆上限，不是預期常態值）；
# 超過 30 筆之後表格本身會在固定高度的框裡捲動，不會把整個頁面越撐越長

SIDEBAR_ITEMS = [
    ("dashboard", "Dashboard", True),
    ("chat", "Chat", False),
    ("user", "User", False),
    ("board", "Board", False),
    ("database", "資料庫查看", False),
    ("setting", "Setting", False),
]


# ---------------------------------------------------------------------------
# 讀資料 / 解析
# ---------------------------------------------------------------------------


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


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _enrich(rows: list[dict]) -> list[dict]:
    """幫每一列補上 parse 過的數字欄位跟時間戳記，缺 timestamp 的舊資料
    （改欄位之前寫進去的紀錄）ts 會是 None，之後一律當「未知日期」處理。"""
    out = []
    for r in rows:
        out.append(
            {
                **r,
                "_cost_time": _safe_float(r.get("cost_time")),
                "_quality_pass_rate": _safe_float(r.get("quality_pass_rate")),
                "_content_coverage": _safe_float(r.get("content_coverage")),
                "_redundancy_ratio": _safe_float(r.get("redundancy_ratio")),
                "_seconds": _safe_float(r.get("seconds")),
                "_same_session_baseline_cost_time": _safe_float(r.get("same_session_baseline_cost_time")),
                "_ts": _parse_ts(r.get("timestamp")),
            }
        )
    return out


def _to_taiwan(ts: datetime) -> datetime:
    """只有帶時區資訊（aware）的時間才能安全轉換，沒有時區資訊的舊資料維持原樣。"""
    return ts.astimezone(TAIWAN_TZ) if ts.tzinfo is not None else ts


def _fmt_date(ts: Optional[datetime]) -> str:
    """統一換算成台灣時間再顯示。harness.py 正常寫入的 timestamp 是 UTC（結尾 +00:00，
    來自 `datetime.now(timezone.utc).isoformat()`），但少數用 `git log --format=%cI`
    補記的舊資料是本地時間（結尾 +08:00）——兩種格式如果不先統一轉成同一個時區就直接
    印出來，會出現同一份歷史紀錄裡的時間互相對不齊、甚至讓人誤判成完全不合理的時間點
    （例如把 UTC 的下午誤看成凌晨）。"""
    if ts is None:
        return "未知日期"
    return _to_taiwan(ts).strftime("%Y-%m-%d %H:%M")


def _filter_by_date(rows: list[dict], start: str, end: str) -> list[dict]:
    """沒有選日期範圍時回傳全部（含未知日期的舊資料）；一旦選了任一邊，未知日期
    的舊資料就篩不到（沒有時間可以比對），這是使用者確認過的行為。"""
    if not start and not end:
        return rows
    filtered = []
    for r in rows:
        ts = r["_ts"]
        if ts is None:
            continue
        d = _to_taiwan(ts).date().isoformat()
        if start and d < start:
            continue
        if end and d > end:
            continue
        filtered.append(r)
    return filtered


# ---------------------------------------------------------------------------
# 指標定義
# ---------------------------------------------------------------------------


def _first_value(rows: list[dict], key: str) -> Optional[float]:
    """從（未經日期篩選的）完整歷史裡找第一筆有值的紀錄，當作 baseline 用。
    務必傳未篩選過的 rows 進來——如果傳篩選後的列表，日期篩選一旦排除掉真正的
    第一筆實驗，篩選後的第一筆會被誤當成新的 baseline，導致同一筆實驗在篩選
    前後顯示不同的進步幅度（QA／codex 審查抓到的問題）。"""
    return next((r[key] for r in rows if r.get(key) is not None), None)


def _speed_baseline(all_kept: list[dict]) -> Optional[float]:
    return _first_value(all_kept, "_cost_time")


def _same_session_pct(r: dict) -> Optional[float]:
    """回傳這一筆「同時段重測基準」跟「這次 cost_time」比較出來的 %，
    沒有資料就回傳 None。跟最原始 baseline 比的累積 % 會受機器負載波動
    影響失真，這個數字排除了機器負載的干擾，比較準確反映單一這次改動
    實際的效果。"""
    base = r.get("_same_session_baseline_cost_time")
    cur = r.get("_cost_time")
    if base is None or cur is None or base == 0:
        return None
    return (base - cur) / base * 100


def _same_session_note(r: dict) -> str:
    """跟最原始 baseline 比的累積 % 會受機器負載波動影響失真（同一份程式碼，
    機器忙的時候跑起來就是比較慢，看起來像退步）。Hermes 每輪決定 keep/discard
    時，其實有另外在同一個時間窗口重新測過 attempt_base 的版本、排除掉機器負載
    的干擾，這裡把那個「同時段公平比較」的數字顯示出來，比跟很久以前的歷史
    baseline 比更準確反映「這次改動」實際的效果。舊資料沒有這個欄位就不顯示，
    不強迫補資料。"""
    base = r.get("_same_session_baseline_cost_time")
    cur = r.get("_cost_time")
    pct = _same_session_pct(r)
    if pct is None:
        return ""
    return f"\n同時段重測基準：{base:.4f} → 本次：{cur:.4f}（{pct:+.1f}%，已排除機器負載雜訊）"


def _speed_improvement_series(kept: list[dict], baseline: Optional[float]) -> list[Optional[float]]:
    out = []
    for r in kept:
        v = r["_cost_time"]
        if v is None or baseline is None or baseline == 0:
            out.append(None)
        else:
            out.append((baseline - v) / baseline * 100)
    return out


def _coverage_baseline(all_kept: list[dict]) -> Optional[float]:
    v = _first_value(all_kept, "_content_coverage")
    return None if v is None else (1 - v) * 100


def _coverage_improvement_series(kept: list[dict], baseline: Optional[float]) -> list[Optional[float]]:
    """content_coverage 原始值是「保留率」，但概念上這裡真正在追蹤的是「誤丟率」
    （= 1 - 保留率，越低越好）。用跟 baseline 比「差幾個百分點」（直接相減），不是
    「差幾成」（除以 baseline 算比例）——因為 baseline 的誤丟率通常非常接近 0，
    除法算比例會把一點點差距放大成離譜的數字（例如從 0.04% 變成 0.5%，算比例會
    變成「差了1096%」），改成百分點的直接相減就穩定、看得懂多了。"""
    out = []
    for r in kept:
        v = r["_content_coverage"]
        if v is None or baseline is None:
            out.append(None)
        else:
            out.append(baseline - (1 - v) * 100)
    return out


def _redundancy_baseline(all_kept: list[dict]) -> Optional[float]:
    return _first_value(all_kept, "_redundancy_ratio")


def _redundancy_improvement_series(kept: list[dict], baseline: Optional[float]) -> list[Optional[float]]:
    """redundancy_ratio 原始值是「重複比例」，越低越好；這裡跟 baseline 自己的
    第一筆結果比較，換算成「重複減少了幾 %」的正向數字，跟速度提升度同一套處理
    方式——不跟固定門檻比，只跟 baseline 自己比。"""
    out = []
    for r in kept:
        v = r["_redundancy_ratio"]
        if v is None or baseline is None or baseline == 0:
            out.append(None)
        else:
            out.append((baseline - v) / baseline * 100)
    return out


METRICS = {
    "cost_time": {
        "label": "速度提升度",
        "desc": (
            "跟最原始 baseline 比，這次跑得快了幾 %（正向表示，越高越好）——"
            "但這是跟很久以前記錄的歷史數字比，機器負載如果在不同時段差很多，"
            "這個累積 % 可能會失真（明明有進步卻顯示一大截負成長）。滑鼠移到"
            "下面圖上的每個點，如果有「同時段重測基準」的資訊，那才是排除機器"
            "負載干擾、比較準確反映這次改動實際效果的數字。"
        ),
        "unit": "%",
        "higher_is_better": True,
        "color": "#4f8cff",
        "baseline_relative": True,
        "baseline_fn": _speed_baseline,
        "series_fn": _speed_improvement_series,
    },
    "quality_pass_rate": {
        "label": "組裝正確率",
        "desc": (
            "每個 chunk 自己的格式對不對（分頁範圍／字數／表格標題）以及表格有沒有被腰斬的檢查。"
            "kept 紀錄規定一定要 100% 過關才留得下來，所以這條線幾乎都是一直線 100%——"
            "這是正常現象，代表沒有任何一筆留下來的結果組裝出錯；真正因組裝錯誤被刷掉的嘗試，"
            "會出現在下面的 discard 歷史紀錄，不會畫進這張圖。"
        ),
        "unit": "%",
        "higher_is_better": True,
        "color": "#8a7cff",
        "baseline_fn": lambda all_kept: None,
        "series_fn": lambda kept, baseline: [
            None if r["_quality_pass_rate"] is None else r["_quality_pass_rate"] * 100 for r in kept
        ],
    },
    "content_coverage": {
        "label": "內容保留率",
        "desc": (
            "卡片大數字是原始絕對保留率（最新一筆 keep 實際測到的比例，100% 代表完全沒丟東西，"
            "跟「組裝正確率」卡片同一種呈現方式）。下面小字徽章跟折線圖走的是另一套算法：跟 "
            "baseline 比，誤丟率少了幾個百分點（正向表示，越高越好——用百分點直接相減，不是算"
            "比例，因為 baseline 的誤丟率通常非常接近 0，算比例會被一點點差距放大成離譜的數字）。"
        ),
        "unit": " 個百分點",
        "higher_is_better": True,
        "color": "#f2b134",
        "baseline_relative": True,
        "baseline_fn": _coverage_baseline,
        "series_fn": _coverage_improvement_series,
    },
    "redundancy_ratio": {
        "label": "內容擷取範圍精確度",
        "desc": "跟 baseline 比，chunk 之間重複／灌水的內容減少了幾 %（正向表示，越高越好）。",
        "unit": "%",
        "higher_is_better": True,
        "color": "#2fbf8f",
        "baseline_relative": True,
        "baseline_fn": _redundancy_baseline,
        "series_fn": _redundancy_improvement_series,
    },
}


# ---------------------------------------------------------------------------
# SVG 圖表
# ---------------------------------------------------------------------------


def _mini_sparkline_svg(values: list[float], color: str, width: int = 220, height: int = 64) -> str:
    if not values:
        return '<svg viewBox="0 0 220 64" width="100%" height="64"></svg>'
    display = values * 2 if len(values) == 1 else values
    lo, hi = min(display), max(display)
    span = hi - lo or 1.0
    n = len(display)
    step = width / max(n - 1, 1)
    pad = 6
    plot_h = height - pad * 2
    coords = [(i * step, pad + plot_h - ((v - lo) / span) * plot_h) for i, v in enumerate(display)]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2.5" stroke-linecap="round" '
        f'stroke-linejoin="round" points="{polyline}" />'
        f"</svg>"
    )


def _big_chart_svg(
    points: list[dict],
    higher_is_better: bool,
    unit: str,
    accent_color: str,
    grad_id: str,
    baseline_relative: bool = False,
    width: int = 760,
    height: int = 320,
) -> str:
    """points: [{"value": float, "x_label": str, "commit": str, "description": str}, ...]"""
    if not points:
        return '<p class="empty">（還沒有資料）</p>'

    # 左邊留白要跟著單位文字長度變，不然「個百分點」這種長單位的刻度數字會
    # 跟左側直書的座標軸標題疊在一起（原本固定 60px 是抓「%」「s」這種短單位）。
    left_pad, top_pad, right_pad, bottom_pad = 66 + len(unit) * 11, 20, 24, 44

    # 使用者明確要求：不管點數多少，圖表一律用固定像素寬（每個點留夠讓日期標籤
    # 不會互相重疊的間距，不是把點擠更近），外層永遠包一層 overflow-x:auto 的
    # 捲動容器——點數不夠多、寬度小於容器可視範圍時瀏覽器本來就不會生出捲軸
    # （這是正常行為，不是沒做），但只要點數一多到超出可視範圍，捲軸機制保證
    # 都在，不用另外判斷「需不需要」。
    # 110px 是抓「YYYY-MM-DD」這種 10 字元日期標籤在 font-size 10 底下的寬度
    # 再留一點間隙，兩個點的間距只要不小於這個數字，相鄰的日期標籤就不會重疊。
    min_point_spacing = 110
    width = max(width, left_pad + right_pad + max(len(points) - 1, 0) * min_point_spacing)

    plot_w = width - left_pad - right_pad
    plot_h = height - top_pad - bottom_pad

    values = [p["value"] for p in points]
    lo, hi = min(values), max(values)
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    span = hi - lo
    n = len(points)
    step_x = plot_w / max(n - 1, 1)

    def x_at(i: int) -> float:
        return left_pad + i * step_x

    def y_at(v: float) -> float:
        return top_pad + plot_h - (v - lo) / span * plot_h

    coords = [(x_at(i), y_at(p["value"])) for i, p in enumerate(points)]

    grid = []
    ticks = 4
    for t in range(ticks + 1):
        val = lo + span * t / ticks
        y = y_at(val)
        grid.append(
            f'<line x1="{left_pad}" y1="{y:.1f}" x2="{width - right_pad}" y2="{y:.1f}" '
            f'class="grid-line" />'
            f'<text x="{left_pad - 8:.1f}" y="{y + 4:.1f}" font-size="11" class="axis-label" '
            f'text-anchor="end">{val:.1f}{unit}</text>'
        )

    # 置中對齊（text-anchor="middle"）的文字，中心點卡在最左/最右邊界上時，
    # 會有將近一半的文字寬度超出 SVG 的 viewBox 範圍被裁掉——第一筆跟最後一筆
    # 改成貼齊邊界內側對齊（start／end），不再置中，才不會被裁到看不全。
    # min_point_spacing 本身已經保證點與點之間留夠標籤寬度，所以每個點都可以
    # 直接標日期，不用再像以前那樣每隔幾個點才標一次（那是為了省空間，現在
    # 反而讓標籤看起來稀疏又跳號，不需要了——寬度不夠看就交給橫向捲軸處理）。
    x_labels = []
    for i, p in enumerate(points):
        if i == 0:
            anchor = "start"
        elif i == n - 1:
            anchor = "end"
        else:
            anchor = "middle"
        x_labels.append(
            f'<text x="{x_at(i):.1f}" y="{height - bottom_pad + 18:.1f}" font-size="10" '
            f'class="axis-label" text-anchor="{anchor}">{html.escape(p["x_label"])}</text>'
        )

    # baseline 參考線：這幾個指標的數列本身就是「跟 baseline 比的差距」，baseline
    # 永遠對應數值 0（第一筆點本身就是 0），畫一條橫線讓其他點跟 baseline 的落差
    # 一眼就看得出來，不用每次都對照最左邊那個點。
    baseline_line = ""
    if baseline_relative and lo <= 0 <= hi:
        by = y_at(0)
        baseline_line = (
            f'<line x1="{left_pad}" y1="{by:.1f}" x2="{width - right_pad}" y2="{by:.1f}" '
            f'stroke="#8fa3b8" stroke-width="1.5" stroke-dasharray="4,4" />'
            f'<text x="{width - right_pad - 4:.1f}" y="{by - 6:.1f}" font-size="10" '
            f'class="axis-label" text-anchor="end">baseline</text>'
        )

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    baseline_y = top_pad + plot_h
    area_path = (
        f"M{coords[0][0]:.1f},{baseline_y:.1f} "
        + " ".join(f"L{x:.1f},{y:.1f}" for x, y in coords)
        + f" L{coords[-1][0]:.1f},{baseline_y:.1f} Z"
    )

    point_svgs = []
    for i, ((x, y), p) in enumerate(zip(coords, points)):
        if i == 0:
            color = "#8fa3b8"
            label = "baseline"
        else:
            prev_val = points[i - 1]["value"]
            diff = p["value"] - prev_val
            improved = diff > 0 if higher_is_better else diff < 0
            color = "#4caf50" if improved else ("#ef5350" if diff != 0 else "#8fa3b8")
            if baseline_relative:
                # 這幾個指標的數列本身已經是「跟 baseline 比的差距」，第一筆
                # 恆為 0，再對這個數列算一次「相對前一點的比例」一樣會除以
                # 接近 0 的分母、炸出離譜數字（跟之前修過的百分點問題同一類）。
                # 直接顯示兩點間的差距（跟數列本身同單位），不要再換算成比例。
                label = f"{diff:+.2f}{unit}"
            else:
                pct = 0.0 if prev_val == 0 else diff / abs(prev_val) * 100
                label = f"{pct:+.1f}%"
        tooltip_text = (
            f"第 {i + 1} 筆（{p['commit']}）：{p['value']:.4f}{unit}（{label}）"
            f"{p.get('extra_note', '')}\n{p['description']}"
        )
        tooltip_attr = html.escape(tooltip_text).replace("\n", "&#10;")
        point_svgs.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" class="chart-point" '
            f'data-tip="{tooltip_attr}" '
            f'onmouseenter="showTip(event,this)" onmousemove="moveTip(event)" onmouseleave="hideTip()">'
            f"</circle>"
        )

    y_axis_title = (
        f'<text x="16" y="{top_pad + plot_h / 2:.1f}" font-size="11" class="axis-label" '
        f'text-anchor="middle" transform="rotate(-90 16 {top_pad + plot_h / 2:.1f})">數值（{unit}）</text>'
    )
    x_axis_title = (
        f'<text x="{left_pad + plot_w / 2:.1f}" y="{height - 4}" font-size="11" class="axis-label" '
        f'text-anchor="middle">實驗次序（保留下來的嘗試，依時間先後）</text>'
    )

    # SVG 一律用固定像素寬（不是 100%），外層 .chart-scroll 才有東西可以捲——
    # 點數不夠多、寬度小於容器可視範圍時瀏覽器自然不會顯示捲軸，但捲動機制
    # 本身一律都在，不看點數多寡切換模式。
    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" '
        f'style="display:block;min-width:{width}px">'
        f"<defs><linearGradient id=\"{grad_id}\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">"
        f'<stop offset="0%" stop-color="{accent_color}" stop-opacity="0.35" />'
        f'<stop offset="100%" stop-color="{accent_color}" stop-opacity="0.02" />'
        f"</linearGradient></defs>"
        f"{''.join(grid)}"
        f"{baseline_line}"
        f'<path d="{area_path}" fill="url(#{grad_id})" stroke="none" />'
        f'<polyline fill="none" stroke="{accent_color}" stroke-width="3" stroke-linecap="round" '
        f'stroke-linejoin="round" points="{polyline}" />'
        f"{''.join(point_svgs)}"
        f"{''.join(x_labels)}"
        f"{y_axis_title}{x_axis_title}"
        f"</svg>"
    )
    return f'<div class="chart-scroll">{svg}</div>'


def _growth_pct(first: float, last: float, higher_is_better: bool) -> float:
    if first == 0:
        return 0.0
    raw = (last - first) / abs(first) * 100
    return raw if higher_is_better else -raw


# ---------------------------------------------------------------------------
# 頁面組裝
# ---------------------------------------------------------------------------


def _sidebar_html(active_page: str) -> str:
    items = []
    for key, label, enabled in SIDEBAR_ITEMS:
        classes = "nav-item"
        if key == active_page:
            classes += " active"
        if not enabled:
            classes += " disabled"
            items.append(
                f'<div class="{classes}" title="待開發">{html.escape(label)} '
                f'<span class="badge-soon">待開發</span></div>'
            )
        else:
            items.append(f'<a class="{classes}" href="/">{html.escape(label)}</a>')
    return "".join(items)


def _minicard_html(
    key: str,
    cfg: dict,
    series: list[Optional[float]],
    selected: bool,
    qs_keep: str,
    extra_line: str = "",
    card_value_override: Optional[str] = None,
) -> str:
    clean = [v for v in series if v is not None]
    if len(clean) >= 2:
        if cfg.get("baseline_relative"):
            # 這幾個指標的原始數列本來就是「跟 baseline 比的累積進步 %」，
            # 大數字（metric-card-value）已經在顯示這個累積值了——小字徽章
            # 改成「這一筆比上一筆 keep 又進步了幾個百分點」，用直接相減
            # 就好（數列本身是可加減的百分點差距，不是比例，不會有除以 0
            # 的問題），這樣兩個數字才各自有意義，不會重複顯示同一個東西。
            growth = clean[-1] - clean[-2]
        else:
            growth = _growth_pct(clean[0], clean[-1], cfg["higher_is_better"])
        growth_str = f"{growth:+.1f}{cfg['unit']}"
        growth_class = "up" if growth >= 0 else "down"
        latest = f"{clean[-1]:.2f}{cfg['unit']}"
    elif len(clean) == 1:
        growth_str = "（還沒有足夠資料比較）"
        growth_class = ""
        latest = f"{clean[0]:.2f}{cfg['unit']}"
    else:
        growth_str = "（尚無資料）"
        growth_class = ""
        latest = "—"

    # content_coverage 這類指標的「大數字」改顯示原始絕對值（例如 99.96%），
    # 不是跟 baseline 的差值——差值本身在還沒有任何嘗試動到內容邏輯時永遠是
    # 0，看起來像沒資料，改成絕對值後 100% 才能直觀對應「完全沒丟東西」，
    # 跟「組裝正確率」卡片的呈現方式一致。折線圖／成長徽章的趨勢邏輯不受影響，
    # 只有這個 headline 數字換算法。
    if card_value_override is not None:
        latest = card_value_override

    spark = _mini_sparkline_svg(clean, cfg["color"])
    active_class = " active" if selected else ""
    href = f"/?metric={key}{qs_keep}"
    extra_line_html = (
        f'<div class="metric-card-extra">{html.escape(extra_line)}</div>' if extra_line else ""
    )
    return (
        f'<a class="metric-card{active_class}" href="{html.escape(href)}">'
        f'<div class="metric-card-label">{html.escape(cfg["label"])}</div>'
        f'<div class="metric-card-value">{latest}</div>'
        f'<div class="metric-card-growth {growth_class}">{growth_str}</div>'
        f"{extra_line_html}"
        f'<div class="metric-card-spark">{spark}</div>'
        f"</a>"
    )


def render_page(query: dict) -> str:
    selected_metric = query.get("metric", ["cost_time"])[0]
    if selected_metric not in METRICS:
        selected_metric = "cost_time"
    start = query.get("start", [""])[0]
    end = query.get("end", [""])[0]

    all_rows = _enrich(_read_rows())
    # baseline 一律從「完整、未經日期篩選」的歷史裡算，日期篩選只決定要顯示
    # 哪些點——不然只要篩選範圍剛好排除掉第一筆實驗，篩選後的第一筆就會被誤當
    # 成新的 baseline，同一筆實驗在篩選前後會顯示不同的進步幅度（codex 審查
    # 抓到的問題）。
    all_kept = [r for r in all_rows if r.get("status") == "keep"]
    rows = _filter_by_date(all_rows, start, end)
    kept = [r for r in rows if r.get("status") == "keep"]

    qs_keep = ""
    if start:
        qs_keep += f"&start={html.escape(start)}"
    if end:
        qs_keep += f"&end={html.escape(end)}"

    # 每個指標的 baseline 都從 all_kept 算一次，series 才用（可能被日期篩選過的）
    # kept 算要顯示的點。
    metric_series: dict[str, list[Optional[float]]] = {}
    for key, cfg in METRICS.items():
        baseline = cfg["baseline_fn"](all_kept)
        metric_series[key] = cfg["series_fn"](kept, baseline)

    # --- 距離通知門檻 ---
    speed_clean = [v for v in metric_series["cost_time"] if v is not None]
    best_speed_pct = max(speed_clean) if speed_clean else 0.0
    threshold_progress = max(0.0, min(100.0, best_speed_pct / NOTIFY_THRESHOLD_PCT * 100))
    threshold_note = (
        f"已達 {NOTIFY_THRESHOLD_PCT:.0f}% 通知門檻，等待新紀錄"
        if best_speed_pct >= NOTIFY_THRESHOLD_PCT
        else f"距離 {NOTIFY_THRESHOLD_PCT:.0f}% 通知門檻還差 {NOTIFY_THRESHOLD_PCT - best_speed_pct:.1f} 個百分點"
    )

    # --- 四個小卡片 ---
    # cost_time 卡片額外加一行「最新一筆同時段比較」——主要的累積 % 徽章跟
    # 最原始 baseline 比，機器負載波動時容易失真；這行是排除負載干擾、只看
    # 最新這一筆改動的準確數字，兩個一起顯示，不用只靠 tooltip 才看得到。
    latest_same_session_pct = _same_session_pct(kept[-1]) if kept else None
    cost_time_extra = (
        f"最新一筆同時段比較：{latest_same_session_pct:+.1f}%"
        if latest_same_session_pct is not None
        else ""
    )
    # content_coverage 的「大數字」改顯示原始絕對保留率（例如 99.96%），不是
    # 跟 baseline 的差值，理由見 _minicard_html 裡的註解。
    latest_coverage = kept[-1].get("_content_coverage") if kept else None
    content_coverage_card_value = (
        f"{latest_coverage * 100:.2f}%" if latest_coverage is not None else None
    )
    minicards = "".join(
        _minicard_html(
            key,
            cfg,
            metric_series[key],
            key == selected_metric,
            qs_keep,
            extra_line=cost_time_extra if key == "cost_time" else "",
            card_value_override=content_coverage_card_value if key == "content_coverage" else None,
        )
        for key, cfg in METRICS.items()
    )

    # --- 中間大圖 ---
    cfg = METRICS[selected_metric]
    big_label, big_unit, big_higher, big_color = cfg["label"], cfg["unit"], cfg["higher_is_better"], cfg["color"]
    series = metric_series[selected_metric]

    big_points = [
        {
            "value": v,
            "x_label": _fmt_date(r["_ts"])[:10] if r["_ts"] else f"#{i + 1}",
            "commit": r.get("commit") or "",
            "description": r.get("description") or "",
            "extra_note": _same_session_note(r) if selected_metric == "cost_time" else "",
        }
        for i, (r, v) in enumerate(zip(kept, series))
        if v is not None
    ]
    big_chart = _big_chart_svg(
        big_points,
        big_higher,
        big_unit,
        big_color,
        f"chartGrad_{selected_metric}",
        baseline_relative=cfg.get("baseline_relative", False),
    )
    big_desc = cfg["desc"]

    # --- 右側統計 ---
    total = len(rows)
    kept_n = len(kept)
    discarded_n = sum(1 for r in rows if r.get("status") == "discard")
    crashed_n = sum(1 for r in rows if r.get("status") == "crash")
    max_count = max(kept_n, discarded_n, crashed_n, 1)

    def _bar(label: str, count: int, color: str) -> str:
        pct = count / max_count * 100
        return (
            f'<div class="stat-bar-row"><span class="stat-bar-label">{label}</span>'
            f'<div class="stat-bar-track"><div class="stat-bar-fill" style="width:{pct:.0f}%;background:{color}"></div></div>'
            f'<span class="stat-bar-count">{count}</span></div>'
        )

    stats_bars = (
        _bar("keep", kept_n, "#4caf50") + _bar("discard", discarded_n, "#ffa726") + _bar("crash", crashed_n, "#ef5350")
    )

    latest_seconds = kept[-1]["_seconds"] if kept and kept[-1]["_seconds"] is not None else None
    latest_seconds_str = f"{latest_seconds:.3f} 秒" if latest_seconds is not None else "—"

    # --- 歷史紀錄表 ---
    # `csv.DictReader` 遇到「欄位數比表頭少」的資料列時，缺的欄位值是 None
    # （restval 預設值），不是空字串——`r.get(key, "")` 只有在 key 不存在時才會
    # 用到 default，key 存在但值是 None 時還是回傳 None，直接丟給 html.escape()
    # 會炸掉。這裡一律用 `or ""` 把 None 轉成空字串，不管是 key 不存在還是值是
    # None 都能安全處理，短列資料不會讓整頁掛掉。
    history_rows = "".join(
        f'<tr><td>{html.escape(_fmt_date(r["_ts"]))}</td>'
        f'<td>{html.escape(r.get("commit") or "")}</td>'
        f'<td class="status-{html.escape(r.get("status") or "")}">{html.escape(r.get("status") or "")}</td>'
        f'<td>{html.escape(r.get("cost_time") or "")}</td>'
        f'<td>{html.escape(r.get("description") or "")}</td></tr>'
        for r in reversed(rows[-HISTORY_ROW_LIMIT:])
    )
    history_count = min(len(rows), HISTORY_ROW_LIMIT)

    date_label = f"{start or '最早'} ~ {end or '最新'}" if (start or end) else "全部日期"

    return f"""<!doctype html>
<html lang="zh-Hant" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>chunking-autoresearch 儀表板</title>
<style>
:root {{
  --bg: #eef1fb; --panel: #ffffff; --sidebar: #3366ff; --sidebar-text: #d6e0ff;
  --text: #16213a; --muted: #7a88a8; --accent: #3366ff; --chart-area: rgba(51,102,255,0.14);
  --grid: #eef1fb; --border: #eaedf7;
}}
html[data-theme="dark"] {{
  --bg: #0b0f14; --panel: #121a24; --sidebar: #0e1520; --sidebar-text: #a9b8cf;
  --text: #e6edf3; --muted: #8695ab; --accent: #63a4ff; --chart-area: rgba(99,164,255,0.14);
  --grid: #223142; --border: #223142;
}}
* {{ box-sizing: border-box; }}
body {{ font-family: system-ui, -apple-system, "Noto Sans TC", sans-serif; margin: 0; background: var(--bg); color: var(--text); }}
.layout {{ display: flex; min-height: 100vh; }}
.sidebar {{ width: 200px; flex-shrink: 0; background: var(--sidebar); color: var(--sidebar-text); padding: 1.25rem 1rem; }}
.sidebar-brand {{ font-weight: 700; font-size: 1.1rem; color: #fff; margin-bottom: 1.5rem; }}
.nav-item {{ display: block; padding: 0.55rem 0.75rem; border-radius: 8px; color: var(--sidebar-text); text-decoration: none; margin-bottom: 0.25rem; font-size: 0.9rem; }}
.nav-item.active {{ background: rgba(255,255,255,0.18); color: #fff; font-weight: 600; }}
.nav-item.disabled {{ opacity: 0.5; display: flex; justify-content: space-between; align-items: center; cursor: default; }}
.badge-soon {{ font-size: 0.65rem; background: rgba(255,255,255,0.15); padding: 0.1rem 0.4rem; border-radius: 6px; }}
.main {{ flex: 1; min-width: 0; }}
.topbar {{ display: flex; align-items: center; gap: 1rem; padding: 0.9rem 1.5rem; background: var(--panel); border-bottom: 1px solid var(--border); flex-wrap: wrap; }}
.topbar input[type="text"], .topbar input[type="date"] {{ background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 0.45rem 0.7rem; color: var(--text); font-size: 0.85rem; }}
.search-box {{ flex: 1; min-width: 160px; }}
.date-form {{ display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; color: var(--muted); }}
.theme-toggle, .bell {{ background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 0.45rem 0.6rem; cursor: pointer; font-size: 0.9rem; color: var(--text); position: relative; }}
.avatar {{ width: 32px; height: 32px; border-radius: 50%; background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: 600; }}
.content {{ padding: 1.5rem; }}
h1 {{ font-size: 1.5rem; margin: 0 0 0.2rem; }}
.subtitle {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 1.25rem; }}
.panel {{ background: var(--panel); border-radius: 16px; padding: 1.1rem 1.25rem; border: 1px solid var(--border); box-shadow: 0 2px 10px rgba(30,50,100,0.06); }}
.chart-tooltip {{ position: fixed; display: none; background: #1f2937; color: #fff; padding: 0.5rem 0.7rem; border-radius: 8px; font-size: 0.78rem; white-space: pre-line; max-width: 280px; box-shadow: 0 4px 14px rgba(0,0,0,0.28); z-index: 999; pointer-events: none; line-height: 1.4; }}
.chart-point {{ cursor: pointer; }}
.history-scroll {{ max-height: 420px; overflow-y: scroll; margin-top: 0.5rem; }}
.chart-scroll {{ overflow-x: auto; padding-bottom: 12px; scrollbar-width: thin; }}
.chart-scroll::-webkit-scrollbar {{ height: 7px; }}
.chart-scroll::-webkit-scrollbar-track {{ background: transparent; }}
.chart-scroll::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
.history-scroll table {{ margin-top: 0; }}
.history-scroll thead th {{ position: sticky; top: 0; background: var(--panel); z-index: 1; }}
.grid-top {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1rem; }}
.metric-card {{ display: block; text-decoration: none; color: var(--text); }}
.metric-card-label {{ font-size: 0.8rem; color: var(--muted); }}
.metric-card-value {{ font-size: 1.5rem; font-weight: 700; margin: 0.15rem 0; }}
.metric-card-growth {{ font-size: 0.8rem; }}
.metric-card-growth.up {{ color: #2e9e4a; }}
.metric-card-growth.down {{ color: #e05353; }}
.metric-card-extra {{ font-size: 0.72rem; color: var(--muted); margin-top: 0.15rem; }}
.metric-card.active {{ outline: 2px solid var(--accent); }}
.composite-panel {{ display: flex; justify-content: space-between; align-items: center; gap: 1.5rem; margin-bottom: 1rem; flex-wrap: wrap; }}
.composite-score {{ font-size: 2.2rem; font-weight: 800; color: var(--accent); }}
.progress-track {{ background: var(--grid); border-radius: 6px; height: 10px; width: 260px; overflow: hidden; }}
.progress-fill {{ background: var(--accent); height: 100%; }}
.body-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; align-items: start; }}
.body-grid > .panel {{ min-width: 0; }}
.side-stack {{ display: flex; flex-direction: column; gap: 1rem; }}
.stat-bar-row {{ display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; font-size: 0.8rem; }}
.stat-bar-label {{ width: 56px; color: var(--muted); }}
.stat-bar-track {{ flex: 1; background: var(--grid); border-radius: 6px; height: 8px; overflow: hidden; }}
.stat-bar-fill {{ height: 100%; }}
.stat-bar-count {{ width: 28px; text-align: right; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 0.75rem; }}
td, th {{ border-bottom: 1px solid var(--border); padding: 5px 8px; text-align: left; font-size: 0.8rem; }}
.status-keep {{ color: #2e9e4a; }}
.status-discard {{ color: #d99a2b; }}
.status-crash {{ color: #e05353; }}
.grid-line {{ stroke: var(--grid); stroke-width: 1; }}
.axis-label {{ fill: var(--muted); }}
.empty {{ color: var(--muted); font-size: 0.85rem; }}
.section-title {{ font-weight: 600; margin-bottom: 0.5rem; }}
.footnote {{ color: var(--muted); font-size: 0.75rem; margin-top: 1rem; }}
@media (max-width: 900px) {{
  .layout {{ flex-direction: column; }}
  .sidebar {{ width: 100%; display: flex; gap: 0.5rem; overflow-x: auto; }}
  .grid-top {{ grid-template-columns: repeat(2, 1fr); }}
  .body-grid {{ grid-template-columns: 1fr; }}
}}
</style>
<script>
(function() {{
  var saved = localStorage.getItem('dashboard-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
}})();
function toggleTheme() {{
  var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  var next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('dashboard-theme', next);
}}
function filterHistory(q) {{
  q = q.toLowerCase();
  document.querySelectorAll('#historyTable tbody tr').forEach(function(tr) {{
    tr.style.display = tr.textContent.toLowerCase().indexOf(q) === -1 ? 'none' : '';
  }});
}}
function showTip(evt, el) {{
  var tip = document.getElementById('chartTooltip');
  tip.textContent = el.getAttribute('data-tip');
  tip.style.display = 'block';
  moveTip(evt);
}}
function moveTip(evt) {{
  var tip = document.getElementById('chartTooltip');
  if (tip.style.display !== 'block') return;
  var x = evt.clientX + 14, y = evt.clientY + 14;
  var maxX = window.innerWidth - tip.offsetWidth - 10;
  var maxY = window.innerHeight - tip.offsetHeight - 10;
  tip.style.left = Math.max(4, Math.min(x, maxX)) + 'px';
  tip.style.top = Math.max(4, Math.min(y, maxY)) + 'px';
}}
function hideTip() {{
  document.getElementById('chartTooltip').style.display = 'none';
}}
document.addEventListener('DOMContentLoaded', function() {{
  // 資料點是舊到新由左到右排列，圖表捲動容器預設停在最左邊（最舊那筆），
  // 使用者一打開頁面反而看不到最新結果，要自己往右捲——載入時直接捲到底，
  // 預設就看得到最新一筆。
  document.querySelectorAll('.chart-scroll').forEach(function(el) {{
    el.scrollLeft = el.scrollWidth;
  }});
}});
</script>
</head>
<body onload="(function(){{var t=localStorage.getItem('dashboard-theme'); if(t) document.documentElement.setAttribute('data-theme', t);}})()">
<div id="chartTooltip" class="chart-tooltip"></div>
<div class="layout">
  <nav class="sidebar">
    <div class="sidebar-brand">chunking-autoresearch</div>
    {_sidebar_html("dashboard")}
  </nav>
  <div class="main">
    <div class="topbar">
      <input class="search-box" type="text" placeholder="搜尋歷史紀錄（commit / 說明）" oninput="filterHistory(this.value)">
      <form class="date-form" method="get">
        <input type="hidden" name="metric" value="{html.escape(selected_metric)}">
        日期：<input type="date" name="start" value="{html.escape(start)}" onchange="this.form.submit()">
        ~ <input type="date" name="end" value="{html.escape(end)}" onchange="this.form.submit()">
        <a href="/?metric={html.escape(selected_metric)}">全部</a>
      </form>
      <button class="bell" title="{html.escape(threshold_note)}">🔔</button>
      <button class="theme-toggle" onclick="toggleTheme()">🌓</button>
      <div class="avatar">YY</div>
      <span style="font-size:0.85rem;color:var(--muted)">yoyu0326</span>
    </div>
    <div class="content">
      <h1>Dashboard</h1>
      <div class="subtitle">chunking-autoresearch 即時結果 · 目前顯示範圍：{html.escape(date_label)}</div>

      <div class="panel composite-panel">
        <div>
          <div class="metric-card-label">{html.escape(threshold_note)}</div>
          <div class="progress-track"><div class="progress-fill" style="width:{threshold_progress:.0f}%"></div></div>
        </div>
      </div>

      <div class="grid-top">{minicards}</div>

      <div class="body-grid">
        <div class="panel">
          <div class="section-title">{html.escape(big_label)}</div>
          <div class="subtitle" style="margin-bottom:0.75rem">{html.escape(big_desc)}</div>
          {big_chart}
        </div>
        <div class="side-stack">
          <div class="panel">
            <div class="section-title">實驗統計</div>
            {stats_bars}
            <div class="footnote">總實驗數：{total}</div>
          </div>
          <div class="panel">
            <div class="section-title">本次執行資源</div>
            <div class="footnote" style="font-size:0.85rem;color:var(--text)">最新一筆耗時：{latest_seconds_str}</div>
            <div class="footnote" style="font-size:0.85rem;color:var(--text)">花費：$0.00（Phase 1 完全本機執行，零 API 成本）</div>
          </div>
        </div>
      </div>

      <div class="panel" style="margin-top:1rem">
        <div class="section-title">歷史紀錄（顯示最近 {history_count} 筆，超過表格高度可滑動捲動）</div>
        <div class="history-scroll">
          <table id="historyTable">
            <thead><tr><th>日期</th><th>commit</th><th>status</th><th>cost_time</th><th>description</th></tr></thead>
            <tbody>{history_rows}</tbody>
          </table>
        </div>
      </div>
      <p class="footnote">按瀏覽器的重新整理即可看到最新結果。資料來源：results.tsv</p>
    </div>
  </div>
</div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        if parts.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        query = parse_qs(parts.query)
        body = render_page(query).encode("utf-8")
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
