"""Read Zotero Desktop through its documented, local, read-only HTTP API.

No Zotero database writes, credentials, external hosts or third-party packages.
"""
from __future__ import annotations

import json
from journal_metadata import journal_metadata
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen, url2pathname


class ZoteroAPIError(RuntimeError):
    """An unavailable endpoint, permission error or invalid Zotero response."""


class ZoteroLocalAPI:
    def __init__(self, base_url: str = "http://127.0.0.1:23119/api", timeout: float = 5):
        address = urlsplit(base_url)
        if (address.scheme != "http" or address.hostname not in {"localhost", "127.0.0.1", "::1"}
                or address.username or address.password or address.query or address.fragment):
            raise ValueError("Zotero Local API must use a loopback HTTP address")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, path: str, params: dict[str, str | int] | None = None) -> bytes:
        if path.startswith("/") or ".." in path.split("/"):
            raise ValueError("API paths must be relative and cannot traverse directories")
        url = f"{self.base_url}/{path}"
        if params:
            url += "?" + urlencode(params)
        request = Request(url, headers={"Accept": "application/json", "Zotero-API-Version": "3"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as error:
            if error.code == 403:
                raise ZoteroAPIError("Zotero Local API is disabled (HTTP 403); enable it in Zotero Settings → Advanced") from error
            if error.code == 404:
                raise ZoteroAPIError(f"Zotero resource was not found: {path}") from error
            raise ZoteroAPIError(f"Zotero API HTTP {error.code} for {path}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise ZoteroAPIError("Cannot reach Zotero Local API; start Zotero and enable its local API") from error

    def _json(self, path: str, params: dict[str, str | int] | None = None):
        try:
            return json.loads(self._request(path, params).decode("utf-8"))
        except (ValueError, UnicodeError) as error:
            raise ZoteroAPIError(f"Invalid JSON returned by Zotero for {path}") from error

    @staticmethod
    def _prefix(library_type: str, library_id: str | int) -> str:
        if library_type not in {"users", "groups"}:
            raise ValueError("library_type must be users or groups")
        identifier = str(library_id)
        if not identifier.isdecimal():
            raise ValueError("library_id must be numeric")
        return f"{library_type}/{identifier}"

    @staticmethod
    def _key(key: str) -> str:
        if not key or not key.isalnum():
            raise ValueError("Zotero item key must be alphanumeric")
        return quote(key)

    def probe(self) -> dict:
        self._request("")
        return {"available": True}

    def search_items(self, query: str, *, library_type: str = "users", library_id: str | int = 0,
                     limit: int = 30) -> list[dict]:
        path = f"{self._prefix(library_type, library_id)}/items/top"
        result = self._json(path, {"q": query, "limit": max(1, min(limit, 100))})
        if not isinstance(result, list):
            raise ZoteroAPIError("Zotero item search did not return a list")
        return result

    def get_item(self, key: str, *, library_type: str = "users", library_id: str | int = 0) -> dict:
        return self._json(f"{self._prefix(library_type, library_id)}/items/{self._key(key)}")

    def get_children(self, key: str, *, library_type: str = "users", library_id: str | int = 0) -> list[dict]:
        result = self._json(f"{self._prefix(library_type, library_id)}/items/{self._key(key)}/children")
        if not isinstance(result, list):
            raise ZoteroAPIError("Zotero child attachments did not return a list")
        return result

    def get_fulltext(self, attachment_key: str, *, library_type: str = "users",
                     library_id: str | int = 0) -> dict | None:
        try:
            data = self._json(f"{self._prefix(library_type, library_id)}/items/{self._key(attachment_key)}/fulltext")
        except ZoteroAPIError as error:
            if "not found" in str(error):
                return None
            raise
        return data if isinstance(data, dict) and isinstance(data.get("content"), str) else None

    def get_pdf_path(self, attachment_key: str, *, library_type: str = "users",
                     library_id: str | int = 0) -> Path | None:
        path = f"{self._prefix(library_type, library_id)}/items/{self._key(attachment_key)}/file/view/url"
        try:
            uri = self._request(path).decode("utf-8").strip()
        except ZoteroAPIError as error:
            if "not found" in str(error):
                return None
            raise
        address = urlsplit(uri)
        if address.scheme != "file" or address.netloc not in {"", "localhost"}:
            return None
        filename = url2pathname(unquote(address.path))
        candidate = Path(filename).resolve()
        return candidate if candidate.is_file() and candidate.suffix.lower() == ".pdf" else None


def pdf_children(children: list[dict]) -> list[dict]:
    return [item for item in children if item.get("data", {}).get("itemType") == "attachment"
            and item.get("data", {}).get("contentType") == "application/pdf"]


def item_details(item: dict) -> dict:
    data = item.get("data", {})
    creators = data.get("creators", [])
    return {
        "zotero_key": item.get("key") or data.get("key"),
        "title": data.get("title"),
        "author": "; ".join(" ".join(filter(None, (c.get("firstName"), c.get("lastName")))) or
                            c.get("name", "") for c in creators),
        "year": (data.get("date") or "")[:4],
        "doi": data.get("DOI"),
        **journal_metadata(data),
        "tags": data.get("tags", []),
        "extra": data.get("extra", ""),
        "collections": data.get("collections", []),
        "zotero_item": item.get("links", {}).get("alternate", {}).get("href"),
    }
