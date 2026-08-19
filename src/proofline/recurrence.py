"""Connected recurrence clusters over deterministic near-duplicate segment candidates.

A recurrence cluster is still a derived candidate structure, not an accusation or finding.
It groups pairwise similarity edges so one pattern spanning several publisher contexts is not
presented as several independent findings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .hashing import stable_id
from .segment_similarity import NearDuplicateCandidate, SegmentOccurrence, SegmentSimilarityIndex

_METHOD = "segment_recurrence_connected_components/v1"


@dataclass(frozen=True, slots=True)
class RecurrenceEdge:
    left_key: str
    right_key: str
    similarity: float
    shared_shingles: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecurrenceCluster:
    cluster_id: str
    method: str
    similarity_method: str
    threshold: float
    occurrence_count: int
    family_count: int
    evidence_count: int
    edge_count: int
    min_edge_similarity: float
    max_edge_similarity: float
    mean_edge_similarity: float
    occurrences: tuple[SegmentOccurrence, ...]
    edges: tuple[RecurrenceEdge, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["occurrences"] = [item.to_dict() for item in self.occurrences]
        data["edges"] = [item.to_dict() for item in self.edges]
        data["limitations"] = list(self.limitations)
        return data


@dataclass(frozen=True, slots=True)
class RecurrenceResult:
    method: str
    similarity_method: str
    threshold: float
    candidate_edge_count: int
    cluster_count: int
    returned_cluster_count: int
    clusters: tuple[RecurrenceCluster, ...]

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "similarity_method": self.similarity_method,
            "threshold": self.threshold,
            "candidate_edge_count": self.candidate_edge_count,
            "cluster_count": self.cluster_count,
            "returned_cluster_count": self.returned_cluster_count,
            "clusters": [cluster.to_dict() for cluster in self.clusters],
        }


def _occurrence_key(item: SegmentOccurrence) -> str:
    return f"{item.family_id}|{item.segment.segment_id}"


class SegmentRecurrenceClusterer:
    """Group cross-family near-duplicate edges into deterministic connected components."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.similarity = SegmentSimilarityIndex(self.state_dir)

    @staticmethod
    def _find(parent: dict[str, str], value: str) -> str:
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            next_value = parent[value]
            parent[value] = root
            value = next_value
        return root

    @classmethod
    def _union(cls, parent: dict[str, str], left: str, right: str) -> None:
        left_root = cls._find(parent, left)
        right_root = cls._find(parent, right)
        if left_root == right_root:
            return
        if right_root < left_root:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root

    @classmethod
    def from_candidates(
        cls,
        candidates: tuple[NearDuplicateCandidate, ...],
        *,
        similarity_method: str,
        threshold: float,
        min_occurrences: int = 2,
        limit: int | None = 100,
    ) -> RecurrenceResult:
        if min_occurrences < 2:
            raise ValueError("min_occurrences must be at least 2")
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive or None")

        parent: dict[str, str] = {}
        occurrence_by_key: dict[str, SegmentOccurrence] = {}
        edge_records: list[tuple[str, str, NearDuplicateCandidate]] = []
        for candidate in candidates:
            left_key = _occurrence_key(candidate.left)
            right_key = _occurrence_key(candidate.right)
            parent.setdefault(left_key, left_key)
            parent.setdefault(right_key, right_key)
            occurrence_by_key[left_key] = candidate.left
            occurrence_by_key[right_key] = candidate.right
            cls._union(parent, left_key, right_key)
            if right_key < left_key:
                left_key, right_key = right_key, left_key
            edge_records.append((left_key, right_key, candidate))

        component_nodes: dict[str, list[str]] = {}
        for key in sorted(parent):
            root = cls._find(parent, key)
            component_nodes.setdefault(root, []).append(key)

        component_edges: dict[str, list[tuple[str, str, NearDuplicateCandidate]]] = {}
        for left_key, right_key, candidate in edge_records:
            root = cls._find(parent, left_key)
            component_edges.setdefault(root, []).append((left_key, right_key, candidate))

        clusters: list[RecurrenceCluster] = []
        for root, keys in component_nodes.items():
            if len(keys) < min_occurrences:
                continue
            occurrences = tuple(
                sorted(
                    (occurrence_by_key[key] for key in keys),
                    key=lambda item: (item.family_id, item.segment.segment_id),
                )
            )
            edges_raw = component_edges.get(root, [])
            edges = tuple(
                RecurrenceEdge(
                    left_key=left_key,
                    right_key=right_key,
                    similarity=candidate.similarity,
                    shared_shingles=candidate.shared_shingles,
                )
                for left_key, right_key, candidate in sorted(
                    edges_raw,
                    key=lambda item: (item[0], item[1], -item[2].similarity),
                )
            )
            similarities = [edge.similarity for edge in edges]
            family_count = len({item.family_id for item in occurrences})
            evidence_count = len({item.segment.evidence_id for item in occurrences})
            cluster_id = stable_id(
                "segment-recurrence-cluster",
                _METHOD,
                similarity_method,
                f"{threshold:.12g}",
                *sorted(keys),
            )
            clusters.append(
                RecurrenceCluster(
                    cluster_id=cluster_id,
                    method=_METHOD,
                    similarity_method=similarity_method,
                    threshold=threshold,
                    occurrence_count=len(occurrences),
                    family_count=family_count,
                    evidence_count=evidence_count,
                    edge_count=len(edges),
                    min_edge_similarity=min(similarities),
                    max_edge_similarity=max(similarities),
                    mean_edge_similarity=sum(similarities) / len(similarities),
                    occurrences=occurrences,
                    edges=edges,
                    limitations=(
                        "Connected components use single-linkage: two endpoint occurrences may share no direct edge if each connects through another occurrence.",
                        "Lexical similarity can reflect routine agenda carry-forward, boilerplate, amendments, or repeated procurement language.",
                        "A recurrence cluster describes repeated language across publisher contexts; it does not establish wrongdoing, coordination, or material significance.",
                    ),
                )
            )

        clusters.sort(
            key=lambda item: (
                -item.family_count,
                -item.occurrence_count,
                -item.max_edge_similarity,
                item.cluster_id,
            )
        )
        cluster_count = len(clusters)
        returned = clusters if limit is None else clusters[:limit]
        return RecurrenceResult(
            method=_METHOD,
            similarity_method=similarity_method,
            threshold=threshold,
            candidate_edge_count=len(candidates),
            cluster_count=cluster_count,
            returned_cluster_count=len(returned),
            clusters=tuple(returned),
        )

    def find(
        self,
        *,
        threshold: float = 0.60,
        shingle_size: int = 3,
        min_shared_shingles: int = 3,
        max_shingle_frequency: int = 64,
        rule_name: str | None = None,
        segment_type: str | None = None,
        min_occurrences: int = 2,
        limit: int | None = 100,
    ) -> RecurrenceResult:
        similarity = self.similarity.find(
            threshold=threshold,
            shingle_size=shingle_size,
            min_shared_shingles=min_shared_shingles,
            max_shingle_frequency=max_shingle_frequency,
            rule_name=rule_name,
            segment_type=segment_type,
            limit=None,
        )
        return self.from_candidates(
            similarity.candidates,
            similarity_method=similarity.method,
            threshold=threshold,
            min_occurrences=min_occurrences,
            limit=limit,
        )
