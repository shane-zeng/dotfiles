#!/usr/bin/env python3
"""Summarize which model and reasoning effort were used in Claude Code, Codex and AgY sessions.

Reads native transcripts without modifying them:
  Claude Code: ~/.claude/projects/*/<session>.jsonl and */<session>/subagents/agent-*.jsonl
  Codex:       ~/.codex/sessions and ~/.codex/archived_sessions (rollout-*.jsonl, and .jsonl.zst
               when the `zstd` command is installed)
  AgY:         ~/.gemini/antigravity/conversations/*.db (SQLite with protobuf blobs; model and
               effort only, token counts are not decoded because the schema is undocumented)

Standard library only (Python 3.9+).

  uv run --no-project model_usage.py                 # summary by tool / model / effort
  uv run --no-project model_usage.py sessions        # one row per session
  uv run --no-project model_usage.py roles           # subagent sessions by role / model / effort
  uv run --no-project model_usage.py --json sessions # machine-readable
  uv run --no-project model_usage.py save            # merge into the local usage history

  uv run --no-project model_usage.py meta --apply DOC.md
                                                     # write 模型 / 推理強度 bullets into a session document

Reports (summary, sessions, --json) merge that JSONL with the live transcripts, so sessions whose
transcript was purged still show up; `--live-only` turns this off.

Units differ by tool: Claude counts assistant API responses ("calls", de-duplicated by
message id); Codex counts turns (one `turn_context` event per turn); AgY counts generations
(one `gen_metadata` row per model request).
Token columns are comparable for Claude and Codex: out = all output tokens, think = the
reasoning/thinking part. AgY rows store null and show "-".
"""
import argparse
import fcntl
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HOME = os.path.expanduser("~")
DEFAULT_OUT = os.environ.get("MODEL_USAGE_OUT") or os.path.join(
    HOME, ".local", "state", "session-docs", "model-usage.jsonl"
)


def new_combo():
    return {"n": 0, "out": 0, "think": 0}


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:  # odd fractional-second widths on older Python
            return datetime.fromisoformat(value.split(".")[0].replace("Z", "") + "+00:00")
        except ValueError:
            return None


