from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

from proofline.disposition_surfaces import build_inventory, stable_json

LEGAL_NOTICES_URL = "https://www.akroncitycouncil.org/legal-notices"
LEGISLATION_MINUTES_URL = "https://www.akroncitycouncil.org/legislationminutes"
EXPECTED_HOST = "www.akroncitycouncil.org"


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def normalize_html_text(raw: bytes) -> str:
    parser = TextExtractor()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def fetch(url: str) -> tuple[bytes, str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != EXPECTED_HOST:
        raise ValueError("Council contract URL must remain HTTPS on the official Council host")
    req = urllib.request.Request(url, headers={"User-Agent": "Proofline-T21/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        final_url = response.geturl()
        final = urlparse(final_url)
        if final.scheme != "https" or final.hostname != EXPECTED_HOST:
            raise ValueError("Council page redirected off the official Council host")
        raw = response.read()
    if not raw:
        raise ValueError("official Council page returned empty body")
    return raw, final_url


def contains(text: str, phrase: str) -> bool:
    return phrase.casefold() in text.casefold()


def council_contract(legal_text: str, legislation_text: str) -> dict:
    contract = {
        "schema": "proofline-akron-t21-council-publication-contract/v1",
        "legal_notices_url": LEGAL_NOTICES_URL,
        "legislation_minutes_url": LEGISLATION_MINUTES_URL,
        "legal_notices_section38_declared": contains(
            legal_text, "In accordance with Section 38 of the Charter, Legal Notices will be published on a City of Akron website"
        ),
        "legal_notices_full_passed_list_points_to_agenda": contains(
            legal_text, "For a full list of Ordinances and Resolutions passed at each Council Meeting"
        ) and contains(legal_text, "view the Agenda"),
        "legislation_minutes_passed_archive_declared": contains(
            legislation_text, "Passed Legislation and Council Meeting Minutes are available on our documents portal"
        ),
        "legislation_minutes_municipal_code_declared": contains(
            legislation_text, "The Code of the City of Akron, also called the Municipal Code"
        ),
        "public_record_request_path_declared": contains(
            legislation_text, "For other public record requests, please see the Public Record Request Policy"
        ),
    }
    required = [
        "legal_notices_section38_declared",
        "legal_notices_full_passed_list_points_to_agenda",
        "legislation_minutes_passed_archive_declared",
        "legislation_minutes_municipal_code_declared",
        "public_record_request_path_declared",
    ]
    if not all(contract[key] for key in required):
        missing = [key for key in required if not contract[key]]
        raise ValueError(f"official Council publication declarations drifted: {missing}")
    return contract


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("public_access_receipt")
    parser.add_argument("chronology_receipt")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    public_access_path = pathlib.Path(args.public_access_receipt)
    chronology_path = pathlib.Path(args.chronology_receipt)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    public_access = json.loads(public_access_path.read_text())
    chronology = json.loads(chronology_path.read_text())

    legal_raw, legal_final = fetch(LEGAL_NOTICES_URL)
    legislation_raw, legislation_final = fetch(LEGISLATION_MINUTES_URL)
    legal_text = normalize_html_text(legal_raw)
    legislation_text = normalize_html_text(legislation_raw)
    contract = council_contract(legal_text, legislation_text)

    inventory = build_inventory(public_access, chronology, contract)
    measurement = {
        "schema": "proofline-akron-t21-disposition-surface-inventory-measurement/v1",
        "source_receipts": {
            "public_access": {
                "path": public_access_path.name,
                "file_sha256": sha256_bytes(public_access_path.read_bytes()),
                "custom_query_signature_sha256": public_access["custom_queries"]["signature_sha256"],
            },
            "chronology": {
                "path": chronology_path.name,
                "file_sha256": sha256_bytes(chronology_path.read_bytes()),
                "chronology_signature_sha256": chronology["chronology_signature_sha256"],
            },
        },
        "official_council_publication_contract": contract,
        "canonical_page_fetches": {
            "legal_notices": {
                "requested_url": LEGAL_NOTICES_URL,
                "final_url": legal_final,
                "byte_length": len(legal_raw),
                "sha256": sha256_bytes(legal_raw),
            },
            "legislation_minutes": {
                "requested_url": LEGISLATION_MINUTES_URL,
                "final_url": legislation_final,
                "byte_length": len(legislation_raw),
                "sha256": sha256_bytes(legislation_raw),
            },
        },
        "inventory": inventory,
    }
    measurement["inventory_signature_sha256"] = hashlib.sha256(
        stable_json(inventory).encode("utf-8")
    ).hexdigest()

    out = output_dir / "disposition-surface-inventory-measurement.json"
    out.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "surface_count": inventory["counts"]["surface_count"],
        "tested_count": inventory["counts"]["tested_count"],
        "selected_next_surface_id": inventory["selected_next_surface_id"],
        "inventory_signature_sha256": measurement["inventory_signature_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
