#!/usr/bin/env python3
"""Index, search and read the user's saved session documents.

Session documents are Markdown files saved under docs/sessions. This tool keeps a
derived index (index.json) next to them so a request such as "read session
DEMO-12345" can be answered without the user pasting a path.

Stdlib only, Python 3.9+. Everything except `archive --yes` is read-only with
respect to the documents; `find`, `outline`, `read` and `archive-candidates`
only refresh the derived index.

Commands:
  build                      rebuild or refresh the index
  find QUERY...              locate documents (Jira key, PR number, date, title, alias, body)
  outline REF                list the headings of a document with line ranges
  read REF [--section S]     print a whole document or only one section
  archive-candidates         propose documents that look archivable (never moves anything)
  archive REF --reason R     move a document into _archive/ (dry-run unless --yes)

REF is an absolute path, a path relative to the sessions directory, a file name,
or a query that resolves to exactly one document.

Exit codes: 0 ok, 1 nothing found, 2 usage or environment error, 3 ambiguous.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ENV_DIR = "SESSION_DOCS_DIR"
ENV_REPO_PREFIXES = "SESSION_DOCS_REPO_PREFIXES"
INDEX_NAME = "index.json"
ALIASES_NAME = "index.aliases.json"
ARCHIVE_DIR = "_archive"
MANIFEST_NAME = "manifest.json"
SCHEMA_VERSION = 2
HEADER_LINES = 40
BODY_PREVIEW = 110

# Upper-case prefixes that look like Jira keys but are not (SHA-256, ISO-8601, ...).
JIRA_BLOCKLIST = {
    "SHA", "UTF", "ISO", "RFC", "AES", "RSA", "MD", "HTTP", "TLS", "SSL", "CVE", "PHP",
    "PSR", "ANSI", "CWE", "OWASP", "HS", "RS", "ES", "UTC", "GMT", "ECMA", "IEEE",
}
QUERY_STOPWORDS = {
    "session", "sessions", "doc", "docs", "document", "documents", "文件", "文檔", "那份",
    "這份", "一份", "的", "讀", "看", "看一下", "讀取", "read", "the", "那個", "這個", "紀錄",
}

RE_FENCE_OPEN = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
RE_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
RE_META = re.compile(r"^\s*(?:[-*]|>)\s*\**([^:：*\n]{1,12}?)\**\s*[:：]\s*(.+?)\s*$")
RE_FILE_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")
RE_ANY_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
RE_JIRA = re.compile(r"\b([A-Za-z]{2,6})-(\d{3,6})\b")
RE_PR_FILE = re.compile(r"(?<![a-z])pr[-_]?(\d{3,5})(?!\d)", re.I)
RE_PR_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)")
RE_PR_REPO_REF = re.compile(r"\b([\w.-]+/[\w.-]+)#(\d{3,5})\b")
RE_PR_LABEL = re.compile(r"\bPR\s*#?\s*(\d{3,5})\b", re.I)
RE_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
RE_MD_REF = re.compile(r"([A-Za-z0-9_\-.一-鿿]+\.md)\b")
RE_QUERY_PR = re.compile(r"(?:\bpr[\s_-]*#?|#)\s*(\d{3,5})\b", re.I)
RE_QUERY_JIRA = re.compile(r"\b([A-Za-z]{2,6})[\s_-]*(\d{3,6})\b")
RE_QUERY_DATE = re.compile(r"\b(20\d{2}-\d{2}(?:-\d{2})?)\b")


# --------------------------------------------------------------------------- paths

def docs_root(arg_dir: Optional[str]) -> Path:
    configured_dir = arg_dir or os.environ.get(ENV_DIR)
    if not configured_dir:
        die(f"session directory is not configured (use --dir or set {ENV_DIR})", 2)
    root = Path(configured_dir).expanduser()
    if not root.is_dir():
        die(f"sessions directory not found: {root} (use --dir or set {ENV_DIR})", 2)
    return root


def die(message: str, code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


def list_docs(root: Path) -> List[str]:
    """Markdown documents at the top level and directly inside _archive/."""
    found = [p.name for p in root.glob("*.md") if not p.name.startswith(".")]
    archive = root / ARCHIVE_DIR
    if archive.is_dir():
        found += [f"{ARCHIVE_DIR}/{p.name}" for p in archive.glob("*.md") if not p.name.startswith(".")]
    return sorted(found)


# --------------------------------------------------------------------------- parsing

def clean_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_headings(lines: List[str]) -> List[Dict[str, Any]]:
    """Headings with 1-based line numbers; lines inside code fences are ignored."""
    headings: List[Dict[str, Any]] = []
    fence: Optional[Tuple[str, int]] = None
    for number, line in enumerate(lines, 1):
        opener = RE_FENCE_OPEN.match(line)
        if fence is None:
            if opener:
                marker = opener.group(1)
                fence = (marker[0], len(marker))
                continue
        else:
            stripped = line.strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= fence[1]:
                fence = None
            continue
        match = RE_HEADING.match(line)
        if match:
            headings.append({"level": len(match.group(1)), "title": clean_inline(match.group(2)), "line": number})
    return headings


def valid_date(year: str, month: str, day: str) -> Optional[str]:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def jira_keys(text: str) -> List[str]:
    keys = set()
    for prefix, number in RE_JIRA.findall(text):
        if prefix.upper() not in JIRA_BLOCKLIST:
            keys.add(f"{prefix.upper()}-{number}")
    return sorted(keys)


def parse_text(rel: str, text: str, repo_pattern: Optional[re.Pattern[str]] = None) -> Dict[str, Any]:
    name = rel.split("/")[-1]
    lines = text.splitlines()
    headings = parse_headings(lines)
    title = next((h["title"] for h in headings if h["level"] == 1), name[:-3])

    # Header zone: the metadata bullets between the title and the first section.
    zone_end = min(HEADER_LINES, len(lines))
    for h in headings:
        if h["level"] >= 2 and h["line"] <= zone_end:
            zone_end = h["line"] - 1
            break
    zone_lines = lines[:zone_end]
    zone = "\n".join(zone_lines)
    scan = f"{name}\n{title}\n{zone}"

    meta: Dict[str, str] = {}
    for line in zone_lines:
        m = RE_META.match(line)
        if m and m.group(1).strip() not in meta:
            meta[m.group(1).strip()] = clean_inline(m.group(2))

    doc_date, date_source = None, None
    fm = RE_FILE_DATE.match(name)
    if fm:
        doc_date = valid_date(*fm.groups())
        date_source = "filename" if doc_date else None
    if not doc_date:
        for key in ("日期", "整理日期", "date", "Date"):
            if key in meta:
                dm = RE_ANY_DATE.search(meta[key])
                if dm and valid_date(*dm.groups()):
                    doc_date, date_source = valid_date(*dm.groups()), "header"
                    break

    prs: Dict[int, Optional[str]] = {}
    repos = set()
    for m in RE_PR_FILE.finditer(name):
        prs.setdefault(int(m.group(1)), None)
    for pattern in (RE_PR_URL, RE_PR_REPO_REF):
        for m in pattern.finditer(zone):
            owner_repo, number = m.groups()
            prs[int(number)] = owner_repo
            repos.add(owner_repo.split("/", 1)[1].lower())
    for m in RE_PR_LABEL.finditer(f"{title}\n{zone}"):
        prs.setdefault(int(m.group(1)), None)

    if repo_pattern is not None:
        repos.update(repo_pattern.findall(scan.lower()))

    summary = ""
    for key in ("結論", "摘要", "目的", "範圍"):
        if key in meta:
            summary = meta[key]
            break
    if not summary:
        in_fence = False
        for line in lines[1:80]:
            if RE_FENCE_OPEN.match(line):
                in_fence = not in_fence
                continue
            stripped = line.strip()
            if (in_fence or not stripped or stripped.startswith(("#", "|", ">", "-", "*", "```"))
                    or RE_META.match(line)):
                continue
            summary = clean_inline(stripped)
            break
    status = meta.get("狀態") or meta.get("status") or meta.get("Status") or ""

    return {
        "path": rel,
        "name": name,
        "archived": rel.startswith(ARCHIVE_DIR + "/"),
        "date": doc_date,
        "date_source": date_source,
        "title": title,
        "summary": summary[:160],
        "status": status[:160],
        "jira": jira_keys(scan),
        "jira_mentions": jira_keys(text)[:30],
        "prs": [{"number": n, "repo": r} for n, r in sorted(prs.items())],
        "repos": sorted(repos),
        "chat_ids": sorted({u.lower() for u in RE_UUID.findall(zone)}),
        "headings": headings,
        "md_refs": sorted({r for r in RE_MD_REF.findall(text) if r != name}),
    }


# --------------------------------------------------------------------------- sidecars

def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json_if_changed(path: Path, data: Any) -> bool:
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    try:
        if path.read_text(encoding="utf-8") == text:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return True


def load_manifest(root: Path) -> Dict[str, Any]:
    data = read_json(root / ARCHIVE_DIR / MANIFEST_NAME, {})
    return data.get("entries", {}) if isinstance(data, dict) else {}


def save_manifest(root: Path, entries: Dict[str, Any]) -> None:
    write_json_if_changed(root / ARCHIVE_DIR / MANIFEST_NAME, {"version": 1, "entries": entries})


def aliases_for(doc: Dict[str, Any], table: Dict[str, List[str]]) -> List[str]:
    found: List[str] = []
    for key, values in table.items():
        if key in (doc["path"], doc["name"]) or fnmatch.fnmatch(doc["name"], key) or fnmatch.fnmatch(doc["path"], key):
            found += [v for v in values if isinstance(v, str)]
    return sorted(set(found))


# --------------------------------------------------------------------------- git helpers

def git(root: Path, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def fallback_date(root: Path, rel: str) -> Tuple[Optional[str], str]:
    """Date for undated documents: first commit date (stable across clones), else mtime."""
    first = git(root, "log", "--diff-filter=A", "--follow", "--format=%ad", "--date=short", "--", rel)
    if first:
        return first.splitlines()[-1], "git"
    try:
        return datetime.fromtimestamp((root / rel).stat().st_mtime).date().isoformat(), "mtime"
    except OSError:
        return None, "unknown"


# --------------------------------------------------------------------------- index

def load_index(root: Path) -> Dict[str, Any]:
    data = read_json(root / INDEX_NAME, {})
    return data if isinstance(data, dict) and data.get("version") == SCHEMA_VERSION else {}


def refresh(root: Path, write: bool = True, force: bool = False) -> Dict[str, Any]:
    configured_prefixes = os.environ.get(ENV_REPO_PREFIXES, "").split(",")
    repo_prefixes = sorted({prefix.strip().lower() for prefix in configured_prefixes if prefix.strip()})
    repo_pattern = None
    if repo_prefixes:
        alternatives = "|".join(re.escape(prefix) for prefix in repo_prefixes)
        repo_pattern = re.compile(rf"\b(?:{alternatives})-[a-z0-9]+(?:-[a-z0-9]+)*\b")
    cached_index = load_index(root)
    previous = {}
    if cached_index.get("repo_prefixes") == repo_prefixes:
        previous = {d["path"]: d for d in cached_index.get("docs", [])}
    aliases = read_json(root / ALIASES_NAME, {})
    manifest = load_manifest(root)
    docs: List[Dict[str, Any]] = []
    for rel in list_docs(root):
        data = (root / rel).read_bytes()
        sha = hashlib.sha1(data).hexdigest()
        cached = previous.get(rel)
        if cached and cached.get("sha1") == sha and not force:
            doc = dict(cached)
        else:
            doc = parse_text(rel, data.decode("utf-8", errors="replace"), repo_pattern)
            doc["sha1"], doc["size"] = sha, len(data)
            if not doc["date"]:
                doc["date"], doc["date_source"] = fallback_date(root, rel)
        docs.append(doc)

    names = {d["name"] for d in docs}
    for doc in docs:
        doc["links"] = sorted(r for r in doc.get("md_refs", []) if r in names and r != doc["name"])
        doc["aliases"] = aliases_for(doc, aliases) if isinstance(aliases, dict) else []
        doc["archive"] = manifest.get(doc["name"], {"reason": None}) if doc["archived"] else None

    index = {"version": SCHEMA_VERSION, "repo_prefixes": repo_prefixes, "docs": docs}
    if write:
        write_json_if_changed(root / INDEX_NAME, index)
    return index


# --------------------------------------------------------------------------- search

class ParsedQuery:
    def __init__(self, query: str) -> None:
        text = query
        self.uuids = [u.lower() for u in RE_UUID.findall(text)]
        text = RE_UUID.sub(" ", text)
        self.prs = sorted({int(n) for n in RE_QUERY_PR.findall(text)})
        text = RE_QUERY_PR.sub(" ", text)
        self.jira: List[str] = []
        for prefix, number in RE_QUERY_JIRA.findall(text):
            if prefix.upper() not in JIRA_BLOCKLIST:
                self.jira.append(f"{prefix.upper()}-{number}")
        text = RE_QUERY_JIRA.sub(" ", text) if self.jira else text
        self.dates = RE_QUERY_DATE.findall(text)
        text = RE_QUERY_DATE.sub(" ", text)
        tokens = [t for t in re.split(r"[\s,，、;；]+", text) if t]
        self.numbers = [int(t) for t in tokens if re.fullmatch(r"\d{3,6}", t)]
        self.words = [t.casefold() for t in tokens
                      if not re.fullmatch(r"\d{3,6}", t) and t.casefold() not in QUERY_STOPWORDS]
        # Raw tokens for the body fallback (keeps forms such as "demo-23456").
        self.raw = [t.casefold() for t in re.split(r"[\s,，、;；]+", query)
                    if t and t.casefold() not in QUERY_STOPWORDS]

    @property
    def empty(self) -> bool:
        return not (self.uuids or self.prs or self.jira or self.dates or self.numbers or self.words)


def score_doc(doc: Dict[str, Any], pq: ParsedQuery) -> Tuple[int, int, int, List[str]]:
    """Returns (score, hits, needed, matched fields)."""
    score, hits, need, why = 0, 0, 0, []
    pr_numbers = {p["number"] for p in doc["prs"]}
    jira_numbers = {int(k.split("-")[1]) for k in doc["jira"]}

    def hit(points: int, label: str) -> None:
        nonlocal score, hits
        score += points
        hits += 1
        if label not in why:
            why.append(label)

    for u in pq.uuids:
        need += 1
        if u in doc["chat_ids"]:
            hit(60, "chat id")
    # A key that appears in the file name or title means the document is *about* it, not just mentions it.
    name_title = f"{doc['name']} {doc['title']}".casefold()
    for n in pq.prs:
        need += 1
        if n in pr_numbers:
            hit(60 + (30 if str(n) in name_title else 0), "PR")
    for k in pq.jira:
        need += 1
        if k in doc["jira"]:
            hit(60 + (20 if k.casefold() in name_title else 0), "Jira")
        elif k in doc["jira_mentions"]:
            hit(15, "Jira(內文)")
    for d in pq.dates:
        need += 1
        if (doc["date"] or "").startswith(d):
            hit(25, "date")
    for n in pq.numbers:
        need += 1
        if n in pr_numbers or n in jira_numbers:
            hit(40 + (30 if str(n) in name_title else 0), "number")
    stem = doc["name"][:-3].casefold()
    title = doc["title"].casefold()
    summary = doc["summary"].casefold()
    aliases = [a.casefold() for a in doc.get("aliases", [])]
    headings = [h["title"].casefold() for h in doc["headings"]]
    for w in pq.words:
        need += 1
        best, label = 0, ""
        for points, name, matched in (
            (25, "alias", any(w in a for a in aliases)),
            (20, "filename", w in stem),
            (15, "title", w in title),
            (10, "repo", any(w in r for r in doc["repos"])),
            (8, "heading", any(w in h for h in headings)),
            (4, "summary", w in summary),
        ):
            if matched and points > best:
                best, label = points, name
        if best:
            hit(best, label)
    return score, hits, need, why


def sort_key(item: Dict[str, Any]) -> Tuple[Any, ...]:
    return (-item["hits"], -item["score"], _neg_date(item["date"]), item["name"])


def _neg_date(value: Optional[str]) -> str:
    # Newest first: invert each digit so plain string sorting yields descending dates.
    return "".join(str(9 - int(c)) if c.isdigit() else c for c in (value or "0000-00-00"))


def search_index(docs: List[Dict[str, Any]], pq: ParsedQuery) -> List[Dict[str, Any]]:
    results = []
    for doc in docs:
        score, hits, need, why = score_doc(doc, pq)
        if hits:
            results.append({"doc": doc, "name": doc["name"], "date": doc["date"], "score": score,
                            "hits": hits, "need": need, "why": why})
    strict = [r for r in results if r["hits"] == r["need"]]
    return sorted(strict or results, key=sort_key)


def search_body(root: Path, docs: List[Dict[str, Any]], pq: ParsedQuery) -> List[Dict[str, Any]]:
    tokens = pq.raw
    if not tokens:
        return []
    results = []
    for doc in docs:
        text = (root / doc["path"]).read_text(encoding="utf-8", errors="replace")
        lowered = text.casefold()
        if not all(t in lowered for t in tokens):
            continue
        first_line, preview = 0, ""
        for number, line in enumerate(text.splitlines(), 1):
            if tokens[0] in line.casefold():
                first_line, preview = number, clean_inline(line)[:BODY_PREVIEW]
                break
        count = sum(lowered.count(t) for t in tokens)
        results.append({"doc": doc, "name": doc["name"], "date": doc["date"], "score": count,
                        "hits": len(tokens), "need": len(tokens), "why": ["body"],
                        "line": first_line, "preview": preview})
    return sorted(results, key=sort_key)


def run_search(root: Path, docs: List[Dict[str, Any]], pq: ParsedQuery, args: Any) -> Tuple[List[Dict[str, Any]], str]:
    live = [d for d in docs if not d["archived"]]
    archived = [d for d in docs if d["archived"]]
    if args.archived_only:
        pool, fallback = archived, []
    elif args.include_archived:
        pool, fallback = docs, []
    else:
        pool, fallback = live, archived
    results = search_index(pool, pq) or search_body(root, pool, pq)
    note = ""
    if not results and fallback:
        results = search_index(fallback, pq) or search_body(root, fallback, pq)
        if results:
            note = "沒有在現行文件找到，以下結果來自封存（_archive）"
    return results, note


# --------------------------------------------------------------------------- output

def describe(item: Dict[str, Any], root: Path, position: int) -> str:
    doc = item["doc"]
    tags = list(doc["jira"]) + [f"PR#{p['number']}" for p in doc["prs"]]
    flag = "  [archived]" if doc["archived"] else ""
    lines = [f"{position}. {doc['date'] or '????-??-??'}  {doc['name']}{flag}",
             f"   {doc['title']}"]
    detail = " · ".join(x for x in (" ".join(tags[:6]), ("repos " + ", ".join(doc["repos"][:3])) if doc["repos"] else "",
                                    "比對: " + ", ".join(item["why"])) if x)
    lines.append(f"   {detail}")
    if doc.get("status"):
        lines.append(f"   狀態: {doc['status'][:100]}")
    if item.get("line"):
        lines.append(f"   L{item['line']}: {item['preview']}")
    if doc["archived"] and doc.get("archive") and doc["archive"].get("reason"):
        extra = f"（取代者: {doc['archive']['superseded_by']}）" if doc["archive"].get("superseded_by") else ""
        lines.append(f"   封存原因: {doc['archive']['reason']}{extra}")
    lines.append(f"   {root / doc['path']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- resolve / read

def resolve_ref(root: Path, docs: List[Dict[str, Any]], ref: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns (doc, candidates). doc is None when nothing or several candidates match."""
    by_path = {d["path"]: d for d in docs}
    p = Path(ref).expanduser()
    if p.is_absolute() and p.is_file():
        try:
            rel = p.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = ""
        if rel in by_path:
            return by_path[rel], []
    for candidate in (ref, ref + ".md", f"{ARCHIVE_DIR}/{ref}", f"{ARCHIVE_DIR}/{ref}.md"):
        if candidate in by_path:
            return by_path[candidate], []
    named = [d for d in docs if d["name"] in (ref, ref + ".md")]
    if len(named) == 1:
        return named[0], []

    class Args:
        include_archived = False
        archived_only = False

    results, _ = run_search(root, docs, ParsedQuery(ref), Args)
    if not results:
        return None, []
    if len(results) == 1:
        return results[0]["doc"], []
    first, second = results[0], results[1]
    if first["hits"] > second["hits"] or first["score"] >= 2 * second["score"]:
        return first["doc"], []
    return None, results[:5]


