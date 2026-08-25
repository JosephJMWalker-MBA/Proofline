from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from probe_onbase import BASE, PageParser, fetch

SEARCH_URL = urljoin(
    BASE,
    "Meetings/Search?dropid=11&mtids=101&dropsv=01%2F01%2F2026&dropev=08%2F19%2F2026",
)


def html_text_and_anchors(body: bytes) -> tuple[str, list[dict], str]:
    source = body.decode("utf-8", errors="replace")
    parser = PageParser()
    parser.feed(source)
    return parser.visible_text, parser.anchors, source


def search_result_payload(source: str) -> dict:
    matches = re.findall(
        r"showSearchResults\(new SearchResults\((\{.*?\})\)\);",
        source,
        flags=re.DOTALL,
    )
    payloads = []
    for match in matches:
        try:
            payloads.append(json.loads(match))
        except json.JSONDecodeError:
            continue
    if not payloads:
        raise RuntimeError("no embedded SearchResults JSON found")
    return max(payloads, key=lambda item: len(item.get("Meetings") or []))


def response_record(result: dict, body: bytes) -> dict:
    record = {key: value for key, value in result.items() if key != "body"}
    record["byte_length"] = len(body)
    record["sha256"] = hashlib.sha256(body).hexdigest()
    record["magic_hex"] = body[:16].hex()
    record["is_pdf_magic"] = body.startswith(b"%PDF")
    record["same_host"] = (
        urlparse(record["requested_url"]).hostname
        == urlparse(record["final_url"]).hostname
    )
    return record


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-data-probe-results")
    output.mkdir(parents=True, exist_ok=True)

    search = fetch(SEARCH_URL)
    search_body = search["body"]
    search_record = response_record(search, search_body)
    visible, anchors, source = html_text_and_anchors(search_body)
    (output / "search-2026.html").write_text(source, encoding="utf-8")
    search_record["visible_text_chars"] = len(visible)
    search_record["anchor_count"] = len(anchors)

    payload = search_result_payload(source)
    meetings = payload.get("Meetings") or []
    meeting_rows = []
    for meeting in meetings:
        meeting_rows.append(
            {
                "id": meeting.get("ID"),
                "name": meeting.get("Name"),
                "meeting_type": meeting.get("MeetingTypeName"),
                "time": meeting.get("Time"),
                "is_agenda_available": meeting.get("IsAgendaAvailable"),
                "agenda_unique_name": meeting.get("AgendaUniqueName"),
                "latest_document_type": meeting.get("LatestDocumentType"),
            }
        )

    preferred_ids = [663, 686, 692]
    samples = [meeting for meeting in meetings if meeting.get("ID") in preferred_ids]
    if len(samples) < 2:
        samples = [meeting for meeting in meetings if meeting.get("IsAgendaAvailable")][:3]

    agenda_records = []
    for meeting in samples:
        meeting_id = int(meeting["ID"])
        agenda_tree_url = urljoin(
            BASE,
            f"Documents/ViewAgenda?meetingId={meeting_id}&type=agenda&doctype=1",
        )
        tree_result = fetch(agenda_tree_url)
        tree_body = tree_result["body"]
        tree_record = response_record(tree_result, tree_body)
        tree_visible, tree_anchors, tree_source = html_text_and_anchors(tree_body)
        tree_record["visible_text_chars"] = len(tree_visible)
        tree_record["ordinance_marker"] = bool(re.search(r"\bORDINANCE\b", tree_visible, re.I))
        tree_record["resolution_marker"] = bool(re.search(r"\bRESOLUTION\b", tree_visible, re.I))
        tree_record["item_links"] = [
            anchor
            for anchor in tree_anchors
            if "loadAgendaItem" in (anchor.get("href") or "")
        ][:25]
        (output / f"agenda-tree-{meeting_id}.html").write_text(tree_source, encoding="utf-8")

        unique_name = meeting.get("AgendaUniqueName")
        pdf_record = None
        if unique_name:
            pdf_url = urljoin(
                BASE,
                "Documents/DownloadFileBytes/"
                + quote(str(unique_name), safe="")
                + f".pdf?documentType=1&meetingId={meeting_id}",
            )
            pdf_result = fetch(pdf_url)
            pdf_body = pdf_result["body"]
            pdf_record = response_record(pdf_result, pdf_body)
            if pdf_record["is_pdf_magic"]:
                (output / f"agenda-{meeting_id}.pdf").write_bytes(pdf_body)

        item_ids = []
        for anchor in tree_anchors:
            href = anchor.get("href") or ""
            match = re.search(r"loadAgendaItem\((\d+),(true|false)\)", href, re.I)
            if match and match.group(2).casefold() == "false":
                item_id = int(match.group(1))
                if item_id not in item_ids:
                    item_ids.append(item_id)
            if len(item_ids) >= 2:
                break

        item_records = []
        for item_id in item_ids:
            item_url = urljoin(
                BASE,
                f"Meetings/ViewMeetingAgendaItem?meetingId={meeting_id}&itemId={item_id}&isSection=false&type=agenda",
            )
            item_result = fetch(item_url)
            item_body = item_result["body"]
            item_record = response_record(item_result, item_body)
            item_visible, item_anchors, item_source = html_text_and_anchors(item_body)
            item_record["item_id"] = item_id
            item_record["visible_text_chars"] = len(item_visible)
            item_record["visible_text_preview"] = item_visible[:1800]
            item_record["anchors"] = item_anchors[:25]
            (output / f"agenda-item-{meeting_id}-{item_id}.html").write_text(
                item_source, encoding="utf-8"
            )
            item_records.append(item_record)

        agenda_records.append(
            {
                "meeting_id": meeting_id,
                "agenda_unique_name": unique_name,
                "agenda_tree": tree_record,
                "agenda_pdf": pdf_record,
                "agenda_items": item_records,
            }
        )

    expected_pdf_samples = sum(1 for meeting in samples if meeting.get("AgendaUniqueName"))
    result = {
        "schema": "proofline-akron-onbase-data-probe/v1",
        "search": search_record,
        "search_payload": {
            "meeting_type_ids": payload.get("MeetingTypeIDs"),
            "date_range_option_id": payload.get("DateRangeOptionID"),
            "from_display_date": payload.get("FromDisplayDate"),
            "to_display_date": payload.get("ToDisplayDate"),
            "no_more_results": payload.get("NoMoreResults"),
            "meeting_count": len(meetings),
            "meetings": meeting_rows,
        },
        "agenda_samples": agenda_records,
        "counts": {
            "meetings_discovered": len(meetings),
            "agendas_available": sum(1 for meeting in meetings if meeting.get("IsAgendaAvailable")),
            "sample_agenda_trees": len(agenda_records),
            "expected_pdf_samples": expected_pdf_samples,
            "substantive_agenda_trees": sum(
                1
                for row in agenda_records
                if row["agenda_tree"].get("ordinance_marker")
                or row["agenda_tree"].get("resolution_marker")
            ),
            "pdf_magic_downloads": sum(
                1 for row in agenda_records if row.get("agenda_pdf", {}).get("is_pdf_magic")
            ),
            "agenda_item_responses": sum(len(row["agenda_items"]) for row in agenda_records),
            "substantive_agenda_items": sum(
                1
                for row in agenda_records
                for item in row["agenda_items"]
                if item.get("visible_text_chars", 0) >= 80
            ),
        },
        "limitations": [
            "This probe uses only the publisher-declared search, agenda-tree, item-detail, and DownloadFileBytes routes.",
            "The custom 2026 range is fixed for the transfer experiment and is not yet production scheduling logic.",
            "No Canton semantic policy is applied to Akron content in this probe.",
        ],
    }
    (output / "data-probe.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result["counts"], indent=2, sort_keys=True))

    counts = result["counts"]
    if not search_record.get("ok") or len(meetings) < 10:
        return 2
    if expected_pdf_samples < 1 or counts["pdf_magic_downloads"] != expected_pdf_samples:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
