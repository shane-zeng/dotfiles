#!/bin/bash
set -euo pipefail
PACKAGE=$(cd "${BASH_SOURCE[0]%/*}" && pwd)
JQ=$(command -v jq)
FIXTURE=$(mktemp -d)
trap 'rm -rf -- "$FIXTURE"' EXIT
export HANDOFF_DEST="$FIXTURE/sessions with spaces"
export HANDOFF_JQ="$JQ"

event() {
    "$JQ" -n --arg id "$2" --arg event "$3" --arg source "$4" \
      '{session_id:$id,cwd:"/workspace/project",hook_event_name:$event,source:$source,transcript_path:"/does/not/exist"}' |
      AGENT_SOURCE="$1" /bin/bash "$PACKAGE/session-handoff.sh"
}
# Cached invocations must not emit instructions or create handoff files.
for agent in codex claude; do
    for source in startup compact; do
        event "$agent" session-one SessionStart "$source" > "$FIXTURE/ignored.json"
        [[ ! -s "$FIXTURE/ignored.json" ]]
    done
    event "$agent" session-one PostCompact compact > "$FIXTURE/ignored.json"
    [[ ! -s "$FIXTURE/ignored.json" ]]
done
[[ ! -d "$HANDOFF_DEST" ]]
mkdir -p "$HANDOFF_DEST"
printf 'existing concise summary\n' > "$HANDOFF_DEST/existing.md"
for agent in codex claude; do
    event "$agent" session-two SessionStart compact > "$FIXTURE/ignored.json"
    [[ ! -s "$FIXTURE/ignored.json" ]]
done
[[ $(/bin/cat "$HANDOFF_DEST/existing.md") == 'existing concise summary' ]]
[[ $(ls -A "$HANDOFF_DEST") == 'existing.md' ]]

# Seed a realistic old install with unrelated hooks and a prior status line.
TEST_HOME="$FIXTURE/test home's"
mkdir -p "$TEST_HOME/.codex/skills" "$TEST_HOME/.claude/skills" "$TEST_HOME/.agent-hooks/skills/session-handoff"
QJQ=$("$JQ" -nr --arg path "$JQ" '$path|@sh')
QSCRIPT=$("$JQ" -nr --arg path "$TEST_HOME/.agent-hooks/session-handoff.sh" '$path|@sh')
QSTATUS=$("$JQ" -nr --arg path "$TEST_HOME/.agent-hooks/context-status.sh" '$path|@sh')
for agent in codex claude; do
    COMMAND="AGENT_SOURCE=$agent HANDOFF_JQ=$QJQ /bin/bash $QSCRIPT"
    CONFIG="$TEST_HOME/.codex/hooks.json"
    [[ "$agent" == codex ]] || CONFIG="$TEST_HOME/.claude/settings.json"
    "$JQ" -n --arg cmd "$COMMAND" '{custom:true,hooks:{
      PreCompact:[{hooks:[{type:"command",command:"keep-pre"},{type:"command",command:$cmd}]}],
      PostCompact:[{hooks:[{type:"command",command:$cmd}]}],
      SessionStart:[{matcher:"startup",hooks:[{type:"command",command:"keep-start"}]},
        {matcher:"^compact$",hooks:[{type:"command",command:"keep-compact"},{type:"command",command:$cmd}]}]}}' > "$CONFIG"
    ln -s "$TEST_HOME/.agent-hooks/skills/session-handoff" "$TEST_HOME/.$agent/skills/session-handoff"
