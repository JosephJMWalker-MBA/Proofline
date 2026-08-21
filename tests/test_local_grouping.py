from __future__ import annotations

from dataclasses import replace

import pytest

from proofline.local_grouping import nearest_neighbor_components
from proofline.local_layout import region_from_word_indices
from proofline.spatial_text import SpatialPageResult, SpatialWord


def _page() -> SpatialPageResult:
    words = (
        SpatialWord(1, "A", (10.0, 10.0, 18.0, 20.0), 0, 0, 0),
        SpatialWord(2, "B", (24.0, 10.0, 32.0, 20.0), 0, 0, 1),
        SpatialWord(3, "C", (150.0, 150.0, 158.0, 160.0), 1, 0, 0),
        SpatialWord(4, "D", (164.0, 150.0, 172.0, 160.0), 1, 0, 1),
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


def test_nearest_neighbor_components_split_threshold_free_local_pairs() -> None:
    page = _page()
    regions = [region_from_word_indices(page, (index,)) for index in (1, 2, 3, 4)]

    first = nearest_neighbor_components(page, regions)
    second = nearest_neighbor_components(page, reversed(regions))

    assert first == second
    assert first.grouping_id.startswith("layout-grouping:")
    assert first.spatial_id == page.spatial_id
    assert first.evidence_id == page.evidence_id
    assert len(first.nearest_edges) == 4
    assert all(edge.edge_id.startswith("layout-nearest-edge:") for edge in first.nearest_edges)
    assert all(edge.mutual_nearest for edge in first.nearest_edges)
    assert len(first.components) == 2
    assert [component.word_order_indices for component in first.components] == [(1, 2), (3, 4)]
    assert all(component.component_id.startswith("layout-component:") for component in first.components)

    serialized = first.to_dict()
    assert serialized["region_count"] == 4
    assert serialized["nearest_edge_count"] == 4
    assert serialized["mutual_nearest_edge_count"] == 4
    assert serialized["component_count"] == 2


def test_nearest_neighbor_ties_resolve_by_existing_region_order_contract() -> None:
    words = (
        SpatialWord(1, "LEFT", (36.0, 50.0, 44.0, 60.0), 0, 0, 0),
        SpatialWord(2, "CENTER", (46.0, 50.0, 54.0, 60.0), 0, 0, 1),
        SpatialWord(3, "RIGHT", (56.0, 50.0, 64.0, 60.0), 0, 0, 2),
    )
    page = replace(_page(), words=words)
    regions = [region_from_word_indices(page, (index,)) for index in (1, 2, 3)]

    result = nearest_neighbor_components(page, regions)
    center = regions[1]
    center_edge = next(edge for edge in result.nearest_edges if edge.source_region_id == center.region_id)

    assert center_edge.target_region_id == regions[0].region_id
    assert [component.word_order_indices for component in result.components] == [(1, 2, 3)]


def test_single_region_forms_stable_singleton_without_nearest_edge() -> None:
    page = _page()
    region = region_from_word_indices(page, (2,))

    result = nearest_neighbor_components(page, (region,))

    assert result.region_ids == (region.region_id,)
    assert result.nearest_edges == ()
    assert len(result.components) == 1
    assert result.components[0].region_ids == (region.region_id,)
    assert result.components[0].word_order_indices == (2,)


def test_grouping_rejects_empty_duplicate_cross_page_and_overlapping_regions() -> None:
    page = _page()
    one = region_from_word_indices(page, (1,))

    with pytest.raises(ValueError, match="at least one region"):
        nearest_neighbor_components(page, ())

    with pytest.raises(ValueError, match="duplicate"):
        nearest_neighbor_components(page, (one, one))

    other_page = replace(page, spatial_id="spatial:other")
    other = region_from_word_indices(other_page, (2,))
    with pytest.raises(ValueError, match="lineage"):
        nearest_neighbor_components(page, (one, other))

    overlap_a = region_from_word_indices(page, (1, 2))
    overlap_b = region_from_word_indices(page, (2, 3))
    with pytest.raises(ValueError, match="overlap word membership"):
        nearest_neighbor_components(page, (overlap_a, overlap_b))


def test_grouping_requires_nonempty_method() -> None:
    page = _page()
    region = region_from_word_indices(page, (1,))

    with pytest.raises(ValueError, match="method must be non-empty"):
        nearest_neighbor_components(page, (region,), method="")
