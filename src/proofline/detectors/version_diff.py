"""Deterministic comparison of artifact versions.

This module does not decide that two artifacts are versions of one another.
The caller must establish that relationship from provenance. The comparator
only describes reproducible differences between already-related artifacts.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal
from difflib import SequenceMatcher

from ..hashing import stable_id
from ..models import EvidenceReference, Observation
from ..storage import ProoflineStore
from ..structured import extract_structured_facts

_METHOD = "deterministic_version_diff/v1"


@dataclass(frozen=True, slots=True)
class EvidenceUnitDiff:
    locator: str
    before_evidence_id: str | None
    after_evidence_id: str | None
    before_text: str | None
    after_text: str | None
    similarity: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ArithmeticRelation:
    """An exact arithmetic relationship, not an explanation of causation."""

    removed_value: str
    added_value: str
    delta: str
    unchanged_value: str
    exact_multiple: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class VersionDiffResult:
    before_artifact_id: str
    after_artifact_id: str
    input_fingerprint: str
    changed_units: tuple[EvidenceUnitDiff, ...]
    money_removed: tuple[str, ...]
    money_added: tuple[str, ...]
    dates_removed: tuple[str, ...]
    dates_added: tuple[str, ...]
    arithmetic_relations: tuple[ArithmeticRelation, ...]
    text_similarity: float

    @property
    def changed(self) -> bool:
        return bool(
            self.changed_units
            or self.money_removed
            or self.money_added
            or self.dates_removed
            or self.dates_added
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["changed_units"] = [item.to_dict() for item in self.changed_units]
        data["arithmetic_relations"] = [item.to_dict() for item in self.arithmetic_relations]
        return data


def _preferred_units(store: ProoflineStore, artifact_id: str) -> dict[str, dict]:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT
                eu.evidence_id,
                eu.artifact_id,
                eu.locator,
                best.extraction_id,
                best.extracted_text,
                best.quality_score,
                best.method
            FROM evidence_units eu
            LEFT JOIN evidence_extractions best
              ON best.extraction_id = (
                SELECT ee.extraction_id
                FROM evidence_extractions ee
                WHERE ee.evidence_id = eu.evidence_id
                ORDER BY COALESCE(ee.quality_score, -1.0) DESC,
                         ee.occurred_at DESC,
                         ee.rowid DESC
                LIMIT 1
              )
            WHERE eu.artifact_id = ?
            ORDER BY eu.locator
            """,
            (artifact_id,),
        ).fetchall()
    return {str(row["locator"]): dict(row) for row in rows}


def _input_fingerprint(before: dict[str, dict], after: dict[str, dict]) -> str:
    """Identify the exact preferred Silver extraction attempts used by Gold."""
    parts: list[str] = []
    for side, units in (("before", before), ("after", after)):
        for locator in sorted(units):
            row = units[locator]
            parts.extend(
                [
                    side,
                    locator,
                    str(row.get("evidence_id") or ""),
                    str(row.get("extraction_id") or "none"),
                ]
            )
    return stable_id("version-diff-inputs", *parts)


def _money_values(text: str | None) -> Counter[Decimal]:
    values: Counter[Decimal] = Counter()
    for fact in extract_structured_facts(text or ""):
        if fact.fact_type == "money" and fact.normalized_text is not None:
            values[Decimal(fact.normalized_text)] += 1
    return values


def _date_values(text: str | None) -> Counter[str]:
    values: Counter[str] = Counter()
    for fact in extract_structured_facts(text or ""):
        if fact.fact_type == "date" and fact.normalized_text is not None:
            values[fact.normalized_text] += 1
    return values


def _expanded(counter: Counter, *, formatter=str) -> tuple[str, ...]:
    values: list[str] = []
    for value in sorted(counter):
        values.extend(formatter(value) for _ in range(counter[value]))
    return tuple(values)


