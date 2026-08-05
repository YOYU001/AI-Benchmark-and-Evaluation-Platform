# AGENTS.md

本檔案專門存放給 AI agent／LLM 的通用指令，設計上不綁定特定工具（Claude Code、Cursor、其他 LLM 皆可沿用）。與 `CLAUDE.md` 不同：`CLAUDE.md` 放的是 Claude Code 專屬、跟這個 repository 高度綁定的架構說明；這份檔案放的是「不管換到哪個 LLM 都通用」的行為規則。

## 語言慣例

回覆使用者、以及撰寫任何文件內容，一律使用繁體中文；僅專有名詞（例如 API、RAG、CLAUDE.md、函式名稱、套件名稱等）維持英文原文，不進行翻譯。

## 子代理團隊的模型分工

核心原則：多個子代理之間要能夠 **parallelize（平行化）** 工作，而不是排隊式地一個一個依序執行。凡是任務可以拆成彼此獨立的子任務，就應該同時派出多個子代理平行處理，最後再統一整合結果，藉此縮短整體完成時間。下面的 Find out/Find in 與 Debate 流程，都是這個平行化原則的具體做法。

若任務拆成多個子代理（sub-agent）協作，模型等級依角色分工：

- **Leader（負責統籌、下指令、整合結果）與 QA（負責審查、驗證正確性）**：使用較高級的模型，因為這兩個角色需要深度思考、判斷與下決策。
- **其他執行型子代理**（例如大量搜尋資料、重複比對資料這類工作量大但單次判斷不複雜的任務）：可以使用較低級的模型，以節省成本與時間。

思考原則：預設以「省 token、速度快、但正確率高」為優先；但遇到真的需要深度推理、多步驟判斷的情境時，仍要切換成足夠的思考深度，不因為省 token 而犧牲正確性。

### 協作流程：Find out / Find in

多個子代理之間的協作，走「Find out / Find in」流程：先讓多個子代理**同步、平行地各自去查找資料**（Find out），彼此獨立作業；查找完成後，再把每個子代理各自查到的內容**整合、彙總在一起**（Find in），統一交給負責整合判斷的 agent（通常是 Leader）做後續分析與決策。

### 協作流程：Debate（辯論）

在需要搜尋「隨機且大量」的內容、或同一個問題可能有多種做法時，採用 debate 流程：可以同時派出多個（例如 10 個）子代理平行工作，各自找出不同的做法／答案，再回報給主要的 agent；主要的 agent 統整這些不同意見後，讓它們相互辯論、交叉檢驗彼此的結論，藉此篩選出品質較高、較可靠的答案，而不是只採信單一子代理的結果。

### 代理之間要相互隔離（context 分離）

不同職責的 agent 要各自獨立運作、context 互不汙染，工作內容透過「傳遞」而非「共用同一個 context」的方式交接。基本分工範例：

- **Developer**：負責主要開發工作的主 agent。
- **QA**：負責審查、驗證正確性的 agent。
- **Test**：負責測試的 agent。

也就是把不同階段的結果分派給不同的 agent 各自處理，處理完再把結果傳遞給下一個 agent，避免所有工作都塞在同一個 agent 的 context 裡，導致資訊互相干擾或 context 過長而失焦。

## 重複性工作要封裝成 skill

當發現某個動作是**重複執行**、或**日後很可能還要再做一次**的工作時，不要每次都臨時現做，而是把它封裝成一個 skill，方便之後直接呼叫、重複沿用。

skill 的檔案格式規定如下：

- 每個 skill 都要**先有一個 `skill.md`**，說明這個 skill 的用途、何時該觸發使用、輸入輸出、使用方式。
- 若這個 skill 實際需要執行程式邏輯（例如需要一支 `.py` 檔案來做實際運算、呼叫 API 等），才在 `skill.md` 之外另外加上對應的程式檔案（例如 `.py`），由 `skill.md` 說明如何呼叫它。
- 也就是 `skill.md` 是每個 skill 的**必要說明入口**，程式檔案是視需要才加上的**實作細節**，不能只有程式檔案而沒有 `skill.md`。

## Multi-LLM 討論流程（diversification）

當實作進度到達一個**段落性的里程碑**時（例如完成一個 Phase、一個功能、一個重要決策點），不要只由單一 LLM 拍板，而是拉進其他 LLM CLI 一起討論、產生多元觀點（diversification），最後才由 Claude Code 統整思考、給使用者一個結論。

