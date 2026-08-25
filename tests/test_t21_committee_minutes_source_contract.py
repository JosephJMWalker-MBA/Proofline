from __future__ import annotations
import importlib.util, json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "akron-2026"
SCRIPT = EXPERIMENT / "probe_t21_committee_minutes_source_contract.py"
spec = importlib.util.spec_from_file_location("t21_committee_minutes_contract", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load_source() -> dict:
    return json.loads((EXPERIMENT / "r1_t21_public_access_source_contract_summary.json").read_text(encoding="utf-8"))


def test_select_minutes_query_uses_frozen_publisher_identity() -> None:
    query = module.select_minutes_query(load_source())
    assert query == {
        "id": "202",
        "name": "Committee Meeting Minutes",
        "type": "DocumentType",
        "date_search_option": "NoDate",
        "requires_date_or_keyword": True,
        "requires_keyword": False,
        "requires_date": False,
    }


def test_select_minutes_query_rejects_id_drift() -> None:
    source = load_source()
    row = next(row for row in source["custom_queries"]["queries"] if row["name"] == "Committee Meeting Minutes")
    row["id"] = "999"
    with pytest.raises(ValueError, match="query ID diverged"):
        module.select_minutes_query(source)


def test_keyword_parser_preserves_publisher_schema_without_semantics() -> None:
    raw = json.dumps({"Data": [{"ID": 301, "Name": "Meeting Date", "DataType": "DateTime",
                                "Required": False, "MaxLength": 0, "Dataset": None,
                                "IsMasked": False, "Mask": None, "MaskStatic": None,
                                "MaskFullFieldRequired": False}]}).encode()
    payload, keywords = module.parse_keywords(raw)
    assert payload["Data"][0]["Name"] == "Meeting Date"
    assert keywords == [{"id": "301", "name": "Meeting Date", "data_type": "DateTime",
                         "required": False, "max_length": 0, "dataset": None,
                         "is_masked": False, "mask": None, "mask_static": None,
                         "mask_full_field_required": False}]
    assert "outcome" not in keywords[0]


def test_keyword_parser_fails_closed_without_data_array() -> None:
    with pytest.raises(ValueError, match="Data array"):
        module.parse_keywords(b'{"Status":"ok"}')


def test_keyword_parser_fails_closed_on_missing_id_or_name() -> None:
    with pytest.raises(ValueError, match="stable publisher ID"):
        module.parse_keywords(b'{"Data":[{"Name":"Meeting Date"}]}')
    with pytest.raises(ValueError, match="publisher name"):
        module.parse_keywords(b'{"Data":[{"ID":301}]}')
