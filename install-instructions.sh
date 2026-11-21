#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(/usr/bin/dirname "$0")" && pwd)"

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

failed=0
check_link "$repo_dir/codex-global-AGENTS.md" "$HOME/.codex/AGENTS.md" || failed=1
check_link "$repo_dir/global-AGENTS.md" "$HOME/.claude/CLAUDE.md" || failed=1
check_link "$repo_dir/claude/commands/commit.md" "$HOME/.claude/commands/commit.md" || failed=1
check_link "$repo_dir/skills/session-docs" "$HOME/.agents/skills/session-docs" || failed=1
check_link "$repo_dir/skills/general-code-review" "$HOME/.agents/skills/general-code-review" || failed=1

if [ "$failed" -ne 0 ]; then
    printf 'Resolve the listed conflicts, then rerun this script.\n' >&2
    exit 1
fi

link_path "$repo_dir/codex-global-AGENTS.md" "$HOME/.codex/AGENTS.md"
link_path "$repo_dir/global-AGENTS.md" "$HOME/.claude/CLAUDE.md"
link_path "$repo_dir/claude/commands/commit.md" "$HOME/.claude/commands/commit.md"
link_path "$repo_dir/skills/session-docs" "$HOME/.agents/skills/session-docs"
link_path "$repo_dir/skills/general-code-review" "$HOME/.agents/skills/general-code-review"
