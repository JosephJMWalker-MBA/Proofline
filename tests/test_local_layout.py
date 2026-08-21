from __future__ import annotations

from dataclasses import replace

import pytest

from proofline.local_layout import (
    bounded_word_neighbors,
    region_from_word_indices,
    relation_between_regions,
)
from proofline.spatial_text import SpatialPageResult, SpatialWord


def _page() -> SpatialPageResult:
    words = (
        SpatialWord(1, "CASH", (10.0, 10.0, 40.0, 20.0), 0, 0, 0),
        SpatialWord(2, "ASSESSED:", (45.0, 10.0, 90.0, 20.0), 0, 0, 1),
        SpatialWord(3, "$220,682.90", (100.0, 30.0, 160.0, 40.0), 0, 1, 0),
        SpatialWord(4, "FAR", (170.0, 170.0, 190.0, 180.0), 1, 0, 0),
        SpatialWord(5, "LOCAL", (92.0, 10.0, 122.0, 20.0), 2, 0, 0),
    )
    return SpatialPageResult(
        spatial_id="spatial:test",
        evidence_id="evidence:test-page-1",
        artifact_id="artifact:test",
        page_number=1,
        page_bbox=(0.0, 0.0, 200.0, 200.0),
        source_text_method="pymupdf_native_text",
        spatial_method="pymupdf_native_words/v1",
        software_version="test",
        model_version=None,
        source_text_sha256="abc",
        source_text_quality=1.0,
        word_signature_sha256="def",
        words=words,
    )


def test_region_from_word_indices_is_deterministic_and_lineage_bound() -> None:
    page = _page()

    first = region_from_word_indices(page, (2, 1, 2))
    second = region_from_word_indices(page, (1, 2))

    assert first == second
    assert first.region_id.startswith("layout-region:")
    assert first.spatial_id == page.spatial_id
    assert first.evidence_id == page.evidence_id
    assert first.word_order_indices == (1, 2)
    assert first.text == "CASH ASSESSED:"
    assert first.bbox == (10.0, 10.0, 90.0, 20.0)
    assert first.x_center == 50.0
    assert first.y_center == 15.0


def test_region_from_word_indices_rejects_empty_or_missing_words() -> None:
    page = _page()

    with pytest.raises(ValueError, match="at least one word"):
        region_from_word_indices(page, ())
    with pytest.raises(ValueError, match="missing word indices"):
        region_from_word_indices(page, (99,))


def test_relation_between_regions_measures_local_geometry_without_line_semantics() -> None:
    page = _page()
    label = region_from_word_indices(page, (1, 2))
    amount = region_from_word_indices(page, (3,))

    first = relation_between_regions(page, label, amount)
    second = relation_between_regions(page, label, amount)

    assert first == second
    assert first.relation_id.startswith("layout-relation:")
    assert first.spatial_id == page.spatial_id
    assert first.evidence_id == page.evidence_id
    assert first.source_word_order_indices == (1, 2)
    assert first.target_word_order_indices == (3,)
    assert first.dx_center_points == 80.0
    assert first.dy_center_points == 20.0
    assert first.center_distance_points == pytest.approx(82.462, abs=0.001)
    assert first.normalized_dx_page_width == 0.4
    assert first.normalized_dy_page_height == 0.1
    assert first.normalized_center_distance_page_diagonal == pytest.approx(0.29155, abs=0.00001)
    assert first.normalized_center_distance_mean_word_height == pytest.approx(8.2462, abs=0.0001)
    assert first.horizontal_overlap_ratio == 0.0
    assert first.vertical_overlap_ratio == 0.0
    assert first.horizontal_gap_points == 10.0
    assert first.vertical_gap_points == 10.0
    assert first.reading_order_delta == 1
    assert first.same_extractor_line is False
    assert first.dominant_direction == "right"


def test_relation_rejects_self_relation_and_cross_page_lineage() -> None:
    page = _page()
    label = region_from_word_indices(page, (1, 2))

    with pytest.raises(ValueError, match="distinct regions"):
        relation_between_regions(page, label, label)

    other_page = replace(page, spatial_id="spatial:other")
    other = region_from_word_indices(other_page, (3,))
    with pytest.raises(ValueError, match="lineage"):
        relation_between_regions(page, label, other)


def test_bounded_word_neighbors_are_deterministic_and_distance_ordered() -> None:
    page = _page()
    label = region_from_word_indices(page, (1, 2))

    neighbors = bounded_word_neighbors(
        page,
        label,
        max_page_distance_ratio=0.35,
        limit=10,
    )

    assert [relation.target_word_order_indices for relation in neighbors] == [(5,), (3,)]
    assert all(index not in {1, 2} for relation in neighbors for index in relation.target_word_order_indices)
    assert neighbors[0].center_distance_points < neighbors[1].center_distance_points

    assert bounded_word_neighbors(
        page,
        label,
        max_page_distance_ratio=0.35,
        limit=1,
    ) == neighbors[:1]


def test_bounded_word_neighbors_validate_bounds() -> None:
    page = _page()
    label = region_from_word_indices(page, (1, 2))

    with pytest.raises(ValueError, match="max_page_distance_ratio"):
        bounded_word_neighbors(page, label, max_page_distance_ratio=0.0)
    with pytest.raises(ValueError, match="neighbor limit"):
        bounded_word_neighbors(page, label, limit=0)
