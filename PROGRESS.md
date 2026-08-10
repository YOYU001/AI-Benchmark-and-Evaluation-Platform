# PROGRESS.md

本檔案用來記錄這個專案每一次的工作進度。**每次開始工作前，請先閱讀本檔案**，了解目前進度與上次停在哪裡；每次工作結束或有階段性產出時，請在下方新增一筆紀錄。

紀錄格式：

```
## YYYY-MM-DD

- 做了什麼
- 目前卡在哪裡 / 下一步要做什麼
```

---

## 2026-08-04

- 建立 `CLAUDE.md`，說明專案定位（NVIDIA Evaluation 方法論學習專案，目前僅有 docs + datasets，尚無程式碼）、與 MVP_V1 的關係、資料夾結構與工作慣例。
- 確立溝通與文件語言慣例：一律使用繁體中文，專有名詞除外。
- 建立本 `PROGRESS.md`。
- 目前進度仍在 Phase 1（詞彙）+ Phase 2（第一次 AI Battle）規劃階段，尚未實際執行（見 `docs/00_phase1_2_learning_plan.md`）。
- 下一步：把 Phase 1 詞彙表的「對應 MVP_V1 的實際例子」欄位填完，接著從 `datasets/energyops_test_questions.json` 挑 5–10 題進行 Phase 2 AI Battle，執行前需先用 `embed-cost-estimate` skill 估算成本。

## 2026-08-05

- 建立 `AGENTS.md`：跨 LLM 通用的 agent 行為規則，內容包含語言慣例、子代理團隊模型分工（Leader/QA 用高階模型、執行型子代理用低階模型）、Find out/Find in 與 Debate 協作流程（核心是 parallelize）、Developer/QA/Test 的 context 隔離、重複性工作要封裝成 skill（`skill.md` 為必要入口）、Multi-LLM 討論流程（Claude Code + codex + copilot + agy 四方，段落性里程碑時平行討論再由 Claude Code 統整）、資安規範（API key 只存 `.env`、對話中不得出現完整 key、套件安裝防 typosquatting）。
- 確認並記錄三個 LLM CLI 的非互動呼叫方式：`codex exec "prompt"`、`copilot -p "prompt" --allow-all-tools`、`agy --print "prompt"`（agy 目前不在系統 PATH，需完整路徑 `C:\Users\User\AppData\Local\agy\bin\agy.exe`，使用者計畫等另一個專案跑完後重開機讓 PATH 生效）。
- 資安設定實作並測試通過：`.claude/settings.json` 設定 `permissions.deny`（拒讀 `.env`/`.env.*`/`secrets.json`/`.ssh/**`）、`permissions.ask`（`npm install`/`pip install` 等安裝指令強制確認）、`sandbox.credentials.files`（`.env` 系統層級遮蔽，`failIfUnavailable: false` 避免不支援時整個工作環境壞掉）、`sandbox.network.allowedDomains`（限縮在 npm/PyPI 官方 registry）。測試方式：建立假 `.env` 用 Read 工具驗證被擋、讀取 `README.md` 驗證沒有波及其他檔案。
- 初始化 git repository，建立 `.gitignore`（`.env`、`__pycache__`、`.venv`、`active/**` 等），完成第一次 commit（16 個檔案，不含任何機密資料）。
- 建立 `active/` 工作暫存區（`research/`、`execution/`、`config/`、`temp/` 四個子資料夾，仿照使用者提供的 workspace 設計圖，拿掉不相關的 `leads` 分類），整個資料夾內容不進版控（只保留 `.gitkeep` 骨架），定案產出仍手動搬到 `results/`／`docs/`。
- 背景資安審查（commit 後自動觸發）抓到 `.claude/settings.json` 3 個問題並處理：
  - **control-scope-gap**（已修正）：`sandbox.credentials.files` 原本只保護 `.env`/`.env.local`，沒涵蓋 `secrets.json`/`.ssh`，已補上 `secrets.json`/`.ssh`，並加 `sandbox.filesystem.denyRead`（僅 `**/secrets.json`、`**/.ssh/**`，**不含 `.env` 系列**——`.env` 的保護仍只靠 `credentials.files`，跟 `permissions.deny` 涵蓋 `.env.*` 萬用字元的範圍不是逐條對應，2026-08-05 QA 審查發現此處描述曾經失準，這裡已更正）。
  - **allowlist-semantic-escape**（無法修正，已記錄限制）：`permissions.ask` 只比對指令開頭文字，複合指令（如 `cd tmp && npm install x`）會繞過確認機制。真正防線是 sandbox 那層，不是 `ask` 清單。
  - **fail-open-control**（已查明原因，非設定問題）：用乾淨測試法驗證（用不觸發內建防護的檔名臨時測試，測完清除）確認 **sandbox 在這台機器上完全沒有生效**，查證後確認是 **Claude Code 官方明確不支援原生 Windows**（只支援 macOS/Linux/WSL2），不是重啟能解決的問題。使用者機器：LG gram Pro 16" Windows 11 Home（原生，非 WSL2）。若要完整 sandbox 保護需搬到 WSL2 執行，目前不處理，`sandbox.*` 設定保留在 settings.json 裡供未來沿用。
  - 意外發現：使用者已自行在 `.env` 放入真實內容（過程中沒有讀取或顯示其內容），也順帶驗證了 Claude Code 內建的硬性防護——連 Bash 指令文字提到 `.env` 系列檔名都會被直接擋下，使用者確認也無法解除。
  - 確認以上防護不影響正常呼叫 API 的工作流程：程式（如未來的 `evaluation_runner.py`）自己用 `load_dotenv()` 讀取 `.env` 不會觸發任何一層防護，只有「Claude 自己想看到金鑰內容」這件事會被擋。
