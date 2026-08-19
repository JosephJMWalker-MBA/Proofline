from __future__ import annotations

import json

from proofline import Ingestor
from proofline.cli import main
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule
from proofline.structured import StructuredIndex


def _seed(state, tmp_path) -> None:
    dates = ("April 13, 2026", "October 31, 2026")
    for index, changed_date in enumerate(dates, start=1):
        text = (
            "Ordinance 1/2026\n"
            "Authorize an amendment with Example Development Inc. for cleanup services for "
            "$185,000.00 with a common completion date of July 31, 2026. "
            f"A related milestone is {changed_date}. All remaining administrative language is "
            "substantially the same for this deterministic CLI fixture.\n"
        )
        path = tmp_path / f"meeting-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/cli/{index}",
            source_name=f"Board of Control — CLI Meeting {index}",
        )
    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(
        SegmentationPlan(
            name="cli-candidate",
            rules=(
                SegmentationRule(
                    name="board-items",
                    source_name_regex=r"^Board of Control",
                    anchor_regex=r"(?i)^Ordinance (?P<anchor>\d+/2026)$",
                    segment_type="agenda_item",
                    min_chars=40,
                ),
            ),
        )
    )


def test_analyze_candidates_cli_and_trace_expose_detector_context(tmp_path, capsys) -> None:
    state = tmp_path / "state"
    _seed(state, tmp_path)

    code = main(
        [
            "--state-dir",
            str(state),
            "analyze-candidates",
            "--rule",
            "board-items",
            "--threshold",
            "0.60",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["detector_method"] == "recurrence_fact_variation/v1"
    assert payload["eligible"] == 1
    assert payload["observations_created"] == 1
    assert payload["skipped"] == 0
    item = payload["items"][0]
    assert item["decision"]["eligible"] is True
    assert item["candidate"]["possible_ordinary_explanations"]
    assert item["candidate"]["questions_worth_asking"]
    observation_id = item["observation_id"]

    code = main(["--state-dir", str(state), "trace", observation_id])
    assert code == 0
    trace = json.loads(capsys.readouterr().out)
    assert trace["observation"]["observation_type"] == "recurrence_structured_fact_variation"
    assert len(trace["evidence"]) == 2
    assert trace["source_relations"] == []
    assert len(trace["detector_contexts"]) == 1
    context = trace["detector_contexts"][0]
    assert context["detector_method"] == "recurrence_fact_variation/v1"
    assert context["details"]["family_count"] == 2
    assert context["details"]["possible_ordinary_explanations"]
    assert context["details"]["questions_worth_asking"]
