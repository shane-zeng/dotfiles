#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(/usr/bin/dirname "$0")" && pwd)"
codex_dir="${CODEX_HOME:-$HOME/.codex}"
agy_dir="$HOME/.gemini"

check_link() {
    local source_path="$1"
    local destination="$2"

    if [ ! -e "$source_path" ] && [ ! -L "$source_path" ]; then
        printf 'Missing source path: %s\n' "$source_path" >&2
        return 1
    fi

    if [ -L "$destination" ]; then
        local current_target
        current_target="$(/usr/bin/readlink "$destination")"
        if [ "$current_target" != "$source_path" ]; then
            printf 'Conflicting symlink: %s -> %s\n' "$destination" "$current_target" >&2
            return 1
        fi
    elif [ -e "$destination" ]; then
        printf 'Existing path needs review before linking: %s\n' "$destination" >&2
        return 1
    fi
    return 0
}

link_path() {
    local source_path="$1"
    local destination="$2"

    if [ -L "$destination" ]; then
        printf 'Already linked: %s\n' "$destination"
        return
    fi

    /bin/mkdir -p "$(/usr/bin/dirname "$destination")"
    /bin/ln -s "$source_path" "$destination"
    printf 'Linked: %s\n' "$destination"
}

check_role() {
    local source_path="$1" destination="$2"
    if [ ! -f "$source_path" ]; then
        printf 'Missing Codex role: %s\n' "$source_path" >&2
        return 1
    fi
    if [ ! -L "$destination" ]; then
        if [ ! -e "$destination" ] || { [ -f "$destination" ] && cmp -s "$source_path" "$destination"; }; then
            return 0
        fi
    fi
    printf 'Existing Codex role needs review before installing: %s\n' "$destination" >&2
    return 1
}

failed=0
check_link "$repo_dir/codex-global-AGENTS.md" "$codex_dir/AGENTS.md" || failed=1
check_link "$repo_dir/agy-global-AGENTS.md" "$agy_dir/AGENTS.md" || failed=1
check_link "$repo_dir/global-AGENTS.md" "$HOME/.claude/CLAUDE.md" || failed=1
check_link "$repo_dir/claude/commands/commit.md" "$HOME/.claude/commands/commit.md" || failed=1
for skill in session-docs general-code-review; do
    check_link "$repo_dir/skills/$skill" "$HOME/.agents/skills/$skill" || failed=1
    check_link "$repo_dir/skills/$skill" "$agy_dir/config/skills/$skill" || failed=1
done

# Install into a local directory and leave symlinked directories for manual review.
if [ -L "$codex_dir/agents" ] || { [ -e "$codex_dir/agents" ] && [ ! -d "$codex_dir/agents" ]; }; then
    printf 'Codex roles need a regular directory: %s\n' "$codex_dir/agents" >&2
    failed=1
else
    for role in "$repo_dir"/codex/agents/*.toml; do
        check_role "$role" "$codex_dir/agents/${role##*/}" || failed=1
    done
fi

if [ "$failed" -ne 0 ]; then
    printf 'Resolve the listed conflicts, then rerun this script.\n' >&2
    exit 1
fi

link_path "$repo_dir/codex-global-AGENTS.md" "$codex_dir/AGENTS.md"
link_path "$repo_dir/agy-global-AGENTS.md" "$agy_dir/AGENTS.md"
link_path "$repo_dir/global-AGENTS.md" "$HOME/.claude/CLAUDE.md"
link_path "$repo_dir/claude/commands/commit.md" "$HOME/.claude/commands/commit.md"
for skill in session-docs general-code-review; do
    link_path "$repo_dir/skills/$skill" "$HOME/.agents/skills/$skill"
    link_path "$repo_dir/skills/$skill" "$agy_dir/config/skills/$skill"
done

/bin/mkdir -p "$codex_dir/agents"
for role in "$repo_dir"/codex/agents/*.toml; do
    destination="$codex_dir/agents/${role##*/}"
    if [ -f "$destination" ]; then
        check_role "$role" "$destination"
        printf 'Already installed: %s\n' "$destination"
    else
        /bin/cp -n "$role" "$destination"
        check_role "$role" "$destination"
        printf 'Installed: %s\n' "$destination"
    fi
done
