from __future__ import annotations

from proofline.recurrence import SegmentRecurrenceClusterer
from proofline.segment_similarity import NearDuplicateCandidate, SegmentOccurrence
from proofline.segments import SegmentHit


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
    assert only_three_plus.clusters[0].occurrence_count == 3

    limited = SegmentRecurrenceClusterer.from_candidates(
        candidates,
        similarity_method="fixture",
        threshold=0.8,
        limit=1,
    )
    assert limited.cluster_count == 1
    assert len(limited.clusters) == 1
