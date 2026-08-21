"""Label-free deterministic grouping over local layout regions.

R1.T19 deliberately derives topology from geometric nearest-neighbor relations
only. It does not assign table, field, financial, transaction, event, anomaly,
or lead semantics to a component.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from .hashing import stable_id
from .local_layout import LocalLayoutRelation, SpatialRegion, relation_between_regions
from .spatial_text import SpatialPageResult


LOCAL_GROUPING_METHOD = "proofline-local-grouping/nearest-components-v1"


@dataclass(frozen=True, slots=True)
class NearestNeighborEdge:
    edge_id: str
    grouping_method: str
    spatial_id: str
    evidence_id: str
    source_region_id: str
    target_region_id: str
    relation_id: str
    normalized_distance: float
    reading_order_delta: int
    mutual_nearest: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LocalLayoutComponent:
    component_id: str
    grouping_method: str
    spatial_id: str
    evidence_id: str
    region_ids: tuple[str, ...]
    word_order_indices: tuple[int, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["region_ids"] = list(self.region_ids)
        data["word_order_indices"] = list(self.word_order_indices)
        return data


@dataclass(frozen=True, slots=True)
class LocalGroupingResult:
    grouping_id: str
    method: str
    spatial_id: str
    evidence_id: str
    region_ids: tuple[str, ...]
    nearest_edges: tuple[NearestNeighborEdge, ...]
    components: tuple[LocalLayoutComponent, ...]

    def to_dict(self) -> dict:
        return {
            "grouping_id": self.grouping_id,
            "method": self.method,
            "spatial_id": self.spatial_id,
            "evidence_id": self.evidence_id,
            "region_ids": list(self.region_ids),
            "region_count": len(self.region_ids),
            "nearest_edges": [edge.to_dict() for edge in self.nearest_edges],
            "nearest_edge_count": len(self.nearest_edges),
            "mutual_nearest_edge_count": sum(edge.mutual_nearest for edge in self.nearest_edges),
            "components": [component.to_dict() for component in self.components],
            "component_count": len(self.components),
        }


def _validate_regions(
    page: SpatialPageResult,
    regions,
) -> tuple[SpatialRegion, ...]:
    normalized = tuple(regions)
    if not normalized:
        raise ValueError("local grouping requires at least one region")

    by_id: dict[str, SpatialRegion] = {}
    covered_words: set[int] = set()
    for region in normalized:
        if region.spatial_id != page.spatial_id or region.evidence_id != page.evidence_id:
            raise ValueError("local grouping region lineage does not match page")
        if region.region_id in by_id:
            raise ValueError(f"duplicate local grouping region: {region.region_id}")
        overlapping = covered_words.intersection(region.word_order_indices)
        if overlapping:
            raise ValueError(
                "local grouping regions must not overlap word membership: "
                f"{sorted(overlapping)}"
            )
        by_id[region.region_id] = region
        covered_words.update(region.word_order_indices)

    return tuple(
        sorted(
            by_id.values(),
            key=lambda region: (region.word_order_indices, region.region_id),
        )
    )


def _relation_sort_key(relation: LocalLayoutRelation) -> tuple:
    return (
        relation.normalized_center_distance_page_diagonal,
        abs(relation.reading_order_delta),
        relation.target_word_order_indices,
        relation.target_region_id,
        relation.relation_id,
    )


def _component_word_indices(
    region_ids: tuple[str, ...],
    by_id: dict[str, SpatialRegion],
) -> tuple[int, ...]:
    return tuple(
        sorted(
            index
            for region_id in region_ids
            for index in by_id[region_id].word_order_indices
        )
    )


def nearest_neighbor_components(
    page: SpatialPageResult,
    regions,
    *,
    method: str = LOCAL_GROUPING_METHOD,
) -> LocalGroupingResult:
    """Derive threshold-free components from each region's nearest geometric peer.

    Each non-singleton region chooses exactly one nearest peer under the frozen
    local-layout relation sort. Selected directed edges are then treated as an
    undirected graph and connected components are emitted. Labels, values, and
    document semantics are not inputs.
    """
    if not method:
        raise ValueError("local grouping method must be non-empty")
    ordered = _validate_regions(page, regions)
    by_id = {region.region_id: region for region in ordered}

    grouping_id = stable_id(
        "layout-grouping",
        method,
        page.spatial_id,
        ",".join(region.region_id for region in ordered),
    )

    if len(ordered) == 1:
        region = ordered[0]
        component = LocalLayoutComponent(
            component_id=stable_id(
                "layout-component",
                method,
                page.spatial_id,
                region.region_id,
            ),
            grouping_method=method,
            spatial_id=page.spatial_id,
            evidence_id=page.evidence_id,
            region_ids=(region.region_id,),
            word_order_indices=region.word_order_indices,
        )
        return LocalGroupingResult(
            grouping_id=grouping_id,
            method=method,
            spatial_id=page.spatial_id,
            evidence_id=page.evidence_id,
            region_ids=(region.region_id,),
            nearest_edges=(),
            components=(component,),
        )

    selected_relations: dict[str, LocalLayoutRelation] = {}
    for source in ordered:
        candidates = [
            relation_between_regions(page, source, target)
            for target in ordered
            if target.region_id != source.region_id
        ]
        candidates.sort(key=_relation_sort_key)
        selected_relations[source.region_id] = candidates[0]

    nearest_target = {
        source_region_id: relation.target_region_id
        for source_region_id, relation in selected_relations.items()
    }
    edges: list[NearestNeighborEdge] = []
    for source_region_id in sorted(
        selected_relations,
        key=lambda region_id: (by_id[region_id].word_order_indices, region_id),
    ):
        relation = selected_relations[source_region_id]
        mutual = nearest_target.get(relation.target_region_id) == source_region_id
        edges.append(
            NearestNeighborEdge(
                edge_id=stable_id(
                    "layout-nearest-edge",
                    method,
                    page.spatial_id,
                    source_region_id,
                    relation.target_region_id,
                    relation.relation_id,
                ),
                grouping_method=method,
                spatial_id=page.spatial_id,
                evidence_id=page.evidence_id,
                source_region_id=source_region_id,
                target_region_id=relation.target_region_id,
                relation_id=relation.relation_id,
                normalized_distance=relation.normalized_center_distance_page_diagonal,
                reading_order_delta=relation.reading_order_delta,
                mutual_nearest=mutual,
            )
        )

    adjacency: dict[str, set[str]] = {region.region_id: set() for region in ordered}
    for edge in edges:
        adjacency[edge.source_region_id].add(edge.target_region_id)
        adjacency[edge.target_region_id].add(edge.source_region_id)

    components: list[LocalLayoutComponent] = []
    seen: set[str] = set()
    for region in ordered:
        if region.region_id in seen:
            continue
        stack = [region.region_id]
        seen.add(region.region_id)
        member_ids: list[str] = []
        while stack:
            current = stack.pop()
            member_ids.append(current)
            neighbors = sorted(
                adjacency[current],
                key=lambda region_id: (by_id[region_id].word_order_indices, region_id),
                reverse=True,
            )
            for neighbor in neighbors:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)

        ordered_ids = tuple(
            sorted(
                member_ids,
                key=lambda region_id: (by_id[region_id].word_order_indices, region_id),
            )
        )
        components.append(
            LocalLayoutComponent(
                component_id=stable_id(
                    "layout-component",
                    method,
                    page.spatial_id,
                    ",".join(ordered_ids),
                ),
                grouping_method=method,
                spatial_id=page.spatial_id,
                evidence_id=page.evidence_id,
                region_ids=ordered_ids,
                word_order_indices=_component_word_indices(ordered_ids, by_id),
            )
        )

    components.sort(key=lambda component: (component.word_order_indices, component.component_id))
    return LocalGroupingResult(
        grouping_id=grouping_id,
        method=method,
        spatial_id=page.spatial_id,
        evidence_id=page.evidence_id,
        region_ids=tuple(region.region_id for region in ordered),
        nearest_edges=tuple(edges),
        components=tuple(components),
    )
