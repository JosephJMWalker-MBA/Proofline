from __future__ import annotations

from proofline import Ingestor
from proofline.families import SourceFamilyResolver
from proofline.relations import RelationStore
from proofline.segment_similarity import SegmentSimilarityIndex, token_shingles
from proofline.segments import SegmentIndex, SegmentationPlan, SegmentationRule


_RULE = SegmentationRule(
    name="board-items",
    source_name_regex=r"^Board of Control",
    anchor_regex=r"(?i)^[ \t]*Ordinance[ \t]+(?P<anchor>(?:TBD(?:/\d{4})?|\d{1,4}/\d{4}))[ \t]*$",
    segment_type="agenda_item",
    min_chars=30,
)


def _ingest_board(state, tmp_path, name: str, uri: str, body: str):
    path = tmp_path / f"{name.replace(' ', '-')}.txt"
    path.write_text(body, encoding="utf-8")
    return Ingestor(state).ingest(path, source_uri=uri, source_name=f"Board of Control — {name}")


def test_source_family_resolver_is_transitive_and_singletons_stay_separate(tmp_path) -> None:
    state = tmp_path / "state"
    first = _ingest_board(
        state,
        tmp_path,
        "A",
        "https://example.gov/a",
        "Ordinance 1/2026\nAlpha record long enough for an evidence segment.\n",
    )
    second = _ingest_board(
        state,
        tmp_path,
        "B",
        "https://example.gov/b",
        "Ordinance 1/2026\nBeta record long enough for an evidence segment.\n",
    )
    third = _ingest_board(
        state,
        tmp_path,
        "C",
        "https://example.gov/c",
        "Ordinance 1/2026\nGamma record long enough for an evidence segment.\n",
    )
    singleton = _ingest_board(
        state,
        tmp_path,
        "D",
        "https://example.gov/d",
        "Ordinance 1/2026\nDelta record long enough for an evidence segment.\n",
    )

    relations = RelationStore(state)
    relations.add(
        source_uri="https://example.gov/a",
        relation_type="historical_version_of",
        related_source_uri="https://example.gov/b",
        evidence_artifact_id=first.artifact_id,
        method="fixture",
        method_version="1",
    )
    relations.add(
        source_uri="https://example.gov/c",
        relation_type="historical_version_of",
        related_source_uri="https://example.gov/b",
        evidence_artifact_id=second.artifact_id,
        method="fixture",
        method_version="1",
    )

    resolver = SourceFamilyResolver(state)
    family_a = resolver.family_ids_for_artifact(first.artifact_id)
    family_b = resolver.family_ids_for_artifact(second.artifact_id)
    family_c = resolver.family_ids_for_artifact(third.artifact_id)
    family_d = resolver.family_ids_for_artifact(singleton.artifact_id)

    assert len(family_a) == 1
    assert family_a == family_b == family_c
    assert len(resolver.source_ids_for_family(family_a[0])) == 3
    assert len(family_d) == 1
    assert family_d != family_a
    assert resolver.artifacts_share_family(first.artifact_id, third.artifact_id)
    assert not resolver.artifacts_share_family(first.artifact_id, singleton.artifact_id)


def test_token_shingles_ignore_punctuation_but_preserve_word_changes() -> None:
    first = token_shingles("year one is free. years two and three cost money", size=3)
    punctuation = token_shingles("year one is free, years two and three cost money", size=3)
    changed = token_shingles("year one is free, years two and three cost more money", size=3)
    assert first == punctuation
    assert first != changed