def need_doc(root: Path, docs: List[Dict[str, Any]], ref: str) -> Dict[str, Any]:
    doc, candidates = resolve_ref(root, docs, ref)
    if doc:
        return doc
    if candidates:
        print("多份文件符合，請指定其中一份（檔名或更具體的查詢）：", file=sys.stderr)
        for i, item in enumerate(candidates, 1):
            print(describe(item, root, i), file=sys.stderr)
        sys.exit(3)
    die(f"找不到符合的 session 文件: {ref}", 1)
    raise SystemExit(1)


def section_bounds(headings: List[Dict[str, Any]], total: int) -> List[Tuple[Dict[str, Any], int, int]]:
    bounds = []
    for i, h in enumerate(headings):
        end = total
        for nxt in headings[i + 1:]:
            if nxt["level"] <= h["level"]:
                end = nxt["line"] - 1
                break
        bounds.append((h, h["line"], end))
    return bounds


# --------------------------------------------------------------------------- commands

def cmd_build(args: Any) -> int:
    root = docs_root(args.dir)
    index = refresh(root, write=True, force=args.force)
    live = sum(1 for d in index["docs"] if not d["archived"])
    print(f"索引已更新：{len(index['docs'])} 份文件（現行 {live}，封存 {len(index['docs']) - live}）→ {root / INDEX_NAME}")
    return 0


