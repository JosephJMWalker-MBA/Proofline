"""Evidence-backed relationships between public-record sources.

A source relation is not inferred from similar text or filenames. It must be
supported by a preserved public artifact that explicitly establishes the link.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from .discovery import _AgendaCenterParser, _link_format
from .hashing import source_id_from_uri, stable_id
from .storage import ProoflineStore
from .watch_storage import WatcherStore

_RELATION_METHOD = "civicengage_previous_versions/v1"

_RELATION_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS source_relations (
    relation_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    relation_type TEXT NOT NULL,
    related_source_id TEXT NOT NULL REFERENCES sources(source_id),
    evidence_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    method TEXT NOT NULL,
    method_version TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(
        source_id,
        relation_type,
        related_source_id,
        evidence_artifact_id,
        method,
        method_version
    )
);

CREATE INDEX IF NOT EXISTS idx_source_relations_source
ON source_relations(source_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_source_relations_related
ON source_relations(related_source_id, relation_type);

CREATE TRIGGER IF NOT EXISTS source_relations_no_update
BEFORE UPDATE ON source_relations BEGIN
    SELECT RAISE(ABORT, 'source relations are append-only');
END;
CREATE TRIGGER IF NOT EXISTS source_relations_no_delete
BEFORE DELETE ON source_relations BEGIN
    SELECT RAISE(ABORT, 'source relations are append-only');
END;
"""


@dataclass(frozen=True, slots=True)
class SourceRelation:
    relation_id: str
    source_id: str
    source_uri: str
    relation_type: str
    related_source_id: str
    related_source_uri: str
    evidence_artifact_id: str
    method: str
    method_version: str
    details: dict

    def to_dict(self) -> dict:
        return asdict(self)


