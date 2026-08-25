"""Structural association of OnBase agenda items with publisher status headings.

OnBase agenda-tree HTML renders status headings and agenda items as sibling outer
``table`` blocks. This parser preserves that publisher structure: a recognized
status block applies only to subsequent item blocks until another non-item block
appears. Arbitrary proximity in rendered text is never sufficient.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser

from .agenda_status import AgendaStatusObservation, classify_agenda_status_label

_AGENDA_ITEM_CALL_RE = re.compile(
    r"loadAgendaItem\(\s*(?P<item_id>\d+)\s*,\s*(?P<is_section>true|false)\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class OnBaseAgendaStatusAssignment:
    meeting_id: int
    item_id: int
    item_text: str
    item_block_index: int
    status_block_index: int | None
    status: AgendaStatusObservation | None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["status"] = self.status.to_dict() if self.status is not None else None
        return payload


@dataclass(frozen=True, slots=True)
class _TableBlock:
    block_index: int
    text: str
    item_links: tuple[tuple[int, str], ...]


class _OuterTableParser(HTMLParser):
    """Reduce agenda HTML to ordered publisher outer-table blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self._parts: list[str] = []
        self._item_links: list[tuple[int, str]] = []
        self._href: str | None = None
        self._anchor_parts: list[str] = []
        self.blocks: list[_TableBlock] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        folded = tag.casefold()
        if folded == "table":
            if self.table_depth == 0:
                self._parts = []
                self._item_links = []
            self.table_depth += 1
            return
        if self.table_depth and folded == "a" and self._href is None:
            href = dict(attrs).get("href")
            if isinstance(href, str):
                self._href = href
                self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self.table_depth:
            self._parts.append(data)
        if self._href is not None:
            self._anchor_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        folded = tag.casefold()
        if self.table_depth and folded == "a" and self._href is not None:
            href = self._href
            text = " ".join("".join(self._anchor_parts).split())
            self._href = None
            self._anchor_parts = []
            match = _AGENDA_ITEM_CALL_RE.search(href)
            if match and match.group("is_section").casefold() == "false":
                self._item_links.append((int(match.group("item_id")), text))
            return
        if folded != "table" or self.table_depth == 0:
            return
        self.table_depth -= 1
        if self.table_depth != 0:
            return
        self.blocks.append(
            _TableBlock(
                block_index=len(self.blocks),
                text=" ".join("".join(self._parts).split()),
                item_links=tuple(self._item_links),
            )
        )
        self._parts = []
        self._item_links = []


def extract_onbase_agenda_status_assignments(
    html: str,
    *,
    meeting_id: int,
) -> tuple[OnBaseAgendaStatusAssignment, ...]:
    """Associate agenda items with explicit status blocks using publisher structure.

    A recognized status table remains active across consecutive agenda-item tables.
    Any other non-item table resets it, preventing status leakage across committee or
    section boundaries. ``NO ITEMS`` is section metadata and therefore also resets
    rather than becoming an item status.
    """
    if not isinstance(html, str):
        raise TypeError("html must be a string")
    if not isinstance(meeting_id, int) or meeting_id <= 0:
        raise ValueError("meeting_id must be a positive integer")

    parser = _OuterTableParser()
    parser.feed(html)
    parser.close()

    current_status: AgendaStatusObservation | None = None
    current_status_block: int | None = None
    assignments: list[OnBaseAgendaStatusAssignment] = []

    for block in parser.blocks:
        if block.item_links:
            if len(block.item_links) != 1:
                raise ValueError(
                    "OnBase outer agenda-item table must contain exactly one non-section item link; "
                    f"meeting_id={meeting_id} block={block.block_index} links={len(block.item_links)}"
                )
            item_id, item_text = block.item_links[0]
            assignments.append(
                OnBaseAgendaStatusAssignment(
                    meeting_id=meeting_id,
                    item_id=item_id,
                    item_text=item_text,
                    item_block_index=block.block_index,
                    status_block_index=current_status_block,
                    status=current_status,
                )
            )
            continue

        if not block.text:
            continue
        candidate = classify_agenda_status_label(
            block.text,
            evidence_id=f"onbase-agenda-tree:{meeting_id}:block:{block.block_index}",
        )
        if candidate is None or candidate.normalized_status == "no_items":
            current_status = None
            current_status_block = None
        else:
            current_status = candidate
            current_status_block = block.block_index

    return tuple(assignments)
