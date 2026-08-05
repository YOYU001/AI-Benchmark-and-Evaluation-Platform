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
  - **control-scope-gap**（已修正）：`sandbox.credentials.files` 原本只保護 `.env`/`.env.local`，沒涵蓋 `secrets.json`/`.ssh`，已補上，並加 `sandbox.filesystem.denyRead` 讓範圍跟 `permissions.deny` 一致。
  - **allowlist-semantic-escape**（無法修正，已記錄限制）：`permissions.ask` 只比對指令開頭文字，複合指令（如 `cd tmp && npm install x`）會繞過確認機制。真正防線是 sandbox 那層，不是 `ask` 清單。
  - **fail-open-control**（已查明原因，非設定問題）：用乾淨測試法驗證（用不觸發內建防護的檔名臨時測試，測完清除）確認 **sandbox 在這台機器上完全沒有生效**，查證後確認是 **Claude Code 官方明確不支援原生 Windows**（只支援 macOS/Linux/WSL2），不是重啟能解決的問題。使用者機器：LG gram Pro 16" Windows 11 Home（原生，非 WSL2）。若要完整 sandbox 保護需搬到 WSL2 執行，目前不處理，`sandbox.*` 設定保留在 settings.json 裡供未來沿用。
  - 意外發現：使用者已自行在 `.env` 放入真實內容（過程中沒有讀取或顯示其內容），也順帶驗證了 Claude Code 內建的硬性防護——連 Bash 指令文字提到 `.env` 系列檔名都會被直接擋下，使用者確認也無法解除。
  - 確認以上防護不影響正常呼叫 API 的工作流程：程式（如未來的 `evaluation_runner.py`）自己用 `load_dotenv()` 讀取 `.env` 不會觸發任何一層防護，只有「Claude 自己想看到金鑰內容」這件事會被擋。
- `CLAUDE.md` 補上 `active/` 資料夾結構說明（原本只記錄在 `.gitignore` 註解跟這份 PROGRESS.md 裡，未寫進主要架構文件）。
- 未完成／待辦：
  - `.env` 內容使用者已自行填入，之後若需要除錯要用「是否存在／長度」的方式確認，不能直接讀取內容。
  - `agy` 加入 PATH 一事使用者已知道方法（登出重登入或重開機），等手邊另一個專案跑完再處理，之後要回頭把 `AGENTS.md` 裡 agy 的呼叫方式從完整路徑改回簡短的 `agy`。
  - 這次 commit 之後的所有修正（settings.json 補洞、AGENTS.md 資安限制記錄、CLAUDE.md active/ 說明、本次 PROGRESS.md 更新）都還沒 commit，待使用者確認後一起進版控。
  - `results/` 底下依 Phase + 日期分子資料夾的命名規則，討論過方向但尚未實際建立/套用。
