# chunking-autoresearch

讓 Hermes 自主實驗、找出更好的 RAG chunking 策略，設計方式模仿
`C:\my_Purdue\my_nvidia\autoresearch`（Karpathy 的自動化訓練實驗專案）。
目標是優化姊妹專案「AI Energy Operations Copilot」（MVP_V1）的 chunking
速度與結構品質，讓它更能適應持續變化的公司內部文件格式。

**這是第二版**，第一版做完之後請了 `qa`／`research`／`code-review` 三個
custom subagent 加上 `codex` 一起做了一次獨立審查，抓到「品質分數可以靠
丟光資料鑽漏洞」「`git commit`／`git reset` 指令實際上無效」等嚴重問題，
這一版已經修正，細節見下方。

## 這裡的檔案

- **`schema.py`** — 固定：`PageParseResult`／`Chunk` 資料結構定義。獨立
  出來是為了避免 `harness.py`／`strategy.py` 互相 import 造成循環依賴。
- **`pdf_utils.py`** — 固定：PDF 文字層解析，不做 OCR（已知落差，見下方）。
- **`harness.py`** — 固定、不可改：解析 `docs/spike_documents/` 底下的
  4 份 PDF、透過 `_worker.py` 呼叫 `strategy.chunk()`、算分數、印摘要。
  **agent 不能編輯**。
- **`_worker.py`** — 固定：在獨立 subprocess 裡執行 `strategy.chunk()`，
  讓 agent 的程式碼碰不到 `harness.py` 自己的計時器跟常數，也讓
  `harness.py` 可以對它強制設 timeout。不需要手動執行。
- **`strategy.py`** — agent 唯一能編輯的檔案。目前內容是從 MVP_V1
  `spike/chunker.py` 的 `structured_600_100` 策略簡化移植過來的 baseline。
- **`program.md`** — 餵給 Hermes 的操作說明／agent skill，包含完整的
  setup 步驟、能改不能改的規則、記分方式、以及「有明確停止條件」的實驗
  迴圈演算法。
- **`dashboard.py`** — 本機即時儀表板，讀 `results.tsv` 畫出每項指標的
  趨勢圖跟成長百分比，瀏覽器打開會自動重新整理。

## 記分方式（第二版修正過的部分）

第一版的 `cost` 只檢查 chunk 的欄位格式對不對，完全沒檢查「內容有沒有被
保留下來」——實測發現一個把資料整個丟光的策略反而能拿到比 baseline
更低的 cost（更「進步」）。

第二版加了**硬性門檻**：

1. `quality_pass_rate` 必須是 1.0（欄位格式全部合法）
2. `content_coverage` 必須 ≥ 0.90（用固定長度字元 shingle 比對，原始文件
   內容至少要有 90% 真的出現在切出來的 chunk 裡）

兩個門檻都過，`cost` 才是「執行時間相對 baseline 的倍數」，這時候才是真正
在比速度。只要有一個沒過，`cost` 直接跳到 1000 以上，保證輸給任何有認真
切的策略——「丟資料換速度」這條路已經被堵死。

## 快速開始

```bash
# 手動跑一次 baseline（不管在哪個資料夾底下執行都可以，內部用絕對路徑）
python harness.py

# 或用 uv
uv run harness.py
```

跑完會印出一段像這樣的摘要（這是實際跑出來的真實數字）：

```
---
cost:              1.012085
quality_pass_rate: 1.000000
content_coverage:  0.999582
hard_gate_passed:  True
seconds:           0.111329
baseline_seconds:  0.110000
num_chunks:        257
strategy_name:     baseline_structured_600_100
```

## 讓 Hermes 開始自主實驗

開一個新的 `hermes chat`，指到這個 repo，照 `program.md` 裡的方式下指令：

```
你好，看一下 program.md，我們來跑第一次 chunking 實驗！先做 setup。
```

**開始之前，這個資料夾必須已經是 git tracked 狀態**（不能是 untracked）
——`program.md` 裡的 `git commit`／`git reset --hard <commit>` 流程要有
一個乾淨的起點才會正確運作。如果不確定，先跑 `git status` 確認
`tools/chunking_autoresearch/` 不在 untracked 清單裡。

## 即時儀表板

```bash
python dashboard.py
```

瀏覽器打開 `http://127.0.0.1:8765/`，每 5 秒自動重新整理一次。畫面內容：

- 每項指標（`cost`／`quality_pass_rate`／`content_coverage`／`seconds`）
  的趨勢折線圖，跟相對第一筆 `keep` 紀錄的成長百分比
- 總實驗數／keep／discard／crash 的統計
- 最近 30 筆實驗紀錄的表格

`results.tsv` 裡**每一筆紀錄都會保留**（包含失敗的 discard／crash），只有
失敗嘗試的 `strategy.py` 程式碼本身會被 `program.md` 流程裡的 `git reset`
丟掉——log 保留完整歷史，儀表板才能看到「失敗過幾次、後來怎麼找到對的
方向」的真實趨勢，不是只看到一路向上的曲線。Hermes 在背景持續寫新的實驗
結果時，這個頁面留著開就會一直更新，不用手動重新整理或重啟。

## MCP 橋接（讓 Claude Code 查詢實驗結果）

```bash
claude mcp add chunking-research -- python "<repo 絕對路徑>/tools/chunking_autoresearch/mcp_server.py"
```

註冊之後，Claude Code 可以直接呼叫 `list_chunking_experiments`、
`get_best_chunking_strategy`、`get_chunking_experiment_summary` 這三個工具，
不用你手動複製貼上 `results.tsv` 的內容。

## 現在先不做的事

- **真的接上 OpenAI Embedding API 驗證搜尋準確度**：這裡只測 chunking
  本身的速度跟結構品質（零成本、完全本機），不驗證「切完之後找資料準不準」。
  要驗證這件事，得手動、有限次地接上真的 embedding API，而且要先用
  `.claude/skills/api-cost-estimate/` 估算成本，不會讓 Hermes 自動、無限制
  地呼叫付費 API。`program.md` 裡的停止條件也把這件事列成「觸發後要回報
  人類、不要自己決定」的項目。
- **掃描頁的 OCR**：`pdf_utils.py` 只讀文字層，掃描頁會回傳空文字。
- **doc4 那種「標題在前」的表格偵測路徑**：MVP_V1 完整版有兩種表格偵測
  邏輯，這裡的簡化 baseline 只做了一種（見 `program.md` 的「已知限制」）。
- **完整的 process 沙箱**：目前用 subprocess + timeout 隔離掉大部分風險
  （計時器/常數碰不到、卡住會被強制中止），但還不是真正的沙箱（例如
  沒有限制記憶體用量、沒有斷網）。如果之後真的要在 NAS 上長時間無人值守
  跑，這塊值得加強。
- **Hermes 部署到 NAS**：這裡只負責準備好 Hermes（不管跑在本機還是 NAS）
  需要的實驗環境跟指令。
- **直接連上 MVP_V1 正式資料庫、持續觀察資料型態／大小變化、回饋優化建議**：
  這是更後期、真的接上正式環境的階段，跟這裡「第一階段零成本本機模擬」不
  是同一件事，先記在專案根目錄的 `TODO.md`，真的要做時再細談設計。