- `CLAUDE.md` 補上 `active/` 資料夾結構說明（原本只記錄在 `.gitignore` 註解跟這份 PROGRESS.md 裡，未寫進主要架構文件）。
- settings.json 補洞、AGENTS.md 資安限制記錄、CLAUDE.md active/ 說明已於 commit `2dd7945` 進版控。
- 建立 `.claude/skills/periodic-housekeeping/`（`SKILL.md` + `scripts/check_line_counts.py` + `scripts/archive_progress.py`），用來定期檢查並整理文件行數（規則型文件用修剪、日誌型文件用歸檔）。兩支腳本都實際執行測試過（含中文輸出的 UTF-8 編碼修正）。**門檻與範圍後續有更新，見下方 commit `991da5f` 那筆**：改成 150 行、檢查對象擴大到 5 份檔案（`CLAUDE.md`/`AGENTS.md`/`PROGRESS.md`/`README.md`/`TODO.md`），並新增「待辦清單型文件」第三種處理方式。
- 建立三個自訂 subagent（`.claude/agents/`），格式統一為 frontmatter（name/description/tools/model）+ 獨立性原則 + 你會收到什麼 + 你要做什麼 + 回報格式：
  - `QA.md`（opus）：階段性成果的獨立審查驗證，只讀不改，且明確要求「沒問題就照實說沒問題，不用硬找瑕疵」。
  - `RESEARCH.md`（haiku）：大量平行資訊蒐集，定位為「保持母 agent context 乾淨」的手段，description 刻意不預設查詢範圍，交由母 agent 動態分配。
  - `CODE_REVIEW.md`（sonnet）：專注程式碼寫法品質（效率、簡潔、一致性），跟 `qa` 分工不重疊，不限語言。
