# chunking-autoresearch

這是讓 Hermes 自主實驗、找出更好的 RAG chunking 策略的專案。設計方式模仿
`C:\my_Purdue\my_nvidia\autoresearch`（Karpathy 的自動化訓練實驗專案）：
一個你可以自由修改的檔案、一個固定不可改的評分程式、一個單一的量化指標、
一份實驗紀錄，然後無限迴圈跑下去。

**這份文件經過四方獨立審查（qa／research／code-review／codex）並修正過一次**
（原本的版本有品質分數可以被「丟光資料」鑽漏洞、`git commit`／`git reset`
指令實際上無效等嚴重問題，都已修好——見下方各節）。

## Setup（第一次開始前，先跟人類一起確認）

1. **談好一個 run tag**：根據今天的日期提議一個 tag（例如 `aug7`）。分支
   `chunking-autoresearch/<tag>` 不能已經存在——這一定是全新的一輪。
2. **建立分支**：從目前的 `master` 開 `git checkout -b chunking-autoresearch/<tag>`。
3. **讀懂範圍內的檔案**：
   - `README.md` — 這個資料夾的背景說明。
   - `schema.py` — 固定：`PageParseResult`／`Chunk` 這兩個資料結構的定義。
   - `pdf_utils.py` — 固定：PDF 解析。
   - `harness.py` — 固定、不可改：解析 PDF、透過 `_worker.py` 跑你的策略、
     打分數、印摘要。**這是唯一標準答案，不能改。**
   - `_worker.py` — 固定：在獨立 subprocess 裡執行 `strategy.chunk()` 的
     小型入口腳本，不需要你手動執行它，`harness.py` 會自動呼叫。
   - `strategy.py` — 你唯一能編輯的檔案：目前的 chunking 演算法。
4. **確認資料存在**：檢查 `docs/spike_documents/`（在 repo 根目錄底下，
   不是這個資料夾裡）有沒有 4 份 PDF。沒有的話告訴人類先去複製過來。
5. **初始化 `results.tsv`**：只建立表頭那一行（見下方「記錄結果」的欄位）。
   第一次跑完之後才記錄 baseline。
6. **確認沒問題就開始**：跟人類確認一下設定看起來沒問題。

得到確認之後，就開始跑實驗迴圈。

## 實驗規則

每次實驗都是在本機跑 `harness.py`，完全不需要網路、不呼叫任何付費 API。
不管你在哪個資料夾底下執行都可以（`harness.py` 內部用絕對路徑定位所有
檔案，不依賴目前的工作目錄），直接：

```
python harness.py
```

或（如果有裝 `uv`）：

```
uv run harness.py
```

**你可以做的事**：
- 修改 `strategy.py`——這是你唯一能編輯的檔案。演算法、資料結構、輔助函式，
  都可以自由發揮。

**你不能做的事**：
- 修改 `harness.py`、`schema.py`、`pdf_utils.py`、`_worker.py`。裡面是固定
  的評分邏輯、資料結構、PDF 解析、subprocess 執行機制。這些是唯一標準答案，
  不能改。
- 修改 `docs/spike_documents/` 底下的 4 份 PDF。
- 安裝新套件或加新的相依套件。只能用 `requirements.txt` 裡已經有的。
- **一定要保留 `strategy.py` 裡 `chunk(pages, source_filename) -> list[Chunk]`
  這個函式簽名**——這是 `harness.py`／`_worker.py` 呼叫你程式碼的唯一介面，
  改了函式名稱或參數，每次實驗都會直接 crash。函式內部（演算法本身）完全
  自由，只有這個對外接口不能動。

**目標很簡單：讓 `cost` 越低越好。** `cost` 的計算方式：

1. **先看硬性門檻（hard gate）**：`quality_pass_rate` 必須等於 1.0（所有
   chunk 的欄位格式都合法），而且 `content_coverage` 必須 ≥ 0.90（原始文件
   的內容至少有 90% 真的出現在你切出來的 chunk 裡）。
2. **兩個門檻都過了**，`cost` 就是這次執行時間相對於 baseline 的倍數
   （`normalized_seconds`）——這時候才是真正在比「誰切得快」。
3. **只要有一個門檻沒過**，`cost` 會被設成一個遠高於任何正常結果的數字
   （1000 起跳，看沒過門檻的程度往上加），保證輸給任何有認真切的策略。

