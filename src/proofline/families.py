"""Deterministic connected components over evidence-backed source relations.

Source families are a derived graph view. They do not infer relationships from text,
filenames, dates, or shared bytes. Only persisted source relations may join sources into a
family; otherwise each source is a singleton family.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .hashing import stable_id
from .relations import RelationStore


@dataclass(frozen=True, slots=True)
class SourceFamily:
    family_id: str
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class SourceFamilyResolver:
    """Resolve transitive source families from explicit relation edges."""

    def __init__(
        self,
        state_dir: str | Path = ".proofline",
        *,
        relation_type: str = "historical_version_of",
    ) -> None:
        self.state_dir = Path(state_dir)
        self.relations = RelationStore(self.state_dir)
        self.store = self.relations.store
        self.relation_type = relation_type
        self._families: tuple[SourceFamily, ...] | None = None
        self._source_to_family: dict[str, str] | None = None
        self._family_to_sources: dict[str, tuple[str, ...]] | None = None
        self._artifact_to_families: dict[str, tuple[str, ...]] = {}

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
        # Deterministic root choice keeps the same graph stable across row ordering.
        if right_root < left_root:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root

    def _build(self) -> None:
        if (
            self._families is not None
            and self._source_to_family is not None
            and self._family_to_sources is not None
        ):
            return
        with self.store.connection() as connection:
            sources = [
                str(row["source_id"])
                for row in connection.execute(
                    "SELECT source_id FROM sources ORDER BY source_id"
                ).fetchall()
            ]
            edges = connection.execute(
                """
                SELECT source_id, related_source_id
                FROM source_relations
                WHERE relation_type = ?
                ORDER BY source_id, related_source_id
                """,
                (self.relation_type,),
            ).fetchall()

        parent = {source_id: source_id for source_id in sources}
        for edge in edges:
            left = str(edge["source_id"])
            right = str(edge["related_source_id"])
            # Source-relation FKs normally guarantee these nodes exist; setdefault keeps
            # the graph view robust if an older database predates those constraints.
            parent.setdefault(left, left)
            parent.setdefault(right, right)
            self._union(parent, left, right)

        components: dict[str, list[str]] = {}
        for source_id in sorted(parent):
            root = self._find(parent, source_id)
            components.setdefault(root, []).append(source_id)

        families: list[SourceFamily] = []
        source_to_family: dict[str, str] = {}
        family_to_sources: dict[str, tuple[str, ...]] = {}
        for members in sorted((tuple(sorted(values)) for values in components.values())):
            family_id = stable_id("source-family", *members)
            family = SourceFamily(family_id=family_id, source_ids=members)
            families.append(family)
            family_to_sources[family_id] = members
            for source_id in members:
                source_to_family[source_id] = family_id

        self._families = tuple(families)
        self._source_to_family = source_to_family
        self._family_to_sources = family_to_sources

    def families(self) -> tuple[SourceFamily, ...]:
        self._build()
        assert self._families is not None
        return self._families

    def family_id_for_source(self, source_id: str) -> str | None:
        self._build()
        assert self._source_to_family is not None
        return self._source_to_family.get(source_id)

    def source_ids_for_family(self, family_id: str) -> tuple[str, ...]:
        self._build()
        assert self._family_to_sources is not None
        return self._family_to_sources.get(family_id, ())

    def family_ids_for_artifact(self, artifact_id: str) -> tuple[str, ...]:
        cached = self._artifact_to_families.get(artifact_id)
        if cached is not None:
            return cached
        self._build()
        assert self._source_to_family is not None
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT source_id
                FROM source_snapshots
                WHERE artifact_id = ?
                ORDER BY source_id
                """,
                (artifact_id,),
            ).fetchall()
        family_ids = tuple(
            sorted(
                {
                    self._source_to_family[str(row["source_id"])]
                    for row in rows
                    if str(row["source_id"]) in self._source_to_family
                }
            )
        )
        self._artifact_to_families[artifact_id] = family_ids
        return family_ids

    def artifacts_share_family(self, left_artifact_id: str, right_artifact_id: str) -> bool:
        left = set(self.family_ids_for_artifact(left_artifact_id))
        right = set(self.family_ids_for_artifact(right_artifact_id))
        return bool(left.intersection(right))