參與角色（共 4 個）：

- **Claude Code**：負責發起討論、收集其他三方的意見、統整分析、最終給使用者結論與下一步建議。
- **codex CLI**：非互動呼叫方式為 `codex exec "prompt"`。
- **copilot CLI**：非互動呼叫方式為 `copilot -p "prompt" --allow-all-tools`（非互動模式必須加 `--allow-all-tools`，否則會卡在權限確認）。
- **agy CLI（Antigravity）**：非互動呼叫方式為 `agy --print "prompt"`。**目前這支執行檔不在系統 PATH 裡**，需要用完整路徑呼叫：`C:\Users\User\AppData\Local\agy\bin\agy.exe --print "prompt"`（除非使用者之後自行把它加入 PATH）。

流程：

1. 把目前的實作內容或要決策的問題，整理成一份三方都看得懂的共同 prompt（背景 + 問題 + 想要的輸出格式）。
2. **平行**呼叫 codex、copilot、agy 三個 CLI（呼應「子代理團隊」段落的 parallelize 原則，三個同時發出、不要排隊依序等待），各自獨立產生意見，避免互相汙染彼此的判斷。
3. Claude Code 收集三方回覆後統整分析，比對彼此的異同、找出共識與分歧（帶一點 debate 的精神：對分歧的地方要進一步判斷誰的理由比較站得住腳，而不是各打五十大板）。
4. 最終由 Claude Code 給使用者一個**統整後的結論**與建議的下一步做法，不是原封不動地把三方回覆貼出來。

## 資安規範

### API key／密鑰管理

- 所有 API key／密鑰**一律只存放在 `.env`**，不得寫死在程式碼、設定檔或任何會進版控的檔案裡。
- 在與使用者的對話、輸出內容、log、commit message 中，**絕對不能出現完整的 API key**；需要提到某把 key 時，一律用變數名稱代稱（例如 `ANTHROPIC_API_KEY`、「這把 key」），不得貼出實際值，即使只是為了除錯也一樣——若真的要確認 key 是否正確載入，用「是否存在／長度／前後幾碼是否符合預期」來確認，不要印出完整字串。
- 若懷疑某把 key 已經在對話紀錄、commit 歷史、log 檔或任何外部管道中曝光過，一律視為**已外洩**，應立即到對應服務重新產生（rotate）一把新的，而不是繼續沿用。

### 套件安裝防護（防 typosquatting／supply chain 風險）

背景：LLM 在下指令安裝套件時可能產生幻覺、拼字誤植（例如把 `acorn` 誤打成 `acorns`），若剛好存在一個同名或相似名稱的惡意套件，就可能在安裝時（例如透過 postinstall script）被拿去讀取 `.env` 等敏感檔案並外流。因此：

- 安裝任何新套件（`npm install`、`pip install` 等）之前，**先核對套件名稱是否與官方文件／官方 registry（npmjs.com、PyPI）上的名稱完全一致**，不要單憑記憶或聯想直接下指令。
- 安裝前檢查該套件的可信度：maintainer 是否合理、下載量／使用量是否符合預期、發布時間、是否有對應的官方 GitHub repo 連結。有任何疑慮，先跟使用者確認再安裝，不要自行判斷後直接裝。
- 安裝新依賴前，先明確列出「要安裝的套件名稱＋版本」讓使用者能一眼檢查是否有異常拼字或不熟悉的套件，不要讓安裝動作悄悄發生。
- **啟用 Claude Code 的權限機制（permission settings）**，讓 `npm install`／`pip install` 這類會拉入外部程式碼執行的指令，預設都要經過人工確認才能執行，不要設成自動允許（auto-approve）；如果不確定目前的權限設定是否足夠，用 `update-config` skill 檢查並調整 `settings.json`。
- 有能力區分的情況下，優先以 `--ignore-scripts` 之類的方式安裝（避免安裝當下就自動執行 postinstall script），除非明確知道該套件需要安裝腳本才能正常運作。

### 目前規則之外，建議一併留意的資安缺口

