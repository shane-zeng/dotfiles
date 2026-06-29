# PR Title and Description Guide

Extract useful context for writing a high-quality PR title and description from:

- User requirements
- Optional issue or ticket key
- Branch name
- Git diff
- Commit messages
- Test results
- Related specs, notes, or session documents

Prioritize the following information:

1. The business need, user problem, or technical goal this PR solves.
2. Affected modules, APIs, workflows, environments, configuration, or data sources.
3. Behavior changes: what was different before and after the change, and what users or systems will observe.
4. Release context: if there is an issue key, release branch, target environment, or launch note, include it. Do not guess missing information.
5. Verification: test commands, manual checks, or reasons why tests were not run.
6. Risks and notes: compatibility concerns, data changes, configuration requirements, rollback considerations, or reviewer focus areas.
7. Maintainability judgment: briefly mention when the change intentionally avoids over-abstraction, keeps logic explicit and inline, or extracts functions/services only when reuse or branching complexity justifies it.

## Output Language Rule

The generated PR title and PR description must be written in Traditional Chinese.

Technical terms, command names, file names, API names, class names, function names, package names, environment names, and error messages may remain in English when that improves clarity.

## PR Title Rules

- Write the title in Traditional Chinese.
- Keep it to one concise line.
- Prefer describing the purpose and affected scope.
- If a recognizable issue or ticket key exists, it may be prefixed:

    APP-123 修正登入驗證錯誤處理

- Do not invent an issue key.
- Avoid vague titles such as:
  - 修正 bug
  - 更新程式
  - 調整邏輯
- Avoid titles that only list technical details or filenames unless the file itself is the primary deliverable.

## PR Description Format

## 背景 / 需求

- 說明為什麼需要這個 PR。
- 聚焦使用者問題、業務需求或技術目標。

## 變更內容

- 條列主要變更。
- 聚焦行為與系統影響。
- 除非有助於 reviewer 理解，否則避免逐檔流水帳。

## 影響範圍

- 說明受影響的模組、API、流程、環境、設定或資料來源。

## 驗證方式

- 列出已執行的測試、指令或手動檢查。
- 若未驗證，明確寫「未執行」並說明原因。

## 風險 / 注意事項

- 列出 reviewer 需要特別注意的地方。
- 不確定的資訊請標示「待確認」。
- 資訊不足時不要自行假設。