- 建立 `.claude/rules/`（`python.md`、`sql.md`），用 `paths` frontmatter 做路徑限定載入，內容聚焦效率與不易出錯的寫法。**已確認生效**：派完全沒看過本對話的全新 subagent，只在 prompt 裡提到一個 `.py`／`.sql` 路徑（檔案實際都不存在），兩次都回報收到對應的 `system-reminder` 區塊、附上規則檔逐字內容並正確標註來源路徑——連檔案都沒有真的被成功讀到，光是路徑文字出現就觸發了規則注入，證明 `paths` 機制是真的在運作。
- 查證確認：`.claude/plugins/` 目前只裝了官方 `security-guidance@claude-plugins-official` 一個 plugin，三層防護（pattern 警告本機執行、Stop 時 LLM diff review 用 `claude-opus-4-7`、commit 時 agentic reviewer），且會把 diff/檔案內容送到模型端點（預設 `api.anthropic.com`）。
- 用 `qa` agent 對整個環境配置做一次獨立審查，抓到 10 項文件與實際檔案不一致的落差，已修正：
  - `AGENTS.md` 的 `skill.md`→`SKILL.md`、補上 `scripts/` 子資料夾說明。
  - `AGENTS.md` 對 `update-config` 的引用補充說明「這是 Claude Code 內建 skill，非本專案 `.claude/skills/` 底下的」。
  - `CLAUDE.md` 資料夾結構補上 `.claude/`（`agents/`/`rules/`/`skills/`）。
  - `AGENTS.md` 的「Developer/QA/Test」改成實際建立的 `qa`/`research`/`code-review` 三個 agent。
  - `AGENTS.md` 補上「搬去 WSL2 前必須先把 LLM provider 網域加進 `sandbox.network.allowedDomains`」的待辦提醒。
  - 本檔（`PROGRESS.md`）本身的落差（漏記工作、過時待辦、denyRead 範圍描述不精確）一併修正。
  - `results/` 補上 `.gitkeep`（原本是空資料夾、未被 git 追蹤，但多份文件已把它當既有結構在引用）。
  - `archive_progress.py` 重複執行會累積重複提示行的小 bug，**已修正並重新測試通過**（連續執行兩次不再重複）。
- commit `d99cce6`：`.claude/agents/`、`.claude/rules/`、`.claude/skills/periodic-housekeeping/` 全數進版控，含 QA 審查後的 10 項修正。
- 建立 `TODO.md`：跨對話留存的打勾框樣式待辦清單，跟 `PROGRESS.md`（歷史紀錄）分工——`PROGRESS.md` 記錄「做過什麼」，`TODO.md` 記錄「還沒做的事」。`CLAUDE.md` 已更新為每次開始工作前要同時讀 `PROGRESS.md` 與 `TODO.md`。之後新的待辦事項改記到 `TODO.md`，不再堆在這裡。
- `agy` 加入 PATH：使用者重開機後確認生效（`agy --version` 可直接執行），`AGENTS.md` 呼叫方式已從完整路徑改回簡短的 `agy`，`TODO.md` 該項已打勾。
- `.env` 內容使用者已自行填入，之後若需要除錯要用「是否存在／長度」的方式確認，不能直接讀取內容（持續性規則，不是待辦事項）。
- 段落性里程碑檢查：問「環境建置好了、可以進 Phase 2 了嗎」，平行問了 `qa` agent + codex + copilot + agy 四方（呼應 `AGENTS.md` 的 Multi-LLM 討論流程，也是第一次實戰驗證這個流程）。過程中順手解決了 `agy` 非互動模式讀不到檔案的問題：它有自己獨立的 `C:\Users\User\.gemini\antigravity-cli\settings.json`，需要加 `permissions.allow: ["command(*)"]` 才能執行指令，且要用 `--add-dir <路徑>` 明確指定要讀的專案（它不會跟著 shell 的 `cd` 走，有自己獨立的「目前專案」概念）。四方一致結論：可以進 Phase 2。codex + agy 各自獨立提出「目前 tooling 相對於實際工作量偏重」的批評；copilot + agy 各自獨立發現 `embed-cost-estimate` skill 只存在於 MVP_V1、這個 repo 沒有；codex 額外抓到 `.gitignore` 允許 `.env.example` 但會被 `Read(.env.*)` 擋住的規則衝突（`.env.example` 目前還不存在，暫時無害）。
- `AGENTS.md` 補上明確的階層宣告：Claude 是主要操作、思考、統整的領導者，codex/copilot/antigravity 是合作者、提供獨立意見，不是共同決策者，分歧時由 Claude 判斷取捨並對使用者負責。
- 新增 `.claude/skills/api-cost-estimate/`（`SKILL.md` + `scripts/estimate_cost.py`），取代原本規劃借用的 MVP_V1 `embed-cost-estimate`。刻意設計成**不綁定任何特定專案或資料集**：題目來源可以是任意檔案（純文字一行一題，或 JSON 陣列／物件），也可以純手動指定數量與長度；同時考慮呼叫次數（`--reruns`）與 reasoning/thinking 深度（`--model`／`--judge` 可帶 `low`/`medium`/`high`/`xhigh` 效果等級，套用粗略的 output token 放大倍數）。用真實的 `energyops_test_questions.json` 題目文字實測過，也測過純手動輸入模式跟錯誤處理。`CLAUDE.md`／`docs/00_phase1_2_learning_plan.md` 裡舊的 `embed-cost-estimate` 引用已同步更正。
- 修正 CLAUDE.md 的 `/context 的版面` 小技巧補充說明並 commit（`a832f6d`）。

