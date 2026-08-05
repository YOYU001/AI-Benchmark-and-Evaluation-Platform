# CLAUDE.md

本檔案為 Claude Code（claude.ai/code）在此 repository 中工作時的指引。

## 這個 repository 是什麼

這是一個獨立的學習／作品集專案，目標是建立一套可長期沿用的 **AI Evaluation / Benchmarking 方法論與工具**，用來判斷某個 AI model、RAG pipeline 或 agent 是否值得導入專案。長期規劃以 NVIDIA 官方的 Evaluation/Benchmarking 生態系（NeMo Evaluator、RAG Evaluation metrics、AIPerf、Agent Evaluation）作為參考地圖，分成 10 個 Phase 漸進式進行。

目前此 repo **沒有任何應用程式碼**——只有 docs 與 dataset 測試資料，進度停在 Phase 1/2（詞彙 + 第一次手動 "AI Battle" 比較）。不要假設有 build system、package manifest 或 test runner 存在；使用前請先確認。

## 與 `AI Energy Operations Copilot`（MVP_V1）的關係

這是一個**獨立的姊妹專案**，不是 MVP_V1 底下的子資料夾：

- MVP_V1 是**被評估對象（system under test）**——它的 RAG pipeline、`/assistant` chat endpoint、tool orchestration 都是這個平台要評測的目標。
- `datasets/*.json` 是從 MVP_V1 的 `spike/` 資料夾**複製**（不是搬移）過來的一次性起始快照。MVP_V1 自己的測試／腳本仍依賴原始檔案；這裡的副本之後會獨立演進，**不會**跟 MVP_V1 保持同步。不要把兩邊的檔案互相「修正」拉齊。

## 資料夾結構

```text
docs/
  NVIDIA_AI_EVALUATION_ROADMAP.md            # 定案版長期 roadmap（Phase 1-10），最下方含 Claude review 補充
  NVIDIA_AI_EVALUATION_ROADMAP_draft_superseded.md  # 舊草稿，僅保留備查，不再更新
  00_phase1_2_learning_plan.md               # 目前實際在做的 checklist（Phase 1 詞彙 + Phase 2 AI Battle）
datasets/
  energyops_test_questions.json              # 29 題固定評測問題，複製自 MVP_V1 spike/test_questions.json
  energyops_retrieval_benchmark_baseline.json # MVP_V1 的 retrieval baseline 數字，作為 Baseline 參考
  energyops_chunking_comparison_baseline.json # Phase 5/6 之前用不到
results/                                      # 每次評測跑出來的結果放這裡（目前是空的）
active/                                        # 工作中的暫存區，不進版控（見下方說明）
  research/                                    # 探索性研究、學習筆記草稿
  execution/                                   # 執行中、尚未定案的評測中間產出
  config/                                      # 實驗用的臨時設定草稿
  temp/                                        # 純暫存，隨時可丟
```

`active/` 底下四個子資料夾各自只保留一個 `.gitkeep` 佔位，實際內容透過 `.gitignore` 排除在版控之外，可以放心在裡面產生、堆放任何還沒定案的東西。**定案的東西要手動搬到 `results/`（評測結果）或 `docs/`（正式文件）**，`active/` 本身永遠不會出現在 commit 歷史裡。

## 這個 repo 的工作慣例

- **每次開始工作前，先閱讀 `PROGRESS.md`**，了解目前進度與上次停在哪裡；每次工作結束或有階段性產出時，在該檔案新增一筆紀錄（日期 + 做了什麼 + 下一步）。
- **`docs/00_phase1_2_learning_plan.md` 是「現在要做什麼」的最終依據**；`NVIDIA_AI_EVALUATION_ROADMAP.md` 則是長期地圖。若兩者看似衝突，近期工作以 phase learning plan 為準。
- **`datasets/energyops_test_questions.json` 是 test oracle**（見其 `_meta.purpose`）：一旦 retrieval/citation 測試已經在使用它，就不要隨意修改題目或預期答案——修改它要當成變更 ground truth，而不是一般的資料修正。注意其 `verification_tiers` 欄位：只有 `verified` 的題目可以拿來算正式的 accuracy metric；`partially_verified` 僅能用於定性觀察；`unverified` 是行為面的判斷（系統是否恰當地拒答），不是事實比對。
- 執行 Phase 2 的付費 API 比較（含 LLM-as-a-Judge 那一次呼叫）之前，計畫要求先用 MVP_V1 既有的 `embed-cost-estimate` skill 估算花費，不要盲跑。
- Phase 2 預期產出為 `results/ai_model_scorecard_v1.md`（或 `.csv`），欄位為：Question ID、Model、Accuracy (人工)、Accuracy (Judge)、Latency、Tokens、Cost、Hallucination。
- 依 roadmap 的 Phase 3，手動評測流程最終要變成 Python 的 `evaluation_runner.py`——但目前還不存在；不要假設它的介面長相，等真正進入該 Phase 時再重新設計。
- 此 repo 的文件與 commit 風格說明主要語言為繁體中文（zh-TW）；編輯既有文件時請沿用中文，而非改用英文。
