from datetime import UTC, datetime

import pytest

from proofline import (
    Artifact,
    EvidenceReference,
    EvidenceUnit,
    EvidenceUnitType,
    Lead,
    Observation,
    SourceReference,
    artifact_id_from_sha256,
    sha256_bytes,
)


def test_artifact_identity_is_content_addressed() -> None:
    digest = sha256_bytes(b"public record")
    artifact_id = artifact_id_from_sha256(digest)

    artifact = Artifact(
        artifact_id=artifact_id,
        sha256=digest,
        byte_size=len(b"public record"),
        source=SourceReference(
            source_uri="https://example.gov/record.pdf",
            retrieved_at=datetime.now(UTC),
            native_identifier="RECORD-001",
        ),
        media_type="application/pdf",
    )

    assert artifact.artifact_id == f"artifact:{digest}"


def test_observation_requires_evidence() -> None:
    with pytest.raises(ValueError, match="at least one evidence"):
        Observation(
            observation_id="obs:1",
            observation_type="version_change",
            explanation="The public artifact changed between snapshots.",
            evidence_refs=(),
            method="sha256_compare",
        )


def test_lead_retains_trace_to_artifact() -> None:
    digest = sha256_bytes(b"page content")
    artifact_id = artifact_id_from_sha256(digest)

    evidence = EvidenceUnit(
        evidence_id="evidence:1",
        artifact_id=artifact_id,
        unit_type=EvidenceUnitType.PAGE,
        locator="page:7",
        extracted_text="Contract amount: $250,000",
        extraction_method="native_text",
        quality_score=1.0,
    )

    ref = EvidenceReference(
        evidence_id=evidence.evidence_id,
        artifact_id=evidence.artifact_id,
        locator=evidence.locator,
        excerpt=evidence.extracted_text,
    )

    observation = Observation(
        observation_id="obs:1",
        observation_type="value_conflict",
        explanation="Two related records report different contract amounts.",
        evidence_refs=(ref,),
        method="structured_value_compare",
        score=0.9,
        uncertainty="Second source still requires human context review.",
    )

    lead = Lead(
        lead_id="lead:1",
        title="Contract values differ across related records",
        why_surfaced="A deterministic comparison found conflicting values.",
        observation_ids=(observation.observation_id,),
        evidence_refs=observation.evidence_refs,
        questions_worth_asking=("Which amount is authoritative, and why do the records differ?",),
        possible_benign_explanations=("One record may reflect a later amendment.",),
    )

    assert lead.evidence_refs[0].artifact_id == artifact_id
    assert lead.evidence_refs[0].locator == "page:7"
