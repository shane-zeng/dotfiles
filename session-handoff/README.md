# Compact 交接摘要

本目錄屬於 `/Volumes/workspace/Code/dotfiles` repo，保存本機共用 Hook 的原始碼、安裝程式與測試；交接摘要仍輸出至 `/Volumes/workspace/copilot/docs/sessions/`。Codex／Claude Code 在原生 compact 完成後，透過同一個 `SessionStart` Hook 提醒接續工作的 Agent 更新精簡 Markdown。

同一 Session 只維護一份摘要，跨日沿用原檔名，覆寫並合併有效狀態，刪除重複及已失效的歷程。不同 Session 各自保存，避免同時工作互相覆蓋。內容只保留：

1. 目標與必要限制。
2. 仍有效的決策。
3. 完成事項與實際驗證。
4. 未解問題。
5. 具體下一步。

以約 1200 字內、每節至多三點為目標；關鍵限制與未完成工作優先。摘要不能授予新權限，最新的停止要求仍優先。

## 使用

已安裝後，沿用 Codex／Claude 的原生自動 compact 或 `/compact` 即可，不新增自訂 slash command、skill、Context 門檻、狀態列或通知，也不另行呼叫模型。

Hook 本身只輸出短的 `additionalContext` 指示；摘要由原 Session 的 Agent 在下一次模型續跑時寫入，因此不是 Hook 同步寫檔，也不保證在沒有後續模型請求時產生文件。權限不足或使用者要求停手時保留舊摘要並回報阻礙。原生 compact 的內部結果不會被此 Hook 修改。

檔案預設保存至 `/Volumes/workspace/copilot/docs/sessions/YYYY-MM-DD-<project>-<agent>-handoff-<identity-hash>.md`。日期是首次寫入日期；完整 Session／工作目錄／Agent 身分 hash 避免短 ID 碰撞。讀取指定檔案即可交接給另一個 Codex 或 Claude Session。這些自動摘要不自動提交到 Git。

不複製 Transcript、不建立每次 compact 的封存版本或配對狀態。之前的封存資料不會被安裝程式刪除。

## 安裝與驗證

需求：macOS 系統 Bash、既有的 `jq`。在本 repo 根目錄執行：

```zsh
/bin/bash ./session-handoff/test.sh
/bin/bash ./session-handoff/install.sh
```

安裝程式更新 `~/.agent-hooks/session-handoff.sh`，在 `~/.codex/hooks.json` 與 `~/.claude/settings.json` 合併單一 `SessionStart(compact)` Hook。僅移除本套件之前的 Pre／PostCompact Hook、skill 連結及 Context 提醒；其他設定保留，變更前檔案保存於 `~/.agent-hooks/backups/`。Codex 的 Hook 信任設定不會被修改；新增或修改的 Hook 需在 Codex CLI `/hooks` 檢視與信任，並以新 Session 或設定重新載入生效。

`HANDOFF_DEST` 可指定輸出目錄；`HANDOFF_INSTALL_HOME` 可指定安裝測試目錄；`HANDOFF_JQ` 可指定 jq。測試使用暫存目錄，不修改使用者設定，不刻意消耗 Context。

## 依據

- [Codex Hooks](https://learn.chatgpt.com/docs/hooks)：`SessionStart(source: compact)` 與 `additionalContext`；Codex 在 compact 後的即時續跑前注入此內容。
- [Claude Code Hooks](https://code.claude.com/docs/en/hooks#sessionstart)：`SessionStart(compact)` 支援自動與手動壓縮，並可注入後續模型上下文。

Codex 目前的實際 Transcript 包含加密 compact item，沒有可讀 `message`；Transcript 格式也不是穩定 Hook 介面，因此不依賴解析它取得摘要。
