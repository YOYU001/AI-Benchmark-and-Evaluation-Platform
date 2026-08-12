# Chunking／RAG 評測指標研究整理

本文件彙整 2026-08-12 派出的 10 個平行研究任務結果，主題是「業界／學術界怎麼評斷 chunking 或
RAG 系統做得好不好」，目的是檢視 `tools/chunking_autoresearch/harness.py` 目前的三個指標
（`cost_time`／`quality_pass_rate`／`content_coverage`）跟業界標準的落差，並找出 dashboard
第四張卡片（原本放「原始秒數」，已確認拿掉）可以換成什麼有意義、有 baseline 對比基準的指標。

純粹是資料蒐集整理，不是決策文件——要不要採用、怎麼採用，留在下面「與現況的對應」跟後續討論
裡處理。

## 目錄

1. [檢索品質標準指標（Recall@k／Precision@k／MRR／NDCG）](#1-檢索品質標準指標)
2. [RAG 評測框架（RAGAS／TruLens／ARES）](#2-rag-評測框架)
3. [Chunking 策略比較方法](#3-chunking-策略比較方法)
4. [業界實務評測經驗（Anthropic／Weaviate／Databricks／MongoDB）](#4-業界實務評測經驗)
5. [LLM-as-a-Judge 方法論](#5-llm-as-a-judge-方法論)
6. [NVIDIA 官方評測工具鏈](#6-nvidia-官方評測工具鏈)
7. [學術 RAG Benchmark（BEIR／KILT／Lost in the Middle／RGB／CRAG）](#7-學術-rag-benchmark)
8. [Chunk 精準度／冗餘度量測方法](#8-chunk-精準度冗餘度量測方法)
9. [RAG 延遲／成本／吞吐量評測實務](#9-rag-延遲成本吞吐量評測實務)
10. [Chunk 邊界／結構完整性量化指標](#10-chunk-邊界結構完整性量化指標)
11. [與這個專案現況的對應](#11-與這個專案現況的對應)

---

## 1. 檢索品質標準指標

- **Recall@k**：top-k 結果涵蓋「所有相關文件」的比例，不看排序位置、不分相關程度高低。對 RAG
  來說特別重要，因為直接反映「正確答案所在的 chunk 有沒有被撈進 context」。
- **Precision@k**：top-k 結果裡有多少比例是真正相關的，反映雜訊比例。
- **MRR（Mean Reciprocal Rank）**：只看「第一個相關結果出現的名次」的倒數平均，order-aware
  但仍是二元相關性判斷。
- **NDCG（Normalized Discounted Cumulative Gain）**：同時考慮排序位置與分級相關性，資訊量最
  豐富，但需要有分級的 relevance label，標註成本較高。

**業界主要看板指標**：BEIR／MTEB Leaderboard 的檢索任務類別預設用 **NDCG@10**；重排名任務
用 MAP@K。部分實務教學把 Recall@5（目標 0.80+）當 production 主指標。chunking 策略比較上，
較小 chunk 通常拉高 Recall@k 但犧牲 Precision（AI21 研究：固定 chunk size 與 oracle 之間
Recall@1 差距可達 20–40%）。

來源：[Weaviate — Retrieval Evaluation Metrics](https://weaviate.io/blog/retrieval-evaluation-metrics)、
[Towards Data Science — DCG@k and NDCG@k](https://towardsdatascience.com/how-to-evaluate-retrieval-quality-in-rag-pipelines-part-3-dcgk-and-ndcgk/)、
[AI21 — Chunk size is query-dependent](https://www.ai21.com/blog/query-dependent-chunking/)

---

## 2. RAG 評測框架

- **RAGAS**：component-level 指標，含 Faithfulness（拆解答案成 claim，逐一檢查能否由 context
  推導出）、Answer Relevancy、**Context Precision**（依排名位置判斷每個 chunk 是否相關，
  加權平均，類似 average precision）、**Context Recall**（回答所需資訊有多少比例出現在
  context 裡）。有 LLM 版本跟非 LLM 版本。
- **TruLens**：提出 "RAG Triad"——Context Relevance、Groundedness、Answer Relevance，三者皆用
  LLM-as-judge。
- **ARES**：用合成資料 fine-tune 一個輕量 LM 當 judge，搭配少量人工標註做 PPI 校正，號稱比
  RAGAS/GPT-3.5 judge 更貼近人工排名。

**重要發現**：三個框架**都沒有專門針對「chunking 策略本身」的獨立指標**——chunk 好壞只能透過
下游的 Context Precision/Recall 間接觀察，沒有框架內建「切塊品質分數」。RAGAS、TruLens 皆
MIT 授權開源免費，可接本機開源模型當 judge（例如透過 Ollama），理論上能在零成本階段使用，但
本機模型當 judge 的穩定度沒有官方數據佐證。

來源：[Ragas 官方文件](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)、
[TruLens RAG Triad](https://www.trulens.org/getting_started/core_concepts/rag_triad/)、
[ARES GitHub](https://github.com/stanford-futuredata/ARES)、
[ARES 論文](https://arxiv.org/pdf/2311.09476)

---

## 3. Chunking 策略比較方法

常見策略：Fixed-size（成本低但常切斷句子）、Recursive character splitting（多篇來源列為多數
RAG 系統最佳預設，Denser AI benchmark 端到端準確率 69%，優於 semantic chunking 的 58%）、
Semantic chunking（用 embedding 相似度分群，recall 可提升但計算成本最高、片段有時過短）、
Sentence-aware、Structure-aware（NVIDIA 自家 benchmark 顯示 page-level chunking 最穩定）。

比較方法主要是端到端指標（retrieval recall/precision/MRR/NDCG、答案品質、延遲、token 用量），
加上人工抽查邊界合理性。

**重要發現**：論文 **MoC（Mixtures of Text Chunking Learners for RAG System，ACL 2025）**
提出兩個**不依賴下游任務**的直接指標：
- **Boundary Clarity (BC)**：`BC(q,d) = ppl(q|d) / ppl(q)`，用困惑度衡量邊界處語意分離程度，
  越接近 1 代表邊界越清晰。
- **Chunk Stickiness (CS)**：衡量單一 chunk 內部的凝聚力與邏輯獨立性。

來源：[Denser AI — RAG Chunking Strategies 2026](https://denser.ai/blog/rag-chunking-strategies/)、
[Unstructured.io — Chunking for RAG Best Practices](https://unstructured.io/blog/chunking-for-rag-best-practices)、
[MoC 論文（arXiv 2503.09600）](https://arxiv.org/abs/2503.09600)

---

## 4. 業界實務評測經驗

- **Anthropic — Contextual Retrieval**：核心指標是 `1 - recall@20`（top-20 檢索失敗率）。
  Contextual Embeddings 讓失敗率從 5.7% 降到 3.7%（降 35%），加 Contextual BM25 降到 2.9%
  （降 49%），再加 reranking 降到 1.9%（降 67%）。
- **Weaviate**：三層指標——生成層（Faithfulness、Answer Relevancy）、檢索層（NDCG、Precision、
  Recall）、索引層（ANN recall）。
- **Databricks**：小 chunk（64–128 tokens）適合事實型問答，大 chunk（512–1024 tokens）適合
  需廣泛脈絡的任務；長 context 並非越多越好，多數模型在特定長度後效能開始下降。
- **MongoDB**：建議 Precision@K／Recall@K／MRR／NDCG 搭配 RAGAS 的 faithfulness、answer
  correctness、latency 一起比較不同 chunking 設定。

來源：[Anthropic — Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)、
[Weaviate — An Overview on RAG Evaluation](https://weaviate.io/blog/rag-evaluation)、
[Databricks — Chunking Strategies Guide](https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089)

---

## 5. LLM-as-a-Judge 方法論

- **Prompt 設計**：Pairwise（兩兩比較，穩定但不 scalable）、Pointwise（單獨打分，可平行化但
  波動大）、Rubric-based（分項評分準則，易 debug）。代表方法 **G-Eval**（Chain-of-Thought +
  form-filling，摘要任務 Spearman 相關係數 0.514，優於 BLEU/ROUGE）。
- **已知偏誤**：Position bias（順序影響評分，約 10–15 個百分點波動，緩解法是正反兩次評測取
  一致結果）、Length bias（偏好長答案，約 15–30 個百分點偏移）、Self-preference bias（偏好
  同家族模型生成的答案，約 10–25%）。
- **與人工一致性**：MT-Bench 顯示強 judge（GPT-4）跟人類偏好一致性可達 80% 以上。
- **成本**：self-consistency（多次取樣取多數決）成本隨 ensemble size 線性增加；常見省成本法
  是 adaptive self-consistency（信心度夠高就提早停止）。

來源：[MT-Bench 論文](https://arxiv.org/abs/2306.05685)、
[Position Bias 論文](https://arxiv.org/abs/2406.07791)、
[Self-Preference Bias 論文](https://arxiv.org/pdf/2410.21819)、
[G-Eval 論文](https://arxiv.org/abs/2303.16634)

---

## 6. NVIDIA 官方評測工具鏈

四層分工：
- **NeMo Evaluator**：通用 LLM/RAG 品質評測平台，支援 100+ benchmark、LLM-as-judge，RAG 指標
  含 recall@k、NDCG@k、faithfulness、answer relevancy、context precision。
- **RAG Blueprint 評測腳本**：用 RAGAS 衡量 accuracy/latency/quality，retrieval 階段用
  recall@k。官方部落格有一篇專門比較 chunking 策略的實驗：固定 embedding/reranker/生成模型，
  只改 chunking 策略，跨 5 個資料集，用「評委會」（Mixtral 8x22B + Llama 3.1 70B）降低單一
  judge 偏誤，結論 page-level chunking 平均準確度最高（0.648）且標準差最低（0.107）。
- **AIPerf**：純效能/延遲/吞吐量工具，不涉及答案正確性。指標分 Record（單一請求，如
  time_to_first_token）、Aggregate（跨請求）、Derived（衍生計算，如 throughput）。
- **NeMo Agent Toolkit**：agent 軌跡與工作流評測，可透過 RAGAS 介面評測其中的 RAG 子任務。

來源：[NeMo Evaluator 文件](https://docs.nvidia.com/nemo/microservices/latest/about/core-concepts/evaluation.html)、
[NVIDIA — Finding the Best Chunking Strategy](https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/)、
[AIPerf GitHub](https://github.com/ai-dynamo/aiperf)、
[NeMo Agent Toolkit 文件](https://docs.nvidia.com/nemo/agent-toolkit/latest/improve-workflows/evaluate.html)

---

## 7. 學術 RAG Benchmark

- **BEIR**：18 個公開資料集，涵蓋多樣任務類型與 domain，測 zero-shot 泛化能力，NDCG@10 為主
  要指標。核心發現：BM25 是穩健 baseline，re-ranking/late-interaction 模型平均最好但成本高。
- **KILT**：11 個資料集、5 種任務類型，統一對齊到同一份 Wikipedia snapshot，強調任務無關的
  記憶架構研究。跟 BEIR 的差異：BEIR 重視多樣性/zero-shot 泛化，KILT 重視同一知識源下的多任
  務共用基礎設施。
- **Lost in the Middle**：核心發現是模型對長 context 中不同位置資訊的利用呈 **U 型曲線**——
  相關資訊在開頭或結尾時準確率最高，在中間明顯下降。對 RAG 的啟示：chunk 數量不是越多越好，
  排序也要刻意安排（最相關的放最前或最後）。
- **RGB／CRAG**：RGB 測 RAG 系統的 noise robustness、negative rejection（該拒答時有沒有拒答）
  、information integration、counterfactual robustness 四種核心能力；CRAG 是 Meta 出的
  4,409 組 QA，涵蓋 8 種問題類型含 multi-hop、比較、聚合。

來源：[BEIR 論文](https://arxiv.org/abs/2104.08663)、
[KILT 論文](https://arxiv.org/abs/2009.02252)、
[Lost in the Middle 論文](https://arxiv.org/abs/2307.03172)、
[RGB 論文](https://arxiv.org/abs/2309.01431)、
[CRAG 論文](https://arxiv.org/pdf/2406.04744)

---

## 8. Chunk 精準度／冗餘度量測方法

這是目前 `content_coverage`（只測 recall／有沒有丟資料）最欠缺的「precision／有沒有拿太多」
面向的對應研究：

- **Chroma 官方研究 — IoU 指標**：`IoU = |t_e ∩ t_r| / |t_r|`（t_e = ground-truth 相關 token
  集合，t_r = 檢索出來所有 chunk 的 token 集合）。分母把「所有被檢索出來的 token」都算進去，
  多餘、不相關的 token 會直接拉低分數，等同 precision 型懲罰；同時定義
  `Recall = |t_e ∩ t_r| / |t_e|` 做對照。**需要 query 與 ground-truth 才能算。**
- **Chunk Filtering 論文（arXiv 2604.24334）**：用 cosine similarity 超過閾值，或 named-entity
  集合重疊 ≥50%，判定兩個 chunk 是否冗餘（門檻式二元判斷，非連續分數）。
- **RAGAS Context Precision**：`Context Precision@K = Σ(Precision@k × v_k) / 相關項目總數`，
  同樣**依賴 query** 才能定義什麼是「不必要的雜訊」。
- **HOPE 論文 — Concept Unity (ζ_con)**：對每個 chunk 生成多個陳述句，算陳述句兩兩 cosine
  similarity 的平均，數值接近 1 代表語意單一、聚焦。**這是少數不需要 query、純看 chunk 本身
  就能算的 precision 型指標**——但論文發現它跟下游 RAG 表現呈**負相關**，不是「越高越好」的
  直覺指標，採用前要注意這點。
- **Chunk 太大的量化壞處**：chunk size 從約 1,800 字元增到 14,400 字元，準確率下降約
  10–20%；chunk size 達 1000 tokens 左右開始因內容稀釋而準確率下降。

來源：[Chroma — Evaluating Chunking Strategies](https://www.trychroma.com/research/evaluating-chunking)、
[Chunk Filtering 論文](https://arxiv.org/html/2604.24334v1)、
[RAGAS Context Precision](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/)、
[HOPE 論文](https://arxiv.org/html/2505.02171v1)

---

## 9. RAG 延遲／成本／吞吐量評測實務

- 業界普遍按 pipeline 各階段分別記錄 **p50/p95/p99**，而非只看端到端總延遲；p95 常作 SLA
  目標。
- Chunking 這類前處理步驟的效能評估較不規範化：有測「單文件處理秒數」（不同 chunker 差異可達
  1000 倍），也有測「整批吞吐量 MB/s」；有資料指出典型企業 RAG pipeline 有 70% 時間花在切
  文字上。
- **NVIDIA AIPerf 的穩定性做法**：先跑一段 warmup（暖身結果直接丟棄，排除 cold-start），正式
  量測用大量 request 樣本做百分位統計（P50/P90/P99），**沒有找到官方建議「跑 N 次取中位數」
  這種 run 層級重複策略**——跟這個專案目前「跑 3 次取中位數」的做法比，AIPerf 更依賴大樣本
  統計而非少數幾次重複。
- **複合指標的警告**：一篇論文（arXiv 2511.09545）明確指出 weighted-sum 複合指標的缺陷：
  目標互相衝突時無法代表 Pareto-optimal 解，會掩蓋根因，不同情境需要不同權重。業界更常用
  「門檻式」表達，例如「faithfulness ≥ 0.85 且 p95 延遲 < 1.5 秒」，而非把所有維度平均成一個
  數字。

來源：[AIPerf Warmup 文件](https://docs.nvidia.com/aiperf/tutorials/load-patterns-scheduling/warmup-phase-configuration)、
[NVIDIA NIM Benchmarking Metrics](https://docs.nvidia.com/nim/benchmarking/llm/latest/metrics.html)、
[Cost-Latency-Quality Trade-offs 論文](https://arxiv.org/pdf/2511.09545)

---

## 10. Chunk 邊界／結構完整性量化指標

這是目前 `quality_pass_rate`（只測格式欄位對不對，不測「切得聰不聰明」）最欠缺的面向的對應
研究：

- **Block Integrity (BI)**（Adaptive Chunking 論文，arXiv 2603.25333）：比對結構標記（表格
  header、code fence、list marker）的開頭與結尾是否成對出現在同一 chunk 內，若只有開始標記
  沒有對應結束標記就判定該結構被切壞。**純粹從 chunk 本身計算，不需要下游任務**，GitHub repo
  有現成程式碼（`ekimetrics/adaptive-chunking`，`metrics.py` 的 `compute_block_integrity()`）。
- **Meta-Chunking — Boundary Clarity**（跟第 3 節提到的同一個公式）：`BC(q,d) = ppl(q|d) /
  ppl(q)`，用語言模型困惑度算邊界清不清楚，同樣不需要 query 或下游生成任務，完全 reference-
  free，可直接套用在既有 chunk 上事後評分。
- **HOPE 框架**：把 chunking 品質分三層——Intrinsic（Concept Unity）、Extrinsic（Semantic
  Independence）、Coherence（Information Preservation，較接近現有的 content_coverage）。
- **表格專用**：Structure-Aware Chunking for Tabular Data（arXiv 2605.00318）提出 Row Tree
  表示法對齊列邊界切分，但其驗證方式偏間接（token 利用率、下游 Recall），沒有直接量測
  row/column 完整性的公式。
- Unstructured.io 官方部落格坦承**沒有公布**自己的結構完整性量化方法，建議使用者自行建立
  evaluation set。

**重要提醒**：Boundary Clarity 與 Block Integrity 都是 2026 年才發表的新論文成果，目前沒有
現成 pip 套件可直接安裝套用，要自己依論文公式實作。

來源：[Adaptive Chunking 論文](https://arxiv.org/pdf/2603.25333)、
[Adaptive Chunking GitHub](https://github.com/ekimetrics/adaptive-chunking)、
[Meta-Chunking 論文](https://arxiv.org/html/2410.12788v3)、
[HOPE 論文](https://arxiv.org/pdf/2505.02171)、
[Structure-Aware Chunking for Tabular Data](https://arxiv.org/html/2605.00318)

---

## 11. 與這個專案現況的對應

| 現有欄位 | 對應到業界哪個概念 | 現況缺口 |
|---|---|---|
| `cost_time` | 速度指標，經 baseline 正規化 | 業界建議不要把速度跟品質壓成單一複合分數（第 9 節）——目前 `cost_time` 已經是「速度+及格關卡」的混合設計，跟業界建議的「分維度＋門檻式」方向不完全一致 |
| `quality_pass_rate` | 只是格式欄位健檢，不是任何業界標準指標 | 缺「chunk 切得聰不聰明」——第 10 節的 Boundary Clarity／Block Integrity 是直接對應的候選方法，且不需要下游任務、可離線計算 |
| `content_coverage` | 概念上接近 Recall，但不是标准 IoU/Context Recall 公式 | 缺「有沒有拿太多、重複」——第 8 節的 IoU（需要 query）或 HOPE 的 Concept Unity（不需要 query，但跟下游表現負相關，要謹慎使用）是候選方法 |
| （已拿掉的）原始秒數 | 業界不建議單獨看，會搭配 p50/p95/p99 或跟 chunk size 拉曲線一起看 | 需要重新設計成「有 baseline 對比」的呈現方式 |

這份對應表只是把研究結果跟現有欄位對齊，實際要不要調整、怎麼調整，留到下面的討論。
