#!/bin/bash
set -euo pipefail

repo_dir="$(cd -- "$(/usr/bin/dirname "$0")" && pwd)"
terminal_url='git@github-personal:shane-zeng/terminal-setup.git'
terminal_ref='9e2c8995c58fdb4506400725f268359e0ba6f7fb'
ghostty_config="$HOME/Library/Application Support/com.mitchellh.ghostty/config.ghostty"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/personal-dotfiles"
terminal_stamp="$state_dir/terminal-setup.ref"
dry_run=0
stage=all

usage() {
    echo 'Usage: ./bootstrap.sh [--dry-run] [--only brew|terminal|agents]'
}

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) dry_run=1 ;;
        --only)
            shift
            stage="${1:-}"
            case "$stage" in brew|terminal|agents) ;; *) usage >&2; exit 2 ;; esac
            ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
    shift
done

if [ "$dry_run" = 1 ]; then
    if [ "$stage" != agents ]; then
        xcode-select -p >/dev/null 2>&1 || echo '[preflight] Xcode Command Line Tools are missing.'
        if ! command -v brew >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/brew ] && [ ! -x /usr/local/bin/brew ]; then
            echo '[preflight] Homebrew is missing.'
        fi
    fi
    if [ "$stage" = all ] || [ "$stage" = brew ]; then
        printf '[brew] Install missing packages from %s using brew bundle --no-upgrade.\n' "$repo_dir/Brewfile"
    fi
    if [ "$stage" = all ] || [ "$stage" = terminal ]; then
        printf '[terminal] Fetch %s at %s via SSH into a temporary checkout when setup is needed.\n' "$terminal_url" "$terminal_ref"
        printf '[terminal] Ask before running setup.sh --zsh. Back up existing .zshrc and Ghostty config.\n'
        printf '[terminal] Link %s to %s and install a default Node LTS if missing.\n' "$ghostty_config" "$repo_dir/ghostty/config"
    fi
    if [ "$stage" = all ] || [ "$stage" = agents ]; then
        printf '[agents] Run %s to install instruction and skill links and Codex subagents.\n' "$repo_dir/install-instructions.sh"
    fi
    exit 0
fi

[ "$(uname -s)" = Darwin ] || fail 'This bootstrap requires macOS.'
if [ "$stage" != agents ]; then
    xcode-select -p >/dev/null 2>&1 || fail 'Run xcode-select --install, then retry.'
    if ! command -v brew >/dev/null 2>&1; then
        for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew; do
            if [ -x "$brew_bin" ]; then
                eval "$("$brew_bin" shellenv)"
                break
            fi
        done
    fi
    command -v brew >/dev/null 2>&1 || fail 'Install Homebrew from https://brew.sh/ and retry.'
fi

install_terminal() (
    set -euo pipefail
    if [ -f "$terminal_stamp" ] && [ "$(cat "$terminal_stamp")" = "$terminal_ref" ] &&
        [ -f "$HOME/.zshrc" ] && [ -L "$ghostty_config" ] &&
        [ "$(readlink "$ghostty_config")" = "$repo_dir/ghostty/config" ] &&
        { [ -d /Applications/Ghostty.app ] || [ -d "$HOME/Applications/Ghostty.app" ]; }; then
        echo 'Terminal setup already applied.'
    else
        for path in "$HOME/.zshrc" "$ghostty_config"; do
            if [ "$path" = "$ghostty_config" ] && [ -L "$path" ] &&
                [ "$(readlink "$path")" = "$repo_dir/ghostty/config" ]; then
                continue
            fi
            if [ -L "$path" ] || { [ -e "$path" ] && [ ! -f "$path" ]; }; then
                fail "Review and move this existing path before terminal setup: $path"
            fi
        done
        printf 'Run pinned terminal-setup? It can replace .zshrc and Ghostty config after backing them up [y/N] '
        read -r answer || fail 'Terminal setup needs an interactive confirmation.'
        case "$answer" in y|Y|yes|YES) ;; *) fail 'Terminal setup skipped.' ;; esac

        checkout="$(mktemp -d)"
        trap '/bin/rm -rf -- "$checkout"' EXIT
        git -C "$checkout" init --quiet
        git -C "$checkout" fetch --no-tags --depth=1 "$terminal_url" "$terminal_ref"
        git -C "$checkout" checkout --quiet --detach "$terminal_ref"

        mkdir -p "$state_dir"
        backup="$(mktemp -d "$state_dir/terminal-backup.XXXXXX")"
        if [ -f "$HOME/.zshrc" ]; then cp -p "$HOME/.zshrc" "$backup/zshrc"; fi
        if [ -f "$ghostty_config" ]; then cp -p "$ghostty_config" "$backup/ghostty.config.ghostty"; fi
        printf 'Original terminal files backed up under %s\n' "$backup"

        # Let the fork write a separate file instead of following our link.
        if [ -L "$ghostty_config" ]; then
            mv "$ghostty_config" "$backup/ghostty.link"
            trap '
                if [ ! -L "$ghostty_config" ]; then
                    if [ -f "$ghostty_config" ]; then
                        mv "$ghostty_config" "$backup/terminal-setup.partial.config.ghostty"
                    fi
                    mv -n "$backup/ghostty.link" "$ghostty_config"
                fi
                /bin/rm -rf -- "$checkout"
            ' EXIT
        fi
        (cd "$checkout" && /bin/bash ./setup.sh --zsh)
        [ -d /Applications/Ghostty.app ] || [ -d "$HOME/Applications/Ghostty.app" ] || fail 'Ghostty.app was not installed.'
        [ -f "$HOME/.zshrc" ] || fail 'terminal-setup did not create .zshrc.'
        [ -f "$repo_dir/ghostty/config" ] || fail 'Missing personal Ghostty config.'
        if [ -e "$ghostty_config" ]; then mv "$ghostty_config" "$backup/terminal-setup.config.ghostty"; fi
        mkdir -p "$(dirname "$ghostty_config")"
        ln -s "$repo_dir/ghostty/config" "$ghostty_config"
        printf '%s\n' "$terminal_ref" > "$terminal_stamp"
    fi

    if ! fnm exec --using=default node --version >/dev/null 2>&1; then
        fnm install --lts
        fnm default lts-latest
    fi
)

if [ "$stage" = all ] || [ "$stage" = brew ]; then
    brew bundle install --no-upgrade --file "$repo_dir/Brewfile"
fi
if [ "$stage" = all ] || [ "$stage" = terminal ]; then
    command -v fnm >/dev/null 2>&1 || fail 'Run ./bootstrap.sh --only brew to install fnm first.'
    install_terminal
fi
if [ "$stage" = all ] || [ "$stage" = agents ]; then
    "$repo_dir/install-instructions.sh"
fi
printf 'Run %s/doctor.sh from a fresh terminal.\n' "$repo_dir"
