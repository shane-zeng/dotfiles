"""Tests for model_usage.py, using small synthetic transcripts (no real user data)."""
import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_usage as mu  # noqa: E402


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def claude_msg(mid, out, effort="high", model="claude-opus-5-5", think=0):
    return {"type": "assistant", "sessionId": "s1", "cwd": "/work/app", "timestamp": "2026-11-25T01:00:00Z",
            "perTurnEffort": effort,
            "message": {"id": mid, "model": model,
                        "usage": {"output_tokens": out, "output_tokens_details": {"thinking_tokens": think}}}}


class ClaudeScan(unittest.TestCase):
    def test_dedupes_messages_and_reads_subagent_role(self):
        with tempfile.TemporaryDirectory() as root:
            proj = os.path.join(root, "proj")
            # one API response written as two records: the later one carries the final usage
            write_jsonl(os.path.join(proj, "s1.jsonl"),
                        [claude_msg("m1", 5), claude_msg("m1", 50, think=20), claude_msg("m2", 10, effort="low")])
            write_jsonl(os.path.join(proj, "s1", "subagents", "agent-a.jsonl"), [claude_msg("m9", 7)])
            with open(os.path.join(proj, "s1", "subagents", "agent-a.meta.json"), "w") as fh:
                json.dump({"agentType": "Explore"}, fh)
            by_kind = {s["kind"]: s for s in mu.scan_claude(root)}
            main = by_kind["main"]
            self.assertEqual(main["combos"]["claude-opus-5-5/high"], {"n": 1, "out": 50, "think": 20})
            self.assertEqual(main["combos"]["claude-opus-5-5/low"]["n"], 1)
            self.assertEqual(by_kind["subagent"]["role"], "Explore")
            self.assertNotEqual(main["key"], by_kind["subagent"]["key"])


def codex_rollout(source, thread_source, **meta):
    payload = {"id": "t1", "cwd": "/work/app", "source": source, "thread_source": thread_source, **meta}
    ctx = {"type": "turn_context", "payload": {"model": "gpt-x", "effort": "high"}}
    tokens = lambda out, think: {"type": "event_msg", "payload": {"type": "token_count", "info": {
        "total_token_usage": {"output_tokens": out, "reasoning_output_tokens": think}}}}
    return [{"type": "session_meta", "timestamp": "2026-11-25T01:00:00Z", "payload": payload},
            ctx, tokens(100, 40), ctx, tokens(250, 90)]


class CodexScan(unittest.TestCase):
    def scan(self, records, name="rollout-t1.jsonl"):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        write_jsonl(os.path.join(home, "sessions", name), records)
        return list(mu.scan_codex(home))

    def test_user_session_tokens_are_deltas(self):
        (s,) = self.scan(codex_rollout("vscode", "user"))
        self.assertEqual((s["kind"], s["role"]), ("main", ""))
        self.assertEqual(s["combos"]["gpt-x/high"], {"n": 2, "out": 250, "think": 90})

    def test_old_and_new_guardian_formats(self):
        guardian = {"subagent": {"other": "guardian"}}
        (new,) = self.scan(codex_rollout(guardian, "guardian_review", parent_thread_id="p"))
        (old,) = self.scan(codex_rollout(guardian, "subagent", parent_thread_id="p"))
        self.assertEqual((new["kind"], old["kind"]), ("guardian", "guardian"))

    def test_spawned_agent_role(self):
        spawn = {"subagent": {"thread_spawn": {"agent_role": "code_mapper"}}}
        (s,) = self.scan(codex_rollout(spawn, "subagent", parent_thread_id="p"))
        self.assertEqual((s["kind"], s["role"]), ("subagent", "code_mapper"))

    @unittest.skipUnless(shutil.which("zstd"), "zstd not installed")
    def test_reads_zstd_archive(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        plain = os.path.join(home, "sessions", "rollout-t1.jsonl")
        write_jsonl(plain, codex_rollout("vscode", "user"))
        subprocess.run(["zstd", "-q", "--rm", plain], check=True)
        (s,) = list(mu.scan_codex(home))
        self.assertEqual(s["combos"]["gpt-x/high"]["n"], 2)


class DocumentMetadata(unittest.TestCase):
    session = {"combos": {"opus/high": {"n": 40}, "opus/medium": {"n": 5}, "sonnet/high": {"n": 1}}}

    def test_meta_lines(self):
        single = mu.meta_lines({"combos": {"opus/high": {"n": 3}}})
        self.assertEqual(single, ["- 模型：opus", "- 推理強度：high"])
        self.assertEqual(mu.meta_lines({"combos": {"o/high": {"n": 40}, "o/medium": {"n": 5}}})[1],
                         "- 推理強度：high×40、medium×5")
        multi = mu.meta_lines(self.session)
        self.assertEqual(multi[0], "- 模型：opus、sonnet")
        self.assertIn("sonnet high×1", multi[1])

    def apply(self, text):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, "doc.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        lines = ["- 模型：m", "- 推理強度：e"]
        changed = mu.apply_meta(path, lines)
        again = mu.apply_meta(path, lines)  # second run must be a no-op
        with open(path, encoding="utf-8") as fh:
            return changed, again, fh.read()

    def test_appends_to_existing_block(self):
        changed, again, out = self.apply("# T\n\n- 日期：2026-11-25\n\n## A\n\nbody\n")
        self.assertEqual((changed, again), (True, False))
        self.assertEqual(out, "# T\n\n- 日期：2026-11-25\n- 模型：m\n- 推理強度：e\n\n## A\n\nbody\n")

    def test_creates_block_when_missing(self):
        _, _, out = self.apply("# T\n\n## A\n- item\n")
        self.assertEqual(out, "# T\n\n- 模型：m\n- 推理強度：e\n\n## A\n- item\n")

    def test_replaces_old_values(self):
        _, _, out = self.apply("# T\n\n- 模型：old\n- 推理強度：old\n- 日期：d\n\n## A\n")
        self.assertEqual(out.count("模型"), 1)
        self.assertIn("- 模型：m", out)

    def test_meta_uses_latest_agy_session_even_inside_codex(self):
        session = {
            "tool": "agy", "kind": "main", "key": "agy-1", "session_id": "agy-1",
            "cwd": os.getcwd(), "started": None, "ended": None, "title": "", **self.session,
        }
        args = SimpleNamespace(session=None, tool="agy", apply=None)
        out = io.StringIO()
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "codex-1"}, clear=True):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(mu.run_meta(args, [session]), 0)
        self.assertIn("- 模型：opus、sonnet", out.getvalue())


class Save(unittest.TestCase):
    def test_keeps_rows_whose_transcript_is_gone(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "usage.jsonl")
            row = {"tool": "claude", "key": "gone", "started": "2026-01-01T00:00:00+00:00"}
            write_jsonl(out, [row])
            new = {"tool": "codex", "key": "t1", "started": None, "ended": None}
            mu.save_rows([new], out)
            with open(out, encoding="utf-8") as fh:
                keys = [json.loads(line)["key"] for line in fh]
            self.assertEqual(sorted(keys), ["gone", "t1"])
            self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
