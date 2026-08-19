from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE = "https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/"
URLS = {
    "home": BASE,
    "meetings": urljoin(BASE, "Meetings"),
    "meeting-663": urljoin(BASE, "Meetings/ViewMeeting?doctype=1&id=663"),
    "meeting-669": urljoin(BASE, "Meetings/ViewMeeting?doctype=1&id=669"),
    "meeting-678": urljoin(BASE, "Meetings/ViewMeeting?doctype=1&id=678"),
    "meeting-686": urljoin(BASE, "Meetings/ViewMeeting?doctype=1&id=686"),
    "meeting-692": urljoin(BASE, "Meetings/ViewMeeting?doctype=1&id=692"),
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict] = []
        self.forms: list[dict] = []
        self.inputs: list[dict] = []
        self._anchor: dict | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {key: value for key, value in attrs}
        if tag == "a":
            self._anchor = {
                "href": attributes.get("href"),
                "title": attributes.get("title"),
                "id": attributes.get("id"),
                "text": [],
            }
        elif tag == "form":
            self.forms.append(
                {
                    "action": attributes.get("action"),
                    "method": attributes.get("method"),
                    "id": attributes.get("id"),
                }
            )
        elif tag in {"input", "select", "option"}:
            self.inputs.append(
                {
                    "tag": tag,
                    "name": attributes.get("name"),
                    "id": attributes.get("id"),
                    "value": attributes.get("value"),
                    "type": attributes.get("type"),
                    "selected": "selected" in attributes,
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor is not None:
            self._anchor["text"] = " ".join(" ".join(self._anchor["text"]).split())
            self.anchors.append(self._anchor)
            self._anchor = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._text.append(text)
            if self._anchor is not None:
                self._anchor["text"].append(text)

    @property
    def visible_text(self) -> str:
        return "\n".join(self._text)


def fetch(url: str, *, timeout: float = 30.0, maximum_bytes: int = 25_000_000) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": "Proofline/0.1 public-record source-contract probe",
            "Accept": "text/html,application/pdf,application/octet-stream;q=0.9,*/*;q=0.5",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(maximum_bytes + 1)
            if len(body) > maximum_bytes:
                raise RuntimeError(f"response exceeded {maximum_bytes} bytes")
            return {
                "ok": True,
                "requested_url": url,
                "final_url": response.geturl(),
                "status": getattr(response, "status", 200),
                "content_type": response.headers.get("Content-Type"),
                "content_length_header": response.headers.get("Content-Length"),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "body": body,
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "requested_url": url,
            "final_url": exc.geturl(),
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "error": f"HTTP {exc.code}: {exc.reason}",
            "body": exc.read(1_000_000),
        }
    except (URLError, TimeoutError, RuntimeError) as exc:
        return {
            "ok": False,
            "requested_url": url,
            "final_url": url,
            "status": None,
            "content_type": None,
            "error": str(exc),
            "body": b"",
        }


def page_record(name: str, result: dict, output: Path) -> dict:
    body: bytes = result.pop("body")
    record = dict(result)
    record["byte_length"] = len(body)
    record["sha256"] = hashlib.sha256(body).hexdigest()
    record["magic_hex"] = body[:16].hex()
    record["same_host"] = urlparse(record["requested_url"]).hostname == urlparse(record["final_url"]).hostname

    content_type = (record.get("content_type") or "").casefold()
    if "html" in content_type or body.lstrip().startswith((b"<!DOCTYPE", b"<html", b"<HTML")):
        text = body.decode("utf-8", errors="replace")
        parser = PageParser()
        parser.feed(text)
        visible = parser.visible_text
        record["visible_text_chars"] = len(visible)
        record["substantive_markers"] = {
            "council_agenda": bool(re.search(r"Council\s+Agenda", visible, re.I)),
            "ordinance": bool(re.search(r"\bORDINANCE\b", visible, re.I)),
            "resolution": bool(re.search(r"\bRESOLUTION\b", visible, re.I)),
        }
        record["anchors"] = parser.anchors
        record["forms"] = parser.forms
        record["form_controls"] = parser.inputs
        record["visible_text_preview"] = visible[:2500]
        (output / f"{name}.html").write_text(text, encoding="utf-8")
    return record


def agenda_links(page: dict) -> list[str]:
    links: list[str] = []
    for anchor in page.get("anchors", []):
        href = anchor.get("href") or ""
        title = anchor.get("title") or ""
        text = anchor.get("text") or ""
        if "documents/download" not in href.casefold():
            continue
        if "agenda" not in (title + " " + text + " " + href).casefold():
            continue
        absolute = urljoin(BASE, href)
        if urlparse(absolute).hostname != "onlinedocs.akronohio.gov":
            continue
        if absolute not in links:
            links.append(absolute)
    return links


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-probe-results")
    output.mkdir(parents=True, exist_ok=True)
    pages: dict[str, dict] = {}
    for name, url in URLS.items():
        result = fetch(url)
        pages[name] = page_record(name, result, output)

    discovered_agendas: list[dict] = []
    seen: set[str] = set()
    for name, page in pages.items():
        if not name.startswith("meeting-"):
            continue
        for url in agenda_links(page):
            if url in seen:
                continue
            seen.add(url)
            result = fetch(url)
            body: bytes = result.pop("body")
            record = dict(result)
            record["source_page"] = name
            record["byte_length"] = len(body)
            record["sha256"] = hashlib.sha256(body).hexdigest()
            record["magic_hex"] = body[:16].hex()
            record["is_pdf_magic"] = body.startswith(b"%PDF")
            record["same_host"] = urlparse(record["requested_url"]).hostname == urlparse(record["final_url"]).hostname
            discovered_agendas.append(record)
            if record["is_pdf_magic"] and len([p for p in output.glob("sample-agenda-*.pdf")]) < 2:
                index = len([p for p in output.glob("sample-agenda-*.pdf")]) + 1
                (output / f"sample-agenda-{index}.pdf").write_bytes(body)

    summary = {
        "schema": "proofline-akron-onbase-probe/v1",
        "base": BASE,
        "pages": pages,
        "agenda_downloads": discovered_agendas,
        "counts": {
            "page_requests": len(pages),
            "successful_pages": sum(1 for page in pages.values() if page.get("ok")),
            "meeting_pages": sum(1 for name in pages if name.startswith("meeting-")),
            "successful_meeting_pages": sum(
                1 for name, page in pages.items() if name.startswith("meeting-") and page.get("ok")
            ),
            "substantive_meeting_html": sum(
                1
                for name, page in pages.items()
                if name.startswith("meeting-")
                and page.get("substantive_markers", {}).get("ordinance")
            ),
            "publisher_agenda_links": len(seen),
            "successful_agenda_downloads": sum(1 for item in discovered_agendas if item.get("ok")),
            "pdf_magic_downloads": sum(1 for item in discovered_agendas if item.get("is_pdf_magic")),
        },
        "limitations": [
            "This is a bounded source-contract probe, not a production discovery adapter.",
            "The selected meeting IDs came from official/search-visible Akron meeting pages; the probe does not sweep numeric IDs.",
            "No result is treated as evidence of wrongdoing or omission; failures describe publisher transport behavior only.",
        ],
    }
    (output / "probe.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))

    if summary["counts"]["successful_meeting_pages"] < 3:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
