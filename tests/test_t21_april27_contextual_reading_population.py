import hashlib
import json
from pathlib import Path

POPULATION = Path("experiments/akron-2026/r1_t21_april27_contextual_reading_population.json")


def _sha256_json(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_t21_contextual_reading_population_is_frozen_from_canonical_acquisition():
    payload = json.loads(POPULATION.read_text(encoding="utf-8"))
    assert payload["schema"] == "proofline-akron-t21-april27-contextual-reading-population/v1"
    assert payload["stage"] == "post_ocr_receipt_pre_full_family_contextual_reading"
    assert payload["document_count"] == 20
    assert payload["page_count"] == 88
    assert payload["native_nonblank_page_count"] == 47
    assert payload["native_low_quality_page_count"] == 41
    assert [row["publish_id"] for row in payload["documents"]] == list(range(102587, 102607))
    assert _sha256_json(payload["documents"]) == "8238c57440a8d4257f697ef465a7a47b041c0fb2f5b77d01c244c8b23f71d72d"
    assert payload["population_signature_sha256"] == "8238c57440a8d4257f697ef465a7a47b041c0fb2f5b77d01c244c8b23f71d72d"
    assert payload["basis"]["selection_signature_sha256"] == "0f58180207c3bf55e90a8494ddd15d1606f53281d2dad2df133b5db9ea60485d"
    assert payload["basis"]["canonical_acquisition_raw_json_sha256"] == "012242bc20fbd07b1e70fdf58bc0b7a95b24e926d33f472fbc730eb004d53f07"
    assert payload["authority_boundary"] == {
        "document_content_interpreted_by_this_population_freeze": False,
        "outcome_assigned": False,
        "detector_authorized": False,
        "lead_count": None,
    }
