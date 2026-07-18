"""Validation of V2 snapshots, requirements, chronology, and source contracts."""

from collections import Counter
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from workflowtwin.source_contracts.contradictions import detect_snapshot_contradictions
from workflowtwin.source_contracts.models import (
    ALLOWED_FIELD_IDS,
    FICTIONAL_DECLARATION,
    IncomingReferralSnapshotV2,
    SourceContractDefinition,
    SourceContractModel,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import AdministrativeFieldStateV2, UpdateType


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class ContractFinding(SourceContractModel):
    code: str
    severity: ValidationSeverity
    count: int = Field(ge=1)
    references: tuple[str, ...]
    message: str


class SourceContractValidation(SourceContractModel):
    snapshot_count: int
    case_count: int
    is_valid: bool
    findings: tuple[ContractFinding, ...]
    contradiction_count: int


def validate_definition(
    definition: SourceContractDefinition,
    requirements: AdministrativeRequirementsContract,
) -> None:
    if definition.snapshot_schema_version != 2:
        raise ValueError("source contract must target snapshot schema version 2")
    if set(definition.allowed_fields) != ALLOWED_FIELD_IDS:
        raise ValueError("source contract allowed fields do not match the V2 vocabulary")
    if definition.fictional_declaration != FICTIONAL_DECLARATION:
        raise ValueError("source contract lacks the fictional declaration")
    if requirements.fictional_declaration != FICTIONAL_DECLARATION:
        raise ValueError("requirements contract lacks the fictional declaration")


def validate_snapshots(
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
    *,
    definition: SourceContractDefinition,
    requirements: AdministrativeRequirementsContract,
) -> SourceContractValidation:
    validate_definition(definition, requirements)
    counts: Counter[str] = Counter()
    references: dict[str, list[str]] = {}

    def record(code: str, snapshot_id: str) -> None:
        counts[code] += 1
        references.setdefault(code, []).append(snapshot_id)

    seen: set[str] = set()
    by_case: dict[UUID, list[IncomingReferralSnapshotV2]] = {}
    for snapshot in snapshots:
        if snapshot.snapshot_id in seen:
            record("duplicate_snapshot", snapshot.snapshot_id)
        seen.add(snapshot.snapshot_id)
        by_case.setdefault(snapshot.case_id, []).append(snapshot)
        form = requirements.requirements_for(
            form_identifier=snapshot.form_identifier,
            form_version=snapshot.form_version,
            source_system=snapshot.source_system,
            as_of=snapshot.available_at,
        )
        if form is None:
            record("unsupported_form_contract", snapshot.snapshot_id)
        if snapshot.requirements_contract_version != requirements.contract_version:
            record("requirements_version_mismatch", snapshot.snapshot_id)
        if not snapshot.producer_system.strip():
            record("absent_producer", snapshot.snapshot_id)
        if snapshot.update_type is UpdateType.SUPERSESSION and not (
            snapshot.superseded_snapshot_id
        ):
            record("invalid_supersession", snapshot.snapshot_id)
        if snapshot.fictional_declaration != FICTIONAL_DECLARATION:
            record("missing_fictional_declaration", snapshot.snapshot_id)
        for field in snapshot.fields:
            if field.field_id not in ALLOWED_FIELD_IDS:
                record("unsupported_field_identifier", snapshot.snapshot_id)
            if (
                field.state is AdministrativeFieldStateV2.NOT_APPLICABLE
                and field.applicable is True
            ):
                record("impossible_field_state", snapshot.snapshot_id)

    for case_snapshots in by_case.values():
        ordered = sorted(case_snapshots, key=lambda item: (item.available_at, item.snapshot_id))
        previous = None
        ids = {item.snapshot_id for item in ordered}
        for snapshot in ordered:
            if previous and snapshot.source_record_version < previous.source_record_version:
                record("out_of_order_source_version", snapshot.snapshot_id)
            if snapshot.superseded_snapshot_id and snapshot.superseded_snapshot_id not in ids:
                record("unknown_superseded_snapshot", snapshot.snapshot_id)
            previous = snapshot

    contradictions = detect_snapshot_contradictions(snapshots)
    if contradictions:
        counts["source_contradiction"] += len(contradictions)
        references["source_contradiction"] = [item.snapshot_ids[-1] for item in contradictions]
    error_codes = {
        "duplicate_snapshot",
        "absent_producer",
        "invalid_supersession",
        "missing_fictional_declaration",
        "unsupported_field_identifier",
        "impossible_field_state",
        "unknown_superseded_snapshot",
    }
    findings = tuple(
        ContractFinding(
            code=code,
            severity=(
                ValidationSeverity.ERROR if code in error_codes else ValidationSeverity.WARNING
            ),
            count=count,
            references=tuple(references[code][:20]),
            message=code.replace("_", " "),
        )
        for code, count in sorted(counts.items())
    )
    return SourceContractValidation(
        snapshot_count=len(snapshots),
        case_count=len(by_case),
        is_valid=not any(item.severity is ValidationSeverity.ERROR for item in findings),
        findings=findings,
        contradiction_count=len(contradictions),
    )
