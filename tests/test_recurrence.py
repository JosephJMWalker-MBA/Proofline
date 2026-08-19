from __future__ import annotations

from proofline import Ingestor
from proofline.recurrence import SegmentRecurrenceClusterer
from proofline.segment_similarity import (
    NearDuplicateCandidate,
    SegmentOccurrence,
    SegmentSimilarityIndex,
)
from proofline.segments import (
    SegmentHit,
    SegmentIndex,
    SegmentationPlan,
    SegmentationRule,
)


def _occurrence(label: str, family: str, text: str) -> SegmentOccurrence:
    hit = SegmentHit(
        build_id="segments:fixture",
        segment_id=f"segment:{label}",
        evidence_id=f"evidence:{label}",
        artifact_id=f"artifact:{label}",
        locator="page:1",
        rule_name="board-items",
        segment_type="agenda_item",
        anchor_text=label,
        normalized_anchor=label.casefold(),
        raw_text=text,
        normalized_text=" ".join(text.split()).casefold(),
        text_sha256=f"sha:{label}",
        char_start=0,
        char_end=len(text),
        sources=(
            {
                "source_id": f"source:{label}",
                "source_uri": f"https://example.gov/{label}",
                "source_name": f"Board of Control — {label}",
                "native_identifier": label,
            },
        ),
    )
    return SegmentOccurrence(family_id=family, sources=hit.sources, segment=hit)


def _candidate(left, right, similarity: float, shared: int) -> NearDuplicateCandidate:
    return NearDuplicateCandidate(
        similarity=similarity,
        shared_shingles=shared,
        left=left,
        right=right,
    )


def test_recurrence_clusters_are_deterministic_connected_components() -> None:
    a = _occurrence("A", "family:a", "public safety drone program")
    b = _occurrence("B", "family:b", "public safety drone program")
    c = _occurrence("C", "family:c", "public safety BRINCS drone program")
    d = _occurrence("D", "family:d", "records management contract")
    e = _occurrence("E", "family:e", "records management contract amended")

    edges = (
        _candidate(a, b, 1.0, 20),
        _candidate(b, c, 0.91, 18),
        _candidate(d, e, 0.72, 8),
    )
    first = SegmentRecurrenceClusterer.from_candidates(
        edges,
        similarity_method="token_shingle_jaccard/v1",
        threshold=0.60,
    )
    second = SegmentRecurrenceClusterer.from_candidates(
        tuple(reversed(edges)),
        similarity_method="token_shingle_jaccard/v1",
        threshold=0.60,
    )

    assert first.cluster_count == 2
    assert first.returned_cluster_count == 2
    assert first.candidate_edge_count == 3
    assert [item.cluster_id for item in first.clusters] == [
        item.cluster_id for item in second.clusters
    ]

    drone = first.clusters[0]
    assert drone.occurrence_count == 3
    assert drone.family_count == 3
    assert drone.evidence_count == 3
    assert drone.edge_count == 2
    assert drone.min_edge_similarity == 0.91
    assert drone.max_edge_similarity == 1.0
    assert abs(drone.mean_edge_similarity - 0.955) < 1e-12
    assert {item.family_id for item in drone.occurrences} == {
        "family:a",
        "family:b",
        "family:c",
    }
    assert len(drone.limitations) == 3
    assert "single-linkage" in drone.limitations[0]

    records = first.clusters[1]
    assert records.occurrence_count == 2
    assert records.family_count == 2
    assert records.edge_count == 1


def test_recurrence_cluster_limit_and_min_occurrences_are_explicit() -> None:
    a = _occurrence("A", "family:a", "alpha")
    b = _occurrence("B", "family:b", "alpha")
    c = _occurrence("C", "family:c", "alpha")
    d = _occurrence("D", "family:d", "beta")
    e = _occurrence("E", "family:e", "beta")
    candidates = (
        _candidate(a, b, 0.9, 5),
        _candidate(b, c, 0.9, 5),
        _candidate(d, e, 0.9, 5),
    )

    only_three_plus = SegmentRecurrenceClusterer.from_candidates(
        candidates,
        similarity_method="fixture",
        threshold=0.8,
        min_occurrences=3,
    )
    assert only_three_plus.cluster_count == 1
    assert only_three_plus.returned_cluster_count == 1
    assert only_three_plus.clusters[0].occurrence_count == 3

    limited = SegmentRecurrenceClusterer.from_candidates(
        candidates,
        similarity_method="fixture",
        threshold=0.8,
        limit=1,
    )
    assert limited.cluster_count == 2
    assert limited.returned_cluster_count == 1
    assert len(limited.clusters) == 1


def test_recurrence_find_consumes_complete_similarity_edge_set(tmp_path) -> None:
    state = tmp_path / "state"
    rule = SegmentationRule(
        name="board-items",
        source_name_regex=r"^Board of Control",
        anchor_regex=r"(?i)^Ordinance (?P<anchor>\d+/2026)$",
        segment_type="agenda_item",
        min_chars=30,
    )
    text = (
        "Ordinance 1/2026\n"
        "Enter into a four year contract with Example Systems for a public safety drone "
        "program with year one free and later years billed annually under cooperative "
        "purchasing authority.\n"
    )
    for index in range(1, 4):
        path = tmp_path / f"record-{index}.txt"
        path.write_text(text, encoding="utf-8")
        Ingestor(state).ingest(
            path,
            source_uri=f"https://example.gov/meeting/{index}",
            source_name=f"Board of Control — Meeting {index}",
        )

    SegmentIndex(state).rebuild(SegmentationPlan(name="fixture", rules=(rule,)))

    similarity = SegmentSimilarityIndex(state)
    limited = similarity.find(rule_name="board-items", threshold=0.5, limit=1)
    complete = similarity.find(rule_name="board-items", threshold=0.5, limit=None)
    assert complete.matched_candidate_count == 3
    assert complete.returned_candidate_count == 3
    assert len(complete.candidates) == 3
    assert limited.matched_candidate_count == 3
    assert limited.returned_candidate_count == 1
    assert len(limited.candidates) == 1

    clustered = SegmentRecurrenceClusterer(state).find(
        rule_name="board-items",
        threshold=0.5,
        limit=None,
    )
    assert clustered.candidate_edge_count == 3
    assert clustered.cluster_count == 1
    assert clustered.returned_cluster_count == 1
    cluster = clustered.clusters[0]
    assert cluster.occurrence_count == 3
    assert cluster.family_count == 3
    assert cluster.evidence_count == 1
    assert cluster.edge_count == 3
    assert len(cluster.limitations) == 3
