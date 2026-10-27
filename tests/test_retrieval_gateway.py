"""Offline contract tests; a fake loopback API stands in for Zotero Desktop."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from create_note_draft import prepare_draft
from init_vault import initialize
from retrieval_gateway import RetrievalError, RetrievalGateway, resolve_vault_path
from zotero_local_api import ZoteroAPIError, ZoteroLocalAPI


class FakeZotero(BaseHTTPRequestHandler):
    pdf_uri = ""
    calls: list[str] = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        self.calls.append(path)
        item = {"key": "ABCD1234", "data": {"key": "ABCD1234", "title": "A study of building height",
                                             "date": "2024", "DOI": "10.example/123",
                                             "creators": [{"firstName": "Jane", "lastName": "Doe"}]}}
        children = [{"key": "PDFK1234", "data": {"itemType": "attachment",
                                                     "contentType": "application/pdf", "title": "Paper PDF"}}]
        if path == "/api/":
            content = b"{}"
        elif path == "/api/users/0/items/ABCD1234":
            content = json.dumps(item).encode()
        elif path == "/api/users/0/items/ABCD1234/children":
            content = json.dumps(children).encode()
        elif path == "/api/users/0/items/PDFK1234/fulltext":
            content = json.dumps({"content": "The study used random forest with 120 trees.\n\n"
                                                  "The robustness check used 10-fold validation."}).encode()
        elif path == "/api/users/0/items/PDFK1234/file/view/url":
            content = self.pdf_uri.encode()
        elif path == "/api/users/0/items/top":
            content = json.dumps([item]).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Compare canonical paths even when Windows TEMP uses a short-name alias.
        self.root = Path(self.tmp.name).resolve()
        self.vault = self.root / "New Research Vault"
        self.config = self.root / "config.toml"
        initialize(self.vault, self.config, with_codex=True)
        self.pdf = self.root / "article.pdf"
        self.pdf.write_bytes(b"Not a real PDF for the offline API contract test")
        FakeZotero.pdf_uri = self.pdf.as_uri()
        FakeZotero.calls = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeZotero)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.api = ZoteroLocalAPI(f"http://127.0.0.1:{self.server.server_port}/api")
        self.gateway = RetrievalGateway(self.vault, config_path=self.config, zotero=self.api)

    def add_note(self, path="02阅读笔记/Building/article.md", body="Building height affects demand."):
        target = self.vault / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\ntype: literature-note\ntitle: A study of building height\n"
                          "zotero_key: ABCD1234\npdf_key: PDFK1234\n---\n\n" + body, encoding="utf-8")
        return target

    def test_new_vault_is_idempotent_and_has_codex_guidance(self):
        self.assertTrue((self.vault / "AGENTS.md").is_file())
        self.assertTrue((self.vault / "00_开始使用.md").is_file())
        self.assertEqual(initialize(self.vault, self.config, with_codex=True), [])

    def test_api_read_only_metadata_and_attachment_lookup(self):
        record = self.gateway.zotero_record("ABCD1234")
        record["title_zh"] = "建筑高度研究"
        self.assertEqual(record["zotero_key"], "ABCD1234")
        self.assertEqual(record["pdf_attachments"][0]["pdf_key"], "PDFK1234")
        self.assertEqual(self.api.get_pdf_path("PDFK1234"), self.pdf)
        self.assertEqual(len(self.api.search_items("height")), 1)
        self.assertEqual(self.gateway.search_zotero("height")[0]["zotero_key"], "ABCD1234")

    def test_note_first_while_original_evidence_requires_explicit_followup(self):
        self.add_note(body="The authors used random forest.")
        first = self.gateway.evidence("ABCD1234", "random forest")
        self.assertEqual(first["status"], "note_candidates_require_agent_assessment")
        self.assertEqual([x["source"] for x in first["evidence"]], ["analytical_note"])
        self.assertFalse(any("fulltext" in call for call in FakeZotero.calls))
        verified = self.gateway.evidence("ABCD1234", "120 trees", verify_original=True)
        self.assertEqual(verified["evidence"][-1]["source"], "zotero_indexed_text")
        self.assertEqual(verified["evidence"][-1]["verification"], "original_text_no_verified_pdf_page")
        self.assertFalse(verified["write_performed"])

    def test_draft_note_automatically_continues_into_zotero_original(self):
        self.add_note(body="The authors used random forest.").write_text(
            "---\ntype: literature-note\nzotero_key: ABCD1234\nnote_status: draft\n---\n\n"
            "The authors used random forest.", encoding="utf-8")
        result = self.gateway.evidence("ABCD1234", "random forest")
        self.assertEqual([item["source"] for item in result["evidence"]],
                         ["analytical_note", "zotero_indexed_text"])
        self.assertEqual(result["status"], "original_text_candidates")

    def test_fulltext_precedes_zotero_lookup(self):
        note = self.add_note()
        full = self.vault / "03原始资料/Building/ABCD1234.md"
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("---\ntype: literature-fulltext\nzotero_key: ABCD1234\n"
                        "note_path: 02阅读笔记/Building/article.md\n---\n\n120 trees were used.", encoding="utf-8")
        note.write_text(note.read_text(encoding="utf-8").replace("pdf_key: PDFK1234",
                          "pdf_key: PDFK1234\nfulltext_path: 03原始资料/Building/ABCD1234.md"), encoding="utf-8")
        result = self.gateway.evidence("ABCD1234", "120 trees", verify_original=True)
        self.assertEqual(result["evidence"][-1]["source"], "archived_fulltext")
        self.assertEqual(FakeZotero.calls, [])

    def test_missing_note_can_still_resolve_exact_zotero_key(self):
        result = self.gateway.evidence("ABCD1234", "10-fold", verify_original=True)
        self.assertIsNone(result["note_path"])
        self.assertEqual(result["evidence"][0]["source"], "zotero_indexed_text")

    def test_group_identity_does_not_inherit_personal_fulltext(self):
        full = self.vault / "03原始资料/Building/ABCD1234.md"
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("---\nzotero_key: ABCD1234\n---\n\nPersonal library only", encoding="utf-8")
        self.assertIsNone(self.gateway.resolve_fulltext("ABCD1234", None,
                                                        library_type="groups", library_id="12"))

    def test_ambiguous_identity_and_path_escape_are_rejected(self):
        self.add_note()
        self.add_note("02阅读笔记/Other/duplicate.md")
        with self.assertRaises(RetrievalError):
            self.gateway.resolve_note("ABCD1234")
        with self.assertRaises(RetrievalError):
            resolve_vault_path(self.vault, "../../outside.md")

    def test_pdf_page_is_never_invented(self):
        result = self.gateway.evidence("ABCD1234", "120 trees", require_pdf_page=True)
        self.assertEqual(result["status"], "insufficient_verified_evidence")
        self.assertFalse(any("pdf_page" in snippet for item in result["evidence"]
                             for snippet in item["snippets"]))

    def test_actual_pdf_page_comes_from_opened_pdf(self):
        try:
            import pymupdf
        except ImportError:
            self.skipTest("Optional PyMuPDF not installed")
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((72, 72), "The coefficient of building height is 0.42.")
        document.save(str(self.pdf))
        document.close()
        result = self.gateway.evidence("ABCD1234", "coefficient building height", require_pdf_page=True)
        self.assertEqual(result["status"], "original_pdf_page_candidates")
        self.assertEqual(result["evidence"][-1]["source"], "original_pdf")
        self.assertEqual(result["evidence"][-1]["snippets"][0]["pdf_page"], 1)

    def test_reject_remote_api_and_uncertain_multiple_pdf_attachments(self):
        with self.assertRaises(ValueError):
            ZoteroLocalAPI("https://api.zotero.org")
        record = self.gateway.zotero_record("ABCD1234")
        record["title_zh"] = "建筑高度研究"
        record["pdf_attachments"].append({"pdf_key": "OTHERPDF"})
        with self.assertRaises(RetrievalError):
            prepare_draft(self.vault, record)

    def test_note_draft_does_not_write_until_requested(self):
        record = self.gateway.zotero_record("ABCD1234")
        record["title_zh"] = "建筑高度研究"
        target, content = prepare_draft(self.vault, record, collection="建筑/环境")
        self.assertFalse(target.exists())
        self.assertIn('"zotero_key":"ABCD1234"', content)
        self.assertIn('"note_status":"draft"', content)
        self.assertIn("本文件仅依据Zotero元数据建立草稿", content)
        self.assertTrue(target.is_relative_to(self.vault))


if __name__ == "__main__":
    unittest.main()