## 2026-08-06

- **裝好 hermes-agent（獨立於本專案之外）**：完整安裝在 `C:\my_Purdue\my_nvidia\hermes-agent`（clone + uv venv + Python/npm 依賴），Nous Portal 登入完成，大腦模型換成 Claude Sonnet 5，VS Code／Cursor 都裝了 ACP Client 擴充套件並成功連線。過程中排查並修正一個環境問題：手動安裝（非官方安裝程式）少了 `HERMES_GIT_BASH_PATH` 環境變數，加上 Git 裝在非標準路徑（`C:\my_AI\Git`），導致 Hermes 的 terminal 工具誤判走到系統裡一個沒作用的 WSL 樁——修法是把 `HERMES_GIT_BASH_PATH` 直接寫進 VS Code／Cursor 的 `acp.agents` 設定的 `env` 欄位（不只依賴系統環境變數，避免 ACP Client 擴充套件的 child_process 沒繼承到）。這部分是使用者個人工具鏈的一部分，不進這個 repo 的版控。
- **新增 `tools/chunking_autoresearch/`**：讓 Hermes 之後可以對姊妹專案 MVP_V1 的 RAG chunking 策略做自動化實驗（速度＋結構品質），設計上完整模仿 `C:\my_Purdue\my_nvidia\autoresearch`（Karpathy 的自動化訓練實驗專案）的模式——`harness.py`（固定、agent 不可改的驗證程式，量化指標 `cost` 越低越好）、`strategy.py`（agent 唯一能自由改寫的檔案，目前是 MVP_V1 `structured_600_100` 簡化移植的 baseline）、`program.md`（Hermes 的完整操作說明，含「無限迴圈、不要停」的自主實驗規則）、`mcp_server.py`（暴露 `list_chunking_experiments`／`get_best_chunking_strategy`／`get_chunking_experiment_summary` 三個工具給 Claude Code 查詢實驗結果）。同時複製 MVP_V1 的 4 份 spike PDF 到 `docs/spike_documents/`（符合本 repo 一次性複製、不跟 MVP_V1 同步的慣例），並建立本專案第一份 `requirements.txt`（`pymupdf==1.28.0`、`mcp==1.28.1`）與對應的 `.venv/`。
  - 明確分兩階段：**第一階段（已建好、可以跑）**完全本機、零成本，只測 chunking 速度與結構品質；**第二階段（刻意不自動化）**要手動用 `api-cost-estimate` 抓成本上限，才能接上 MVP_V1 真的 OpenAI Embedding API 驗證搜尋準確度，不讓 Hermes 自動、無限制地花錢。
  - 已驗證：`harness.py` baseline 可以完整跑完（257 個 chunk，量級跟 MVP_V1 原版 366 個吻合，差異來自刻意簡化掉的第二種表格偵測路徑）；手動改 `strategy.py` 的 `CHUNK_SIZE` 後 `cost`／`num_chunks` 確實跟著變化，迴圈機制沒問題；`mcp_server.py` 的三個工具在空檔案與有資料兩種情況都測過，讀取正確；已用 `claude mcp add chunking-research` 註冊進這個專案的 Claude Code 設定。
  - 下一步：讓 Hermes 實際照 `program.md` 走一次完整的 setup + 實驗迴圈（目前只有 Claude Code 手動驗證過機制沒問題，還沒讓 Hermes 自己跑過）；新的 MCP server 要等 Claude Code 重啟一次 session 才會出現在可用工具清單裡。

