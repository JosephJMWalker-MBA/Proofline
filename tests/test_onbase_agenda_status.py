import pytest

from proofline.onbase_agenda_status import extract_onbase_agenda_status_assignments


def _table(text: str, *, href: str | None = None) -> str:
    if href is None:
        body = text
    else:
        body = f'<a href="{href}">{text}</a>'
    return f"<table><tr><td>{body}</td></tr></table>"


def test_structural_time_heading_applies_across_consecutive_item_tables():
    html = "".join(
        [
            _table("PLANNING & ECONOMIC DEVELOPMENT"),
            _table("TIME:"),
            _table(
                "ORDINANCE authorizing a Conditional Use at 1928 Eastwood Avenue",
                href="javascript:loadAgendaItem(47077,false);",
            ),
            _table(
                "D-14 Petition PC-2025-80-CU",
                href="javascript:loadAgendaItem(47078,false);",
            ),
        ]
    )
    assignments = extract_onbase_agenda_status_assignments(html, meeting_id=675)
    assert len(assignments) == 2
    assert assignments[0].status is not None
    assert assignments[0].status.normalized_status == "time"
    assert assignments[1].status is not None
    assert assignments[1].status.normalized_status == "time"
    assert assignments[0].status_block_index == assignments[1].status_block_index == 1
    assert all(item.status.terminal_outcome_assigned is False for item in assignments if item.status)


def test_unrecognized_non_item_table_resets_status_to_prevent_section_leakage():
    html = "".join(
        [
            _table("TIME:"),
            _table("D-14 PC-2025-80-CU", href="javascript:loadAgendaItem(1,false);"),
            _table("NEW LEGISLATION"),
            _table("Unrelated item", href="javascript:loadAgendaItem(2,false);"),
        ]
    )
    first, second = extract_onbase_agenda_status_assignments(html, meeting_id=1)
    assert first.status is not None and first.status.normalized_status == "time"
    assert second.status is None
    assert second.status_block_index is None


def test_no_items_resets_instead_of_becoming_item_status():
    html = "".join(
        [
            _table("TIME:"),
            _table("Old item", href="javascript:loadAgendaItem(1,false);"),
            _table("NO ITEMS"),
            _table("Later item", href="javascript:loadAgendaItem(2,false);"),
        ]
    )
    first, second = extract_onbase_agenda_status_assignments(html, meeting_id=1)
    assert first.status is not None and first.status.normalized_status == "time"
    assert second.status is None


def test_nested_tables_are_one_outer_structural_block():
    html = (
        "<table><tr><td><table><tr><td>TIME:</td></tr></table></td></tr></table>"
        + _table("D-14 PC-2025-80-CU", href="javascript:loadAgendaItem(9,false);")
    )
    assignments = extract_onbase_agenda_status_assignments(html, meeting_id=2)
    assert len(assignments) == 1
    assert assignments[0].status is not None
    assert assignments[0].status.normalized_status == "time"


def test_section_links_are_ignored_and_do_not_create_item_assignments():
    html = "".join(
        [
            _table("TIME:"),
            _table("Section", href="javascript:loadAgendaItem(10,true);"),
            _table("D-14 PC-2025-80-CU", href="javascript:loadAgendaItem(11,false);"),
        ]
    )
    assignments = extract_onbase_agenda_status_assignments(html, meeting_id=3)
    assert [item.item_id for item in assignments] == [11]
    # The section-link table is a non-item structural block and resets status.
    assert assignments[0].status is None


def test_multiple_item_links_in_one_outer_table_fail_closed():
    html = (
        "<table><tr><td>"
        '<a href="javascript:loadAgendaItem(1,false);">one</a>'
        '<a href="javascript:loadAgendaItem(2,false);">two</a>'
        "</td></tr></table>"
    )
    with pytest.raises(ValueError, match="exactly one"):
        extract_onbase_agenda_status_assignments(html, meeting_id=4)


def test_requires_positive_meeting_id_and_string_html():
    with pytest.raises(ValueError, match="meeting_id"):
        extract_onbase_agenda_status_assignments("<html></html>", meeting_id=0)
    with pytest.raises(TypeError, match="html"):
        extract_onbase_agenda_status_assignments(None, meeting_id=1)  # type: ignore[arg-type]
