from __future__ import annotations

import json

import proofline.cli as cli
from proofline import Ingestor
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule


def test_near_segments_cli_emits_family_context_and_candidate_statistics(tmp_path, capsys) -> None:
    state = tmp_path / "state"
    rule = SegmentationRule(
        name="board-items",
        source_name_regex=r"^Board of Control",
        anchor_regex=r"(?i)^Ordinance (?P<anchor>\d+/2026)$",
        segment_type="agenda_item",
        min_chars=20,
    )
    first_text = (
        "Ordinance 1/2026\n"
        "Enter into a four year contract with Example Systems for a public safety drone program.\n"
    )
    second_text = first_text.replace("drone program", "BRINCS drone program")
    for index, text in enumerate((first_text, second_text), start=1):
        path = tmp_path / f"record-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/meeting/{index}",
            source_name=f"Board of Control — Meeting {index}",
        )

    SegmentIndex(state).rebuild(SegmentationPlan(name="fixture", rules=(rule,)))
    exit_code = cli.main(
        [
            "--state-dir",
            str(state),
            "near-segments",
            "--rule",
            "board-items",
            "--threshold",
            "0.5",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["method"] == "token_shingle_jaccard/v1"
    assert payload["segment_count"] == 2
    assert payload["occurrence_count"] == 2
    assert payload["possible_all_pairs"] == 1
    assert payload["candidate_pairs_generated"] == 1
    assert payload["candidate_pairs_compared"] == 1
    assert len(payload["candidates"]) == 1
    candidate = payload["candidates"][0]
    assert candidate["left"]["family_id"] != candidate["right"]["family_id"]
    assert candidate["left"]["segment"]["evidence_id"]
    assert candidate["right"]["segment"]["evidence_id"]
