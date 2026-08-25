from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

from proofline.public_record_request_scope import build_request_packet, stable_json

POLICY_URL = "https://www.akronohio.gov/departments/law/index.php"
EXPECTED_RECIPIENT = "publicrecords@akronohio.gov"
EXPECTED_HOSTS = {"www.akronohio.gov", "akronohio.gov"}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def normalize_html_text(raw: bytes) -> str:
    parser = TextExtractor()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch_policy() -> tuple[bytes, str, str]:
    req = urllib.request.Request(POLICY_URL, headers={"User-Agent": "Proofline-T21/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        final_url = response.geturl()
        parsed = urlparse(final_url)
        if parsed.scheme != "https" or parsed.hostname not in EXPECTED_HOSTS:
            raise ValueError("public-record policy redirected off official Akron host")
        raw = response.read()
    if not raw:
        raise ValueError("public-record policy returned empty body")
    return raw, final_url, normalize_html_text(raw)


def policy_contract(text: str) -> dict:
    folded = text.casefold()
    recipient_verified = EXPECTED_RECIPIENT in folded
    records_instruction = (
        "to file a public record request please email" in folded
        and "with what records you are seeking" in folded
    )
    law_oversees = "law department oversees public records requests" in folded
    if not recipient_verified or not records_instruction or not law_oversees:
        raise ValueError("City of Akron public-record request policy contract drifted")
    return {
        "schema": "proofline-akron-public-record-request-policy-contract/v1",
        "policy_url": POLICY_URL,
        "recipient": EXPECTED_RECIPIENT,
        "law_department_oversees_requests_verified": True,
        "records_only_instruction_verified": True,
        "email_submission_path_verified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    parser.add_argument("section38_receipt")
    parser.add_argument("target")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    plan_path = pathlib.Path(args.plan)
    section38_path = pathlib.Path(args.section38_receipt)
    target_path = pathlib.Path(args.target)
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plan = json.loads(plan_path.read_text())
    section38 = json.loads(section38_path.read_text())
    target = json.loads(target_path.read_text())
    policy_raw, final_url, policy_text = fetch_policy()
    contract = policy_contract(policy_text)
    packet = build_request_packet(plan, section38, target, contract)

    measurement = {
        "schema": "proofline-akron-t21-clerk-public-record-request-scope-measurement/v1",
        "source_receipts": {
            "plan": {"path": plan_path.name, "file_sha256": sha256_bytes(plan_path.read_bytes())},
            "section38": {
                "path": section38_path.name,
                "file_sha256": sha256_bytes(section38_path.read_bytes()),
                "measurement_signature_sha256": section38["measurement_signature_sha256"],
            },
            "target": {
                "path": target_path.name,
                "file_sha256": sha256_bytes(target_path.read_bytes()),
                "ordinance_title_sha256": target["ordinance_title_sha256"],
            },
        },
        "policy_contract": contract,
        "policy_page_provenance": {
            "requested_url": POLICY_URL,
            "final_url": final_url,
            "byte_length": len(policy_raw),
            "sha256": sha256_bytes(policy_raw),
            "normalized_text_sha256": sha256_bytes(policy_text.encode("utf-8")),
        },
        "request_packet": packet,
        "submission_performed": False,
    }
    measurement["measurement_signature_sha256"] = hashlib.sha256(
        stable_json({
            "source_receipts": measurement["source_receipts"],
            "policy_contract": contract,
            "request_packet": packet,
            "submission_performed": False,
        }).encode("utf-8")
    ).hexdigest()

    path = out_dir / "clerk-public-record-request-scope-measurement.json"
    path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n")
    (out_dir / "request-subject.txt").write_text(packet["delivery"]["subject"] + "\n")
    (out_dir / "request-body.txt").write_text(packet["delivery"]["body"] + "\n")
    print(json.dumps({
        "recipient": packet["delivery"]["recipient"],
        "category_count": len(packet["requested_existing_record_categories"]),
        "request_scope_signature_sha256": packet["request_scope_signature_sha256"],
        "delivery_signature_sha256": packet["delivery_signature_sha256"],
        "submission_performed": False,
        "outcome": packet["outcome"]["status"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
