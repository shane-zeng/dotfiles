# Personal Dotfiles Repository Instructions

- This is the personal dotfiles repository. The work setup remains an independent project at /path/to/workspace/work/dotfiles.
- global-AGENTS.md contains shared personal instructions. codex-global-AGENTS.md and agy-global-AGENTS.md resolve their installed symlinks to load it.
- This repository root AGENTS.md applies to work in this repository. Keep claude/CLAUDE.md at its existing path and unchanged.
- install-instructions.sh deploys Codex, agy, and Claude Code instruction links, Claude’s commit command, and the session-docs and general-code-review skills under ~/.agents/skills and ~/.gemini/config/skills.
- codex/agents/ contains the personal Codex subagents installed as regular TOML files. codex/config.toml.example is a snippet for the user’s Codex config.
- global-git-commit-instructions.md contains shared commit rules. Codex and agy read it through their global entry points. claude/commands/commit.md is the Claude command entry point symlink to the same guide.
- Never add private keys, tokens, or machine-specific authentication data to this repository.
