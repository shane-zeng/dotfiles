# Compact 交接摘要（已停用）

自動產生 handoff 文件的 Hook 已停用。Codex 與 Claude 的原生自動 compact 和手動 `/compact` 保留；只有使用者明確要求存 session 或保存討論時才寫入文件。

`install.sh` 現在移除本套件的 Hook，並安裝不輸出指示的停用腳本，讓已開啟對話可能仍快取的指令也不會要求寫檔。再次執行不會重新啟用自動摘要。

其他 Hook、原生 compact 設定、信任設定及既有 session 文件保留。變更前設定與腳本備份至 `~/.agent-hooks/backups/`。

在本 repo 根目錄執行：

```zsh
/bin/bash ./session-handoff/test.sh
/bin/bash ./session-handoff/install.sh
```

測試只使用暫存目錄，驗證停用、舊指令無輸出、既有文件及其他設定保留，以及重複執行結果一致。

手動保存 session 沿用 `/path/to/workspace/copilot/docs/sessions/YYYY-MM-DD-topic.md`。
