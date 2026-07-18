"""V1 compatibility, deterministic V2 publication, and quality validation."""

from workflowtwin.shadow.fingerprint import shadow_fingerprint
from workflowtwin.source_contracts.generator import v2_snapshot_fingerprint
from workflowtwin.source_contracts.models import (
    AdministrativeTruthRecord,
    IncomingReferralSnapshotV2,
    SourceContractDefinition,
)
from workflowtwin.source_contracts.precedence import SourcePrecedencePolicy
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import ConflictStatus, FreshnessStatus
from workflowtwin.source_contracts.validation import validate_snapshots


def test_v2_publication_is_deterministic_and_truth_is_separate(
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[AdministrativeTruthRecord, ...]],
) -> None:
    snapshots, truth = v2_source
    assert snapshots and truth
    assert v2_snapshot_fingerprint(snapshots) == v2_snapshot_fingerprint(snapshots)
    assert "supporting_document_present" not in IncomingReferralSnapshotV2.model_fields
    assert snapshots[0].schema_version == 2
    assert shadow_fingerprint(snapshots[0]) != shadow_fingerprint(truth[0])


def test_validation_reports_quality_and_rejects_duplicate_delivery(
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
    source_definition: SourceContractDefinition,
    requirements: AdministrativeRequirementsContract,
) -> None:
    snapshots = v2_source[0]
    report = validate_snapshots(snapshots, definition=source_definition, requirements=requirements)
    assert report.is_valid is True
    duplicate = validate_snapshots(
        (*snapshots, snapshots[0]), definition=source_definition, requirements=requirements
    )
    assert duplicate.is_valid is False
    assert any(item.code == "duplicate_snapshot" for item in duplicate.findings)


def test_precedence_abstains_on_stale_or_conflicting_state() -> None:
    policy = SourcePrecedencePolicy()
    assert policy.usable(FreshnessStatus.FRESH, ConflictStatus.NONE) is True
    assert policy.usable(FreshnessStatus.STALE, ConflictStatus.NONE) is False
    assert policy.usable(FreshnessStatus.FRESH, ConflictStatus.DETECTED) is False
