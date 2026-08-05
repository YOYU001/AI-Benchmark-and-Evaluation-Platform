---
paths:
  - "**/*.py"
---

# Python 撰寫慣例

目標：執行起來最省時間、最乾淨、最不容易因為粗心或狀態混亂而出錯。以下規則優先於「先求能動就好」的寫法。

## 效率

- 處理大量資料（JSON 資料集、評測結果）優先用內建函式與 list/dict comprehension，不要手刻 for 迴圈做本來就有內建方法的事（`sum`、`max`、`min`、`sorted`、`any`、`all` 等）。
- 資料量大時考慮用 generator／迭代器處理，不要一次性把整個大檔案讀進記憶體；讀取超大 JSON/CSV 時評估是否需要串流處理。
- 不要在迴圈裡重複做可以在迴圈外做一次的事（例如重複編譯同一個 regex、重複開關同一個檔案／連線）。

## 乾淨與可維護

- 所有函式簽名要標 type hint（參數與回傳型別），減少之後看不懂、猜錯型別的成本。
- 避免全域可變狀態（global mutable variable）；能透過參數傳遞就不要依賴全域變數，降低函式之間互相汙染的風險。
- 命名要清楚、有意義，不要為了省打字縮寫到看不懂（除非是業界通用縮寫如 `df`、`idx`）。

## 不容易出錯 / 不容易造成執行混亂

- 所有檔案讀寫、外部連線一律用 `with` context manager，確保資源正確釋放，不要手動 `open()`/`close()`。
- 呼叫外部 API（LLM provider、任何 HTTP request）要明確設定 timeout，並用 `try/except` 包住、記錄清楚的錯誤訊息——不要讓一次呼叫失敗就讓整支腳本掛住或無聲中斷。
- 例外處理不要用空的 `except:` 或 `except Exception: pass` 吞掉錯誤，至少要記錄下來。
- `.env` 讀取一律用 `python-dotenv` 的 `load_dotenv()`，不要手動 parse 檔案內容。
- 印出的 log／debug 訊息絕對不能包含完整 API key 或其他敏感資訊（呼應 `AGENTS.md` 的資安規範）。