def _money_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _exact_arithmetic_relations(
    removed: Counter[Decimal],
    added: Counter[Decimal],
    common: Counter[Decimal],
) -> tuple[ArithmeticRelation, ...]:
    relations: set[ArithmeticRelation] = set()
    for old_value in removed:
        for new_value in added:
            delta = abs(new_value - old_value)
            if delta == 0:
                continue
            for unchanged in common:
                if unchanged <= 0 or unchanged in {old_value, new_value, delta}:
                    continue
                quotient = delta / unchanged
                if quotient != quotient.to_integral_value():
                    continue
                multiple = int(quotient)
                if not 2 <= multiple <= 36:
                    continue
                relations.add(
                    ArithmeticRelation(
                        removed_value=_money_text(old_value),
                        added_value=_money_text(new_value),
                        delta=_money_text(delta),
                        unchanged_value=_money_text(unchanged),
                        exact_multiple=multiple,
                    )
                )
    return tuple(
        sorted(
            relations,
            key=lambda item: (
                Decimal(item.removed_value),
                Decimal(item.added_value),
                Decimal(item.unchanged_value),
            ),
        )
    )


def _compare_preferred_units(
    before_artifact_id: str,
    after_artifact_id: str,
    before: dict[str, dict],
    after: dict[str, dict],
) -> VersionDiffResult:
    all_locators = sorted(set(before) | set(after))
    changed_units: list[EvidenceUnitDiff] = []
    before_document: list[str] = []
    after_document: list[str] = []
    before_money: Counter[Decimal] = Counter()
    after_money: Counter[Decimal] = Counter()
    before_dates: Counter[str] = Counter()
    after_dates: Counter[str] = Counter()

    for locator in all_locators:
        before_row = before.get(locator)
        after_row = after.get(locator)
        before_text = before_row.get("extracted_text") if before_row else None
        after_text = after_row.get("extracted_text") if after_row else None

        if before_text:
            before_document.append(before_text)
            before_money.update(_money_values(before_text))
            before_dates.update(_date_values(before_text))
        if after_text:
            after_document.append(after_text)
            after_money.update(_money_values(after_text))
            after_dates.update(_date_values(after_text))

        if before_text != after_text or before_row is None or after_row is None:
            similarity = None
            if before_text is not None and after_text is not None:
                similarity = round(SequenceMatcher(None, before_text, after_text).ratio(), 6)
            changed_units.append(
                EvidenceUnitDiff(
                    locator=locator,
                    before_evidence_id=(before_row["evidence_id"] if before_row else None),
                    after_evidence_id=(after_row["evidence_id"] if after_row else None),
                    before_text=before_text,
                    after_text=after_text,
                    similarity=similarity,
                )
            )

    money_removed = before_money - after_money
    money_added = after_money - before_money
    money_common = before_money & after_money
    dates_removed = before_dates - after_dates
    dates_added = after_dates - before_dates

    before_joined = "\n\n".join(before_document)
    after_joined = "\n\n".join(after_document)
    similarity = SequenceMatcher(None, before_joined, after_joined).ratio()

    return VersionDiffResult(
        before_artifact_id=before_artifact_id,
        after_artifact_id=after_artifact_id,
        input_fingerprint=_input_fingerprint(before, after),
        changed_units=tuple(changed_units),
        money_removed=_expanded(money_removed, formatter=_money_text),
        money_added=_expanded(money_added, formatter=_money_text),
        dates_removed=_expanded(dates_removed),
        dates_added=_expanded(dates_added),
        arithmetic_relations=_exact_arithmetic_relations(
            money_removed,
            money_added,
            money_common,
        ),
        text_similarity=round(similarity, 6),
    )


def compare_artifact_versions(
    store: ProoflineStore,
    before_artifact_id: str,
    after_artifact_id: str,
) -> VersionDiffResult:
    """Compare preferred Silver evidence for two explicitly related artifacts."""
    if before_artifact_id == after_artifact_id:
        raise ValueError("before and after artifact IDs must differ")

    before = _preferred_units(store, before_artifact_id)
    after = _preferred_units(store, after_artifact_id)
    if not before:
        raise ValueError(f"artifact has no evidence units: {before_artifact_id}")
    if not after:
        raise ValueError(f"artifact has no evidence units: {after_artifact_id}")
    return _compare_preferred_units(before_artifact_id, after_artifact_id, before, after)