def open_lines(path):
    """Text lines of a file; `.zst` files (Codex compresses archived sessions) go through the zstd CLI.

    The caller checks that `zstd` exists first. A corrupt archive reads as empty.
    """
    if not path.endswith(".zst"):
        return open(path, encoding="utf-8", errors="replace")
    try:
        proc = subprocess.run(["zstd", "-dc", "-q", path], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        return iter(())
    return iter(proc.stdout.decode("utf-8", "replace").splitlines())


def iter_json(path):
    """Yield parsed JSON lines; skip unreadable lines instead of failing the whole scan."""
    lines = open_lines(path)
    try:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue
    finally:
        if hasattr(lines, "close"):
            lines.close()


def finish(rec, stamps):
    stamps = [s for s in stamps if s]
    rec["started"] = min(stamps) if stamps else None
    rec["ended"] = max(stamps) if stamps else None
    return rec


# ---------------------------------------------------------------- Claude Code

def scan_claude(root):
    files = glob.glob(os.path.join(root, "*", "*.jsonl")) + glob.glob(
        os.path.join(root, "*", "*", "subagents", "agent-*.jsonl")
    )
    for path in sorted(files):
        is_sub = os.sep + "subagents" + os.sep in path
        calls = {}  # message id -> (combo key, output tokens, thinking tokens); last/largest wins
        stamps, cwd, title, sid, advisors = [], "", "", "", set()
        for d in iter_json(path):
            kind = d.get("type")
            if d.get("sessionId") and not sid:
                sid = d["sessionId"]
            if kind == "custom-title":
                title = d.get("customTitle") or title
            elif kind == "agent-name" and not title:
                title = d.get("agentName") or ""
            if kind != "assistant":
                continue
            msg = d.get("message") or {}
            model = msg.get("model")
            if not model or model.startswith("<"):  # "<synthetic>" placeholders
                continue
            stamps.append(parse_ts(d.get("timestamp")))
            cwd = cwd or d.get("cwd", "")
            if d.get("advisorModel"):
                advisors.add(d["advisorModel"])
            usage = msg.get("usage") or {}
            out = usage.get("output_tokens") or 0
            think = (usage.get("output_tokens_details") or {}).get("thinking_tokens") or 0
            effort = d.get("perTurnEffort") or d.get("effort") or "unknown"
            mid = msg.get("id") or d.get("uuid")
            # one API response is written as several records; keep the one with final usage
            if mid not in calls or out >= calls[mid][1]:
                calls[mid] = (f"{model}/{effort}", out, think)
        if not calls:
            continue
        combos = defaultdict(new_combo)
        for key, out, think in calls.values():
            c = combos[key]
            c["n"] += 1
            c["out"] += out
            c["think"] += think
        sid = sid or os.path.basename(path)
        role = ""
        if is_sub:  # the role (agentType, e.g. "general-purpose", "Explore") sits in a sidecar file
            try:
                with open(path[:-len(".jsonl")] + ".meta.json", encoding="utf-8") as fh:
                    role = json.load(fh).get("agentType") or ""
            except (OSError, ValueError):
                pass
        yield finish({
            "tool": "claude",
            "kind": "subagent" if is_sub else "main",
            "role": role,
            # The recorded sessionId is not unique per file (resumed/forked sessions and subagents
            # reuse it), so key on the file name instead; subagent files sit under their parent id.
            "key": os.path.relpath(path, root)[:-6].replace(os.sep + "subagents" + os.sep, "/"),
            "session_id": sid,
            "file": path,
            "cwd": cwd,
            "title": title or ("(subagent)" if is_sub else ""),
            "advisors": sorted(advisors),
            "combos": dict(combos),
        }, stamps)


# ---------------------------------------------------------------------- Codex

def codex_titles(codex_home):
    titles = {}
    index = os.path.join(codex_home, "session_index.jsonl")
    if os.path.exists(index):
        for d in iter_json(index):
            if d.get("id"):
                titles[d["id"]] = d.get("thread_name") or ""
    return titles


def scan_codex(codex_home):
    titles = codex_titles(codex_home)
    files = []
    for sub in ("sessions", "archived_sessions"):
        for pattern in ("rollout-*.jsonl", "rollout-*.jsonl.zst"):
            files += glob.glob(os.path.join(codex_home, sub, "**", pattern), recursive=True)
    skipped_zst = 0
    for path in sorted(files):
        if path.endswith(".zst") and not shutil.which("zstd"):
            skipped_zst += 1
            continue
        meta, stamps = {}, []
        combos = defaultdict(new_combo)
        current = None  # combo key of the latest turn, to attribute token deltas
        settings_key = None  # fallback when a session has settings but no recorded turn
        prev_out = prev_think = 0
        for d in iter_json(path):
            kind = d.get("type")
            p = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            stamps.append(parse_ts(d.get("timestamp")))
            if kind == "session_meta":
                meta = p
            elif kind == "turn_context":
                effort = p.get("effort") or ((p.get("collaboration_mode") or {}).get("settings") or {}).get(
                    "reasoning_effort") or "unknown"
                current = f"{p.get('model', 'unknown')}/{effort}"
                combos[current]["n"] += 1
            elif kind == "event_msg" and p.get("type") == "thread_settings_applied":
                ts = p.get("thread_settings") or {}
                settings_key = f"{ts.get('model', 'unknown')}/{ts.get('reasoning_effort') or 'unknown'}"
            elif kind == "event_msg" and p.get("type") == "token_count" and p.get("info"):
                total = p["info"].get("total_token_usage") or {}
                out, think = total.get("output_tokens") or 0, total.get("reasoning_output_tokens") or 0
                key = current or settings_key
                if key:
                    combos[key]["out"] += max(out - prev_out, 0)
                    combos[key]["think"] += max(think - prev_think, 0)
                prev_out, prev_think = out, think
        if not combos and settings_key:
            combos[settings_key]  # settings only: show the session, zero turns
        if not combos:
            continue
        source = meta.get("source")
        spawned = source.get("subagent") if isinstance(source, dict) else None
        # The automatic permission reviewer is not a development session. Newer rollouts say so in
        # thread_source; older ones only in source.subagent.other (thread_source is then "subagent").
        if meta.get("thread_source") == "guardian_review" or (
                isinstance(spawned, dict) and spawned.get("other") == "guardian"):
            kind = "guardian"
        elif meta.get("parent_thread_id") or spawned:
            kind = "subagent"
        else:
            kind = "main"
        sid = meta.get("id") or os.path.basename(path)
        # A spawned agent's role can be in session metadata or the rollout's thread_spawn record.
        spawn = spawned.get("thread_spawn") if isinstance(spawned, dict) else None
        role = meta.get("agent_role") or (spawn.get("agent_role") if isinstance(spawn, dict) else "") or ""
        yield finish({
            "tool": "codex",
            "kind": kind,
            "role": role if kind == "subagent" else "",
            "key": sid,
            "session_id": sid,
            "file": path,
            "cwd": meta.get("cwd", ""),
            "title": titles.get(sid, ""),
            "advisors": [],
            "combos": dict(combos),
        }, stamps)
    if skipped_zst:
        print(f"warning: skipped {skipped_zst} compressed Codex sessions (.zst); install zstd to include them",
              file=sys.stderr)


# ------------------------------------------------------------------------ AgY

def _varint(b, i):
    result = shift = 0
    while True:
        x = b[i]  # IndexError on truncated data is handled by the caller
        i += 1
        result |= (x & 0x7F) << shift
        shift += 7
        if x < 0x80:
            return result, i


def pb_fields(b):
    """One level of a protobuf message as (field number, wire type, value); [] if it does not parse.

    No schema is available, so field numbers were found by inspecting real AgY data:
      gen_metadata.data    1 -> {19: model id, 21: display name such as "Gemini 4 Hydrogen (Medium)"}
      steps.metadata       1 -> {1: unix seconds}
      trajectory_metadata  somewhere inside: a "file://<workspace>" string
    """
    out, i = [], 0
    try:
        while i < len(b):
            key, i = _varint(b, i)
            field, wire = key >> 3, key & 7
            if wire == 0:
                value, i = _varint(b, i)
            elif wire == 2:
                n, i = _varint(b, i)
                value = b[i:i + n]
                if len(value) < n:
                    return []
                i += n
            elif wire == 1:
                value, i = b[i:i + 8], i + 8
            elif wire == 5:
                value, i = b[i:i + 4], i + 4
            else:
                return []
            out.append((field, wire, value))
    except IndexError:
        return []
    return out


def pb_get(fields, number, wire):
    return next((v for f, w, v in fields if f == number and w == wire), None)


def pb_find_prefix(b, prefix, depth=0):
    """First length-delimited value starting with `prefix`, searching nested messages."""
    for _, wire, value in pb_fields(b):
        if wire != 2:
            continue
        if value.startswith(prefix):
            return value.decode("utf-8", "replace")
        found = depth < 4 and pb_find_prefix(value, prefix, depth + 1)
        if found:
            return found
    return None


def agy_first_prompts(agy_cli_dir):
    """conversationId -> first typed prompt, from the CLI history file (used as a title)."""
    prompts = {}
    path = os.path.join(agy_cli_dir, "history.jsonl")
    if os.path.exists(path):
        for d in iter_json(path):
            cid = d.get("conversationId")
            if cid and d.get("type") != "slash_command" and cid not in prompts:
                prompts[cid] = (d.get("display") or "")[:80]
    return prompts


def scan_agy(agy_dir, agy_cli_dir):
    prompts = agy_first_prompts(agy_cli_dir)
    for path in sorted(glob.glob(os.path.join(agy_dir, "conversations", "*.db"))):
        # immutable read-only: never touch the live database or create journal files
        uri = "file:" + path + "?mode=ro&immutable=1"
        try:
            con = sqlite3.connect(uri, uri=True)
            gens = con.execute("select data from gen_metadata order by idx").fetchall()
            first = con.execute("select metadata from steps order by idx limit 1").fetchone()
            last = con.execute("select metadata from steps order by idx desc limit 1").fetchone()
            tm = con.execute("select data from trajectory_metadata_blob limit 1").fetchone()
            con.close()
        except sqlite3.Error:
            continue
        combos = defaultdict(lambda: {"n": 0, "out": None, "think": None})
        for (blob,) in gens:
            body = pb_get(pb_fields(blob or b""), 1, 2)
            fields = pb_fields(body) if body else []
            display = (pb_get(fields, 21, 2) or b"").decode("utf-8", "replace")
            model_id = (pb_get(fields, 19, 2) or b"").decode("utf-8", "replace")
            m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", display)
            model = model_id or (m.group(1) if m else display) or "unknown"
            effort = m.group(2).lower() if m else "unknown"
            # some ids carry the effort as a suffix ("claude-sonnet-5-5-medium"); keep the model name clean
            if model.endswith("-" + effort):
                model = model[: -len(effort) - 1]
            combos[f"{model}/{effort}"]["n"] += 1
        if not combos:
            continue

        def step_time(row):
            outer = pb_get(pb_fields(row[0] or b""), 1, 2) if row else None
            seconds = pb_get(pb_fields(outer), 1, 0) if outer else None
            return datetime.fromtimestamp(seconds, timezone.utc) if seconds else None

        cwd = (pb_find_prefix(tm[0], b"file://") or "")[len("file://"):] if tm and tm[0] else ""
        cid = os.path.basename(path)[:-3]
        yield {
            "tool": "agy",
            "kind": "main",
            "role": "",
            "key": cid,
            "session_id": cid,
            "file": path,
            "cwd": cwd,
            "title": prompts.get(cid, ""),
            "advisors": [],
            "combos": dict(combos),
            "started": step_time(first),
            "ended": step_time(last) or datetime.fromtimestamp(os.path.getmtime(path), timezone.utc),
        }


# ------------------------------------------------------------------- Reporting

def table(headers, rows, right=()):
    """Plain-text table; columns whose index is in `right` are right-aligned (numbers)."""
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)] if rows else [len(h) for h in headers]
    line = lambda r: "  ".join(
        str(c).rjust(w) if i in right else str(c).ljust(w) for i, (c, w) in enumerate(zip(r, widths))
    ).rstrip()
    out = [line(headers), "  ".join("-" * w for w in widths)]
    return "\n".join(out + [line(r) for r in rows])


