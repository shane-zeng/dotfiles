# Personal Dotfiles

This repository stores personal computer configuration and personal global agent instructions. It is independent of the work bootstrap repository at /path/to/workspace/work/dotfiles and the work instructions repository at /path/to/work/example-instructions.

## Agent Instructions

- global-AGENTS.md is shared personal guidance linked to ~/.claude/CLAUDE.md.
- codex-global-AGENTS.md is linked to ~/.codex/AGENTS.md; it loads the shared guidance and the Codex commit-guide pointer.
- The root AGENTS.md applies to this repository. Keep claude/CLAUDE.md in its existing location.
- global-git-commit-instructions.md is the shared commit guide for Codex and Claude Code. Codex reads it through codex-global-AGENTS.md; claude/commands/commit.md is Claude Code’s command entry point to the same guide.
- install-instructions.sh creates five home symlinks, including the session-docs and general-code-review skill directories under ~/.agents/skills. It stops if a target already exists with a different link or as a file or directory; resolve that conflict before retrying.
- The installer does not replace ~/.claude/settings.json or other machine-specific app settings.

## Personal Computer Conventions

- GitHub remotes use github-example-work for owners example-org and example-work-account, and github-personal for shane-zeng and third-party repositories.
- Personal projects and open-source checkouts live under /path/to/workspace/Code/; company projects live under /path/to/workspace/work/; session exports and specifications live under /path/to/workspace/copilot/.
- The repository directory is a convention, not an account selector. Choose the SSH alias from the GitHub owner.

## Install the Global Links

Run this from the repository root:

    ./install-instructions.sh