**這代表什麼**：不要想著「切少一點、切快一點」來取巧。`harness.py` 會
用內容比對（比較切出來的 chunk 有沒有涵蓋到原始文件的內容）抓出「丟資料
換取速度」這種投機做法，一旦被抓到，`cost` 會爆表，肯定比 baseline 差。
真正能讓 `cost` 進步的路只有一條：**在保留完整內容的前提下，讓 chunking
本身跑得更快，或是讓格式檢查更穩定地全數通過**。

**簡潔原則**：條件都一樣的話，簡單的寫法比較好。一個很小的進步卻讓程式碼變
得又醜又複雜，通常不值得。反過來說，刪掉一些東西還能維持一樣或更好的結果，
是很棒的成果。

**第一次跑**：你的第一次實驗永遠是先跑現在 `strategy.py` 的原樣，建立 baseline。

## 已知限制（MVP_V1 那邊已經踩過的坑，你不用重新踩一次）

這些是姊妹專案 MVP_V1（`AI Energy Operations Copilot`）用完整版 chunker 處理
同一批文件時，已經記錄下來的已知限制，這裡的簡化版繼承了同樣的邊界：

- **不做 OCR**：`pdf_utils.py` 只讀 PDF 的文字層，掃描頁（沒有文字層的頁面）
  會回傳空文字。如果你的策略想要「辨識更多掃描頁內容」，在這個本機模擬環境
  裡不會有任何進步空間可言（因為 harness 根本沒有 OCR 能力），不用往這個
  方向想。
- **表格偵測只做了一種路徑**：目前的 baseline 只偵測「表格資料在前、標題
  在後」這種格式（日期行 + 前面帶單位的欄位名稱）。MVP_V1 完整版另外還有
  一種「標題在前、資料在後」的偵測路徑（用在其中一份文件上），這裡沒有
  對應實作——如果某份文件的表格完全沒被抓到，用純段落方式處理，這是已知
  的簡化範圍，不是 bug，你可以自己嘗試補上這個偵測邏輯。
- **表格句尾標點可能被截斷**：MVP_V1 完整版在處理這批文件時，記錄過幾個
  表格儲存格因為句尾標點判斷邏輯而被截斷內容的案例。如果你的策略也用
  類似「行尾標點決定要不要繼續收進表格」的判斷方式，這是一個已知會出錯
  的方向，值得小心。
- **段落偵測依賴縮排特徵**：目前用「這一行前面有沒有空白縮排」判斷是不是
  新段落開始，這只在這批文件的排版習慣下有效，換一批格式完全不同的文件
  可能整個失效。

## 輸出格式

跑完之後 `harness.py` 會印出一段摘要：

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

（以上是實際跑 baseline 的真實輸出，不是編出來的範例數字。）

用這個抓出關鍵指標：

```
grep "^cost:" run.log
```

如果 `grep` 抓不到任何東西，代表這次執行失敗或逾時了（沒有印出摘要），
直接當作 crash 處理，見下方「Crash」段落。

## 記錄結果

每次實驗跑完，記錄進 `results.tsv`（tab 分隔，**不是逗號**，逗號在說明欄位裡
會出問題）。

表頭跟 7 個欄位：

```
commit	cost	quality_pass_rate	content_coverage	seconds	status	description
```

1. git commit hash（短版，7 碼）
2. 這次跑出來的 cost——crash 或逾時的話填 `999999.000000`（代表「無限差」，
   不要填 0——`cost` 是越低越好，0 會被誤判成「最好的結果」）
3. quality_pass_rate——crash 的話填 `0.000000`
4. content_coverage——crash 的話填 `0.000000`
5. seconds——crash 的話填 `0.000000`
6. status：`keep`、`discard`、或 `crash`
7. 一句話說明這次嘗試了什麼

範例：

```
commit	cost	quality_pass_rate	content_coverage	seconds	status	description
a1b2c3d	1.012085	1.000000	0.999582	0.111329	keep	baseline
b2c3d4e	0.870000	1.000000	0.995000	0.096000	keep	改用更嚴格的表格偵測
c3d4e5f	1075.000000	1.000000	0.250000	0.085000	discard	改成過度激進的過濾，內容覆蓋率沒過門檻
d4e5f6g	999999.000000	0.000000	0.000000	0.000000	crash	overlap 設成負數
```

（`results.tsv` 不要進版控，保持 untracked，跟 autoresearch 的做法一樣，
`.gitignore` 已經排除它。）

## 實驗迴圈