## 2026-08-07

- **四方獨立審查 `tools/chunking_autoresearch/`**：平行呼叫 `qa`／`research`／`code-review` 三個 custom subagent 加上 `codex`，一起審查前一天做出來的 chunking-autoresearch 初版設計。四方收斂到同一個核心結論：**品質分數機制形同虛設**——QA 實測證明一個「每份文件只回傳一個字 `x`、丟光所有內容」的策略，`cost` 反而比 baseline 進步 25%，直接超過原本設計的「進步 20% 就自動停下回報」門檻；codex 從理論面獨立提出同樣的警告（quality 檢查只驗證欄位格式，沒驗證內容有沒有被保留）。另外還抓到：`program.md` 裡的 `git commit`／`git reset` 指令因為 `tools/` 當時還是 untracked 狀態、裸指令沒帶 `-a`／目標雜湊，實際上完全不會生效；`program.md` 說「可以整個重寫 strategy.py」卻沒把函式簽名契約寫進去；strategy.py 跟 harness.py 之間有循環 import（QA 實測證實會產生兩個不同的 `Chunk` class）；`strategy.py` 裡一段死碼（`_PARA_START_RE`，research 和 codex 各自獨立抓到）；表格前面最多 6 行的表頭會被直接丟掉、沒放進 table chunk（codex 抓到，實際是個內容遺失 bug）；crash 的 cost 規定填 0，但 cost 是越低越好，語意矛盾；`program.md` 的範例數字實際上跟公式算不出來對得上的結果（codex 幫忙重新驗算過）。
- **依照四方建議重新設計並修正**（使用者選擇「先集中修好嚴重問題再讓 Hermes 開始」，並要求次要問題一併處理）：
  - 新增 `schema.py`（拆出 `PageParseResult`／`Chunk`，徹底消掉循環 import）、`pdf_utils.py`（拆出 PDF 解析，`fitz.open()` 改用 `with` 而不是手動 try/finally，呼應 code-review 對照 `.claude/rules/python.md` 抓到的一項）、`_worker.py`（讓 `strategy.chunk()` 在獨立 subprocess 裡執行，父行程 `harness.py` 自己的計時器跟常數碰不到，也真的能用 `subprocess.run(timeout=...)` 強制中止卡住的策略——這同時也補上了 research 抓到的「program.md 承諾 timeout 但完全沒實作」）。
  - `harness.py` 加入**內容覆蓋率硬性門檻**（`content_coverage`，用固定長度字元 shingle 比對原始文件內容有多少比例真的出現在切出來的 chunk 裡，門檻 90%）：`quality_pass_rate` 跟 `content_coverage` 兩個門檻只要有一個沒過，`cost` 直接設成 1000 起跳的懲罰值，保證輸給任何有認真切的策略，堵死「丟資料換速度」這條路。計時範圍也排除掉固定不變的 PDF 解析時間，並跑 3 次取中位數降低雜訊。
  - 實測驗證：把先前那個「丟光內容」的退化策略重新餵進新版 harness，`cost` 從原本騙到的「進步」變成 1075（`content_coverage` 只有 0.25，直接被硬性門檻擋下），baseline 正常情況下 `cost` 穩定在 ~1.0 附近；另外用一個故意 `time.sleep(5)` 卡住的假策略測過 timeout 機制，1 秒內就被強制中止、正確判定為 crash。
  - `strategy.py`：改成 import `schema.py`（不再跟 `harness.py` 循環依賴）、刪掉沒用到的 `_PARA_START_RE` 死碼、修好表頭被丟掉的內容遺失 bug（改成把偵測到的表頭欄位名稱塞進 table chunk 開頭，而不是直接丟棄）、表格標題也改成用實際偵測到的標題文字，不再寫死成「表格」。
  - `program.md` 整份重寫：setup 步驟加上「開始前 `tools/` 必須已經是 tracked 狀態」的檢查；git 流程改成「每輪開始前先記錄 `attempt_base`（`git rev-parse HEAD`），discard 時用 `git reset --hard <attempt_base>` 精確回退，不再用會失效的裸指令或有歧義的 `HEAD^`」；函式簽名契約明確寫進「不能做的事」；crash 的 cost 改成填 `999999.000000`（不再是語意矛盾的 0）；範例數字換成實際跑出來的真實輸出；「絕對不要停」改成有 5 個明確的硬性停止條件（跑滿 500 次／4 小時／連續 10 次 crash／連續 30 次沒有任何進步／cost 進步超過 20%）；新增「已知限制」段落，把 MVP_V1 已經踩過的坑（表格句尾標點截斷、OCR 不支援、doc4 的第二種表格偵測路徑沒實作、段落偵測依賴縮排）直接告訴 Hermes，不用它自己重新踩一次。
  - `README.md` 同步更新反映新設計；`mcp_server.py` 補上 `_safe_float` 防呆（code-review 抓到：`results.tsv` 欄位如果壞掉，原本會讓 `float()` 直接炸例外），已用假的 malformed 資料測過不會 crash。
  - 全部修正都重新跑過驗證：baseline 正常、退化策略被正確擋下、timeout 正確觸發、mcp_server 三個工具都正常、`.gitignore` 排除產物正確、從 repo 根目錄跟 `tools/chunking_autoresearch/` 兩種工作目錄執行都正常（codex 原本擔心的「可能從錯誤目錄執行」問題，實測證實現有設計已經用 `Path(__file__)` 處理掉了，不是真的問題）。
  - commit 把 `tools/chunking_autoresearch/`、`docs/spike_documents/`（4 份 PDF）、`requirements.txt` 一起進版控，讓 `program.md` 裡 Hermes 要用的 git commit/reset 流程有一個乾淨、tracked 的起點可以運作。
