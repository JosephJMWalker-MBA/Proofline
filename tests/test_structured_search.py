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


def test_money_parser_reconstructs_whitespace_separated_thousands() -> None:
    text = "Total expenditure (if applicable): $ 51 ,780.00"
    money = [fact for fact in extract_structured_facts(text) if fact.fact_type == "money"]

    assert len(money) == 1
    assert money[0].raw_text == "$ 51 ,780.00"
    assert money[0].normalized_text == "51780.00"
    assert money[0].numeric_value == 51780.0
    assert text[money[0].char_start : money[0].char_end] == money[0].raw_text


def test_money_parser_expands_supported_magnitude_suffix_without_truncation() -> None:
    text = "Sold over $138MM since 2013, 466+ transactions"
    money = [fact for fact in extract_structured_facts(text) if fact.fact_type == "money"]

    assert len(money) == 1
    assert money[0].raw_text == "$138MM"
    assert money[0].normalized_text == "138000000.00"
    assert money[0].numeric_value == 138000000.0
    assert not any(fact.raw_text == "$138" for fact in money)


def test_money_parser_fails_closed_on_unknown_attached_suffix() -> None:
    facts = extract_structured_facts("Reported exposure: $138XYZ during the period.")
    assert not any(fact.fact_type == "money" for fact in facts)


def test_money_parser_v3_fails_closed_on_malformed_ocr_continuation() -> None:
    text = "Estimated TOTAL Project Cost $20,001___- $100,000 Applicable Fee $500"
    money = [fact for fact in extract_structured_facts(text) if fact.fact_type == "money"]

    assert [(fact.raw_text, fact.normalized_text) for fact in money] == [
        ("$100,000", "100000.00"),
        ("$500", "500.00"),
    ]
    assert not any(fact.raw_text == "$20" for fact in money)


def test_money_parser_v3_preserves_valid_thousands_ranges() -> None:
    text = "Estimated TOTAL Project Cost $20,001 - $100,000"
    money = [fact for fact in extract_structured_facts(text) if fact.fact_type == "money"]

    assert [(fact.raw_text, fact.normalized_text) for fact in money] == [
        ("$20,001", "20001.00"),
        ("$100,000", "100000.00"),
    ]


def test_v1_money_parser_remains_available_for_frozen_receipts() -> None:
    spaced = extract_structured_facts(
        "Total expenditure (if applicable): $ 51 ,780.00",
        parser_version="proofline-structured/v1",
    )
    magnitude = extract_structured_facts(
        "Sold over $138MM since 2013, 466+ transactions",
        parser_version="proofline-structured/v1",
    )

    spaced_money = [fact for fact in spaced if fact.fact_type == "money"]
    magnitude_money = [fact for fact in magnitude if fact.fact_type == "money"]
    assert [(fact.raw_text, fact.normalized_text) for fact in spaced_money] == [("$ 51", "51.00")]
    assert [(fact.raw_text, fact.normalized_text) for fact in magnitude_money] == [("$138", "138.00")]


def test_v2_money_parser_remains_available_for_t13b_receipt() -> None:
    money = [
        fact
        for fact in extract_structured_facts(
            "$20,001___- $100,000",
            parser_version="proofline-structured/v2",
        )
        if fact.fact_type == "money"
    ]

    assert [(fact.raw_text, fact.normalized_text) for fact in money] == [
        ("$20", "20.00"),
        ("$100,000", "100000.00"),
    ]


def test_structured_index_records_requested_parser_version(tmp_path) -> None:
    state = tmp_path / "state"
    source = tmp_path / "memo.txt"
    source.write_text("Amount: $138MM", encoding="utf-8")
    Ingestor(state).ingest(source, source_uri="https://fixtures.proofline.local/memo.txt")

    build = StructuredIndex(state).rebuild(parser_version="proofline-structured/v1")
    assert build.parser_version == "proofline-structured/v1"
    assert StructuredIndex(state).current_build()["parser_version"] == "proofline-structured/v1"


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
    assert build.parser_version == "proofline-structured/v3"

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
