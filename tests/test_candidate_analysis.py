from __future__ import annotations

from proofline import Ingestor
from proofline.candidate_analysis import CandidateObservationRunner
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule
from proofline.structured import StructuredIndex


_RULE = SegmentationRule(
    name="board-items",
    source_name_regex=r"^Board of Control",
    anchor_regex=r"(?i)^Ordinance (?P<anchor>\d+/2026)$",
    segment_type="agenda_item",
    min_chars=40,
)
_PLAN = SegmentationPlan(name="candidate-fixture", rules=(_RULE,))


def _seed_variation(state, tmp_path) -> None:
    milestone_dates = (
        "April 13, 2026",
        "July 1, 2026",
        "October 31, 2026",
    )
    for index, milestone in enumerate(milestone_dates, start=1):
        text = (
            "Ordinance 1/2026\n"
            "Authorize an amendment with Example Development Inc. for environmental cleanup "
            "services in an amount not to exceed $185,000.00. The common completion date is "
            f"July 31, 2026. A related milestone is {milestone}. The remainder of the scope and "
            "procurement language is unchanged for this fixture.\n"
        )
        path = tmp_path / f"meeting-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/board/{index}",
            source_name=f"Board of Control — Meeting {index}",
        )
    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(_PLAN)


def test_candidate_runner_promotes_only_evidence_backed_fact_variation(tmp_path) -> None:
    state = tmp_path / "state"
    _seed_variation(state, tmp_path)

    runner = CandidateObservationRunner(state)
    result = runner.run_recurrence_variations(
        rule_name="board-items",
        threshold=0.60,
        min_occurrences=3,
    )
    assert result.cluster_count == 1
    assert result.eligible == 1
    assert result.observations_created == 1
    assert result.already_observed == 0
    assert result.skipped == 0

    item = result.items[0]
    assert item.status == "observed"
    assert item.decision.eligible is True
    assert item.decision.reason == "eligible_recurrence_fact_variation"
    assert item.candidate is not None
    candidate = item.candidate
    assert candidate.observation.observation_type == "recurrence_structured_fact_variation"
    assert candidate.observation.score is None
    assert candidate.possible_ordinary_explanations
    assert candidate.questions_worth_asking
    assert any("routine" in value.casefold() for value in candidate.possible_ordinary_explanations)
    assert any("Possible ordinary explanation:" in value for value in candidate.observation.limitations)
    assert any("Question worth asking:" in value for value in candidate.observation.limitations)

    common = {
        (value.fact_type, value.normalized_text, value.unit)
        for value in candidate.common_values
    }
    varying = {
        (value.fact_type, value.normalized_text, value.unit)
        for value in candidate.varying_values
    }
    assert ("money", "185000.00", "USD") in common
    assert ("date", "2026-07-31", None) in common
    assert ("date", "2026-04-13", None) in varying
    assert ("date", "2026-07-01", None) in varying
    assert ("date", "2026-10-31", None) in varying

    contexts = runner.contexts_for_observation(candidate.observation.observation_id)
    assert len(contexts) == 1
    context = contexts[0]
    assert context["context_type"] == "recurrence_cluster"
    assert context["context_key"] == candidate.cluster_id
    assert context["details"]["family_count"] == 3
    assert len(context["details"]["family_contexts"]) == 3
    assert context["details"]["possible_ordinary_explanations"]


def test_candidate_observation_identity_survives_rebuild_and_rerun(tmp_path) -> None:
    state = tmp_path / "state"
    _seed_variation(state, tmp_path)
    runner = CandidateObservationRunner(state)

    first = runner.run_recurrence_variations(
        rule_name="board-items", threshold=0.60, min_occurrences=3
    )
    first_id = first.items[0].observation_id
    assert first_id

    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(_PLAN)
    second = runner.run_recurrence_variations(
        rule_name="board-items", threshold=0.60, min_occurrences=3
    )
    assert second.items[0].observation_id == first_id
    assert second.observations_created == 0
    assert second.already_observed == 1
    assert second.items[0].status == "already_observed"
    assert len(runner.contexts_for_observation(first_id)) == 1


def test_recurrence_with_identical_structured_facts_stays_below_gold(tmp_path) -> None:
    state = tmp_path / "state"
    for index, marker in enumerate(("alpha", "beta", "gamma"), start=1):
        text = (
            "Ordinance 1/2026\n"
            "Enter into a routine services contract with Example Systems for $299,991.00 "
            "through July 31, 2026 under cooperative purchasing. "
            f"Administrative meeting marker {marker} does not change the structured facts.\n"
        )
        path = tmp_path / f"same-facts-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/same/{index}",
            source_name=f"Board of Control — Same Facts {index}",
        )
    StructuredIndex(state).rebuild()
    SegmentIndex(state).rebuild(_PLAN)

    runner = CandidateObservationRunner(state)
    result = runner.run_recurrence_variations(
        rule_name="board-items", threshold=0.60, min_occurrences=3
    )
    assert result.cluster_count == 1
    assert result.eligible == 0
    assert result.observations_created == 0
    assert result.skipped == 1
    assert result.items[0].decision.reason == "no_structured_fact_variation"
    assert runner.store.status()["observations"] == 0