實驗跑在專屬分支上（例如 `chunking-autoresearch/aug7`）。這個 repo 在你
開始之前，`tools/chunking_autoresearch/` 整個資料夾應該已經是 **tracked**
狀態（人類已經先建好一個乾淨的 baseline commit）——如果你發現 `git status`
顯示這個資料夾是 untracked，先停下來告訴人類，不要自己 `git add` 整個
資料夾亂猜要 commit 什麼。

無限迴圈：

1. **記錄這一輪開始前的 commit**：`git rev-parse HEAD`，記下這個雜湊值
   （之後叫它 `attempt_base`）。這是這一輪如果要丟棄時，精確回到的那個
   點——不要用 `HEAD^` 或 `HEAD~1` 這種相對寫法，因為如果中途手動介入過，
   相對位置會算錯。
2. 對 `strategy.py` 動手——想一個實驗性的改法，直接改程式碼。
3. `git add strategy.py && git commit -m "描述這次嘗試"`
4. 跑實驗：`python harness.py > run.log 2>&1`（全部導向檔案，不要用 tee，
   也不要讓輸出灌爆你自己的 context）。
5. 讀結果：`grep "^cost:\|^quality_pass_rate:\|^content_coverage:" run.log`
6. grep 沒東西代表 crash 了。跑 `tail -n 50 run.log` 看 Python 錯誤訊息，
   試著修。修了幾次還是不行，就放棄這個想法，跳到步驟 7 用 crash 記錄，
   然後執行步驟 9 的丟棄動作。
7. 把結果記進 tsv（提醒：不要把 `results.tsv` 加進 git）。
8. 如果 `cost` 進步了（變低）**而且 `hard_gate_passed` 是 `True`**，保留
   這個 commit（status 記 `keep`），繼續往前推進分支——不需要做任何 git
   操作，這個 commit 已經是目前分支的 HEAD，直接進入下一輪。
9. 如果 `cost` 一樣或變差，或是 `hard_gate_passed` 是 `False`（status 記
   `discard`），或是 crash 了（status 記 `crash`），執行：
   `git reset --hard <attempt_base>`（用步驟 1 記下的那個雜湊值，不是
   `HEAD^`）——精確回到這一輪開始之前的狀態。

你是一個完全自主的研究者，在不斷試東西。有效就留下，沒效就丟掉。往前推進
分支才能持續疊代。如果覺得卡住了，可以退回去重來，但這應該非常少發生
（如果真的要做的話）。

**Timeout**：`harness.py` 內部已經對 `strategy.chunk()` 的執行設了
30 秒的 subprocess timeout，超過會被強制中止並印出錯誤（等同 crash，不
用你自己另外計時或判斷）。整支 `harness.py` 正常執行（含 3 次重複計時）
通常在幾秒內結束。

**Crash**：如果一次實驗壞掉了（例如程式錯誤、或觸發了上面的 30 秒
timeout），自行判斷：如果是很蠢、很好修的問題（打錯字、忘記 import），
修一下重跑；如果這個想法本身就是有根本問題，直接跳過，在 tsv 裡記成
crash，繼續下一個。

## 停下來的條件（不是「絕對不要停」）

原版 autoresearch 說「絕對不要停」，但那是設計成有人整晚看著硬體資源的
GPU 訓練場景。這裡改成**有明確的硬性停止條件**（達到任何一個就停下來，
把目前為止最好的幾個策略整理成摘要回報給人類，不要無限跑下去），但上限
拉高到符合「本機 24 小時不間斷」的使用情境：

- **累積跑滿 5000 次實驗**，或
- **累積跑滿 24 小時**（不含人類介入的時間），或
- **連續 10 次 crash**（代表可能卡在某個系統性問題上，不是策略本身的問題——
  這條「系統性問題」的煞車不因為想跑滿 24 小時而放寬），或
- **連續 30 次都是 discard、沒有任何一次 keep**（代表已經找不到新方向了，
  同樣不因為想跑滿 24 小時而放寬），或
- **`cost` 比一開始的 baseline 進步超過 20%**——這代表已經有夠好的候選了，
  接下來要不要花錢接上真的 embedding API 做搜尋準確度驗證，是人類要自己
  決定、自己用 `.claude/skills/api-cost-estimate/` 估算成本的事，不是你
  可以自己決定去做的。

在跑到以上任何一個條件之前，不要主動停下來問人類「要繼續嗎」——正常情況
下就是照這個迴圈一直跑。觸發任何一個停止條件後，整理一段摘要（最好的
幾個 commit、對應的 cost、簡短說明改了什麼），回報給人類，然後停下來
等待進一步指示。