def cmd_find(args: Any) -> int:
    root = docs_root(args.dir)
    pq = ParsedQuery(" ".join(args.query))
    if pq.empty:
        die("查詢是空的", 2)
    docs = refresh(root, write=not args.no_refresh)["docs"]
    results, note = run_search(root, docs, pq, args)
    if not results:
        print("找不到符合的 session 文件。可以換個關鍵字，或加上 --include-archived。")
        return 1
    shown = results[: args.limit]
    if args.json:
        print(json.dumps({"note": note, "total": len(results), "results": [
            {"path": str(root / r["doc"]["path"]), "name": r["name"], "date": r["date"], "title": r["doc"]["title"],
             "jira": r["doc"]["jira"], "prs": r["doc"]["prs"], "archived": r["doc"]["archived"],
             "score": r["score"], "match": r["why"]} for r in shown]}, ensure_ascii=False, indent=1))
        return 0
    if note:
        print(f"注意：{note}")
    print(f"找到 {len(results)} 筆，顯示前 {len(shown)} 筆（依相關度，其次新到舊）：")
    for i, item in enumerate(shown, 1):
        print(describe(item, root, i))
    return 0


def cmd_outline(args: Any) -> int:
    root = docs_root(args.dir)
    doc = need_doc(root, refresh(root, write=not args.no_refresh)["docs"], args.ref)
    lines = (root / doc["path"]).read_text(encoding="utf-8", errors="replace").splitlines()
    print(f"{doc['title']}  ({root / doc['path']}, {len(lines)} 行)")
    for number, (h, start, end) in enumerate(section_bounds(parse_headings(lines), len(lines)), 1):
        print(f"{number:>3}. L{start}-L{end} ({end - start + 1} 行) {'  ' * (h['level'] - 1)}{'#' * h['level']} {h['title']}")
    return 0