def local_date(dt):
    return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "-"


def print_summary(sessions):
    agg = defaultdict(lambda: {"sessions": set(), "n": 0, "out": 0, "think": 0, "tokens": True})
    for s in sessions:
        for key, c in s["combos"].items():
            a = agg[(s["tool"], key)]
            a["sessions"].add(s["key"])
            a["n"] += c["n"]
            if c["out"] is None:  # tool does not expose token counts (AgY)
                a["tokens"] = False
            else:
                a["out"] += c["out"]
                a["think"] += c["think"]
    rows = []
    for (tool, key), a in sorted(agg.items(), key=lambda kv: (kv[0][0], -kv[1]["out"], -kv[1]["n"])):
        model, _, effort = key.rpartition("/")
        if a["tokens"]:
            out, think = f"{a['out']:,}", f"{a['think']:,}"
            share = f"{a['think'] * 100 // a['out']}%" if a["out"] else "-"
        else:
            out = think = share = "-"
        rows.append((tool, model, effort, len(a["sessions"]), a["n"], out, think, share))
    print(table(("tool", "model", "effort", "sessions", "calls/turns", "out", "think", "think%"), rows, right=(3, 4, 5, 6, 7)))
    print("\ncalls/turns: Claude = assistant API responses, Codex = turns, AgY = generations. "
          "A session using several model/effort pairs is counted once under each. AgY has no token data.")