class RelationStore:
    def __init__(self, state_dir: str | Path = ".proofline") -> None:
        self.state_dir = Path(state_dir)
        self.store = ProoflineStore(self.state_dir / "proofline.db")
        with self.store.connection() as connection:
            connection.executescript(_RELATION_SCHEMA)

    def add(
        self,
        *,
        source_uri: str,
        relation_type: str,
        related_source_uri: str,
        evidence_artifact_id: str,
        method: str,
        method_version: str,
        details: dict | None = None,
    ) -> SourceRelation | None:
        source_id = source_id_from_uri(source_uri)
        related_source_id = source_id_from_uri(related_source_uri)
        relation_id = stable_id(
            "relation",
            source_id,
            relation_type,
            related_source_id,
            evidence_artifact_id,
            method,
            method_version,
        )
        payload = details or {}

        with self.store.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone() is None:
                return None
            if connection.execute(
                "SELECT 1 FROM sources WHERE source_id = ?", (related_source_id,)
            ).fetchone() is None:
                return None
            if connection.execute(
                "SELECT 1 FROM artifacts WHERE artifact_id = ?", (evidence_artifact_id,)
            ).fetchone() is None:
                raise ValueError(f"unknown relation evidence artifact: {evidence_artifact_id}")

            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO source_relations(
                    relation_id, source_id, relation_type, related_source_id,
                    evidence_artifact_id, method, method_version, occurred_at, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    source_id,
                    relation_type,
                    related_source_id,
                    evidence_artifact_id,
                    method,
                    method_version,
                    datetime.now(UTC).isoformat(),
                    json.dumps(payload, sort_keys=True),
                ),
            )
            if cursor.rowcount == 0:
                return None

        return SourceRelation(
            relation_id=relation_id,
            source_id=source_id,
            source_uri=source_uri,
            relation_type=relation_type,
            related_source_id=related_source_id,
            related_source_uri=related_source_uri,
            evidence_artifact_id=evidence_artifact_id,
            method=method,
            method_version=method_version,
            details=payload,
        )

    def list(self, *, relation_type: str | None = None) -> list[SourceRelation]:
        where = "WHERE sr.relation_type = ?" if relation_type else ""
        params = (relation_type,) if relation_type else ()
        with self.store.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    sr.*,
                    s.source_uri,
                    related.source_uri AS related_source_uri
                FROM source_relations sr
                JOIN sources s ON s.source_id = sr.source_id
                JOIN sources related ON related.source_id = sr.related_source_id
                {where}
                ORDER BY sr.occurred_at, sr.relation_id
                """,
                params,
            ).fetchall()
        return [
            SourceRelation(
                relation_id=row["relation_id"],
                source_id=row["source_id"],
                source_uri=row["source_uri"],
                relation_type=row["relation_type"],
                related_source_id=row["related_source_id"],
                related_source_uri=row["related_source_uri"],
                evidence_artifact_id=row["evidence_artifact_id"],
                method=row["method"],
                method_version=row["method_version"],
                details=json.loads(row["details_json"]),
            )
            for row in rows
        ]


def _latest_source_artifact(
    root: Path,
    store: ProoflineStore,
    watcher: WatcherStore,
    source_id: str,
) -> tuple[str, Path] | None:
    """Resolve source bytes from watcher chronology, with snapshot fallback.

    The watcher ledger is authoritative for temporal state because the source
    snapshot table intentionally stores unique source/artifact pairs and can
    therefore collapse A -> B -> A revisits.
    """
    artifact_id = watcher.latest_successful_artifact(source_id)
    if artifact_id is None:
        artifact_id = store.latest_artifact_for_source(source_id)
    if artifact_id is None:
        return None

    with store.connection() as connection:
        row = connection.execute(
            "SELECT stored_path FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
    if row is None:
        return None
    return artifact_id, root / row["stored_path"]


def derive_civicengage_version_relations(
    state_dir: str | Path = ".proofline",
) -> tuple[SourceRelation, ...]:
    """Derive historical-version edges from preserved Previous Versions pages.

    Every relation is supported by the exact HTML artifact whose published links
    place both the archived and current records in one version family. When a
    watcher ledger exists, the relation evidence uses the bytes observed on the
    latest successful visit rather than first-seen source/artifact ordering.
    """
    root = Path(state_dir)
    relations = RelationStore(root)
    store = relations.store
    watcher = WatcherStore(root / "proofline.db")

    with store.connection() as connection:
        sources = connection.execute(
            """
            SELECT source_id, source_uri
            FROM sources
            WHERE source_uri LIKE '%/AgendaCenter/PreviousVersions/%'
            ORDER BY source_uri
            """
        ).fetchall()

    created: list[SourceRelation] = []
    for source in sources:
        latest = _latest_source_artifact(root, store, watcher, str(source["source_id"]))
        if latest is None:
            continue
        evidence_artifact_id, evidence_path = latest
        listing_uri = str(source["source_uri"])
        html = evidence_path.read_text(encoding="utf-8", errors="replace")
        parser = _AgendaCenterParser(listing_uri)
        parser.feed(html)
        parser.close()

        current_by_format: dict[str, str] = {}
        archived: list[tuple[str, str]] = []
        for link in parser.links:
            fmt = _link_format(link)
            if fmt not in {"html", "pdf", "packet"}:
                continue
            path = urlparse(link.source_uri).path
            if "/AgendaCenter/ViewFile/ArchivedAgenda/" in path:
                archived.append((fmt, link.source_uri))
            elif "/AgendaCenter/ViewFile/Agenda/" in path:
                current_by_format.setdefault(fmt, link.source_uri)

        for fmt, archived_uri in archived:
            current_uri = current_by_format.get(fmt)
            if current_uri is None:
                continue
            relation = relations.add(
                source_uri=archived_uri,
                relation_type="historical_version_of",
                related_source_uri=current_uri,
                evidence_artifact_id=evidence_artifact_id,
                method=_RELATION_METHOD,
                method_version="1",
                details={
                    "listing_uri": listing_uri,
                    "format": fmt,
                    "evidence_kind": "publisher_previous_versions_listing",
                },
            )
            if relation is not None:
                created.append(relation)

    return tuple(created)