def cmd_read(args: Any) -> int:
    root = docs_root(args.dir)
    doc = need_doc(root, refresh(root, write=not args.no_refresh)["docs"], args.ref)
    lines = (root / doc["path"]).read_text(encoding="utf-8", errors="replace").splitlines()
    ranges: List[Tuple[int, int, str]] = []
    if args.lines:
        m = re.fullmatch(r"(\d+)-(\d+)", args.lines)
        if not m or int(m.group(1)) < 1 or int(m.group(2)) < int(m.group(1)):
            die("--lines 格式應為 A-B（例如 10-40）", 2)
        ranges.append((int(m.group(1)), min(int(m.group(2)), len(lines)), "lines"))
    elif args.section:
        bounds = section_bounds(parse_headings(lines), len(lines))
        key = args.section.casefold()
        if re.fullmatch(r"#\d+", args.section):
            index = int(args.section[1:])
            matches = [bounds[index - 1]] if 1 <= index <= len(bounds) else []
        else:
            matches = [b for b in bounds if key in b[0]["title"].casefold()]
        if not matches:
            die(f"找不到章節「{args.section}」，可先用 outline 查看章節", 1)
        if len(matches) > 1 and not (args.all or args.first):
            print(f"「{args.section}」符合 {len(matches)} 個章節，請用更精確的名稱、#編號，或加 --first / --all：", file=sys.stderr)
            for h, start, end in matches:
                print(f"  L{start}-L{end} {'#' * h['level']} {h['title']}", file=sys.stderr)
            return 3
        if args.first:
            matches = matches[:1]
        ranges = [(start, end, h["title"]) for h, start, end in matches]
    else:
        ranges.append((1, len(lines), "all"))

    budget = args.max_chars
    for start, end, label in ranges:
        info = f"{doc['path']} L{start}-L{end}"
        if label not in ("all", "lines"):
            info += f" § {label}"
        print(f"<!-- {info} -->")
        chunk = "\n".join(lines[start - 1:end])
        if len(chunk) > budget:
            print(chunk[:budget])
            print(f"\n<!-- 已截斷：輸出超過 {args.max_chars} 字元。用 outline 找章節，再用 --section 或 --lines 讀取需要的部分 -->")
            return 0
        print(chunk)
        budget -= len(chunk)
    return 0


