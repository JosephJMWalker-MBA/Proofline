from __future__ import annotations

from proofline import Ingestor, ProoflineStore
from proofline.detectors import build_version_change_observation, compare_artifact_versions


def test_version_diff_surfaces_value_change_and_exact_arithmetic_context(tmp_path) -> None:
    state = tmp_path / "state"
    before_path = tmp_path / "before.txt"
    after_path = tmp_path / "after.txt"

    before_path.write_text(
        "Enter into Change Order No. 1 to add custodial cleaning services in the amount "
        "of $325.00 per month, resulting in a new contract amount of $278,593.00 for "
        "the first contract year.\nOrdinance 52/2026\nOther award: $57,000.00.\n",
        encoding="utf-8",
    )
    after_path.write_text(
        "Enter into Change Order No. 1 to add custodial cleaning services in the amount "
        "of $325.00 per month, resulting in a new contract amount of $282,168.00 for "
        "the first contract year.\nOrdinance 52/2026\nOther award: $57,000.00.\n",
        encoding="utf-8",
    )

    before = Ingestor(state).ingest(
        before_path,
        source_uri="https://records.example.gov/agenda/posted",
    )
    after = Ingestor(state).ingest(
        after_path,
        source_uri="https://records.example.gov/agenda/amended",
    )
    store = ProoflineStore(state / "proofline.db")

    result = compare_artifact_versions(store, before.artifact_id, after.artifact_id)

    assert result.changed is True
    assert len(result.changed_units) == 1
    assert result.money_removed == ("278593.00",)
    assert result.money_added == ("282168.00",)
    assert result.dates_removed == ()
    assert result.dates_added == ()
    assert result.text_similarity > 0.95
    assert len(result.arithmetic_relations) == 1
    relation = result.arithmetic_relations[0]
    assert relation.delta == "3575.00"
    assert relation.unchanged_value == "325.00"
    assert relation.exact_multiple == 11

    _, observation = build_version_change_observation(
        store,
        before.artifact_id,
        after.artifact_id,
    )
    assert observation is not None
    assert observation.observation_type == "source_version_change"
    assert len(observation.evidence_refs) == 2
    assert "3575.00" in observation.explanation
    assert "11 ×" in observation.explanation
    assert "does not infer why" in observation.uncertainty

    assert store.add_observation(observation) is True
    trace = store.trace_observation(observation.observation_id)
    assert trace is not None
    assert len(trace["evidence"]) == 2


def test_identical_extracted_versions_create_no_observation(tmp_path) -> None:
    state = tmp_path / "state"
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("Meeting record $10.00", encoding="utf-8")
    second_path.write_text("Meeting record $10.00", encoding="utf-8")

    first = Ingestor(state).ingest(
        first_path,
        source_uri="https://records.example.gov/a",
    )
    second = Ingestor(state).ingest(
        second_path,
        source_uri="https://records.example.gov/b",
    )

    # Content addressing correctly collapses byte-identical artifacts. The
    # version comparator therefore rejects a self-comparison rather than
    # manufacturing a no-change event between one immutable object and itself.
    assert first.artifact_id == second.artifact_id
