# Personal Dotfiles Repository Instructions

- This is the personal dotfiles repository. The work setup remains an independent project at /path/to/workspace/work/dotfiles.
- global-AGENTS.md contains shared personal instructions for Claude and other tools. codex-global-AGENTS.md is the Codex-only entry point and loads the shared file.
- This repository root AGENTS.md applies to work in this repository. Keep claude/CLAUDE.md at its existing path and unchanged.
- install-instructions.sh links Codex to codex-global-AGENTS.md, Claude to global-AGENTS.md, and Claude’s commit command to the shared guide.
- global-git-commit-instructions.md contains shared commit rules for Codex and Claude Code. Codex reads it through codex-global-AGENTS.md; claude/commands/commit.md is the Claude command entry point symlink to the same guide.
- Never add private keys, tokens, or machine-specific authentication data to this repository.