# --------------------------------------------------------------------------- archive

# Only the date prefix is stripped. Prefixes such as `_project_b-` / `_project_c-` name the project the
# analysis was done in (two parallel analyses), not a version, so they must not make documents "equal".
SLUG_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def slug_of(name: str) -> str:
    return SLUG_PREFIX.sub("", name[:-3] if name.endswith(".md") else name).casefold()


def candidates(root: Path, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}
    rank = {"high": 3, "medium": 2, "low": 1}

    def add(path: str, confidence: str, reason: str, target: Optional[str] = None) -> None:
        if path not in found or rank[confidence] > rank[found[path]["confidence"]]:
            found[path] = {"path": path, "confidence": confidence, "reason": reason, "superseded_by": target}

    live = [d for d in docs if not d["archived"]]
    live_names = {d["name"] for d in live}

    # 1. Save scripts whose target document already exists (derived artifacts).
    for script in sorted(root.glob("*.sh")):
        text = script.read_text(encoding="utf-8", errors="replace")
        for target in re.findall(r"docs/sessions/([^'\" \n]+\.md)", text):
            if "tee" in text and target in live_names:
                add(script.name, "high", f"儲存腳本；目標文件已存在：{target}", target)

    # 2. Documents that say they were superseded, or that name the one they supersede.
    for doc in live:
        for line in (root / doc["path"]).read_text(encoding="utf-8", errors="replace").splitlines():
            refs = [r for r in RE_MD_REF.findall(line) if r != doc["name"] and r in live_names]
            if not refs:
                continue
            if re.search(r"已被|被.{0,12}取代|superseded by", line, re.I) and not re.search(r"原為", line):
                add(doc["name"], "medium", f"文件自述已被取代：{clean_inline(line)[:90]}", refs[0])
            elif re.search(r"取代了?|supersedes|併入此|合併了", line, re.I) and not re.search(r"原為", line):
                add(refs[0], "medium", f"{doc['name']} 自述取代它：{clean_inline(line)[:90]}", doc["name"])

    # 3. Same normalized slug: the older document may be a duplicate.
    by_slug: Dict[str, List[Dict[str, Any]]] = {}
    for doc in live:
        by_slug.setdefault(slug_of(doc["name"]), []).append(doc)
    for slug, group in by_slug.items():
        if len(group) > 1:
            ordered = sorted(group, key=lambda d: (d["date"] or "", d["name"]))
            newest = ordered[-1]
            for older in ordered[:-1]:
                add(older["name"], "low", f"與 {newest['name']} 主題相同（slug「{slug}」），可能是舊版", newest["name"])
    return sorted(found.values(), key=lambda c: (-rank[c["confidence"]], c["path"]))


