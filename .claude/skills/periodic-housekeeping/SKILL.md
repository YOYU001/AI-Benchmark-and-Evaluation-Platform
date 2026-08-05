---
name: periodic-housekeeping
description: 定期檢查並整理 CLAUDE.md、AGENTS.md、PROGRESS.md 的長度，避免內容膨脹到影響 Claude Code 的判讀準確率；規則型文件用「修剪」處理，日誌型文件用「歸檔」處理。
---

# Periodic Housekeeping

## 用途

`CLAUDE.md`、`AGENTS.md`、`PROGRESS.md` 會隨著專案進行持續增長。官方建議每份檔案控制在 **200 行以內**，超過會吃掉更多 context、降低指令遵從度。這個 skill 用來定期檢查這三份檔案的長度，並依「規則型文件」跟「日誌型文件」用不同方式整理，讓它們維持精簡。

## 何時觸發

- 使用者明確要求「整理一下 CLAUDE.md/AGENTS.md/PROGRESS.md」、「幫我做 housekeeping」之類的請求。
- 一個大 Phase 或段落性里程碑結束時，可以主動提醒使用者是否要跑一次檢查（不要沒問過就自己動手整理）。

## 使用方式

1. 執行 `scripts/check_line_counts.py`，會印出 `CLAUDE.md`、`AGENTS.md`、`PROGRESS.md` 目前的行數，並標示哪些超過 200 行門檻。
2. 依檢查結果分流處理：

### 情境 A：`CLAUDE.md` 或 `AGENTS.md` 超過門檻（規則型文件 → 修剪）

這兩份是「規則型」文件，不能用機械化的方式砍內容，需要 Claude 自己讀過一遍、用判斷力修剪：

- **可以砍**：可以從程式碼／專案結構直接推導出來的內容（例如資料夾結構、套件清單這種一看就知道的東西）。
- **不能砍**：陷阱、理由（WHY）、非標準慣例、之前踩過的坑——這些是光看程式碼猜不出來的東西，也是這兩份文件存在的意義。
- 修剪完的結果**一定要先給使用者看過、確認之後才套用**，不能自己直接覆寫檔案。這是規則型文件，內容本身就是使用者要求的行為準則，擅自刪減等於片面改變雙方約定。

### 情境 B：`PROGRESS.md` 超過門檻（日誌型文件 → 歸檔，不是修剪）

`PROGRESS.md` 本質是時間序日誌，會一直變長是正常的，**不該用刪減內容的方式處理**，而是把舊紀錄搬到別的地方：

1. 執行 `scripts/archive_progress.py`，預設會把 `PROGRESS.md` 裡**最舊的一半日期區塊**搬進 `PROGRESS_ARCHIVE.md`（依 `## YYYY-MM-DD` 標題切分），`PROGRESS.md` 只留下最近的紀錄。
2. `PROGRESS.md` 開頭會自動加上一行提示：「更早的紀錄請見 `PROGRESS_ARCHIVE.md`」。
3. 執行前**先跟使用者確認**要保留最近幾筆／幾天的紀錄，不要用預設值默默執行。

## 檔案

- `scripts/check_line_counts.py`：檢查三份檔案目前行數，回報是否超過 200 行門檻。
- `scripts/archive_progress.py`：把 `PROGRESS.md` 裡較舊的日期區塊搬到 `PROGRESS_ARCHIVE.md`。

## 注意事項

- 這個 skill 不會自動、無聲地修改任何檔案內容——`check_line_counts.py` 只讀不寫；`archive_progress.py` 會寫入檔案，但執行前一定要先跟使用者確認範圍。
- `CLAUDE.md`／`AGENTS.md` 的修剪永遠需要 Claude 人工判斷「什麼該留、什麼該砍」，這個 skill 不提供、也不應該提供自動化的修剪腳本。