def test_near_duplicate_candidates_use_source_family_occurrences_not_artifact_labels(
    tmp_path,
) -> None:
    state = tmp_path / "state"
    base = (
        "Ordinance TBD/2026\n"
        "Enter into a contract for up to four years with Motorola Solutions, Inc. "
        "in the total amount of $299,991.00 for a public safety drone program for the police "
        "department. Year one is a free trial to the city, years 2, 3 & 4 will cost "
        "$99,997.00 per year, if utilized. This purchase is being made via the Sourcewell "
        "cooperative purchasing program which exempts it from competitive bidding.\n"
    )
    archived = base.replace("city, years", "city. years")
    brincs = base.replace("public safety drone program", "public safety BRINCS drone program")
    unrelated = (
        "Ordinance 7/2026\n"
        "Enter into a construction contract with Example Excavating for water-main work in "
        "the amount of $1,000,000.00 after competitive bidding.\n"
    )

    current = _ingest_board(
        state, tmp_path, "Jan 27 Current", "https://example.gov/jan27", base
    )
    _ingest_board(
        state, tmp_path, "Jan 27 Archived", "https://example.gov/jan27-old", archived
    )
    # Feb 3 intentionally publishes byte-identical content to the Jan 27 archived artifact.
    # Bronze/Silver therefore deduplicate the bytes, but the source-family contexts remain distinct.
    _ingest_board(state, tmp_path, "Feb 3", "https://example.gov/feb3", archived)
    _ingest_board(state, tmp_path, "Feb 10", "https://example.gov/feb10", brincs)
    _ingest_board(state, tmp_path, "Other", "https://example.gov/other", unrelated)

    RelationStore(state).add(
        source_uri="https://example.gov/jan27-old",
        relation_type="historical_version_of",
        related_source_uri="https://example.gov/jan27",
        evidence_artifact_id=current.artifact_id,
        method="fixture",
        method_version="1",
    )

    SegmentIndex(state).rebuild(SegmentationPlan(name="fixture", rules=(_RULE,)))
    result = SegmentSimilarityIndex(state).find(
        rule_name="board-items",
        threshold=0.60,
        shingle_size=3,
        min_shared_shingles=3,
        max_shingle_frequency=64,
        limit=20,
    )

    # Byte-identical Jan-27-archived / Feb-3 source contexts collapse to one segment but
    # expand back to distinct family occurrences for recurrence analysis.
    assert result.segment_count == 4
    assert result.occurrence_count == 5
    assert result.possible_all_pairs == 10
    assert result.candidate_pairs_generated < result.possible_all_pairs
    assert result.candidate_pairs_compared <= result.candidate_pairs_generated
    assert result.same_family_pairs_skipped >= 1

    pairs = {
        frozenset(
            source["source_uri"]
            for occurrence in (candidate.left, candidate.right)
            for source in occurrence.sources
        )
        for candidate in result.candidates
    }

    # The current/archived Jan 27 pair is explicitly version-related and must not surface.
    assert frozenset({"https://example.gov/jan27", "https://example.gov/jan27-old"}) not in pairs

    # The same content published under the unrelated Feb 3 source remains visible as a
    # cross-family occurrence even though it shares one content-addressed artifact with Jan 27.
    assert frozenset({"https://example.gov/jan27-old", "https://example.gov/feb3"}) in pairs

    # Cross-meeting variants also surface, including the later addition of BRINCS.
    assert any(
        {"https://example.gov/feb3", "https://example.gov/feb10"}.issubset(pair)
        for pair in pairs
    )
    assert any(candidate.similarity > 0.90 for candidate in result.candidates)
    assert all(candidate.left.family_id != candidate.right.family_id for candidate in result.candidates)

    # All candidates remain evidence-local and each occurrence carries only the sources
    # belonging to its own family context.
    assert all(
        candidate.left.segment.evidence_id and candidate.right.segment.evidence_id
        for candidate in result.candidates
    )
    assert all(candidate.left.sources and candidate.right.sources for candidate in result.candidates)
    for candidate in result.candidates:
        left_family_sources = {
            source["source_id"] for source in candidate.left.sources
        }
        right_family_sources = {
            source["source_id"] for source in candidate.right.sources
        }
        assert left_family_sources.isdisjoint(right_family_sources)