- 下一步：讓 Hermes 實際照這一版修正過的 `program.md` 走一次完整的 setup + 實驗迴圈（仍然還沒讓 Hermes 自己跑過，這次多了硬性品質門檻，理論上不會再重演「丟資料換分數」的問題，但要實際跑過才能確認）。
- **加入即時儀表板 `dashboard.py`**：在正式讓 Hermes 開始跑之前，使用者提出想先確認「結果能不能做成儀表板、記錄每項指標的成長趨勢與成長%、失敗的資料與方式會不會被丟棄、24 小時不間斷跑」這幾件事。釐清後的結論：
  - `results.tsv` 的紀錄本來就是全部保留（含 discard／crash），只有失敗嘗試的 `strategy.py` 程式碼本身會被 `git reset` 丟掉——確認現有機制已經符合「留下完整趨勢、只丟棄失敗的程式碼」的需求，不用改。
  - 不需要固定「每次測試 5 分鐘」（那是誤會，我們的 chunking 測試本身很快，不像 Karpathy 原版的 GPU 訓練需要真的跑滿時間才有意義）。
  - `program.md` 的硬性停止條件（避免 Hermes 真的失控無限跑）從「跑滿 500 次／4 小時」拉高到「跑滿 5000 次／24 小時」，符合「本機 24 小時不間斷」的使用情境；但「連續 10 次 crash」「連續 30 次沒有任何進步」這兩條防系統性問題失控的煞車、以及「進步超過 20% 就停下回報人類」都維持不變，不因為想跑得久就放寬。
  - 新增 `dashboard.py`：純標準函式庫（不加新套件）寫的本機 HTTP server，讀 `results.tsv` 用 inline SVG 畫出 `cost`／`quality_pass_rate`／`content_coverage`／`seconds` 四項指標的趨勢折線圖，跟相對第一筆 keep 紀錄的成長百分比，瀏覽器打開 `http://127.0.0.1:8765/` 每 5 秒自動重新整理。用假資料（含 keep/discard/crash 混合）實測過：成長百分比計算正確（cost 下降顯示為正成長、quality/coverage 用直接差值），總數統計含 discard/crash 在內都正確。
  - 「之後接上 MVP_V1 正式資料庫、持續觀察資料型態/大小、回饋優化建議」使用者確認是更後期的階段，跟現在的「第一階段零成本本機模擬」不是同一件事，先記進 `TODO.md`，之後真的要做時再細談設計（權限範圍、唯讀與否、怎麼避免影響正式環境效能都還沒討論）。

