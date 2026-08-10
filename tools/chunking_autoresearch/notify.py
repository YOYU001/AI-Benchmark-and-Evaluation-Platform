"""tools/chunking_autoresearch/notify.py

檢查 results.tsv 裡目前最好的 keep 紀錄，相對 baseline 的 cost_time 進步幅度
有沒有跨過門檻（預設 20%），有的話透過 `hermes send` 推播 Telegram 通知。

設計成「只在有新的、跨過門檻的最佳結果時才通知」——用 .last_notified 記錄上次
通知過的 commit，避免同一個結果每次 cron 執行都重複推播。

前提：這個腳本要在已經設定好 Telegram gateway 的 Hermes 環境裡執行（同一個容器內），
`hermes send` 才找得到已儲存的 bot token / home channel。

用法：python notify.py（通常由 cron 排程在每輪 chunking-autoresearch 跑完後呼叫）
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

RESULTS_TSV = Path(__file__).resolve().parent / "results.tsv"
LAST_NOTIFIED_FILE = Path(__file__).resolve().parent / ".last_notified"
IMPROVEMENT_THRESHOLD_PCT = 20.0


def _read_kept_rows() -> list[dict]:
    if not RESULTS_TSV.exists():
        return []
    with RESULTS_TSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    return [r for r in rows if r.get("status") == "keep"]


def _improvement_pct(baseline: float, current: float) -> float:
    if baseline == 0:
        return 0.0
    return (baseline - current) / baseline * 100


def _last_notified_commit() -> str | None:
    if not LAST_NOTIFIED_FILE.exists():
        return None
    return LAST_NOTIFIED_FILE.read_text(encoding="utf-8").strip() or None


def main() -> None:
    kept = _read_kept_rows()
    if len(kept) < 2:
        return

    baseline_cost_time = float(kept[0]["cost_time"])
    best = min(kept, key=lambda r: float(r["cost_time"]))
    best_cost_time = float(best["cost_time"])
    pct = _improvement_pct(baseline_cost_time, best_cost_time)

    if pct < IMPROVEMENT_THRESHOLD_PCT:
        return
    if best["commit"] == _last_notified_commit():
        return

    message = (
        f"[chunking-autoresearch] 找到 {pct:.1f}% 的進步\n"
        f"最佳結果 commit：{best['commit']}\n"
        f"cost_time：{best_cost_time:.6f}（baseline：{baseline_cost_time:.6f}）\n"
        f"說明：{best.get('description', '')}"
    )
    subprocess.run(["hermes", "send", "--to", "telegram", message], check=True)
    LAST_NOTIFIED_FILE.write_text(best["commit"], encoding="utf-8")


if __name__ == "__main__":
    main()
