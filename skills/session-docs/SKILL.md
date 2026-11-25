---
name: session-docs
description: Locate and read the user's saved session documents (docs/sessions/*.md) without the user pasting a path. Use when the user says to read, open, continue, or look up a session by Jira key (ABC-1234), PR number (pr1234), topic, date, alias, or Codex chat id, or asks for one section of such a document (for example the conclusion). Also use to see why a session was archived or to propose archiving, to record model and reasoning effort after a user-requested session save, or when the user asks about model and effort usage. Native logs are used only as a source for usage metadata.
---

# Session documents

Session documents are Markdown files saved in the configured session directory. A derived index
(`index.json`) sits next to them. Let the script look up documents instead of reading the index or scanning
the directory yourself.

Resolve the script relative to this skill: `<skill-dir>/scripts/session_docs.py`. It uses only the Python
standard library (3.9+).

```bash
uv run --no-project <skill-dir>/scripts/session_docs.py [--dir DIR] [--no-refresh] <command> ...
```

If `uv run` is blocked by the sandbox (uv cache lock), run the same script with `python3` instead. No packages are
needed. `--dir` and `--no-refresh` go **before** the command. Pass `--dir` to override
`SESSION_DOCS_DIR`. If the environment variable is unavailable, pass the session documentation directory
from `~/.config/personal-dotfiles/agent-local.md` with `--dir`. Check those settings before asking for a path.

Repository names in GitHub pull request URLs and `owner/repo#1234` references are indexed automatically.
To also index bare repository names in the filename, title, or metadata block, set
`SESSION_DOCS_REPO_PREFIXES` in the environment that runs the script. Use comma-separated prefixes
without the trailing hyphen, for example `example,demo` to match `example-web` and `demo-api`.
The index refreshes when the prefix list changes.

## Workflow

1. **Locate.** `find <words from the user's request>`. Pass Jira keys, PR numbers, dates, aliases, or title words
   as they were given; the script normalizes `abc1234`, `ABC 1234`, `pr1234`, `PR #1234`, and `#1234`.
2. **Decide.**
   - One clear match: use it.
   - Several close matches: show the candidates (date, title, file name) and ask which one. Do not guess.
   - No match: retry once with fewer or different words. Then say nothing was found; do not invent a path.
3. **Read only what is needed.** For a whole-document request, `read <ref>`. When the user names a part
   ("the conclusion", "the second round"), run `outline <ref>` and then
   `read <ref> --section "<heading text>"` (or `--section "#N"`). Long documents are truncated at 40,000
   characters; read by section or `--lines A-B` instead of reading everything.
4. **Say which file you used** (name and date), so the user can correct a wrong pick.

`<ref>` is a file name, a path, or a query that resolves to exactly one document; exit code 3 means ambiguous
(candidates are printed).

## Commands

| Command | Purpose |
| --- | --- |
| `find QUERY... [--limit N] [--include-archived] [--archived-only] [--json]` | Locate documents; best matches first, newest first on ties |
| `outline REF` | Headings with line ranges |
| `read REF [--section S] [--first\|--all] [--lines A-B] [--max-chars N]` | Print a document or one section |
| `build [--force]` | Refresh the index explicitly |
| `archive-candidates [--json]` | Propose archivable documents (never moves anything) |
| `archive REF --reason R [--superseded-by REF2] [--update-links] [--yes]` | Move a document to `_archive/` |

Exit codes: 0 ok, 1 nothing found, 2 usage or environment error, 3 ambiguous.

The index refreshes itself on every `find`, `outline`, and `read` (change detection by content hash), so it does
not need manual upkeep. Refreshing may modify `index.json`, which is tracked in the sessions repository; mention
it if the user is about to commit.

## Archived documents

A document is archived when it is under `docs/sessions/_archive/`. The path is the only source of truth; do not
add markers inside documents.

- `find` ignores archived documents by default.
- Look at them only when the user asks for old versions, history, or why a decision was made; when nothing
  current matches (the script then says the result came from the archive); when following a "superseded by" or
  "merged into" reference; or when comparing versions.
- Results from the archive are labeled `[archived]`. The reason and replacement come from
  `_archive/manifest.json`. Tell the user a document is archived and point to its replacement before relying on it.

### Archiving

