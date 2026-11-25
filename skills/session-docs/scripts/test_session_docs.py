#!/usr/bin/env python3
"""Tests for session_docs.py. Run with: python3 -m unittest discover -s <skill-dir>/scripts"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_docs as sd  # noqa: E402

DOC_PR = """# PR 4321 主題切換：PR 切分方式討論

- 日期：2026-11-19
- PR：[example-org/example-repo#4321](https://github.com/example-org/example-repo/pull/4321)「feat」
- Jira：DEMO-12345「新增主題切換」
- Codex chat：12345678-1234-4abc-8abc-123456789abc

## 結論

PR0 是資料層 PR。

```
## 這行在 code fence 內，不是標題
```

## 建議

- 先補呼叫端。

### 細節

細節內容。

## 結論

第二個同名章節。
"""

DOC_EXPORT = """# DEMO-23456 匯出預覽驗收流程

- 日期：2026-11-18
- 目的：驗收範疇的具體流程
- 狀態：進行中

## 進度

表格。
"""

DOC_OLD_PLAN = "# 舊的實作計畫\n\n- 日期：2026-04-23\n\n## 內容\n\n舊內容。\n"
DOC_NEW_PLAN = "# 新的實作計畫\n\n- 日期：2026-10-02\n\n已取代舊版 `2026-04-23-impl-plan.md`。\n\n## 內容\n\n新內容。\n"


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = sd.main(list(argv))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 2
    return code, out.getvalue(), err.getvalue()


class SessionDocsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.write("2026-11-19-pr4321-theme-toggle-split.md", DOC_PR)
        self.write("2026-11-18-DEMO-23456-export-preview-flows.md", DOC_EXPORT)
        self.write("2026-04-23-impl-plan.md", DOC_OLD_PLAN)
        self.write("2026-10-02-impl-plan-v2.md", DOC_NEW_PLAN)
        self.write("undated-note.md", "# 沒有日期的筆記\n\n只是一句摘要。\n\n## 內容\n\n深處才提到 DEMO-99999 與 unique-needle。\n")

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def cli(self, *argv):
        return run_cli("--dir", str(self.root), *argv)

    def test_cli_uses_session_dir_environment_and_prefers_explicit_dir(self):
        env_dir = self.root / "configured-sessions"
        env_dir.mkdir()
        with patch.dict(os.environ, {sd.ENV_DIR: str(env_dir)}):
            self.assertEqual(self.cli("build")[0], 0)
            self.assertTrue((self.root / sd.INDEX_NAME).is_file())
            self.assertFalse((env_dir / sd.INDEX_NAME).exists())
            self.assertEqual(run_cli("build")[0], 0)
            self.assertTrue((env_dir / sd.INDEX_NAME).is_file())

    def test_cli_explains_how_to_configure_a_missing_session_dir(self):
        with patch.dict(os.environ):
            os.environ.pop(sd.ENV_DIR, None)
            code, _, err = run_cli("build")
        self.assertEqual(code, 2)
        self.assertIn(f"use --dir or set {sd.ENV_DIR}", err)

    # ---- parsing
    def test_parse_extracts_identifiers_and_headings(self):
        doc = sd.parse_text("2026-11-19-pr4321-theme-toggle-split.md", DOC_PR)
        self.assertEqual(doc["date"], "2026-11-19")
        self.assertEqual(doc["jira"], ["DEMO-12345"])
        self.assertEqual(doc["prs"], [{"number": 4321, "repo": "example-org/example-repo"}])
        self.assertIn("example-repo", doc["repos"])
        self.assertEqual(doc["chat_ids"], ["12345678-1234-4abc-8abc-123456789abc"])
        titles = [h["title"] for h in doc["headings"]]
        self.assertNotIn("這行在 code fence 內，不是標題", titles)
        self.assertEqual(titles.count("結論"), 2)

    def test_repos_are_extracted_from_pr_urls_and_refs_without_prefixes(self):
        self.write("repo-refs.md", "# Repositories\n\n"
                   "- PR: https://github.com/example-org/Weather-Dashboard/pull/2345\n"
                   "- PR: sample-org/recipe-library#2345\n"
                   "- Repo: ignored-name\n")
        with patch.dict(os.environ, {sd.ENV_REPO_PREFIXES: ""}):
            for query in ("weather-dashboard", "recipe-library"):
                code, out, _ = self.cli("find", query, "--json")
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out)["results"][0]["match"], ["repo"])
        index = sd.load_index(self.root)
        doc = next(d for d in index["docs"] if d["name"] == "repo-refs.md")
        self.assertEqual(doc["repos"], ["recipe-library", "weather-dashboard"])

    def test_jira_blocklist_ignores_sha_and_iso(self):
        self.assertEqual(sd.jira_keys("SHA-256 and ISO-8601 but DEMO-23456"), ["DEMO-23456"])

    def test_header_date_used_when_filename_has_none(self):
        doc = sd.parse_text("note.md", "# t\n\n- 日期：2026-03-01\n")
        self.assertEqual((doc["date"], doc["date_source"]), ("2026-03-01", "header"))

    # ---- index
    def test_build_writes_index_and_is_idempotent(self):
        self.assertEqual(self.cli("build")[0], 0)
        first = (self.root / sd.INDEX_NAME).read_text(encoding="utf-8")
        self.assertEqual(self.cli("build")[0], 0)
        self.assertEqual(first, (self.root / sd.INDEX_NAME).read_text(encoding="utf-8"))
        names = [d["name"] for d in json.loads(first)["docs"]]
        self.assertEqual(len(names), 5)
        self.assertNotIn(sd.INDEX_NAME, names)

    def test_index_refreshes_after_edit(self):
        self.cli("build")
        self.write("2026-11-18-DEMO-23456-export-preview-flows.md", DOC_EXPORT + "\n## 新章節\n")
        code, out, _ = self.cli("outline", "2026-11-18-DEMO-23456-export-preview-flows.md")
        self.assertEqual(code, 0)
        self.assertIn("新章節", out)

    def test_index_refreshes_legacy_entries_and_after_prefix_changes(self):
        self.write("repo-names.md", "# Repositories\n\n- Repo: Sample-UI, Demo-API, ignored-name\n")
        index_path = self.root / sd.INDEX_NAME
        with patch.dict(os.environ, {sd.ENV_REPO_PREFIXES: ""}):
            self.assertEqual(self.cli("build")[0], 0)
        legacy_index = sd.load_index(self.root)
        legacy_index["version"] = 1
        del legacy_index["repo_prefixes"]
        index_path.write_text(json.dumps(legacy_index), encoding="utf-8")

        for config, expected in (
            (" Sample, DEMO, sample, ", ["demo-api", "sample-ui"]),
            ("demo", ["demo-api"]),
            ("", []),
        ):
            with self.subTest(config=config), patch.dict(os.environ, {sd.ENV_REPO_PREFIXES: config}):
                self.assertEqual(self.cli("build")[0], 0)
                index = sd.load_index(self.root)
                doc = next(d for d in index["docs"] if d["name"] == "repo-names.md")
                self.assertEqual(doc["repos"], expected)

    # ---- find
    def test_find_by_jira_variants(self):
        for query in ("DEMO-23456", "demo23456", "demo 23456", "23456"):
            code, out, _ = self.cli("find", query)
            self.assertEqual(code, 0, query)
            self.assertIn("export-preview-flows", out.splitlines()[1], query)

    def test_find_by_pr_variants(self):
        for query in ("pr4321", "PR 4321", "#4321", "pr-4321"):
            code, out, _ = self.cli("find", query)
            self.assertEqual(code, 0, query)
            self.assertIn("theme-toggle-split", out, query)

    def test_find_by_chinese_title_and_alias(self):
        self.write(sd.ALIASES_NAME, json.dumps({"*export-preview*": ["預覽驗收"]}, ensure_ascii=False))
        self.assertIn("theme-toggle-split", self.cli("find", "主題切換")[1])
        self.assertIn("export-preview-flows", self.cli("find", "預覽驗收")[1])

    def test_find_by_date_and_chat_id(self):
        self.assertIn("export-preview-flows", self.cli("find", "2026-11-18")[1])
        self.assertIn("theme-toggle-split", self.cli("find", "12345678-1234-4abc-8abc-123456789abc")[1])

    def test_find_falls_back_to_body(self):
        code, out, _ = self.cli("find", "unique-needle")
        self.assertEqual(code, 0)
        self.assertIn("undated-note", out)
        self.assertIn("body", out)

    def test_find_not_found(self):
        self.assertEqual(self.cli("find", "完全不存在的字串xyz")[0], 1)

    def test_undated_document_gets_a_date(self):
        self.cli("build")
        docs = {d["name"]: d for d in json.loads((self.root / sd.INDEX_NAME).read_text(encoding="utf-8"))["docs"]}
        self.assertTrue(docs["undated-note.md"]["date"])

    # ---- outline / read
    def test_outline_ranges(self):
        code, out, _ = self.cli("outline", "pr4321")
        self.assertEqual(code, 0)
        self.assertIn("## 結論", out)
        self.assertIn("### 細節", out)

    def test_read_section_stops_at_same_level_heading(self):
        code, out, _ = self.cli("read", "pr4321", "--section", "建議")
        self.assertEqual(code, 0)
        self.assertIn("先補呼叫端", out)
        self.assertIn("細節內容", out)  # subsection belongs to the section
        self.assertNotIn("第二個同名章節", out)

    def test_read_ambiguous_section_requires_choice(self):
        code, _, err = self.cli("read", "pr4321", "--section", "結論")
        self.assertEqual(code, 3)
        self.assertIn("2 個章節", err)
        code, out, _ = self.cli("read", "pr4321", "--section", "結論", "--first")
        self.assertEqual(code, 0)
        self.assertIn("PR0 是資料層 PR", out)
        self.assertNotIn("第二個同名章節", out)
        code, out, _ = self.cli("read", "pr4321", "--section", "結論", "--all")
        self.assertIn("第二個同名章節", out)

    def test_read_lines_and_truncation(self):
        code, out, _ = self.cli("read", "pr4321", "--lines", "1-3")
        self.assertEqual(code, 0)
        self.assertIn("PR 4321", out)
        code, out, _ = self.cli("read", "pr4321", "--max-chars", "20")
        self.assertIn("已截斷", out)

    def test_ambiguous_reference_exit_code(self):
        self.write("2026-11-20-impl-plan-copy.md", "# 實作計畫 impl plan\n\n- 日期：2026-11-20\n")
        code, _, err = self.cli("outline", "impl-plan")
        self.assertEqual(code, 3)
        self.assertIn("多份文件符合", err)

    # ---- archive
    def test_archived_documents_are_hidden_until_needed(self):
        self.write("_archive/2026-04-01-old-thing.md", "# 古老的設計\n\n- 日期：2026-04-01\n")
        self.cli("build")
        code, out, _ = self.cli("find", "古老的設計")
        self.assertEqual(code, 0)
        self.assertIn("來自封存", out)
        self.assertIn("[archived]", out)
        code, out, _ = self.cli("find", "export")
        self.assertNotIn("old-thing", out)
        self.assertEqual(self.cli("find", "古老的設計", "--include-archived")[0], 0)
        self.assertEqual(self.cli("find", "export", "--archived-only")[0], 1)

    def test_manifest_reason_is_shown(self):
        self.write("_archive/2026-04-01-old-thing.md", "# 古老的設計\n")
        sd.save_manifest(self.root, {"2026-04-01-old-thing.md": {"reason": "已併入新文件", "superseded_by": "x.md"}})
        out = self.cli("find", "古老的設計", "--archived-only")[1]
        self.assertIn("已併入新文件", out)

    def test_archive_dry_run_changes_nothing(self):
        code, out, _ = self.cli("archive", "2026-04-23-impl-plan.md", "--reason", "被取代")
        self.assertEqual(code, 0)
        self.assertIn("dry-run", out)
        self.assertTrue((self.root / "2026-04-23-impl-plan.md").exists())
        self.assertFalse((self.root / sd.ARCHIVE_DIR).exists())

    def test_archive_moves_file_records_manifest_and_updates_links(self):
        self.write("2026-11-21-ref.md",
                   "# 引用者\n\n參考 /x/docs/sessions/2026-04-23-impl-plan.md 與 2026-04-23-impl-plan.md。\n")
        code, out, _ = self.cli("archive", "2026-04-23-impl-plan.md", "--reason", "被 v2 取代",
                                "--superseded-by", "2026-10-02-impl-plan-v2.md", "--update-links", "--yes")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.root / "2026-04-23-impl-plan.md").exists())
        self.assertTrue((self.root / "_archive" / "2026-04-23-impl-plan.md").exists())
        entry = sd.load_manifest(self.root)["2026-04-23-impl-plan.md"]
        self.assertEqual(entry["superseded_by"], "2026-10-02-impl-plan-v2.md")
        self.assertIn("docs/sessions/_archive/2026-04-23-impl-plan.md",
                      (self.root / "2026-11-21-ref.md").read_text(encoding="utf-8"))
        self.assertTrue(any(d["path"].startswith("_archive/") for d in
                            json.loads((self.root / sd.INDEX_NAME).read_text(encoding="utf-8"))["docs"]))

    def test_archive_refuses_overwrite_and_already_archived(self):
        self.write("_archive/2026-04-23-impl-plan.md", "# x\n")
        self.assertEqual(self.cli("archive", "2026-04-23-impl-plan.md", "--reason", "r", "--yes")[0], 2)
        self.assertEqual(self.cli("archive", "_archive/2026-04-23-impl-plan.md", "--reason", "r", "--yes")[0], 2)

    def test_candidates(self):
        self.write("2026-11-01-save-doc.sh",
                   "#!/bin/sh\ntee '/x/docs/sessions/2026-11-18-DEMO-23456-export-preview-flows.md' <<'EOF'\nEOF\n")
        self.write("2026-09-01-impl-plan-v2.md", "# 同主題的舊版\n\n- 日期：2026-09-01\n")
        # Parallel analyses of two projects are not duplicates of each other.
        self.write("_project_b-impl-plan-v2.md", "# b 專案\n\n- 日期：2026-09-05\n")
        _, out, _ = self.cli("archive-candidates", "--json")
        found = {c["path"]: c for c in json.loads(out)}
        self.assertEqual(found["2026-11-01-save-doc.sh"]["confidence"], "high")
        self.assertIn("2026-04-23-impl-plan.md", found)  # named as superseded by the v2 document
        self.assertEqual(found["2026-04-23-impl-plan.md"]["superseded_by"], "2026-10-02-impl-plan-v2.md")
        # Same normalized slug: the older one (2026-09-01) is flagged against the newest (2026-10-02).
        self.assertEqual(found["2026-09-01-impl-plan-v2.md"]["confidence"], "low")
        self.assertEqual(found["2026-09-01-impl-plan-v2.md"]["superseded_by"], "2026-10-02-impl-plan-v2.md")
        self.assertNotIn("_project_b-impl-plan-v2.md", found)
        # Candidates must never move anything.
        self.assertTrue((self.root / "2026-04-23-impl-plan.md").exists())


if __name__ == "__main__":
    unittest.main()
