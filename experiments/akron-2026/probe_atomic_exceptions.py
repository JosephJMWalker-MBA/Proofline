from __future__ import annotations

import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

URLS = (
    "https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/Meetings/ViewMeetingAgendaItem?meetingId=681&itemId=47515&isSection=false&type=agenda",
    "https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/Meetings/ViewMeetingAgendaItem?meetingId=684&itemId=47717&isSection=false&type=agenda",
    "https://onlinedocs.akronohio.gov/OnBaseAgendaOnline/Meetings/ViewMeetingAgendaItem?meetingId=695&itemId=48818&isSection=false&type=agenda",
)


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def value(self) -> str:
        return "\n".join(self.parts)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "akron-atomic-exceptions")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, url in enumerate(URLS, start=1):
        request = Request(
            url,
            headers={"User-Agent": "Proofline/0.1 bounded public-record exception probe"},
        )
        with urlopen(request, timeout=30) as response:
            body = response.read(2_000_000)
            content_type = response.headers.get("Content-Type")
        source = body.decode("utf-8", errors="replace")
        parser = VisibleText()
        parser.feed(source)
        visible = parser.value()
        start = visible.find("Item Details")
        start = start + len("Item Details") if start >= 0 else 0
        support = visible.find("Supporting Documents", start)
        back = visible.find("Back to Meeting Outline", start)
        ends = [value for value in (support, back) if value >= 0]
        end = min(ends) if ends else len(visible)
        item_body = visible[start:end].strip()
        (out / f"exception-{index}.html").write_text(source, encoding="utf-8")
        (out / f"exception-{index}.txt").write_text(visible, encoding="utf-8")
        rows.append(
            {
                "url": url,
                "content_type": content_type,
                "byte_length": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "visible_text_chars": len(visible),
                "item_body": item_body,
                "item_body_chars": len(item_body),
                "item_details_count": visible.count("Item Details"),
                "back_to_outline_count": visible.count("Back to Meeting Outline"),
                "supporting_documents_count": visible.count("Supporting Documents"),
            }
        )
    (out / "exceptions.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(rows, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
