#!/bin/bash
set -euo pipefail

repo_dir="$(cd -- "$(/usr/bin/dirname "$0")" && pwd)"
codex_dir="${CODEX_HOME:-$HOME/.codex}"
agy_dir="$HOME/.gemini"
failed=0

pass() { printf 'OK    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failed=1; }
check_link() {
    local target="$1" link="$2"
    if [ -L "$link" ] && [ -e "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
        pass "$link"
    else
        fail "$link should link to $target"
    fi
}

for tool in brew git gh php composer fnm node npm uv bat eza fd rg lazygit zoxide starship; do
    if path="$(command -v "$tool")"; then pass "$tool ($path)"; else fail "$tool is unavailable on PATH"; fi
done
for tool in php composer node uv; do
    if command -v "$tool" >/dev/null 2>&1 && ! "$tool" --version >/dev/null 2>&1; then
        fail "$tool --version failed"
    fi
done
if command -v fnm >/dev/null 2>&1; then
    if fnm exec --using=default node --version >/dev/null 2>&1; then
        pass 'fnm default Node is runnable'
    else
        fail 'fnm has no runnable default Node'
    fi
fi
if [ -d /Applications/Ghostty.app ] || [ -d "$HOME/Applications/Ghostty.app" ]; then
    pass 'Ghostty.app'
else
    fail 'Ghostty.app not found'
fi
check_link "$repo_dir/ghostty/config" "$HOME/Library/Application Support/com.mitchellh.ghostty/config.ghostty"
check_link "$repo_dir/codex-global-AGENTS.md" "$codex_dir/AGENTS.md"
check_link "$repo_dir/agy-global-AGENTS.md" "$agy_dir/AGENTS.md"
check_link "$repo_dir/global-AGENTS.md" "$HOME/.claude/CLAUDE.md"
check_link "$repo_dir/claude/commands/commit.md" "$HOME/.claude/commands/commit.md"
for skill in session-docs general-code-review; do
    check_link "$repo_dir/skills/$skill" "$HOME/.agents/skills/$skill"
    check_link "$repo_dir/skills/$skill" "$agy_dir/config/skills/$skill"
done
if [ -L "$codex_dir/agents" ] || [ ! -d "$codex_dir/agents" ]; then
    fail "$codex_dir/agents should be a regular directory"
else
    for role in "$repo_dir"/codex/agents/*.toml; do
        destination="$codex_dir/agents/${role##*/}"
        if [ -f "$destination" ] && [ ! -L "$destination" ] && cmp -s "$role" "$destination"; then
            pass "$destination"
        else
            fail "$destination should be a regular file matching $role"
        fi
    done
fi
if [ ! -d /path/to/workspace/Code ]; then
    printf '%s\n' 'NOTE  /path/to/workspace/Code is unavailable. Mount the workspace for personal instructions and session paths.'
fi
exit "$failed"
