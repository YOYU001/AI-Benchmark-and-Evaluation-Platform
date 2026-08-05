# AI Benchmark and Evaluation Platform

## 這是什麼

這是一個獨立的學習與作品集專案，目標是建立一套可長期沿用的 **AI Evaluation / Benchmarking 方法論與工具**，用來系統化判斷不同 AI 模型、RAG、Agent 是否值得導入專案。

長期規劃見 `docs/NVIDIA_AI_EVALUATION_ROADMAP.md`（NVIDIA 官方 Evaluation/Benchmarking 生態系為主線，Phase 1–10 漸進式學習路線）。

## 與 AI Energy Operations Copilot (MVP_V1) 的關係

本專案**不是** MVP_V1 的一部分，是獨立資料夾，避免兩個專案的檔案互相混雜。但兩者關係緊密：

- MVP_V1 是「被評估對象」（system under test）——它的 RAG pipeline、`/assistant` chat、tool orchestration 都可以是這裡的評測目標。
- `datasets/` 底下的起始測試資料是從 MVP_V1 的 `spike/` 複製過來的既有驗證資產（**複製，不是搬移**——MVP_V1 自己的測試與腳本仍依賴原始檔案，這裡的副本只作為 Evaluation Platform 的起始資料，兩邊之後會各自演進，不會互相同步）。

## 資料夾結構

```text
AI Benchmark and Evaluation Platform/
├── docs/                                          # 學習筆記、roadmap、每個 Phase 的 checklist
│   ├── NVIDIA_AI_EVALUATION_ROADMAP.md            # 長期參考地圖（定案版，含 Claude review 補充）
│   ├── NVIDIA_AI_EVALUATION_ROADMAP_draft_superseded.md  # 舊草稿，保留備查，不再更新
│   └── 00_phase1_2_learning_plan.md               # 目前正在做的 Phase 1+2 學習清單與評測方式
├── datasets/                                      # 測試資料（含從 MVP_V1 複製的起始資料）
│   ├── energyops_test_questions.json              # 29 題，複製自 MVP_V1 spike/test_questions.json
│   ├── energyops_retrieval_benchmark_baseline.json # 複製自 MVP_V1，作為 baseline 數字參考
│   └── energyops_chunking_comparison_baseline.json
└── results/                                        # 之後每次評測跑出來的結果放這裡
```

## 目前進度

Phase 1（Evaluation 詞彙）+ Phase 2（第一次手動 AI Battle）規劃中，尚未開始執行。見 `docs/00_phase1_2_learning_plan.md`。
