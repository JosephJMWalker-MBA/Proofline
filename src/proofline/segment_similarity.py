"""Deterministic near-duplicate candidates over evidence-local segments.

Candidate generation uses an inverted token-shingle index with a maximum document-frequency
bucket size. It therefore never constructs an all-pairs similarity matrix. Exact Jaccard is
computed only for pairs that share enough non-ubiquitous shingles and occur in distinct
publisher-backed source-family contexts.
"""

from __future__ import annotations

import itertools
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from .families import SourceFamilyResolver
from .segments import SegmentHit, SegmentIndex

_METHOD = "token_shingle_jaccard/v1"
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SegmentOccurrence:
    """One segment observed in one publisher-backed source-family context."""

    family_id: str
    sources: tuple[dict, ...]
    segment: SegmentHit

    def to_dict(self) -> dict:
        return {
            "family_id": self.family_id,
            "sources": list(self.sources),
            "segment": self.segment.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class NearDuplicateCandidate:
    similarity: float
    shared_shingles: int
    left: SegmentOccurrence
    right: SegmentOccurrence
    method: str = _METHOD

    def to_dict(self) -> dict:
        return {
            "similarity": self.similarity,
            "shared_shingles": self.shared_shingles,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class NearDuplicateResult:
    build_id: str
    method: str
    rule_name: str | None
    segment_type: str | None
    segment_count: int
    occurrence_count: int
    possible_all_pairs: int
    candidate_pairs_generated: int
    candidate_pairs_compared: int
    same_family_pairs_skipped: int
    common_shingle_buckets_ignored: int
    shingle_size: int
    min_shared_shingles: int
    max_shingle_frequency: int
    threshold: float
    candidates: tuple[NearDuplicateCandidate, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return data


def token_shingles(text: str, *, size: int = 3) -> frozenset[tuple[str, ...]]:
    if size < 1:
        raise ValueError("shingle size must be positive")
    tokens = [match.group(0).casefold() for match in _TOKEN_RE.finditer(text)]
    if len(tokens) < size:
        return frozenset()
    return frozenset(tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1))


class SegmentSimilarityIndex:
    """Generate scalable lexical near-duplicate candidates from the current segment build."""

    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.segments = SegmentIndex(self.state_dir)
        self.store = self.segments.store
        self.families = SourceFamilyResolver(self.state_dir)
        self._source_cache: dict[str, tuple[dict, ...]] = {}

    def _sources_for_artifact(self, artifact_id: str) -> tuple[dict, ...]:
        cached = self._source_cache.get(artifact_id)
        if cached is not None:
            return cached
        with self.store.connection() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT s.source_id, s.source_uri, s.source_name, ss.native_identifier
                FROM source_snapshots ss
                JOIN sources s ON s.source_id = ss.source_id
                WHERE ss.artifact_id = ?
                ORDER BY s.source_uri
                """,
                (artifact_id,),
            ).fetchall()
        value = tuple(dict(row) for row in rows)
        self._source_cache[artifact_id] = value
        return value

    def _hit(self, row) -> SegmentHit:
        return SegmentHit(
            build_id=row["build_id"],
            segment_id=row["segment_id"],
            evidence_id=row["evidence_id"],
            artifact_id=row["artifact_id"],
            locator=row["locator"],
            rule_name=row["rule_name"],
            segment_type=row["segment_type"],
            anchor_text=row["anchor_text"],
            normalized_anchor=row["normalized_anchor"],
            raw_text=row["raw_text"],
            normalized_text=row["normalized_text"],
            text_sha256=row["text_sha256"],
            char_start=int(row["char_start"]),
            char_end=int(row["char_end"]),
            sources=self._sources_for_artifact(row["artifact_id"]),
        )

    def _occurrences(self, hits: list[SegmentHit]) -> list[SegmentOccurrence]:
        occurrences: list[SegmentOccurrence] = []
        for hit in hits:
            for family_id in self.families.family_ids_for_artifact(hit.artifact_id):
                member_ids = set(self.families.source_ids_for_family(family_id))
                sources = tuple(
                    source for source in hit.sources if source.get("source_id") in member_ids
                )
                if not sources:
                    continue
                occurrences.append(
                    SegmentOccurrence(
                        family_id=family_id,
                        sources=sources,
                        segment=hit,
                    )
                )
        occurrences.sort(
            key=lambda item: (item.family_id, item.segment.segment_id)
        )
        return occurrences

    def find(
        self,
        *,
        threshold: float = 0.60,
        shingle_size: int = 3,
        min_shared_shingles: int = 3,
        max_shingle_frequency: int = 64,
        rule_name: str | None = None,
        segment_type: str | None = None,
        limit: int = 100,
    ) -> NearDuplicateResult:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        if shingle_size < 1:
            raise ValueError("shingle_size must be positive")
        if min_shared_shingles < 1:
            raise ValueError("min_shared_shingles must be positive")
        if max_shingle_frequency < 2:
            raise ValueError("max_shingle_frequency must be at least 2")
        if limit < 1:
            raise ValueError("limit must be positive")

        build = self.segments.current_build()
        if build is None:
            raise RuntimeError("segment index has not been built; run `proofline segment` first")

        clauses = ["build_id = ?"]
        params: list[object] = [build["build_id"]]
        if rule_name is not None:
            clauses.append("rule_name = ?")
            params.append(rule_name)
        if segment_type is not None:
            clauses.append("segment_type = ?")
            params.append(segment_type)
        with self.store.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM evidence_segments
                WHERE {' AND '.join(clauses)}
                ORDER BY segment_id
                """,
                params,
            ).fetchall()

        hits = [self._hit(row) for row in rows]
        occurrences = self._occurrences(hits)
        shingle_cache = {
            hit.segment_id: token_shingles(hit.normalized_text, size=shingle_size)
            for hit in hits
        }
        occurrence_shingles = [
            shingle_cache[item.segment.segment_id] for item in occurrences
        ]

        inverted: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for index, values in enumerate(occurrence_shingles):
            for shingle in values:
                inverted[shingle].append(index)

        shared_candidate_counts: dict[tuple[int, int], int] = defaultdict(int)
        same_family_pairs: set[tuple[int, int]] = set()
        common_shingle_buckets_ignored = 0
        for members in inverted.values():
            if len(members) > max_shingle_frequency:
                common_shingle_buckets_ignored += 1
                continue
            if len(members) < 2:
                continue
            for left_index, right_index in itertools.combinations(members, 2):
                if occurrences[left_index].family_id == occurrences[right_index].family_id:
                    same_family_pairs.add((left_index, right_index))
                    continue
                shared_candidate_counts[(left_index, right_index)] += 1

        compared = 0
        candidates: list[NearDuplicateCandidate] = []
        for pair, candidate_shared in shared_candidate_counts.items():
            if candidate_shared < min_shared_shingles:
                continue
            left_index, right_index = pair
            left_shingles = occurrence_shingles[left_index]
            right_shingles = occurrence_shingles[right_index]
            if not left_shingles or not right_shingles:
                continue
            compared += 1
            shared_shingles = len(left_shingles.intersection(right_shingles))
            union_size = len(left_shingles.union(right_shingles))
            similarity = shared_shingles / union_size if union_size else 0.0
            if similarity < threshold:
                continue
            candidates.append(
                NearDuplicateCandidate(
                    similarity=similarity,
                    shared_shingles=shared_shingles,
                    left=occurrences[left_index],
                    right=occurrences[right_index],
                )
            )

        candidates.sort(
            key=lambda item: (
                -item.similarity,
                -item.shared_shingles,
                item.left.family_id,
                item.left.segment.segment_id,
                item.right.family_id,
                item.right.segment.segment_id,
            )
        )
        limited = tuple(candidates[:limit])
        occurrence_count = len(occurrences)
        return NearDuplicateResult(
            build_id=str(build["build_id"]),
            method=_METHOD,
            rule_name=rule_name,
            segment_type=segment_type,
            segment_count=len(hits),
            occurrence_count=occurrence_count,
            possible_all_pairs=occurrence_count * (occurrence_count - 1) // 2,
            candidate_pairs_generated=len(shared_candidate_counts),
            candidate_pairs_compared=compared,
            same_family_pairs_skipped=len(same_family_pairs),
            common_shingle_buckets_ignored=common_shingle_buckets_ignored,
            shingle_size=shingle_size,
            min_shared_shingles=min_shared_shingles,
            max_shingle_frequency=max_shingle_frequency,
            threshold=threshold,
            candidates=limited,
        )
