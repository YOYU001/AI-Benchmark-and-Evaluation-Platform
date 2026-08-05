---
name: api-cost-estimate
description: 在真正呼叫付費的 chat completion API（模型比較、LLM-as-a-Judge）之前，先在本機估算大概要花多少美金，不呼叫任何 API、不花任何錢。不綁定特定專案或資料集——題目來源可以是任何檔案，也可以完全手動指定數量與長度。用法："/api-cost-estimate --model 'name:price_in:price_out[:effort]' [--model ...] [--judge '...'] [--questions-file <路徑>] [--num-questions N]"。
---

執行 `python .claude/skills/api-cost-estimate/scripts/estimate_cost.py [參數]`（從有這個 `.claude/` 資料夾的專案根目錄執行）。

## 這個 skill 在算什麼

Phase 2 這類「AI Battle」評測，一次完整流程通常包含：**每題問過每個要比較的模型一次**（chat completion 呼叫），**加上每題一次 LLM-as-a-Judge 評分**（另一個模型看過題目跟所有候選答案後打分）。這支腳本把這整套流程要花的 token 跟美金，在真的打 API 之前先估算出來。

## 用法

```
python estimate_cost.py \
  --model "gpt-x:2.50:10.00" \
  --model "claude-x:3.00:15.00:medium" \
  --judge "judge-model:2.50:10.00" \
  --questions-file path/to/questions.json \
  --reruns 1
```

- `--model`／`--judge` 格式：`name:每百萬 input token 美金:每百萬 output token 美金[:效果等級]`，可重複給多個 `--model`。效果等級（`low`/`medium`/`high`/`xhigh`）是給有 reasoning/thinking 模式的模型用的，會用一個粗略倍數放大估算的 output token 用量（真實模型行為依 provider 而異，這只是概略估計）。
- `--questions-file`：**任何**檔案都行，不綁定特定資料集結構——可以是純文字檔（一行一題），或 JSON（陣列、或物件裡有 `question`/`text`/`prompt`/`content` 其中一個欄位）。腳本會讀出**真實題目文字**去算平均長度，比純猜測準確。
- 沒有現成題目檔案時，改用 `--num-questions N --avg-question-chars C` 純手動指定。
- `--reruns`：每題每個模型要重跑幾次（例如想多跑幾次取平均），預設 1。
- `--context-overhead-tokens`／`--avg-answer-tokens`／`--avg-judge-tokens`：系統提示／上下文、模型回答、Judge 回覆的預設 token 估計量，都可以覆寫成更準確的數字。

## 估算依據與限制

字元／token 比例是概略估計（`2.0` 字元 ≈ 1 token，適用中英混合文字），**不是精確的 tokenizer 計算**，輸出會明確標註這是估算值。如果之後真的跑完一輪、實際用量跟估算差很多，把它當成之後校準的參考，不代表這個估算工具有 bug。

## 跟 MVP_V1 的 `embed-cost-estimate` 的差別

MVP_V1 那個 skill 算的是「PDF 切 chunk 後送 embedding API」的成本，跟這個 skill 算的「chat completion + judge 呼叫」成本是完全不同的東西，兩者不能互相取代。這個 skill 也不綁定這個專案或任何特定資料集，之後可以拿去用在其他專案的模型比較評測上。