def print_roles(sessions):
    """Subagent sessions grouped by role, model and effort: what each role costs and how often it runs."""
    agg = defaultdict(lambda: {"sessions": set(), "n": 0, "out": 0, "think": 0})
    for s in sessions:
        if s["kind"] != "subagent":
            continue
        for key, c in s["combos"].items():
            a = agg[(s["tool"], s.get("role") or "(unknown)", key)]
            a["sessions"].add(s["key"])
            a["n"] += c["n"]
            a["out"] += c["out"] or 0
            a["think"] += c["think"] or 0
    if not agg:
        print("no subagent sessions found")
        return
    rows = []
    for (tool, role, key), a in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1]["out"])):
        model, _, effort = key.rpartition("/")
        rows.append((tool, role, model, effort, len(a["sessions"]), a["n"], f"{a['out']:,}", f"{a['think']:,}"))
    print(table(("tool", "role", "model", "effort", "sessions", "calls/turns", "out", "think"), rows,
                right=(4, 5, 6, 7)))


def print_sessions(sessions):
    rows = []
    for s in sorted(sessions, key=lambda x: x["started"] or datetime.min.replace(tzinfo=timezone.utc)):
        combos = ", ".join(f"{k}×{c['n']}" for k, c in sorted(s["combos"].items(), key=lambda kv: -kv[1]["n"]))
        kind = f"{s['kind']}:{s['role']}" if s.get("role") else s["kind"]
        rows.append((s["tool"], kind, local_date(s["started"]), os.path.basename(s["cwd"]) or "-",
                     (s["title"] or "-")[:40], combos))
    print(table(("tool", "kind", "started", "cwd", "title", "model/effort×n"), rows))


