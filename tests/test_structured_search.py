from __future__ import annotations

from proofline import Ingestor
from proofline.structured import StructuredIndex, extract_structured_facts, parse_query_date


def test_structured_parser_is_conservative_about_money_dates_and_identifiers() -> None:
    spreadsheet_row = (
        '{"columns":{"award_date":"08/18/2026","amount":"250000",'
        '"contract_id":"C-001","vendor":"Northstar Civic Systems"},'
        '"raw":["08/18/2026","250000","C-001","Northstar Civic Systems"]}'
    )
    facts = extract_structured_facts(spreadsheet_row)

    assert any(
        fact.fact_type == "money"
        and fact.field_name == "amount"
        and fact.numeric_value == 250000.0
        for fact in facts
    )
    assert any(
        fact.fact_type == "date"
        and fact.field_name == "award_date"
        and fact.normalized_text == "2026-08-18"
        for fact in facts
    )
    assert any(
        fact.fact_type == "identifier"
        and fact.field_name == "contract_id"
        and fact.normalized_text == "c-001"
        for fact in facts
    )
    assert not any(fact.raw_text == "Northstar Civic Systems" for fact in facts)

    prose = "Approved August 18, 2026 for $410,000. Internal count: 93821."
    prose_facts = extract_structured_facts(prose)
    assert any(f.fact_type == "money" and f.numeric_value == 410000.0 for f in prose_facts)
    assert any(f.fact_type == "date" and f.normalized_text == "2026-08-18" for f in prose_facts)
    assert not any(f.numeric_value == 93821.0 for f in prose_facts)


def test_structured_index_queries_ranges_with_provenance(tmp_path) -> None:
    state = tmp_path / "state"
    csv_path = tmp_path / "awards.csv"
    csv_path.write_text(
        "contract_id,vendor,amount,award_date\n"
        "C-001,Northstar Civic Systems,250000,08/18/2026\n"
        "C-002,Lakeview Systems,410000,2026-09-02\n",
        encoding="utf-8",
    )

    Ingestor(state).ingest(
        csv_path,
        source_uri="https://fixtures.proofline.local/awards.csv",
        native_identifier="AWARDS-2026",
    )

    index = StructuredIndex(state)
    build = index.rebuild()
    assert build.evidence_count == 3
    assert build.fact_count >= 6

    money = index.money(minimum=300000, maximum=500000)
    assert {hit.raw_text for hit in money} == {"410000"}
    assert money[0].locator == "sheet:CSV!A3:D3"
    assert money[0].sources[0]["source_uri"] == "https://fixtures.proofline.local/awards.csv"

    dates = index.dates(start="2026-08-20", end="2026-12-31")
    assert any(hit.normalized_text == "2026-09-02" for hit in dates)
    assert not any(hit.normalized_text == "2026-08-18" for hit in dates)

    identifiers = index.identifier("C-001")
    assert len(identifiers) == 1
    assert identifiers[0].locator == "sheet:CSV!A2:D2"


def test_query_dates_require_unambiguous_iso_boundaries() -> None:
    assert parse_query_date("2026-08-18") == "2026-08-18"
    try:
        parse_query_date("08/18/2026")
    except ValueError as exc:
        assert "YYYY-MM-DD" in str(exc)
    else:
        raise AssertionError("ambiguous query date should be rejected")
