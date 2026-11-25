# Personal Dotfiles

This repository stores personal computer configuration and shared instructions for coding agents.

## Bootstrap a Personal Mac

Install Xcode Command Line Tools and [Homebrew](https://brew.sh/) first. For the terminal step, set up the `github-personal` SSH alias and add its public key to GitHub.

From the repository root:

```bash
./bootstrap.sh --dry-run
./bootstrap.sh
./doctor.sh
```

For the same Ghostty appearance on a new Mac, install the four [MesloLGS NF font files](https://github.com/romkatv/powerlevel10k#manual-font-installation). The Ghostty config uses MesloLGS NF at 16 pt and the Raycast Dark theme.

Open a fresh terminal before running `doctor.sh`. It checks CLI availability, runtimes, Ghostty, installed links, and Codex role files without connecting to GitHub.

| Step | What it sets up |
| --- | --- |
| `brew` | Installs missing items from `Brewfile`, including PHP, Composer, uv, fnm, GitHub CLI, and daily CLI tools. Existing packages are not explicitly upgraded. |
| `terminal` | Runs the pinned `shane-zeng/terminal-setup` fork with Zsh for Ghostty, shell plugins and Starship. Links the personal Ghostty config and ensures fnm has a runnable default Node. |
| `agents` | Runs `install-instructions.sh` to deploy Codex, agy, and Claude Code instructions, shared skills, Claude’s commit command, Codex subagents, and initial Claude Code and agy settings. Install and sign in to the agent apps separately. |

Use `./bootstrap.sh --only brew`, `--only terminal` or `--only agents` to rerun a step. Run `brew` before the first `terminal` run. The terminal installer can change the login shell and replace `.zshrc` and Ghostty's config. It asks first, prints the backup directory and stops on unmanaged symlinks it could overwrite. The SSH fetch uses a temporary checkout of the pinned commit. Once the same pin is installed and its files are in place, reruns skip the fork installer.

To update the terminal pin, review the fork changes, update the pin in `bootstrap.sh`, and rerun the terminal step. Review older Ghostty config files under `~/.config/ghostty` if Ghostty loads another config. Existing app logins, private keys, and machine-specific settings stay on the Mac.

## Agent Instructions

- `global-AGENTS.md` is shared personal guidance linked to `~/.claude/CLAUDE.md`. The root `AGENTS.md` applies to this repository.
- `codex-global-AGENTS.md` and `agy-global-AGENTS.md` are linked to `~/.codex/AGENTS.md` and `~/.gemini/AGENTS.md`, respectively. Codex uses `$CODEX_HOME` when set. Both entry points use the installed symlink to locate the shared guidance and commit guide.
- `claude/commands/commit.md` is Claude Code’s command entry point to the shared commit guide. The installer links `session-docs` and `general-code-review` under both `~/.agents/skills/` and `~/.gemini/config/skills/`. See [Antigravity customization discovery](https://antigravity.google/docs/customization-discovery/).
- The installer reports conflicts before installing and leaves existing app settings intact. Review any conflicting paths before rerunning it.

On a fresh setup, the installer copies [Claude Code settings](claude/settings.json.example) to `~/.claude/settings.json` and [Antigravity CLI settings](agy/settings.json.example) to `~/.gemini/antigravity-cli/settings.json`. Both are regular files that the apps can update locally. Configure trusted workspaces on each Mac.

## Codex Subagents

`install-instructions.sh` copies the role files in `codex/agents/` into `${CODEX_HOME:-$HOME/.codex}/agents/`. It uses regular files for Codex’s role loader and preserves other roles in that directory. If a tracked role changes, compare it with the installed copy, then move the old copy aside and rerun the installer to deploy the update. An existing copy with identical content is accepted on reruns.

| Role | Used for | Model and effort |
| --- | --- | --- |
| `code_mapper` | Tracing a bounded code path or data flow | `gpt-6-luna` / `high` |
| `docs_researcher` | Checking version-specific official documentation | `gpt-6-luna` / `high` |
| `reviewer` | Reviewing a change and its callers for regressions | `gpt-6.2-sol` / `high` |

To apply the suggested limit of three concurrent subagents and the default `medium` effort for general-purpose agents, merge the keys from [codex/config.toml.example](codex/config.toml.example) into the active Codex `config.toml`. If there is already an `[agents]` table, add or update its keys there. Rename the legacy `max_threads` key if present. The deprecated `[features] multi_agent` key still controls the V1 fallback. With the current default of enabled subagents, an explicit `multi_agent = true` can be removed. See the [Codex subagent settings](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Open a new session to try the roles in a Codex client that supports custom agents. The role files set the model and effort, and their read-only guidance runs under the parent session’s permissions. See [codex-global-AGENTS.md](codex-global-AGENTS.md) for when to delegate and how to choose a model for the task.

## Personal Computer Conventions

- Define SSH aliases and identity file paths in `~/.ssh/config`. Keep GitHub owner-to-alias mappings and the default alias for third-party owners in `~/.config/personal-dotfiles/agent-local.md`, which the shared agent instructions read when selecting an alias.
- Record checkout locations, the session documentation directory, and the specification directory in the local agent instructions. Choose the SSH alias from the GitHub owner.
- Set `SESSION_DOCS_DIR` to the session documentation directory for the session-docs CLI, or pass `--dir` to override it for a command. Set `DOTFILES_WORKSPACE_DIR` if `doctor.sh` should check a local workspace directory.

## Install the Global Links

Run this from the repository root:

    ./install-instructions.sh