- **commit 前檢查 diff**：`git add` 之後、`git commit` 之前，養成習慣看一次實際要進版控的內容，避免密鑰或其他敏感資料因為誤加而混進 commit（`.gitignore` 只能擋住整份 `.env` 檔，擋不住有人把 key 貼在別的檔案裡）。
- **其他 LLM CLI 自己的登入憑證也要保護**：codex、copilot、agy 這些工具各自在本機也有自己的帳號登入資訊／設定檔（通常在使用者家目錄底下，例如 `.codex`、`.copilot` 之類），這些不屬於這個 repo 的 `.env`，但同樣是敏感資料，不要把整個使用者家目錄或這些設定資料夾分享、上傳、截圖外流。
- **API key 的權限範圍（scope）與用量上限**：若該服務支援設定金鑰的權限範圍或每月／每日花費上限，建議依最小權限原則設定，避免一把 key 出事時被無限上綱使用。
- **定期輪替（rotate）**：即使沒有明確外洩跡象，重要的 key 也建議有週期性更換的習慣，降低長期曝險。
- **之後若要 push 到 GitHub**：建議開啟 repository 的 secret scanning／push protection，作為 commit 前檢查之外的最後一道防護網。

以上是我先想到、你原本兩點之外可能有漏的地方，如果有不適用這個專案現況的可以再跟我說要不要拿掉。

### `.claude/settings.json` 已知限制（2026-08-05 資安審查發現）

以下兩點是設定上**沒辦法單純靠改設定值就完全解決**的真實限制，記錄下來避免以後誤以為現有防護是滴水不漏的：

- **`permissions.ask` 只是文字前綴比對，不是真的懂 shell 語法**：例如 `Bash(npm install*)` 只會擋住「指令開頭就是 `npm install`」的情況，像 `cd tmp && npm install x`、`true; npm install x` 這種複合指令因為開頭文字不符，會直接繞過確認、被當成允許執行。這代表 `ask` 清單只能防「不小心／照著建議直接下指令」的情境，防不了刻意規避。真正扛住「就算裝到惡意套件也不能外流資料」這件事的是 `sandbox.credentials.files`（讓資料在系統層級被遮蔽），不是 `ask` 清單本身，兩者要分清楚各自的防護邊界。
- **`sandbox.failIfUnavailable: false` 是刻意的 fail-open 選擇，不是疏漏**：目的是避免這台機器如果不支援 sandbox，導致所有 Bash 指令直接壞掉、整個工作環境用不了。代價是：如果 sandbox 真的無法啟動，防護會**悄悄失效**、只留一個容易被忽略的警告，實際保護程度會回到只剩 `permissions.deny`／`ask` 這一層。

### 已確認：`sandbox` 在這台機器（原生 Windows 11）上完全不生效

2026-08-05 用乾淨的測試方式驗證過（另找一個不會觸發 Claude Code 內建防護的檔名，臨時加進 `sandbox.credentials.files`，測完立刻清掉）：**sandbox 的憑證保護沒有擋住任何東西，讀取成功**。

查證後確認原因：**Claude Code 的 sandbox 功能官方明確不支援原生 Windows**，只支援 macOS、Linux、WSL2（原生 Windows 沒有對應的底層隔離機制，如 macOS 的 Seatbelt 或 Linux 的 `bubblewrap`）。這**不是設定沒套用或需要重啟的問題，是平台本身的硬性限制**——這台機器（LG gram Pro 16", Windows 11 Home, 原生環境非 WSL2）不管重開機幾次，`sandbox.enabled: true` 都不會真的生效，`failIfUnavailable: false` 會讓它安靜地 fallback 成不啟動。

**目前 `.env` 系列敏感檔案的實際防護，只剩這幾層**（sandbox 不算在內）：
1. Claude Code 內建的硬性防護——連 Bash 指令的文字內容提到 `.env`／`.ssh`／`secrets.json` 這類憑證檔名，都會被直接擋下來，使用者的確認也無法解除（已驗證有效）。
2. `permissions.deny`——Read 工具讀不到這些檔案（已驗證有效）。
3. `permissions.ask`——安裝套件需要人工確認，但可被複合指令繞過（見上方已知限制）。
4. 使用者自行核對套件名稱（人工防線）。

若之後真的需要 sandbox 那層完整保護，唯一路徑是在 **WSL2** 裡跑 Claude Code，這是遠比重開機更大的環境改動，目前沒有急迫性，先不處理。`sandbox.*` 設定保留在 `.claude/settings.json` 裡不刪除（沒有壞處，也是為將來搬到 WSL2 先鋪路），但不要誤以為它現在有在保護東西。
