# Antigravity CLI Global Instructions

- Resolve the installed entry symlink to find this repository's source
  directory. For example:

  ```zsh
  instructions_entry="$HOME/.gemini/AGENTS.md"
  instructions_repo="$(dirname "$(readlink "$instructions_entry")")"
  ```

- At the start of each task, read
  `"$instructions_repo/global-AGENTS.md"` and follow it as the shared personal
  guidance.
- Before drafting or creating a commit message, read
  `"$instructions_repo/global-git-commit-instructions.md"` and follow its
  format. Add the Codex co-author trailer only when Codex materially
  contributed; do not invent an AgY attribution trailer.
- Commit formatting guidance does not authorize creating a commit. Create one
  only when explicitly requested.