Archiving is a judgment call and changes file locations, so **only run `archive ... --yes` after the user has
confirmed that specific document**.

1. Run `archive-candidates` to propose. Candidates are suggestions with a confidence label, not decisions.
2. Archive only these cases: the document was **superseded or merged** into a newer one; it is a **derived
   artifact** whose content already lives in a main document (for example a save script); or it is a
   **fragment** already folded into a main document.
3. Do **not** archive because of age or because a document says "done". Old research and design decisions stay
   useful.
4. Run `archive REF --reason "..." [--superseded-by REF2]` without `--yes` first and show the preview. It lists
   other documents that mention the file name; those links break after the move. `--update-links` rewrites only
   full-path references (`docs/sessions/<name>`). Then ask for confirmation and run again with `--yes`.
5. Every archive needs a reason, recorded in `_archive/manifest.json`.

## Aliases

Short names the user likes to use go in `docs/sessions/index.aliases.json` (a JSON object whose keys are a file
name, a relative path, or a glob such as `*export-preview*`, and whose values are lists of alias strings).
Rebuilding the index never removes them. Add an alias only when the user asks.

## Limits

- Only documents saved as Markdown are indexed (top level and `_archive/`). Native chat transcripts
  (`~/.codex/sessions`, `~/.claude/projects`) are out of scope. When a document records a chat id, `find` can
  match it, but resuming that chat is up to the user.
- Metadata is extracted from the title and the bullet block before the first `##` section (date, PR, Jira,
  status, chat id). A document without that block is still found by file name, title, headings, and body text.
- Line numbers go stale when a document is edited; sections are matched by heading text. Refresh happens on
  every call, so outline numbers are current when printed.

## Model and effort usage

`scripts/model_usage.py` reads native Claude Code, Codex and AgY logs without changing them.
By default, `save` keeps one row per session in `~/.local/state/session-docs/model-usage.jsonl`.
Override the location with `--out` or `MODEL_USAGE_OUT` to reuse an existing history, including a
previous `docs/sessions/model-usage.jsonl`. Keep the history and raw reports private. They can include
session IDs, titles, local paths and part of the first AgY prompt.

**After saving or updating a session document at the user's request, record the model and effort, then save
the local history.** `meta --apply` writes two bullets into the document's metadata block under the H1
(or creates the block):

```markdown
- 模型：claude-opus-5-5
- 推理強度：high
```

```bash
uv run --no-project <skill-dir>/scripts/model_usage.py meta --apply <document.md>
uv run --no-project <skill-dir>/scripts/model_usage.py save
```

- `meta` finds the running session from `CLAUDE_CODE_SESSION_ID` or `CODEX_THREAD_ID`. Without either (for
  example AgY), pass `--tool agy|codex|claude`: it then takes the latest session of that tool that started in
  the current directory, and fails rather than guess when there is none. `--session ID` picks one explicitly.
  It prints the chosen session on stderr; check it matches before relying on the bullets.
- The values cover the session so far. If the model or effort changed, the bullets list each one with its
  count (`high×40、medium×5`). Subagents are not included.
- Do not copy token numbers into the document unless the user asks.

Reports merge the file with the live transcripts, so purged sessions still appear:

```bash
uv run --no-project <skill-dir>/scripts/model_usage.py [summary|sessions|roles] [--tool claude|codex|agy] [--since YYYY-MM-DD] [--main-only] [--json]
```

- `roles` groups subagent sessions by role, model and effort. Claude gets the role from the subagent metadata
  file. Codex uses either the rollout's session metadata or `source.subagent.thread_spawn`.
- Use `python3` directly if the sandbox blocks `uv run` on its cache lock. No packages are needed.
- Units differ: Claude counts API responses, Codex counts turns, AgY counts generations. AgY has no token data
  (its protobuf schema is undocumented), so its token columns show `-`.
- Codex `guardian` sessions (the automatic permission reviewer) are excluded unless `--include-guardian`
  is given.
- Codex compresses older sessions to `.jsonl.zst`. They are read through the `zstd` command; without it the
  script warns on stderr and skips them, so Codex history is incomplete.
- AgY fields were found by inspecting real data; if a report shows many `unknown` efforts, the format changed.

## Tests

```bash
python3 -m unittest discover -s <skill-dir>/scripts
```