## 2026-08-11

- **`cost` 欄位全面改名為 `cost_time`**（`harness.py`／`results.tsv` 表頭／`program.md`／`mcp_server.py`／`dashboard.py`／`README.md`）：使用者發現「cost」容易被誤讀成金錢單位，實際上是純執行時間換算出來的效能分數、這階段完全零成本，改名避免混淆。`dashboard.py` 同時加上每個實驗點的漲跌 % 標籤跟滑鼠 hover 的精確數值 tooltip（純 inline SVG `<title>`，不加 JS 套件）。
- **Hermes 正式部署到 NAS（Docker 容器，Container Manager 管理）**，取代原本純本機執行的模式：
  - VS Code Remote-SSH 直接連 NAS 容器失敗（`glibc`/`libstdc++` 版本不符 VS Code Server 最低需求，Synology DSM 系統本身版本太舊、非能力所及），改用「SSH 進 NAS host + `docker exec -it hermes hermes chat`」取代，額外處理了 docker socket 需要 `sudo` 權限、PATH 在非互動式 SSH 指令中抓不到 `docker` 完整路徑等瑣碎問題。
  - 在 VS Code 使用者設定（`settings.json` 的 `terminal.integrated.profiles.windows`）跟 PowerShell profile（`Microsoft.PowerShell_profile.ps1`）各自新增快捷方式：終端機下拉選單「Hermes chat」、PowerShell 打 `NAS`（純連進 NAS shell）或 `Hermes-Chat`（直接連進去開始聊天）。
  - **NAS 容器多模型認證**：分別完成 Anthropic（Claude Pro/Max OAuth，透過官方 `claude` npm CLI 的 `claude setup-token` 產生長效 token，因為 Hermes 內建的 device-code OAuth 跟 `hermes model` 預設模型選擇要的驗證方式不同）、OpenAI Codex（`hermes auth add openai-codex`，走 ChatGPT 訂閱 OAuth）、Google AI Studio（`hermes auth add google-ai-studio`，走免費申請的 API key）三種，容器內可自由切換 Claude／ChatGPT／Gemini，不透過 Nous Portal 第三方聚合（避免額外計費、額度改走使用者自己的訂閱）。
  - **Telegram 通知管道**：新建 Telegram bot（`@BotFather` 申請）、`hermes gateway setup` 設定 allowlist（只限使用者自己的 user ID）跟 home channel，`hermes send`／`hermes gateway run` 驗證雙向可用。
