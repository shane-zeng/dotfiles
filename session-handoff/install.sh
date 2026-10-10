#!/bin/bash
# Install the shared compact hook and remove only this package's previous extras.
set -euo pipefail
umask 077
PACKAGE_DIR=$(cd "${BASH_SOURCE[0]%/*}" && pwd)
INSTALL_HOME=${HANDOFF_INSTALL_HOME:-$HOME}
JQ=$(command -v jq || true)
[[ -x "$JQ" ]] || { echo 'jq is required; nothing was installed.' >&2; exit 1; }
HOOK_DIR=$INSTALL_HOME/.agent-hooks
CODEX_DIR=$INSTALL_HOME/.codex
CLAUDE_DIR=$INSTALL_HOME/.claude
for target in "$HOOK_DIR" "$HOOK_DIR/backups" "$HOOK_DIR/skills" "$CODEX_DIR" "$CLAUDE_DIR"; do
    [[ ! -L "$target" ]] || { echo "Refusing a symlinked config directory: $target" >&2; exit 1; }
done
[[ ! -L "$HOOK_DIR/session-handoff.sh" ]] || { echo 'Refusing a symlinked hook script.' >&2; exit 1; }
mkdir -p "$HOOK_DIR" "$CODEX_DIR" "$CLAUDE_DIR"
BUILD=$(mktemp -d "$HOOK_DIR/.install.XXXXXX")
trap 'rm -rf -- "$BUILD"' EXIT
CODEX_CONFIG=$CODEX_DIR/hooks.json
CLAUDE_CONFIG=$CLAUDE_DIR/settings.json
QJQ=$("$JQ" -nr --arg path "$JQ" '$path|@sh')
QSCRIPT=$("$JQ" -nr --arg path "$HOOK_DIR/session-handoff.sh" '$path|@sh')
QSTATUS=$("$JQ" -nr --arg path "$HOOK_DIR/context-status.sh" '$path|@sh')
for agent in codex claude; do
    CONFIG=$CODEX_CONFIG
    [[ "$agent" == codex ]] || CONFIG=$CLAUDE_CONFIG
    [[ ! -L "$CONFIG" ]] || { echo "Refusing a symlinked settings file: $CONFIG" >&2; exit 1; }
    if [[ -f "$CONFIG" ]]; then cp -p "$CONFIG" "$BUILD/$agent.before.json"; else printf '{}\n' > "$BUILD/$agent.before.json"; fi
    "$JQ" -e 'type == "object" and ((.hooks // {})|type == "object")' "$BUILD/$agent.before.json" >/dev/null
    COMMAND="AGENT_SOURCE=$agent HANDOFF_JQ=$QJQ /bin/bash $QSCRIPT"
    "$JQ" --arg cmd "$COMMAND" '
      .hooks = ((.hooks // {}) | with_entries(
        .value |= (map(.hooks |= map(select(.command != $cmd))) | map(select(.hooks|length > 0)))
        | select(.value|length > 0))) |
      .hooks.SessionStart = ((.hooks.SessionStart // []) +
        [{matcher:"^compact$",hooks:[{type:"command",command:$cmd,timeout:10}]}])
    ' "$BUILD/$agent.before.json" > "$BUILD/$agent.after.json"
done
STATUS_COMMAND="HANDOFF_JQ=$QJQ /bin/bash $QSTATUS"
REMOVE_STATUS=0
if [[ $("$JQ" -r '.statusLine.command // ""' "$BUILD/claude.before.json") == "$STATUS_COMMAND" ]]; then
    REMOVE_STATUS=1
    if [[ -f "$HOOK_DIR/statusline.previous.json" ]]; then
        "$JQ" -e 'type == "object" and .type == "command" and (.command|type == "string")' "$HOOK_DIR/statusline.previous.json" >/dev/null
        "$JQ" --slurpfile previous "$HOOK_DIR/statusline.previous.json" '.statusLine = $previous[0]' "$BUILD/claude.after.json" > "$BUILD/claude.final.json"
    else
        "$JQ" 'del(.statusLine)' "$BUILD/claude.after.json" > "$BUILD/claude.final.json"
    fi
    mv "$BUILD/claude.final.json" "$BUILD/claude.after.json"
fi
for agent in codex claude; do "$JQ" -e . "$BUILD/$agent.after.json" >/dev/null; done
BACKUP=$HOOK_DIR/backups/$(TZ=Asia/Taipei date +%Y-%m-%d-%H%M%S)-$$
mkdir -p "$BACKUP"
# Keep current configs and obsolete files recoverable; never change hook trust.
for agent in codex claude; do
    CONFIG=$CODEX_CONFIG
    [[ "$agent" == codex ]] || CONFIG=$CLAUDE_CONFIG
    if [[ -f "$CONFIG" ]] && cmp -s "$CONFIG" "$BUILD/$agent.after.json"; then continue; fi
    if [[ -f "$CONFIG" ]]; then cp -p "$CONFIG" "$BACKUP/$agent.config.json"; else printf '%s\n' "$CONFIG" > "$BACKUP/$agent.config.absent"; fi
    TEMP=$(mktemp "${CONFIG%/*}/.handoff-config.XXXXXX")
    cp "$BUILD/$agent.after.json" "$TEMP"
    chmod 600 "$TEMP"
    mv -f "$TEMP" "$CONFIG"
done
if [[ ! -f "$HOOK_DIR/session-handoff.sh" ]] || ! cmp -s "$PACKAGE_DIR/session-handoff.sh" "$HOOK_DIR/session-handoff.sh"; then
    if [[ -e "$HOOK_DIR/session-handoff.sh" ]]; then cp -p "$HOOK_DIR/session-handoff.sh" "$BACKUP/session-handoff.sh"; fi
    TEMP=$(mktemp "$HOOK_DIR/.handoff-script.XXXXXX")
    install -m 700 "$PACKAGE_DIR/session-handoff.sh" "$TEMP"
    mv -f "$TEMP" "$HOOK_DIR/session-handoff.sh"
fi
REMOVE_SKILL=0
for link in "$CODEX_DIR/skills/session-handoff" "$CLAUDE_DIR/skills/session-handoff"; do
    if [[ -L "$link" && $(readlink "$link") == "$HOOK_DIR/skills/session-handoff" ]]; then
        REMOVE_SKILL=1
        rm -- "$link"
    fi
done
if [[ "$REMOVE_SKILL" == 1 && -d "$HOOK_DIR/skills/session-handoff" && ! -L "$HOOK_DIR/skills/session-handoff" ]]; then
    mv "$HOOK_DIR/skills/session-handoff" "$BACKUP/session-handoff-skill"
fi
if [[ "$REMOVE_STATUS" == 1 ]]; then
    for obsolete in context-status.sh statusline.previous.json; do
        if [[ -f "$HOOK_DIR/$obsolete" && ! -L "$HOOK_DIR/$obsolete" ]]; then mv "$HOOK_DIR/$obsolete" "$BACKUP/$obsolete"; fi
    done
fi
rmdir "$BACKUP" 2>/dev/null || true
printf 'Installed: %s\nConfigured: SessionStart(compact), Codex and Claude\nBackup (if changes): %s\n' "$HOOK_DIR/session-handoff.sh" "$BACKUP"