done
"$JQ" --arg cmd "HANDOFF_JQ=$QJQ /bin/bash $QSTATUS" '.statusLine={type:"command",command:$cmd}' "$TEST_HOME/.claude/settings.json" > "$FIXTURE/status.json"
mv "$FIXTURE/status.json" "$TEST_HOME/.claude/settings.json"
printf '{"type":"command","command":"keep-status","padding":2}\n' > "$TEST_HOME/.agent-hooks/statusline.previous.json"
printf 'legacy context script\n' > "$TEST_HOME/.agent-hooks/context-status.sh"
printf 'legacy skill\n' > "$TEST_HOME/.agent-hooks/skills/session-handoff/SKILL.md"
printf 'unchanged trust settings\n' > "$TEST_HOME/.codex/config.toml"
HANDOFF_INSTALL_HOME="$TEST_HOME" /bin/bash "$PACKAGE/install.sh" >/dev/null
for agent in codex claude; do
    CONFIG="$TEST_HOME/.codex/hooks.json"
    [[ "$agent" == codex ]] || CONFIG="$TEST_HOME/.claude/settings.json"
    "$JQ" -e '.custom == true and .hooks.PreCompact[0].hooks[0].command == "keep-pre" and
      (.hooks.PreCompact[0].hooks|length == 1) and (has("PostCompact")|not) and
      (.hooks|has("PostCompact")|not) and (.hooks.SessionStart|length == 2) and
      .hooks.SessionStart[1].matcher == "^compact$" and
      .hooks.SessionStart[1].hooks == [{type:"command",command:"keep-compact"}]' "$CONFIG" >/dev/null
    [[ ! -e "$TEST_HOME/.$agent/skills/session-handoff" && ! -L "$TEST_HOME/.$agent/skills/session-handoff" ]]
done
"$JQ" -e '.statusLine.command == "keep-status" and .statusLine.padding == 2' "$TEST_HOME/.claude/settings.json" >/dev/null
[[ ! -e "$TEST_HOME/.agent-hooks/context-status.sh" && ! -e "$TEST_HOME/.agent-hooks/skills/session-handoff" ]]
[[ $(/bin/cat "$TEST_HOME/.codex/config.toml") == 'unchanged trust settings' ]]
cp "$TEST_HOME/.codex/hooks.json" "$FIXTURE/codex-first.json"
cp "$TEST_HOME/.claude/settings.json" "$FIXTURE/claude-first.json"
HANDOFF_INSTALL_HOME="$TEST_HOME" /bin/bash "$PACKAGE/install.sh" >/dev/null
cmp "$TEST_HOME/.codex/hooks.json" "$FIXTURE/codex-first.json"
cmp "$TEST_HOME/.claude/settings.json" "$FIXTURE/claude-first.json"
cmp "$PACKAGE/session-handoff.sh" "$TEST_HOME/.agent-hooks/session-handoff.sh"
printf '{"hook_event_name":"SessionStart","source":"compact","session_id":"installed","cwd":"/workspace/project"}' |
    /bin/bash -c "AGENT_SOURCE=codex HANDOFF_JQ=$QJQ /bin/bash $QSCRIPT" > "$FIXTURE/installed-output.json"
[[ ! -s "$FIXTURE/installed-output.json" ]]

# Invalid config must fail before replacing the script or either settings file.
printf 'invalid JSON' > "$TEST_HOME/.claude/settings.json"
cp "$TEST_HOME/.agent-hooks/session-handoff.sh" "$FIXTURE/script-before.sh"
if HANDOFF_INSTALL_HOME="$TEST_HOME" /bin/bash "$PACKAGE/install.sh" >/dev/null 2>&1; then exit 1; fi
cmp "$TEST_HOME/.agent-hooks/session-handoff.sh" "$FIXTURE/script-before.sh"
cmp "$TEST_HOME/.codex/hooks.json" "$FIXTURE/codex-first.json"

# Personal status lines and unrelated skill directories must survive a fresh install.
FRESH_HOME="$FIXTURE/fresh"
mkdir -p "$FRESH_HOME/.claude/skills/session-handoff" "$FRESH_HOME/.agent-hooks"
printf '{"statusLine":{"type":"command","command":"personal-status"},"permissions":{"allow":["Read"]}}\n' > "$FRESH_HOME/.claude/settings.json"
printf 'personal skill\n' > "$FRESH_HOME/.claude/skills/session-handoff/SKILL.md"
printf 'personal context script\n' > "$FRESH_HOME/.agent-hooks/context-status.sh"
HANDOFF_INSTALL_HOME="$FRESH_HOME" /bin/bash "$PACKAGE/install.sh" >/dev/null
"$JQ" -e '.statusLine.command == "personal-status" and .permissions.allow == ["Read"]' "$FRESH_HOME/.claude/settings.json" >/dev/null
[[ $(/bin/cat "$FRESH_HOME/.claude/skills/session-handoff/SKILL.md") == 'personal skill' ]]
[[ $(/bin/cat "$FRESH_HOME/.agent-hooks/context-status.sh") == 'personal context script' ]]
printf 'PASS: inert cached hook, preserved summaries, removal of handoff hooks, unrelated hooks, safe migration, idempotent disable, invalid config\n'
