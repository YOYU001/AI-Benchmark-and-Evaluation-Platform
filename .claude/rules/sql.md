---
paths:
  - "**/*.sql"
---

# SQL 撰寫慣例

目標：查詢起來最省時間、最乾淨、最不容易因為寫法問題造成資料錯亂或效能問題。

## 效率

- 只 `SELECT` 實際需要的欄位，不要 `SELECT *`——減少資料傳輸量，也讓查詢意圖一目了然。
- 注意 index 是否有效：對有建 index 的欄位做函式運算（例如 `WHERE LOWER(col) = ...`）會讓 index 失效、變成全表掃描，要避免。
- 需要抽樣或測試用途時明確加 `LIMIT`，不要意外撈出全部資料。
- 查詢邏輯複雜時用 CTE（`WITH ... AS (...)`）拆解，不要寫成一長串難以閱讀的巢狀 subquery——這也是一種「效率」，減少之後除錯與修改的時間成本。

## 不容易出錯 / 不容易造成資料錯亂

- **一律使用參數化查詢（parameterized query / prepared statement）**，絕對不要用字串拼接組 SQL——這不只是效能問題，是安全問題（SQL injection），也容易因為忘記處理特殊字元的轉義而讓查詢整個炸掉。
- `JOIN` 一律明確寫出 join 類型（`INNER JOIN`、`LEFT JOIN` 等）與 join condition，不要用逗號分隔的舊式隱式 join，避免意外產生笛卡兒積、撈出遠超預期的資料量。
- 會修改資料的操作（`UPDATE`、`DELETE`）一律先確認有明確的 `WHERE` 條件，避免整張表被意外改掉。
- 交易（transaction）要明確 commit 或 rollback，不要留著狀態不確定的連線或未關閉的交易。

## 可讀性

- SQL 關鍵字（`SELECT`、`FROM`、`WHERE`、`JOIN` 等）全部大寫，跟欄位名稱／表名區分開來。
- 縮排一致，多層條件或多個 JOIN 時每個子句換行，方便快速掃視整體結構。
