"""Typed V2 source snapshots, provenance, and separated synthetic truth."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from workflowtwin.domain.referrals.enums import ReferralSource, ServiceLine, SourceSystem
from workflowtwin.source_contracts.states import (
    AdministrativeFieldStateV2,
    ConflictStatus,
    FreshnessStatus,
    ManualReviewState,
    UpdateType,
)

FICTIONAL_DECLARATION = "Fictional Northstar administrative data; no real patient records."
ALLOWED_FIELD_IDS = frozenset(
    {
        "referral_form",
        "supporting_document",
        "source_acknowledgement",
        "routing_contact",
    }
)
FORBIDDEN_TERMS = frozenset(
    {
        "diagnosis",
        "symptom",
        "treatment",
        "urgency",
        "nhs_number",
        "patient_name",
        "date_of_birth",
        "clinical_note",
        "protected_attribute",
    }
)


class SourceContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AdministrativeTruthRecord(SourceContractModel):
    """Generator-only truth. This type is forbidden from detector interfaces."""

    case_id: UUID
    supporting_document_required: bool
    supporting_document_present: bool
    acknowledgement_required: bool
    routing_contact_required: bool
    valid_from: datetime
    provenance_reference: str
    is_synthetic: bool = True


class FieldObservation(SourceContractModel):
    field_id: str
    state: AdministrativeFieldStateV2
    applicable: bool | None
    observed_at: datetime
    producer_system: str
    provenance_references: tuple[str, ...]

    @field_validator("field_id")
    @classmethod
    def validate_field_id(cls, value: str) -> str:
        if value not in ALLOWED_FIELD_IDS:
            raise ValueError(f"unsupported or prohibited administrative field: {value}")
        return value


class IncomingReferralSnapshotV2(SourceContractModel):
    snapshot_id: str
    case_id: UUID
    available_at: datetime
    source_event_at: datetime
    source_system: SourceSystem
    source_record_identifier: str
    source_record_version: int = Field(ge=1)
    referral_source: ReferralSource
    requested_service_line: ServiceLine
    form_identifier: str
    form_version: str
    requirements_contract_version: str
    fields: tuple[FieldObservation, ...]
    source_warning_codes: tuple[str, ...] = ()
    manual_review_state: ManualReviewState
    freshness: FreshnessStatus
    conflict_status: ConflictStatus
    update_type: UpdateType
    superseded_snapshot_id: str | None = None
    producer_system: str = Field(min_length=1)
    provenance_references: tuple[str, ...]
    fictional_declaration: str = FICTIONAL_DECLARATION
    is_synthetic: bool = True
    schema_version: int = 2

    @field_validator("available_at", "source_event_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source timestamps must be timezone-aware")
        return value

    @field_validator("source_warning_codes")
    @classmethod
    def prohibit_sensitive_warning_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalised = " ".join(value).lower()
        if any(term in normalised for term in FORBIDDEN_TERMS):
            raise ValueError("source warnings cannot contain clinical or identifying fields")
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> "IncomingReferralSnapshotV2":
        if self.schema_version != 2:
            raise ValueError("IncomingReferralSnapshotV2 requires schema_version 2")
        if self.fictional_declaration != FICTIONAL_DECLARATION:
            raise ValueError("missing required fictional-data declaration")
        if self.source_event_at > self.available_at:
            raise ValueError("source event cannot occur after snapshot availability")
        if self.superseded_snapshot_id == self.snapshot_id:
            raise ValueError("a snapshot cannot supersede itself")
        field_ids = [item.field_id for item in self.fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("snapshot contains duplicate administrative fields")
        if not self.provenance_references:
            raise ValueError("snapshot requires provenance")
        return self

    def field(self, field_id: str) -> FieldObservation | None:
        return next((item for item in self.fields if item.field_id == field_id), None)


class SourceContractDefinition(SourceContractModel):
    contract_id: str
    contract_version: str
    snapshot_schema_version: int = 2
    allowed_fields: tuple[str, ...]
    prohibited_fields: tuple[str, ...]
    state_vocabulary: tuple[str, ...]
    provenance_required: bool
    freshness_tolerance_minutes: int = Field(gt=0)
    conflict_policy_version: str
    supersession_policy_version: str
    fictional_declaration: str = FICTIONAL_DECLARATION
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def prohibit_clinical_metadata(self) -> "SourceContractDefinition":
        serialised = str(self.metadata).lower()
        if any(term in serialised for term in FORBIDDEN_TERMS):
            raise ValueError("source contract metadata contains prohibited content")
        return self
