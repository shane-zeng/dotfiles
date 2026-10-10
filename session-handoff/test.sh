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
for agent in codex claude; do
    event "$agent" session-one SessionStart startup > "$FIXTURE/ignored.json"
    [[ ! -s "$FIXTURE/ignored.json" ]]
    event "$agent" session-one PostCompact compact > "$FIXTURE/ignored.json"
    [[ ! -s "$FIXTURE/ignored.json" ]]
done
[[ ! -d "$HANDOFF_DEST" ]]
for agent in codex claude; do
    event "$agent" session-one SessionStart compact > "$FIXTURE/$agent.json"
    "$JQ" -e '.hookSpecificOutput.hookEventName == "SessionStart" and
      (.hookSpecificOutput.additionalContext | contains("完成與驗證") and contains("停手") and contains("不呼叫其他模型")) and
      (has("systemMessage")|not)' "$FIXTURE/$agent.json" >/dev/null
done
[[ -z $(ls -A "$HANDOFF_DEST") ]]
FILE=$("$JQ" -r '.hookSpecificOutput.additionalContext | split("\n") | .[1] | sub("^交接檔案（JSON 字串）：";"") | fromjson' "$FIXTURE/codex.json")
OLD_FILE="${FILE%/*}/2000-01-01-${FILE##*/????-??-??-}"
printf 'existing concise summary\n' > "$OLD_FILE"
event codex session-one SessionStart compact > "$FIXTURE/repeated.json"
"$JQ" -e --arg path "$OLD_FILE" '.hookSpecificOutput.additionalContext | contains($path)' "$FIXTURE/repeated.json" >/dev/null
[[ $(/bin/cat "$OLD_FILE") == 'existing concise summary' ]]
event codex session-two SessionStart compact > "$FIXTURE/other.json"
[[ $("$JQ" -r '.hookSpecificOutput.additionalContext' "$FIXTURE/repeated.json") != $("$JQ" -r '.hookSpecificOutput.additionalContext' "$FIXTURE/other.json") ]]
event claude session-one SessionStart compact > "$FIXTURE/claude-again.json"
[[ $("$JQ" -r '.hookSpecificOutput.additionalContext' "$FIXTURE/repeated.json") != $("$JQ" -r '.hookSpecificOutput.additionalContext' "$FIXTURE/claude-again.json") ]]
if printf 'not JSON' | AGENT_SOURCE=codex /bin/bash "$PACKAGE/session-handoff.sh" >/dev/null 2>&1; then exit 1; fi
if printf '{"hook_event_name":"SessionStart","source":"compact"}' | AGENT_SOURCE=codex /bin/bash "$PACKAGE/session-handoff.sh" >/dev/null 2>&1; then exit 1; fi
rm "$OLD_FILE"
ln -s "$FIXTURE/other.json" "$FILE"
if event codex session-one SessionStart compact >/dev/null 2>&1; then exit 1; fi
rm "$FILE"

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
      SessionStart:[{matcher:"startup",hooks:[{type:"command",command:"keep-start"}]}]}}' > "$CONFIG"
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
      .hooks.SessionStart[1].matcher == "^compact$"' "$CONFIG" >/dev/null
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
    /bin/bash -c "AGENT_SOURCE=codex HANDOFF_JQ=$QJQ /bin/bash $QSCRIPT" | "$JQ" -e '.hookSpecificOutput.hookEventName == "SessionStart"' >/dev/null

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
printf 'PASS: compact context, stable path, identity isolation, safe migration, idempotent install, installed command, invalid config\n'
