# Personal Dotfiles

This repository stores personal computer configuration and personal global agent instructions. It is independent of the work bootstrap repository at /path/to/workspace/work/dotfiles and the work instructions repository at /path/to/work/example-instructions.

## Bootstrap a Personal Mac

Install Xcode Command Line Tools and [Homebrew](https://brew.sh/) first. For the terminal step, set up the `github-personal` SSH alias and add its public key to GitHub. Check out this repository at `/path/to/workspace/Code/dotfiles` if you use the absolute paths in the personal agent instructions.

From the repository root:

```bash
./bootstrap.sh --dry-run
./bootstrap.sh
./doctor.sh
```

For the same Ghostty appearance on a new Mac, install the four [MesloLGS NF font files](https://github.com/romkatv/powerlevel10k#manual-font-installation). The Ghostty config uses MesloLGS NF at 16 pt and the Raycast Dark theme.

Open a fresh terminal before running `doctor.sh`. It checks CLI availability, runtimes, Ghostty and the installed links without connecting to GitHub.

| Step | What it sets up |
| --- | --- |
| `brew` | Installs missing items from `Brewfile`, including PHP, Composer, uv, fnm, GitHub CLI, and daily CLI tools. Existing packages are not explicitly upgraded. |
| `terminal` | Runs the pinned `shane-zeng/terminal-setup` fork with Zsh for Ghostty, shell plugins and Starship. Links the personal Ghostty config and ensures fnm has a runnable default Node. |
| `agents` | Runs `install-instructions.sh` for the Codex and Claude instructions, commit command and skills. Install and sign in to the agent apps separately. |

Use `./bootstrap.sh --only brew`, `--only terminal` or `--only agents` to rerun a step. Run `brew` before the first `terminal` run. The terminal installer can change the login shell and replace `.zshrc` and Ghostty's config. It asks first, prints the backup directory and stops on unmanaged symlinks it could overwrite. The SSH fetch uses a temporary checkout of the pinned commit. Once the same pin is installed and its files are in place, reruns skip the fork installer.

To update the terminal pin, review the fork changes, update the pin in `bootstrap.sh`, and rerun the terminal step. Review older Ghostty config files under `~/.config/ghostty` if Ghostty loads another config. Existing app logins, private keys, and machine-specific settings stay on the Mac.

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