def _excerpt(text: str | None, *, limit: int = 700) -> str | None:
    if not text:
        return None
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def build_version_change_observation(
    store: ProoflineStore,
    before_artifact_id: str,
    after_artifact_id: str,
) -> tuple[VersionDiffResult, Observation | None]:
    """Build an evidence-backed Gold observation for an explicit version pair.

    The observation ID includes the exact preferred extraction-attempt fingerprint,
    so replacing the preferred Silver extraction yields a new regenerable Gold
    artifact rather than silently reusing analysis produced from stale text.
    """
    if before_artifact_id == after_artifact_id:
        raise ValueError("before and after artifact IDs must differ")
    before_units = _preferred_units(store, before_artifact_id)
    after_units = _preferred_units(store, after_artifact_id)
    if not before_units:
        raise ValueError(f"artifact has no evidence units: {before_artifact_id}")
    if not after_units:
        raise ValueError(f"artifact has no evidence units: {after_artifact_id}")

    result = _compare_preferred_units(
        before_artifact_id,
        after_artifact_id,
        before_units,
        after_units,
    )
    if not result.changed:
        return result, None

    refs: list[EvidenceReference] = []
    seen_evidence: set[str] = set()

    for change in result.changed_units:
        if change.before_evidence_id and change.before_evidence_id not in seen_evidence:
            row = before_units[change.locator]
            refs.append(
                EvidenceReference(
                    evidence_id=change.before_evidence_id,
                    artifact_id=before_artifact_id,
                    locator=change.locator,
                    excerpt=_excerpt(row.get("extracted_text")),
                )
            )
            seen_evidence.add(change.before_evidence_id)
        if change.after_evidence_id and change.after_evidence_id not in seen_evidence:
            row = after_units[change.locator]
            refs.append(
                EvidenceReference(
                    evidence_id=change.after_evidence_id,
                    artifact_id=after_artifact_id,
                    locator=change.locator,
                    excerpt=_excerpt(row.get("extracted_text")),
                )
            )
            seen_evidence.add(change.after_evidence_id)

    pieces = [f"{len(result.changed_units)} evidence unit(s) differ between the supplied versions."]
    if result.money_removed or result.money_added:
        pieces.append(
            "Monetary values changed: "
            f"removed={list(result.money_removed)!r}; added={list(result.money_added)!r}."
        )
    if result.dates_removed or result.dates_added:
        pieces.append(
            "Date values changed: "
            f"removed={list(result.dates_removed)!r}; added={list(result.dates_added)!r}."
        )
    if result.arithmetic_relations:
        relation = result.arithmetic_relations[0]
        pieces.append(
            f"The {relation.delta} monetary delta is exactly {relation.exact_multiple} × "
            f"an unchanged {relation.unchanged_value} value present in both versions."
        )

    observation = Observation(
        observation_id=stable_id(
            "observation",
            "version_change",
            before_artifact_id,
            after_artifact_id,
            result.input_fingerprint,
            _METHOD,
        ),
        observation_type="source_version_change",
        explanation=" ".join(pieces),
        evidence_refs=tuple(refs),
        method=_METHOD,
        uncertainty=(
            "The comparator describes differences only. It does not infer why the record changed, "
            "whether the change is material, or whether the two artifacts should be related; "
            "the caller must establish version provenance separately."
        ),
        limitations=(
            "Evidence units are aligned by stable locator; substantial repagination may appear as added/removed units.",
            "Exact arithmetic relationships are descriptive coincidences unless supported by source context.",
            "Extraction errors can create apparent text/value changes and should be reviewed when quality is low.",
            f"Gold input fingerprint: {result.input_fingerprint}",
        ),
    )
    return result, observation
