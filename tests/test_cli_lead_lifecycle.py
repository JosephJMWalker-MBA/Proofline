from __future__ import annotations

import json

import pytest

from proofline import Ingestor
from proofline.candidate_analysis import CandidateObservationRunner
from proofline.cli import main
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule
from proofline.structured import StructuredIndex


def _seed_candidate(state, tmp_path) -> None:
    dates = ("April 13, 2026", "October 31, 2026")
    for index, changed_date in enumerate(dates, start=1):
        text = (
            "Ordinance 1/2026\n"
            "Authorize an amendment with Example Development Inc. for cleanup services for "
            "$185,000.00 with a common completion date of July 31, 2026. "
            f"A related milestone is {changed_date}. All remaining administrative language is "
            "substantially the same for this deterministic lead CLI fixture.\n"
        )
        path = tmp_path / f"meeting-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/lead-cli/{index}",
            source_name=f"Board of Control — Lead CLI {index}",
        )
    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(
        SegmentationPlan(
            name="lead-cli",
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
    result = CandidateObservationRunner(state).run_recurrence_variations(
        rule_name="board-items",
        threshold=0.60,
    )
    assert result.eligible == 1


def test_package_lead_show_and_explicit_review_commands(tmp_path, capsys) -> None:
    state = tmp_path / "state"
    _seed_candidate(state, tmp_path)

    code = main(["--state-dir", str(state), "package-leads"])
    assert code == 0
    packaged = json.loads(capsys.readouterr().out)
    assert len(packaged) == 1
    assert packaged[0]["created"] is True
    lead_id = packaged[0]["lead_id"]

    code = main(["--state-dir", str(state), "package-leads"])
    assert code == 0
    rerun = json.loads(capsys.readouterr().out)
    assert rerun[0]["lead_id"] == lead_id
    assert rerun[0]["created"] is False

    code = main(["--state-dir", str(state), "lead", lead_id])
    assert code == 0
    packet = json.loads(capsys.readouterr().out)
    assert packet["current_status"] == "candidate"
    assert packet["lead"]["status"] == "candidate"
    assert packet["review_history"] == []

    code = main(
        [
            "--state-dir",
            str(state),
            "review-lead",
            lead_id,
            "--status",
            "explained",
            "--reviewer",
            "Fixture Reviewer",
            "--rationale",
            "The source records describe sequential deadline amendments.",
            "--note",
            "No misconduct inference.",
        ]
    )
    assert code == 0
    reviewed = json.loads(capsys.readouterr().out)
    assert reviewed["event"]["status"] == "explained"
    assert reviewed["event"]["reviewer"] == "Fixture Reviewer"
    assert reviewed["lead"]["current_status"] == "explained"
    assert reviewed["lead"]["lead"]["status"] == "candidate"
    assert len(reviewed["lead"]["review_history"]) == 1


def test_review_lead_cli_does_not_offer_published_status(tmp_path) -> None:
    state = tmp_path / "state"
    _seed_candidate(state, tmp_path)
    assert main(["--state-dir", str(state), "package-leads"]) == 0

    from proofline.lead_lifecycle import LeadLifecycle

    lead_id = LeadLifecycle(state).package_candidate_observations()[0].lead_id
    with pytest.raises(SystemExit):
        main(
            [
                "--state-dir",
                str(state),
                "review-lead",
                lead_id,
                "--status",
                "published",
                "--reviewer",
                "Fixture Reviewer",
                "--rationale",
                "Publication is intentionally outside the R0 review command.",
            ]
        )
