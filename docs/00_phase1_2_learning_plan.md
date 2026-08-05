# Phase 1 + 2 學習清單與評測方式

對應 `NVIDIA_AI_EVALUATION_ROADMAP.md` 的 Phase 1（Evaluation 基礎）與 Phase 2（第一次 AI Battle）。

## 一、學習清單（Phase 1：詞彙）

目標：每個詞不是背定義，而是能對應到 MVP_V1 專案裡實際發生過的例子。

| 詞彙 | 定義 | 對應 MVP_V1 的實際例子（待填） |
|---|---|---|
| Benchmark | Dataset + Metric/Scoring Rules | `datasets/energyops_test_questions.json`（29 題）+ hit@k 計分規則 |
| Dataset | 一組固定的測試輸入 | 同上，29 題固定問題 |
| Ground Truth | 每題「正確答案應該長什麼樣」 | 每題對應的正確 chunk/文件 |
| Metric | 拿什麼數字打分 | hit@1 / hit@3 / hit@5 |
| Baseline | 拿來比較的舊結果 | `datasets/energyops_retrieval_benchmark_baseline.json` |
| Accuracy | 待你自己用例子寫一次定義 | |
| Precision | 待你自己用例子寫一次定義 | |
| Recall | 待你自己用例子寫一次定義（提示：hit@k 其實比較接近 Recall，不是 Accuracy） | |
| Latency | 待 Phase 7 實測，這裡先寫概念 | |
| Throughput | 待 Phase 7 實測，這裡先寫概念 | |
| LLM-as-a-Judge | 用另一個 LLM 幫忙打分 | Phase 2 會第一次實際用到 |
| Regression | 新版本比舊版本差 | MVP_V1 Step 10 Sub-step 5、8 逐題比對 baseline 的動作 |

**產出要求**：把「對應 MVP_V1 的實際例子」欄位自己動手填完，用自己的話寫，不要照抄左邊定義。這是驗證有沒有真的懂的方式。

## 二、評測方式（Phase 2：第一次 AI Battle）

### 步驟

1. 從 `datasets/energyops_test_questions.json` 挑 5–10 題（不用全部 29 題，先求做完整個流程）。
2. 選兩個模型做比較（例如目前 MVP_V1 `/assistant` 用的模型 vs 另一家）。
3. 對每一題，兩個模型各自產生答案，人工記錄：
   - Accuracy（跟 ground truth 是否一致）
   - Latency（回應花多久）
   - Tokens / Cost
   - Hallucination（有沒有講出資料裡沒有的東西）
4. 其中 Accuracy 這一項，額外用 LLM-as-a-Judge 打分（另外呼叫一個模型，給它 question + ground truth + 兩邊的答案，請它評分），跟你自己人工判斷的結果對照，看兩者是否一致。

### 執行前必做：成本估算

Phase 2 會真的呼叫付費 API（含 LLM-as-a-Judge 那一次呼叫），跑之前先用 MVP_V1 專案既有的 `embed-cost-estimate` skill 估算花費，不要盲跑。

### 產出

`results/ai_model_scorecard_v1.md`（或 `.csv`），格式：

| Question ID | Model | Accuracy (人工) | Accuracy (Judge) | Latency | Tokens | Cost | Hallucination |
|---|---|---|---|---|---|---|---|

## 三、需要用到的資料內容

已複製到 `datasets/`：

- `energyops_test_questions.json` — 29 題固定問題，Phase 2 先挑 5–10 題出來用
- `energyops_retrieval_benchmark_baseline.json` — MVP_V1 既有的 retrieval baseline 數字，Phase 1 對照 Baseline 定義時參考
- `energyops_chunking_comparison_baseline.json` — 目前 Phase 1/2 用不到，先放著，Phase 5/6 可能會用到

還缺、需要你自己準備的：

- 兩個要比較的模型的 API access（例如你目前用的 provider + 另一家）
- 一份空白的 scorecard 表格（上面已經給格式，直接建立 `results/ai_model_scorecard_v1.md` 即可）

## 下一步

Phase 1 詞彙表填完、Phase 2 scorecard 跑完 5–10 題之後，回頭找我對答案，再一起進 Phase 3（把這個手動流程寫成 `evaluation_runner.py`）。