def to_row(s):
    """JSON-safe copy of a session record (datetimes become ISO strings)."""
    row = dict(s)
    for f in ("started", "ended"):
        row[f] = row[f].isoformat() if row[f] else None
    return row


def save_rows(sessions, out):
    """Merge scanned sessions into a JSONL file, one row per session, keyed by `key`.

    Rows already in the file are kept even when their transcript is gone (Claude Code purges
    old transcripts); a rescanned session replaces its old row, so running this again is safe.
    Serialize concurrent merges and write the private history atomically.
    """
    directory = os.path.dirname(out) or "."
    os.makedirs(directory, mode=0o700, exist_ok=True)
    lock_fd = os.open(out + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = {}
        if os.path.exists(out):
            for d in iter_json(out):
                old[(d["tool"], d["key"])] = d
        added = updated = 0
        for s in sessions:
            row = to_row(s)
            k = (row["tool"], row["key"])
            if k not in old:
                added += 1
            elif old[k] != row:
                updated += 1
            old[k] = row
        rows = sorted(old.values(), key=lambda r: (r["started"] or "", r["tool"], r["key"]))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".model-usage-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            os.replace(tmp, out)
        finally:
            Path(tmp).unlink(missing_ok=True)
    print(f"{out}: {len(rows)} rows ({added} added, {updated} updated, "
          f"{len(sessions) - added - updated} unchanged, {len(rows) - len(sessions)} kept from earlier runs)")


# ------------------------------------------------------ Session document metadata

# Environment variables that identify the running session for each tool.
SESSION_ENV = {"claude": "CLAUDE_CODE_SESSION_ID", "codex": "CODEX_THREAD_ID"}
RE_META_LINE = re.compile(r"^\s*(?:[-*]|>)\s*\**[^:：*\n]{1,12}?\**\s*[:：]")
RE_OWN_META = re.compile(r"^\s*(?:[-*]|>)\s*\**(?:模型|推理強度)\**\s*[:：]")


def pick_session(sessions, session_id, tool, cwd):
    """The session a document is being written in: by id, else the latest one of `tool` in `cwd`."""
    mains = [s for s in sessions if s["kind"] == "main"]
    if session_id:
        return next((s for s in mains if session_id in (os.path.basename(s["key"]), s["session_id"])), None)
    # No id: only trust a session started in this directory; a different directory is too easy to mix up.
    local = [s for s in mains if s["tool"] == tool and s["cwd"] == cwd]
    return max(local, key=lambda s: s["ended"] or datetime.min.replace(tzinfo=timezone.utc), default=None)


def meta_lines(s):
    """`- 模型：` and `- 推理強度：` bullets for a session, most-used model/effort first."""
    combos = sorted(s["combos"].items(), key=lambda kv: -kv[1]["n"])
    pairs = [(k.rpartition("/")[0], k.rpartition("/")[2], c["n"]) for k, c in combos]
    models = list(dict.fromkeys(m for m, _, _ in pairs))
    if len(pairs) == 1:
        efforts = [pairs[0][1]]
    elif len(models) == 1:  # one model, effort changed mid-session
        efforts = [f"{e}×{n}" for _, e, n in pairs]
    else:
        efforts = [f"{m} {e}×{n}" for m, e, n in pairs]
    return [f"- 模型：{'、'.join(models)}", f"- 推理強度：{'、'.join(efforts)}"]


def apply_meta(path, new_lines):
    """Insert or replace the two bullets in a document's metadata block (the bullets under the H1).

    Returns True if the file changed. A document without a metadata block gets one right after
    the H1, so the bullets stay where session-docs looks for them.
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    h1 = next((i for i, l in enumerate(lines) if l.startswith("# ")), -1)
    start = h1 + 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and RE_META_LINE.match(lines[end]):
        end += 1
    block = [l for l in lines[start:end] if not RE_OWN_META.match(l)] + new_lines
    after = [""] if end < len(lines) and lines[end].strip() else []
    new = lines[:h1 + 1] + ([""] if h1 >= 0 else []) + block + after + lines[end:]
    if new == lines:
        return False
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(new))
    os.replace(tmp, path)
    return True


def run_meta(args, sessions):
    session_id = args.session or next(
        (os.environ[var] for tool, var in SESSION_ENV.items() if args.tool in (tool, "all") and os.environ.get(var)),
        "",
    )
    if not session_id and args.tool == "all":
        print("cannot tell which session this is: pass --session ID or --tool claude|codex|agy "
              "(then the latest session of that tool in this directory is used)", file=sys.stderr)
        return 2
    s = pick_session(sessions, session_id, args.tool, os.getcwd())
    if not s:
        print(f"no matching session for {session_id or args.tool}", file=sys.stderr)
        return 1
    print(f"session: {s['tool']} {s['key'].rsplit('/', 1)[-1]} {local_date(s['started'])} "
          f"{(s['title'] or '-')[:40]}", file=sys.stderr)
    lines = meta_lines(s)
    if args.apply:
        changed = apply_meta(args.apply, lines)
        print(f"{args.apply}: {'updated' if changed else 'unchanged'}")
    print("\n".join(lines))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", nargs="?", choices=("summary", "sessions", "roles", "save", "meta"),
                    default="summary")
    ap.add_argument("--session", help="meta: session id (default: the running session from the environment)")
    ap.add_argument("--apply", metavar="DOC.md", help="meta: write the bullets into this session document")
    ap.add_argument("--out", default=DEFAULT_OUT, help="JSONL file written by `save` and read by reports "
                    "(default: %(default)s)")
    ap.add_argument("--live-only", action="store_true", help="reports: ignore the JSONL, scan transcripts only")
    ap.add_argument("--tool", choices=("claude", "codex", "agy", "all"), default="all")
    ap.add_argument("--since", help="only sessions started on/after this local date, YYYY-MM-DD")
    ap.add_argument("--include-guardian", action="store_true", help="include Codex auto-review sessions")
    ap.add_argument("--main-only", action="store_true", help="exclude subagent sessions")
    ap.add_argument("--json", action="store_true", help="print sessions as JSON (ignores command)")
    ap.add_argument("--claude-dir", default=os.path.join(
        os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude"), "projects"
    ))
    ap.add_argument("--codex-dir", default=os.environ.get("CODEX_HOME") or os.path.join(HOME, ".codex"))
    ap.add_argument("--agy-dir", default=os.path.join(HOME, ".gemini", "antigravity"))
    ap.add_argument("--agy-cli-dir", default=os.path.join(HOME, ".gemini", "antigravity-cli"))
    args = ap.parse_args()

    sessions = []
    if args.tool in ("claude", "all") and os.path.isdir(args.claude_dir):
        sessions += scan_claude(args.claude_dir)
    if args.tool in ("codex", "all") and os.path.isdir(args.codex_dir):
        sessions += scan_codex(args.codex_dir)
    if args.tool in ("agy", "all") and os.path.isdir(args.agy_dir):
        sessions += scan_agy(args.agy_dir, args.agy_cli_dir)

    # Reports also include sessions kept in the JSONL whose transcripts are gone. `save` skips this:
    # it merges with the file itself.
    if args.command not in ("save", "meta") and not args.live_only and os.path.exists(args.out):
        live = {(s["tool"], s["key"]) for s in sessions}
        old = 0
        for d in iter_json(args.out):
            if args.tool in ("all", d["tool"]) and (d["tool"], d["key"]) not in live:
                d["started"], d["ended"] = parse_ts(d.get("started")), parse_ts(d.get("ended"))
                sessions.append(d)
                old += 1
        if old and not args.json:
            print(f"(includes {old} earlier sessions found only in {args.out})", file=sys.stderr)

    since = None
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").astimezone()
    sessions = [
        s for s in sessions
        if (args.include_guardian or s["kind"] != "guardian")
        and not (args.main_only and s["kind"] != "main")
        and (since is None or (s["started"] and s["started"] >= since))
    ]
    if not sessions:
        print("no sessions found", file=sys.stderr)
        return 1

    if args.command == "meta":
        return run_meta(args, sessions)
    if args.command == "save":
        save_rows(sessions, args.out)
    elif args.json:
        json.dump([to_row(s) for s in sessions], sys.stdout, ensure_ascii=False, indent=1)
        print()
    elif args.command == "sessions":
        print_sessions(sessions)
    elif args.command == "roles":
        print_roles(sessions)
    else:
        print_summary(sessions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