def cmd_candidates(args: Any) -> int:
    root = docs_root(args.dir)
    items = candidates(root, refresh(root, write=not args.no_refresh)["docs"])
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
        return 0
    if not items:
        print("沒有發現建議封存的項目。")
        return 0
    print("以下只是候選，不會自動搬移；確認後請用 archive 指令：")
    for c in items:
        target = f"  → 取代者/對應：{c['superseded_by']}" if c["superseded_by"] else ""
        print(f"[{c['confidence']}] {c['path']}\n      {c['reason']}{target}")
    return 0


def inbound_refs(root: Path, name: str) -> List[Path]:
    hits = []
    for rel in list_docs(root):
        if rel.split("/")[-1] == name:
            continue
        if name in (root / rel).read_text(encoding="utf-8", errors="replace"):
            hits.append(root / rel)
    return hits


def cmd_archive(args: Any) -> int:
    root = docs_root(args.dir)
    docs = refresh(root, write=not args.no_refresh)["docs"]
    ref_name = Path(args.ref).name
    if not ref_name.endswith(".md") and (root / ref_name).is_file():
        doc_path = ref_name  # non-Markdown derived file (for example a save script)
    else:
        doc = need_doc(root, docs, args.ref)
        if doc["archived"]:
            die(f"{doc['path']} 已經在封存區", 2)
        doc_path = doc["path"]
    source = root / doc_path
    target = root / ARCHIVE_DIR / source.name
    if target.exists():
        die(f"封存區已有同名檔案: {target}", 2)
    superseded = None
    if args.superseded_by:
        other, _ = resolve_ref(root, docs, args.superseded_by)
        if not other:
            die(f"--superseded-by 找不到對應文件: {args.superseded_by}", 1)
        superseded = other["name"]
    refs = inbound_refs(root, source.name)
    print(("執行" if args.yes else "預覽（dry-run；加 --yes 才會執行）") + f"：{doc_path} → {ARCHIVE_DIR}/{source.name}")
    print(f"  原因：{args.reason}" + (f"；取代者：{superseded}" if superseded else ""))
    if refs:
        print(f"  其他文件提到此檔名（{len(refs)} 份）：")
        for ref in refs:
            print(f"    - {ref.relative_to(root)}")
        print("  搬移後這些連結需要更新；可加 --update-links 自動改寫完整路徑形式（docs/sessions/<檔名>）。")
    if not args.yes:
        return 0

    (root / ARCHIVE_DIR).mkdir(exist_ok=True)
    tracked = git(root, "ls-files", "--error-unmatch", doc_path) is not None
    if not (tracked and git(root, "mv", doc_path, f"{ARCHIVE_DIR}/{source.name}") is not None):
        os.rename(source, target)
    entries = load_manifest(root)
    entries[source.name] = {"archived_at": date.today().isoformat(), "reason": args.reason,
                            "superseded_by": superseded}
    save_manifest(root, entries)
    if args.update_links:
        old, new = f"docs/sessions/{source.name}", f"docs/sessions/{ARCHIVE_DIR}/{source.name}"
        for ref in refs:
            text = ref.read_text(encoding="utf-8")
            if old in text:
                ref.write_text(text.replace(old, new), encoding="utf-8")
                print(f"  已更新連結：{ref.relative_to(root)}")
    refresh(root, write=True)
    print("完成。已移動、寫入 manifest 並更新索引。")
    return 0