- **建立 GitHub repo**（`https://github.com/YOYU001/AI-Benchmark-and-Evaluation-Platform`，Public，使用者作品集用途、刻意不設為 Private），本機 `origin` 已接上、`main` 分支同步。新增 `.github/workflows/codex-review.yml`：PR 開啟/更新時自動用 `codex exec review --base <目標分支>` 產生審查、留言到 PR——**背景自動安全審查**抓到兩個問題並已修正：`--dangerously-bypass-approvals-and-sandbox` 對未知 PR 內容跳過沙盒保護（拿掉，review 本身唯讀分析不需要）、shell 指令字串直接內插 `${{ github.event.* }}` 有 Actions script injection 風險（改用 `env:` + shell 變數引用）。因為 repo 是公開的，額外確認 GitHub 對 fork 來源 PR 的內建保護（secrets 不會傳給 fork PR、`GITHUB_TOKEN` 預設唯讀）已經足以防止陌生人 PR 誤觸費用或寫入。
- **`tools/chunking_autoresearch/notify.py`**（新增）：檢查 `results.tsv` 目前最佳 `keep` 結果相對 baseline 的 `cost_time` 進步幅度，跨過 20% 門檻且是新的最佳結果時（用 `.last_notified` 記錄避免重複通知）透過 `hermes send --to telegram` 推播。原本規劃走 Gmail SMTP + App Password，後來因為 Telegram 已經接通、更簡單而改案。
- **專案 clone 到 NAS 並掛進容器、設定每日排程**：
  - `git clone` 到 NAS `/volume1/Projects/AI-Benchmark-and-Evaluation-Platform`，docker-compose 已有 `/volume1/Projects:/workspace/projects` 這行 volume mount，容器內可見。
  - **踩到 uid/gid 不一致的權限問題**：NAS host 上用 `yoyu0326`（uid 1027, gid 100 `users`）clone，容器內 Hermes 進程原本是 uid 10000、不屬於 `users` 群組，導致 `.git/index`、部分 git 物件、`notify.py`、`.github/` 讀寫失敗。解法選擇「共用群組」而非重新 clone 或大範圍改 owner：docker-compose 加 `user: "10000:100"`（Hermes 執行身分維持 uid 10000，群組改成跟使用者一樣的 `users`），NAS host 端 `chmod -R g+rwX` 該資料夾開放群組讀寫，容器內再 `git config --global --add safe.directory` 解決 git 對「檔案擁有者跟執行者不同」的額外防呆擋檢查。三段修正都個別驗證過（`id`、`git status`）。
  - 用 `hermes cron create`（自然語言請 Hermes 自己呼叫內建 cronjob 工具，而非人工組指令）設定每日台灣時間凌晨 3:00（`0 19 * * *` UTC）觸發 chunking-autoresearch 一輪迴圈，`--workdir` 指到 NAS 上掛載的專案路徑，跑完呼叫 `notify.py`，`--deliver origin,telegram`。
  - **手動觸發驗證兩輪，皆通過獨立查證**（commit 時間窗吻合、`git diff` 實際改動內容跟報告描述一致、`results.tsv` mtime 對得上、使用者獨立用 `uv run` 重跑 `harness.py` 復現出接近的 `cost_time` 數字）：第一輪意外發現 `enabled_toolsets` 同時給 `terminal`+`file` 時，`file` 工具在 `/workspace/projects/` 路徑下必定被 `HERMES_WRITE_SAFE_ROOT=/opt/data` 擋下、Hermes 靠自己換用 `terminal` 補救成功但機制不穩定（不保證每次都會這樣自救），改成只留 `terminal` toolset 後第二輪乾淨執行無異常。目前累積 3 次實驗、3 次 keep、0 discard、0 crash，`cost_time` 從 baseline 1.2625 進步到 1.051304（16.73%，尚未跨過 20% 通知門檻）。
- 下一步：排程已上線、每天凌晨自動執行，之後主要工作是定期查看 Telegram 通知/dashboard、等 20% 門檻觸發時人工 review 該次 PR（目前 Hermes 開分支後續 merge 流程還沒有實際跑過一次完整的「開 PR → Codex 審查 → 人工 merge」，值得找一次機會驗證）。
