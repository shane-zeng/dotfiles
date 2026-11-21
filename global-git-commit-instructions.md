# Commit Message Convention

Use the following commit type labels:

- feat: New feature
- fix: Bug fix
- docs: Documentation change
- style: Code formatting change
- refactor: Code refactoring
- perf: Performance improvement
- test: Add or update tests
- build: Build tool or build process change
- ci: CI configuration change
- add: Add files unrelated to features
- 3rd: Add or update third-party dependency
- sql: Database-related change

## Format

type: Traditional Chinese summary

Example:

    fix: 修正登入表單驗證錯誤

## Language Rule

The commit message summary must be written in Traditional Chinese.

The commit type must remain in English.

Correct:

    fix: 修正登入表單驗證錯誤

Incorrect:

    fix: correct login form validation

## Optional Reference Rule

If there is a related issue, ticket, or note ID, it may be added at the end of the summary.

Example:

    feat: 新增登入失敗次數限制 [#123]

Do not force a reference ID when there is no clear related issue.

## Commit Summary Priority

When generating the Traditional Chinese summary, use the following priority:

1. User-provided change description
2. Code diff and actual behavior change
3. Implementation details

Avoid simply translating method names, class names, or file names into Chinese.

Prefer describing the purpose or functional change.

Good:

    feat: 新增登入失敗次數限制

Avoid:

    feat: 新增 Cache Increment 邏輯

## AI Co-author Attribution

Choose attribution based on which AI assistant materially contributed to the changes or commit message, rather than only which tool performs the final Git command.

- Codex assistance: add `Co-authored-by: Codex <codex@openai.com>`.
- Claude Code assistance: use Claude Code's configured commit attribution. If it is unset, Claude Code uses `Co-Authored-By: <model name> <noreply@anthropic.com>`.
- If both Codex and Claude Code materially contributed, include one trailer for each.
- Do not add a trailer for an assistant that did not contribute, and do not duplicate a trailer Claude Code already added.

Example for a Codex-assisted commit:

    fix: 修正登入表單驗證錯誤

    Co-authored-by: Codex <codex@openai.com>

When Claude Code creates the commit, check its configured attribution before editing the message; preserve its model-specific trailer unless the user requests another format.
