# TODO.md

這個專案跨對話、會一直留著的待辦清單。完成的項目打勾、保留刪除線，不要直接刪掉整行（留個紀錄比較好追蹤）。新的待辦事項隨時可以加在對應區塊底下。

## 環境／設定

- [x] ~~`agy` 加入 PATH 生效後（使用者計畫重開機處理），回頭把 `AGENTS.md` 裡 `agy` 的呼叫方式從完整路徑改回簡短的 `agy`~~（2026-08-05 重開機後確認生效，`AGENTS.md` 已更新）
- [ ] 決定 `results/` 底下依 Phase + 日期分子資料夾的命名規則，並實際套用
- [ ] 若之後要搬去 WSL2 讓 sandbox 真正生效，搬之前要先把要用到的 LLM provider 網域加進 `.claude/settings.json` 的 `sandbox.network.allowedDomains`（目前只有 npm/PyPI）
- [ ] 專案出現第一支真正的 Python 程式碼時，建立 `requirements.txt`（或依當時選定的環境管理工具改建 `environment.yml`），內容依實際 `import` 的套件決定，不要預先猜測（也記在 auto-memory 裡，任何一個 session 應該都會主動提醒）
- [ ] 設定 CI/CD 工作流——觸發時機：這個 repo 有 push 到遠端（GitHub）+ 有真正的程式碼可以跑測試／建置之後，現在沒程式碼、也還沒有遠端，先不處理
- [ ] 設定 git worktree——觸發時機：之後如果讓某個 subagent 也具備 Edit/Write 權限（不只是審查、要它直接改程式碼），或使用者自己需要同時維護多個 branch 或是多個 LLM 需要各自進行工作但不互相干擾時。目前 `qa`/`research`/`code-review` 三個 subagent 都刻意只有 Read/Grep/Glob/Bash，沒有並行編輯衝突的問題，先不處理