# --------------------------------------------------------------------------- cli

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="session_docs.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", help=f"sessions directory (defaults to ${ENV_DIR})")
    parser.add_argument("--no-refresh", action="store_true", help="do not write index.json while searching")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build", help="rebuild or refresh the index")
    p.add_argument("--force", action="store_true", help="re-parse every document")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("find", help="locate documents")
    p.add_argument("query", nargs="+")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--include-archived", action="store_true")
    p.add_argument("--archived-only", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("outline", help="list headings with line ranges")
    p.add_argument("ref")
    p.set_defaults(func=cmd_outline)

    p = sub.add_parser("read", help="print a document or one section")
    p.add_argument("ref")
    p.add_argument("--section", help="heading text (substring) or #N from outline")
    p.add_argument("--first", action="store_true", help="when several sections match, read the first")
    p.add_argument("--all", action="store_true", help="when several sections match, read all of them")
    p.add_argument("--lines", help="line range A-B")
    p.add_argument("--max-chars", type=int, default=40000)
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("archive-candidates", help="propose documents that look archivable")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_candidates)

    p = sub.add_parser("archive", help="move a document into _archive/ (dry-run unless --yes)")
    p.add_argument("ref")
    p.add_argument("--reason", required=True)
    p.add_argument("--superseded-by")
    p.add_argument("--update-links", action="store_true")
    p.add_argument("--yes", action="store_true", help="actually move the file")
    p.set_defaults(func=cmd_archive)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
