from __future__ import annotations

import json

import proofline.cli as cli
from proofline import Ingestor
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule


def test_recurrence_clusters_cli_groups_three_related_meeting_occurrences(tmp_path, capsys) -> None:
    state = tmp_path / "state"
    rule = SegmentationRule(
        name="board-items",
        source_name_regex=r"^Board of Control",
        anchor_regex=r"(?i)^Ordinance (?P<anchor>\d+/2026)$",
        segment_type="agenda_item",
        min_chars=20,
    )
    base = (
        "Ordinance 1/2026\n"
        "Enter into a four year contract with Example Systems for a public safety drone program "
        "with year one free and later years billed annually.\n"
    )
    texts = (
        base,
        base.replace("free and", "free, and"),
        base.replace("public safety drone program", "public safety BRINCS drone program"),
    )
    for index, text in enumerate(texts, start=1):
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
            "recurrence-clusters",
            "--rule",
            "board-items",
            "--threshold",
            "0.5",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["method"] == "segment_recurrence_connected_components/v1"
    assert payload["similarity_method"] == "token_shingle_jaccard/v1"
    assert payload["candidate_edge_count"] == 3
    assert payload["cluster_count"] == 1
    cluster = payload["clusters"][0]
    assert cluster["occurrence_count"] == 3
    assert cluster["family_count"] == 3
    assert cluster["evidence_count"] == 3
    assert cluster["edge_count"] == 3
    assert len(cluster["limitations"]) == 3
    assert all(item["segment"]["evidence_id"] for item in cluster["occurrences"])
