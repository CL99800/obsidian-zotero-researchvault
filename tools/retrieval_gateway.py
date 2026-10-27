"""Note-first ResearchVault retrieval with targeted Zotero original-source fallback.

This CLI returns evidence candidates with provenance; the agent, not this
lexical helper, decides whether evidence actually supports an answer.
All operations here are read-only. Python 3.11+; PyMuPDF is optional for PDF pages.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from vault_schema import read_fields
from config import REPO_ROOT, configured_path, load_config, load_settings
from zotero_local_api import ZoteroAPIError, ZoteroLocalAPI, item_details, pdf_children


class RetrievalError(RuntimeError):
    pass


FIELD = re.compile(r"(?m)^([A-Za-z_][\w-]*):[ \t]*['\"]?([^\r\n'\"]*)")


def frontmatter(path: Path) -> dict[str, str]:
    return read_fields(path)


def resolve_vault_path(vault: Path, path: str) -> Path:
    candidate = (vault / path.replace("\\", "/")).resolve()
    if not candidate.is_relative_to(vault.resolve()):
        raise RetrievalError(f"Path escapes the active Vault: {path}")
    return candidate


def terms_for(query: str) -> list[str]:
    """Language-neutral lexical hints; never a semantic sufficiency verdict."""
    terms: set[str] = set()
    for token in re.findall(r"[a-zA-Z0-9_]+|[\u3400-\u9fff]+", query.lower()):
        if re.search(r"[\u3400-\u9fff]", token):
            terms.add(token)
            if len(token) > 3:
                terms.update(token[i:i + 2] for i in range(len(token) - 1))
        elif len(token) > 2:
            terms.add(token)
    return sorted(terms, key=len, reverse=True)


def excerpts(body: str, query: str, *, limit: int = 3, max_chars: int = 750) -> list[dict]:
    # Navigation metadata and hidden identities are not source-text evidence.
    body = re.sub(r"\A---\s*\r?\n.*?\r?\n---\s*", "", body, count=1, flags=re.S)
    body = re.sub(r"<!-- researchvault-metadata\s+\{.*?\}\s*-->", "", body, flags=re.S)
    fragments = [piece.strip() for piece in re.split(r"\n\s*\n|(?<=。)\s*\n", body) if piece.strip()]
    terms = terms_for(query)
    ranked = []
    for number, fragment in enumerate(fragments, start=1):
        lower = fragment.casefold()
        score = sum(len(t) for t in terms if t in lower)
        if score:
            ranked.append((score, number, fragment))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [{"block": number, "score": score, "excerpt": fragment[:max_chars]}
            for score, number, fragment in ranked[:limit]]


def pdf_excerpts(pdf_path: Path, query: str, *, limit: int = 3) -> tuple[list[dict], str | None]:
    """Search real PDF pages when an optional local extractor is installed."""
    try:
        import pymupdf  # type: ignore[import-not-found]
    except ImportError:
        return [], "Install optional PyMuPDF (`py -m pip install pymupdf`) for PDF page extraction"
    ranked: list[tuple[int, int, dict]] = []
    try:
        with pymupdf.open(str(pdf_path)) as document:
            for index, page in enumerate(document, start=1):
                for hit in excerpts(page.get_text("text"), query, limit=2):
                    ranked.append((hit["score"], index, {"pdf_page": index, "excerpt": hit["excerpt"],
                                                           "score": hit["score"]}))
    except Exception as error:
        return [], f"Could not extract PDF text: {error}"
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [row[2] for row in ranked[:limit]], None


class RetrievalGateway:
    def __init__(self, vault: Path, *, config_path: Path | None = None,
                 zotero: ZoteroLocalAPI | None = None):
        self.vault = vault.expanduser().resolve()
        if not self.vault.is_dir():
            raise RetrievalError(f"Vault folder does not exist: {self.vault}")
        self.config_path = config_path
        settings = load_settings(config_path)
        self.notes_first = settings.get("retrieval", {}).get("notes_first", True)
        self.zotero_fallback = settings.get("retrieval", {}).get("zotero_fallback", True)
        self.sqlite_fallback = settings.get("zotero", {}).get("sqlite_readonly_fallback", True)
        base = settings.get("zotero", {}).get("local_api_base", "http://127.0.0.1:23119/api")
        self.zotero = zotero or ZoteroLocalAPI(base)

    def note_paths(self) -> list[Path]:
        roots = [self.vault / "02阅读笔记"]
        # Legacy folders are read-only during migration.
        roots.extend(self.vault / name for name in ("论文库", "note") if (self.vault / name).is_dir())
        notes = []
        for root in roots:
            if root.is_dir():
                for path in root.rglob("*.md"):
                    if "_index" not in path.parts and (frontmatter(path).get("type") in {"literature-note", "material-note"}
                                                      or frontmatter(path).get("zotero_key")):
                        notes.append(path)
        return sorted(set(notes))

    def search_notes(self, query: str, *, limit: int = 20) -> list[dict]:
        found = []
        for path in self.note_paths():
            hits = excerpts(path.read_text(encoding="utf-8-sig"), query, limit=2)
            if hits:
                fields = frontmatter(path)
                found.append({"zotero_key": fields.get("zotero_key"), "title": fields.get("title", path.stem),
                              "note_path": path.relative_to(self.vault).as_posix(), "score": hits[0]["score"],
                              "snippets": hits})
        return sorted(found, key=lambda row: -row["score"])[:limit]

    def search_zotero(self, query: str, *, library_type: str = "users", library_id: str = "0",
                      limit: int = 20) -> list[dict]:
        """Discover exact parent-item keys for metadata-only paper intake."""
        try:
            items = self.zotero.search_items(query, library_type=library_type,
                                             library_id=library_id, limit=limit)
        except ZoteroAPIError as error:
            raise RetrievalError(str(error)) from error
        return [item_details(item) for item in items if item.get("data", {}).get("itemType")
                not in {"attachment", "note", "annotation"}]

    def resolve_note(self, key: str, *, library_type: str = "users", library_id: str = "0") -> Path | None:
        matches = []
        for path in self.note_paths():
            fields = frontmatter(path)
            if fields.get("zotero_key") != key:
                continue
            # Existing notes without library identity belong to the default personal library.
            if fields.get("library_type", "users") == library_type and (fields.get("library_id", "0") == library_id or (library_type == "users" and library_id == "0")):
                matches.append(path)
        if len(matches) > 1:
            raise RetrievalError(f"Multiple Analytical Notes share the same Zotero identity: {key}")
        return matches[0] if matches else None

    def resolve_fulltext(self, key: str, note: Path | None, *, library_type: str = "users",
                         library_id: str = "0") -> Path | None:
        def matches_identity(path: Path) -> bool:
            fields = frontmatter(path)
            return (fields.get("zotero_key") == key
                    and fields.get("library_type", "users") == library_type
                    and (fields.get("library_id", "0") == library_id or (library_type == "users" and library_id == "0")))

        if note:
            link = frontmatter(note).get("fulltext_path", "").strip()
            if link:
                candidate = resolve_vault_path(self.vault, link)
                if candidate.is_file():
                    if not matches_identity(candidate):
                        raise RetrievalError(f"Fulltext identity mismatch: {candidate}")
                    return candidate
        root = self.vault / "03原始资料"
        candidates = []
        if root.is_dir():
            for path in root.rglob(f"{key}.md"):
                if matches_identity(path):
                    candidates.append(path)
        if len(candidates) > 1:
            raise RetrievalError(f"Multiple Fulltexts share Zotero key {key}")
        return candidates[0] if candidates else None

    def _sqlite_item(self, key: str) -> dict:
        config = load_config(self.config_path)
        cmd = [sys.executable, str(REPO_ROOT / "tools/zotero_readonly_fetch.py"), "--key", key]
        if self.config_path:
            cmd += ["--config", str(self.config_path)]
        if not (configured_path("zotero_data_dir", config) or config.get("zotero_data_dir")):
            # The helper can still discover common Zotero locations by itself.
            pass
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            raise RetrievalError(result.stderr.strip() or "Zotero SQLite read failed")
        return json.loads(result.stdout)

    def zotero_record(self, key: str, *, library_type: str = "users", library_id: str = "0") -> dict:
        try:
            item = self.zotero.get_item(key, library_type=library_type, library_id=library_id)
            metadata = item_details(item)
            children = self.zotero.get_children(key, library_type=library_type, library_id=library_id)
            attachments = pdf_children(children)
            metadata["pdf_attachments"] = [{"pdf_key": child.get("key") or child.get("data", {}).get("key"),
                                             "title": child.get("data", {}).get("title")}
                                           for child in attachments]
            metadata["transport"] = "local_api"
            return metadata
        except ZoteroAPIError as error:
            if not self.sqlite_fallback or library_type != "users" or library_id != "0":
                raise RetrievalError(str(error)) from error
            record = self._sqlite_item(key)
            record["transport"] = "sqlite_readonly"
            return record

    def evidence(self, key: str, query: str, *, library_type: str = "users", library_id: str = "0",
                 verify_original: bool = False, require_pdf_page: bool = False) -> dict:
        note = self.resolve_note(key, library_type=library_type, library_id=library_id)
        fulltext = self.resolve_fulltext(key, note, library_type=library_type, library_id=library_id)
        result: dict[str, Any] = {
            "identity": {"library_type": library_type, "library_id": library_id, "zotero_key": key},
            "question": query, "note_path": note.relative_to(self.vault).as_posix() if note else None,
            "fulltext_path": fulltext.relative_to(self.vault).as_posix() if fulltext else None,
            "evidence": [], "warnings": [], "write_performed": False,
        }
        if note and self.notes_first:
            note_hits = excerpts(note.read_text(encoding="utf-8-sig"), query)
            if note_hits:
                result["evidence"].append({"source": "analytical_note", "path": result["note_path"],
                                           "snippets": note_hits, "verification": "secondary_note"})
        if result["evidence"] and not verify_original and not require_pdf_page:
            note_status = frontmatter(note).get("note_status", "").casefold() if note else ""
            if note_status not in {"draft", "incomplete", "needs_review", "to_read"}:
                result["status"] = "note_candidates_require_agent_assessment"
                return result
            result["warnings"].append("The Note is marked draft/incomplete; original evidence fallback attempted")
        if fulltext and not require_pdf_page:
            hits = excerpts(fulltext.read_text(encoding="utf-8-sig"), query)
            if hits:
                result["evidence"].append({"source": "archived_fulltext", "source_type": frontmatter(fulltext).get("source_type", "unspecified"), "path": result["fulltext_path"],
                                           "snippets": hits, "verification": "original_text_no_verified_pdf_page"})
                result["status"] = "original_text_candidates"
                return result
        if not self.zotero_fallback:
            result["status"] = "insufficient_verified_evidence"
            result["warnings"].append("Zotero fallback disabled by configuration")
            return result
        try:
            record = self.zotero_record(key, library_type=library_type, library_id=library_id)
        except RetrievalError as error:
            result["warnings"].append(str(error))
            result["status"] = "source_unavailable"
            return result
        result["zotero"] = {k: v for k, v in record.items() if k not in {"annotations", "notes", "fulltext_cache"}}
        for attachment in record.get("pdf_attachments", []):
            attachment_key = attachment.get("pdf_key")
            if not attachment_key:
                continue
            pdf_path = None
            if record["transport"] == "local_api":
                try:
                    pdf_path = self.zotero.get_pdf_path(attachment_key, library_type=library_type, library_id=library_id)
                except ZoteroAPIError as error:
                    result["warnings"].append(str(error))
            else:
                pdf_path = Path(attachment["pdf_path"]) if attachment.get("pdf_path") else None
            if pdf_path and pdf_path.is_file():
                result["zotero_pdf_path"] = str(pdf_path)
            if require_pdf_page:
                if not pdf_path:
                    continue
                pdf_hits, warning = pdf_excerpts(pdf_path, query)
                if warning:
                    result["warnings"].append(warning)
                if pdf_hits:
                    result["evidence"].append({"source": "original_pdf", "pdf_key": attachment_key,
                                               "path": str(pdf_path), "snippets": pdf_hits,
                                               "verification": "pdf_page_extracted"})
                    result["status"] = "original_pdf_page_candidates"
                    return result
            elif record["transport"] == "local_api":
                try:
                    indexed = self.zotero.get_fulltext(attachment_key, library_type=library_type, library_id=library_id)
                except ZoteroAPIError as error:
                    result["warnings"].append(str(error))
                    indexed = None
                hits = excerpts(indexed["content"], query) if indexed else []
                if hits:
                    result["evidence"].append({"source": "zotero_indexed_text", "pdf_key": attachment_key,
                                               "snippets": hits, "verification": "original_text_no_verified_pdf_page"})
                    result["status"] = "original_text_candidates"
                    return result
            if pdf_path and not require_pdf_page:
                pdf_hits, warning = pdf_excerpts(pdf_path, query)
                if pdf_hits:
                    result["evidence"].append({"source": "original_pdf", "pdf_key": attachment_key,
                                               "path": str(pdf_path), "snippets": pdf_hits,
                                               "verification": "pdf_page_extracted"})
                    result["status"] = "original_pdf_page_candidates"
                    return result
                if warning:
                    result["warnings"].append(warning)
        result["status"] = "insufficient_verified_evidence"
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, help="Existing Obsidian Vault root")
    parser.add_argument("--config", type=Path, help="Local config.toml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check Vault and Zotero availability without writing")
    search = sub.add_parser("search-notes", help="Lexically search Analytical Notes")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=20)
    zotero_search = sub.add_parser("search-zotero", help="Find Zotero parent items and their keys")
    zotero_search.add_argument("--query", required=True)
    zotero_search.add_argument("--limit", type=int, default=20)
    zotero_search.add_argument("--library-type", choices=("users", "groups"), default="users")
    zotero_search.add_argument("--library-id", default="0")
    evidence = sub.add_parser("evidence", help="Read Note, matching Fulltext, then Zotero original evidence")
    evidence.add_argument("--key", required=True, help="Zotero parent item key")
    evidence.add_argument("--query", required=True)
    evidence.add_argument("--library-type", choices=("users", "groups"), default="users")
    evidence.add_argument("--library-id", default="0")
    evidence.add_argument("--verify-original", action="store_true")
    evidence.add_argument("--require-pdf-page", action="store_true")
    args = parser.parse_args()
    paths = load_config(args.config)
    vault = args.vault or configured_path("vault_root", paths)
    if not vault:
        parser.error("Set --vault or paths.vault_root in config.toml")
    try:
        gateway = RetrievalGateway(vault, config_path=args.config)
        if args.command == "doctor":
            try:
                gateway.zotero.probe()
                zotero = "available"
            except ZoteroAPIError as error:
                zotero = str(error)
            output = {"vault": str(gateway.vault), "notes": len(gateway.note_paths()),
                      "zotero_local_api": zotero, "write_performed": False}
        elif args.command == "search-notes":
            output = {"results": gateway.search_notes(args.query, limit=args.limit), "write_performed": False}
        elif args.command == "search-zotero":
            output = {"results": gateway.search_zotero(args.query, library_type=args.library_type,
                                                        library_id=args.library_id, limit=args.limit),
                      "write_performed": False}
        else:
            output = gateway.evidence(args.key, args.query, library_type=args.library_type,
                                      library_id=args.library_id, verify_original=args.verify_original,
                                      require_pdf_page=args.require_pdf_page)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except RetrievalError as error:
        print(json.dumps({"status": "error", "message": str(error), "write_performed": False},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
