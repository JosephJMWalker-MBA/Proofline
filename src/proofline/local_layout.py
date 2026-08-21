"""Deterministic local-layout relations derived from spatial text evidence.

R1.T18 keeps this layer below document and financial semantics. Regions are
bounded selections of already-preserved spatial words; relations record geometry
between those regions without declaring rows, columns, fields, roles, or events.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .hashing import stable_id
from .spatial_text import BBox, SpatialPageResult, SpatialWord


LOCAL_LAYOUT_METHOD = "proofline-local-layout/v1"


def _extent(start: float, end: float) -> float:
    return max(0.0, float(end) - float(start))


def _axis_overlap_ratio(a0: float, a1: float, b0: float, b1: float) -> float:
    overlap = max(0.0, min(a1, b1) - max(a0, b0))
    denominator = min(_extent(a0, a1), _extent(b0, b1))
    if denominator <= 0:
        return 0.0
    return round(overlap / denominator, 6)


def _axis_gap(a0: float, a1: float, b0: float, b1: float) -> float:
    if a1 < b0:
        return round(b0 - a1, 3)
    if b1 < a0:
        return round(a0 - b1, 3)
    return 0.0


def _union_bbox(words: tuple[SpatialWord, ...]) -> BBox:
    return (
        round(min(word.bbox[0] for word in words), 3),
        round(min(word.bbox[1] for word in words), 3),
        round(max(word.bbox[2] for word in words), 3),
        round(max(word.bbox[3] for word in words), 3),
    )


def _word_map(page: SpatialPageResult) -> dict[int, SpatialWord]:
    result = {word.order_index: word for word in page.words}
    if len(result) != len(page.words):
        raise ValueError("spatial page contains duplicate word order indices")
    return result


@dataclass(frozen=True, slots=True)
class SpatialRegion:
    region_id: str
    spatial_id: str
    evidence_id: str
    word_order_indices: tuple[int, ...]
    text: str
    bbox: BBox

    @property
    def x_center(self) -> float:
        return round((self.bbox[0] + self.bbox[2]) / 2.0, 3)

    @property
    def y_center(self) -> float:
        return round((self.bbox[1] + self.bbox[3]) / 2.0, 3)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["word_order_indices"] = list(self.word_order_indices)
        data["bbox"] = list(self.bbox)
        data["x_center"] = self.x_center
        data["y_center"] = self.y_center
        return data


@dataclass(frozen=True, slots=True)
class LocalLayoutRelation:
    relation_id: str
    method: str
    spatial_id: str
    evidence_id: str
    source_region_id: str
    target_region_id: str
    source_word_order_indices: tuple[int, ...]
    target_word_order_indices: tuple[int, ...]
    dx_center_points: float
    dy_center_points: float
    center_distance_points: float
    normalized_dx_page_width: float
    normalized_dy_page_height: float
    normalized_center_distance_page_diagonal: float
    normalized_center_distance_mean_word_height: float
    horizontal_overlap_ratio: float
    vertical_overlap_ratio: float
    horizontal_gap_points: float
    vertical_gap_points: float
    reading_order_delta: int
    same_extractor_line: bool
    dominant_direction: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["source_word_order_indices"] = list(self.source_word_order_indices)
        data["target_word_order_indices"] = list(self.target_word_order_indices)
        return data


def region_from_word_indices(
    page: SpatialPageResult,
    word_order_indices,
) -> SpatialRegion:
    """Create a deterministic region from one or more words on a spatial page."""
    indices = tuple(sorted({int(index) for index in word_order_indices}))
    if not indices:
        raise ValueError("spatial region requires at least one word")

    words_by_index = _word_map(page)
    missing = [index for index in indices if index not in words_by_index]
    if missing:
        raise ValueError(f"spatial region references missing word indices: {missing}")
    words = tuple(words_by_index[index] for index in indices)
    region_id = stable_id(
        "layout-region",
        page.spatial_id,
        ",".join(str(index) for index in indices),
    )
    return SpatialRegion(
        region_id=region_id,
        spatial_id=page.spatial_id,
        evidence_id=page.evidence_id,
        word_order_indices=indices,
        text=" ".join(word.text for word in words),
        bbox=_union_bbox(words),
    )


def _region_words(page: SpatialPageResult, region: SpatialRegion) -> tuple[SpatialWord, ...]:
    if region.spatial_id != page.spatial_id or region.evidence_id != page.evidence_id:
        raise ValueError("spatial region lineage does not match page")
    words_by_index = _word_map(page)
    try:
        return tuple(words_by_index[index] for index in region.word_order_indices)
    except KeyError as exc:
        raise ValueError(f"spatial region references missing page word: {exc.args[0]}") from exc


def _dominant_direction(dx: float, dy: float) -> str:
    if dx == 0 and dy == 0:
        return "overlap"
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "below" if dy > 0 else "above"


def relation_between_regions(
    page: SpatialPageResult,
    source: SpatialRegion,
    target: SpatialRegion,
    *,
    method: str = LOCAL_LAYOUT_METHOD,
) -> LocalLayoutRelation:
    """Measure geometry between two regions without assigning semantic meaning."""
    if not method:
        raise ValueError("local-layout relation method must be non-empty")
    if source.region_id == target.region_id:
        raise ValueError("local-layout relation requires two distinct regions")

    source_words = _region_words(page, source)
    target_words = _region_words(page, target)

    page_width = _extent(page.page_bbox[0], page.page_bbox[2])
    page_height = _extent(page.page_bbox[1], page.page_bbox[3])
    if page_width <= 0 or page_height <= 0:
        raise ValueError("spatial page bounding box must have positive width and height")
    page_diagonal = math.hypot(page_width, page_height)

    dx = round(target.x_center - source.x_center, 3)
    dy = round(target.y_center - source.y_center, 3)
    distance = round(math.hypot(dx, dy), 3)
    word_heights = [
        _extent(word.bbox[1], word.bbox[3]) for word in (*source_words, *target_words)
    ]
    mean_word_height = sum(word_heights) / len(word_heights)
    normalized_by_height = distance / mean_word_height if mean_word_height > 0 else 0.0

    source_lines = {(word.block_index, word.line_index) for word in source_words}
    target_lines = {(word.block_index, word.line_index) for word in target_words}
    same_extractor_line = (
        len(source_lines) == 1
        and len(target_lines) == 1
        and next(iter(source_lines)) == next(iter(target_lines))
    )

    relation_id = stable_id(
        "layout-relation",
        method,
        page.spatial_id,
        source.region_id,
        target.region_id,
    )
    return LocalLayoutRelation(
        relation_id=relation_id,
        method=method,
        spatial_id=page.spatial_id,
        evidence_id=page.evidence_id,
        source_region_id=source.region_id,
        target_region_id=target.region_id,
        source_word_order_indices=source.word_order_indices,
        target_word_order_indices=target.word_order_indices,
        dx_center_points=dx,
        dy_center_points=dy,
        center_distance_points=distance,
        normalized_dx_page_width=round(dx / page_width, 6),
        normalized_dy_page_height=round(dy / page_height, 6),
        normalized_center_distance_page_diagonal=round(distance / page_diagonal, 6),
        normalized_center_distance_mean_word_height=round(normalized_by_height, 6),
        horizontal_overlap_ratio=_axis_overlap_ratio(
            source.bbox[0], source.bbox[2], target.bbox[0], target.bbox[2]
        ),
        vertical_overlap_ratio=_axis_overlap_ratio(
            source.bbox[1], source.bbox[3], target.bbox[1], target.bbox[3]
        ),
        horizontal_gap_points=_axis_gap(
            source.bbox[0], source.bbox[2], target.bbox[0], target.bbox[2]
        ),
        vertical_gap_points=_axis_gap(
            source.bbox[1], source.bbox[3], target.bbox[1], target.bbox[3]
        ),
        reading_order_delta=target.word_order_indices[0] - source.word_order_indices[-1],
        same_extractor_line=same_extractor_line,
        dominant_direction=_dominant_direction(dx, dy),
    )


def bounded_word_neighbors(
    page: SpatialPageResult,
    source: SpatialRegion,
    *,
    max_page_distance_ratio: float = 0.08,
    limit: int = 12,
) -> tuple[LocalLayoutRelation, ...]:
    """Return nearby single-word relations ordered only by measured geometry."""
    if not 0 < max_page_distance_ratio <= 1:
        raise ValueError("max_page_distance_ratio must be in (0, 1]")
    if limit < 1:
        raise ValueError("neighbor limit must be positive")

    _region_words(page, source)
    excluded = set(source.word_order_indices)
    relations: list[LocalLayoutRelation] = []
    for word in page.words:
        if word.order_index in excluded:
            continue
        target = region_from_word_indices(page, (word.order_index,))
        relation = relation_between_regions(page, source, target)
        if relation.normalized_center_distance_page_diagonal <= max_page_distance_ratio:
            relations.append(relation)

    relations.sort(
        key=lambda relation: (
            relation.normalized_center_distance_page_diagonal,
            abs(relation.reading_order_delta),
            relation.target_word_order_indices,
            relation.relation_id,
        )
    )
    return tuple(relations[:limit])
