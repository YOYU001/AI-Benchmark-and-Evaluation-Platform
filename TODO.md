# TODO.md

這個專案跨對話、會一直留著的待辦清單。完成的項目打勾、保留刪除線，不要直接刪掉整行（留個紀錄比較好追蹤）。新的待辦事項隨時可以加在對應區塊底下。

## 環境／設定

- [x] ~~`agy` 加入 PATH 生效後（使用者計畫重開機處理），回頭把 `AGENTS.md` 裡 `agy` 的呼叫方式從完整路徑改回簡短的 `agy`~~（2026-08-05 重開機後確認生效，`AGENTS.md` 已更新）
- [ ] 決定 `results/` 底下依 Phase + 日期分子資料夾的命名規則，並實際套用
- [ ] 若之後要搬去 WSL2 讓 sandbox 真正生效，搬之前要先把要用到的 LLM provider 網域加進 `.claude/settings.json` 的 `sandbox.network.allowedDomains`（目前只有 npm/PyPI）
- [x] ~~專案出現第一支真正的 Python 程式碼時，建立 `requirements.txt`~~（2026-08-06 `tools/chunking_autoresearch/` 是第一支真正的 Python 程式碼，已建立 `requirements.txt`：`pymupdf==1.28.0`、`mcp==1.28.1`）
- [ ] 設定 CI/CD 工作流——觸發時機：這個 repo 有 push 到遠端（GitHub）+ 有真正的程式碼可以跑測試／建置之後，現在沒程式碼、也還沒有遠端，先不處理
- [ ] 設定 git worktree——觸發時機：之後如果讓某個 subagent 也具備 Edit/Write 權限（不只是審查、要它直接改程式碼），或使用者自己需要同時維護多個 branch 或是多個 LLM 需要各自進行工作但不互相干擾時。目前 `qa`/`research`/`code-review` 三個 subagent 都刻意只有 Read/Grep/Glob/Bash，沒有並行編輯衝突的問題，先不處理

## chunking-autoresearch（Hermes 自動實驗）

- [ ] 讓 Hermes 實際照 `tools/chunking_autoresearch/program.md`（2026-08-07 四方審查修正版）跑第一輪完整的實驗迴圈——目前只有 Claude Code 手動驗證過機制沒問題（baseline 正常、退化策略會被硬性門檻擋下、timeout 會生效、MCP 三個工具讀取正常），還沒讓 Hermes 自己走過 setup + 迴圈
- [ ] 第一階段（本機模擬）跑出幾個有希望的策略之後，手動用 `.claude/skills/api-cost-estimate/` 估算成本，挑少數候選接上 MVP_V1 真的 OpenAI Embedding API + pgvector 驗證真實搜尋準確度——不要讓 Hermes 自動做這一步
- [ ] `harness.py` 目前只讀 PDF 文字層、不做 OCR（掃描頁會是空文字），是刻意的已知簡化，非 bug；如果之後發現這 4 份 spike 文件裡有掃描頁佔比重要，再補 OCR fallback
- [ ] 目前用 subprocess + timeout 隔離 `strategy.py` 的執行，還不是真正的沙箱（沒限制記憶體用量、沒斷網）——如果之後真的要在 NAS 上長時間無人值守跑，這塊要再加強（codex 審查時提出的建議）
- [ ] Hermes 部署到 NAS 24/7 常駐——本次工作只準備好本機能跑的實驗環境，NAS 部署本身還沒開始規劃
- [ ] （更後期）讓 Hermes 直接連上 MVP_V1 正式的 Postgres/pgvector 資料庫，持續觀察真實資料的型態與大小變化，回饋給 Claude Code 判斷怎麼優化——這跟「第一階段零成本本機模擬」是不同階段，2026-08-07 使用者提出方向、確認先記錄、真的要做時再細談設計（權限範圍、要不要唯讀、怎麼避免影響正式環境效能等都還沒討論）
- [ ] `tools/chunking_autoresearch/dashboard.py`（2026-08-07 新增）目前只用瀏覽器手動打開 `http://127.0.0.1:8765/` 看，還沒有「自動啟動」或跟 Hermes 的實驗迴圈綁在一起的機制——之後如果要 Hermes 自己啟動 dashboard 或整合進它的排程，再另外設計
- [ ] （2026-08-12 討論 dashboard 排版時提出）目前 `harness.py` 完全沒有處理圖片——PDF 每頁只抓純文字，chunk 也只有「一般段落」「表格」兩種類型，沒有「圖片有沒有被正確保留／有沒有被切斷」的檢查機制。要做這個要先能把圖片從 PDF 抓出來、辨識圖說跟圖片的對應關係，屬於比較大的獨立功能，先記錄，之後再另外規劃
