"""Explicit administrative source-state vocabulary and detector semantics."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AdministrativeFieldStateV2(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    PENDING_SOURCE_UPDATE = "pending_source_update"
    UNSUPPORTED = "unsupported"
    STALE = "stale"
    CONFLICTING = "conflicting"
    VERIFICATION_REQUIRED = "verification_required"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class ConflictStatus(StrEnum):
    NONE = "none"
    DETECTED = "detected"
    RESOLVED = "resolved"


class ManualReviewState(StrEnum):
    NOT_STARTED = "not_started"
    STARTED = "started"
    COMPLETED = "completed"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


class UpdateType(StrEnum):
    INITIAL = "initial"
    CORRECTION = "correction"
    RETRY = "retry"
    SUPERSESSION = "supersession"


class EvidenceStability(StrEnum):
    STABLE_EXPLICIT_ABSENCE = "stable_explicit_absence"
    PENDING = "pending"
    UNKNOWN = "unknown"
    STALE = "stale"
    CONFLICTING = "conflicting"
    UNSUPPORTED = "unsupported"
    RECENTLY_CORRECTED = "recently_corrected"
    SUPERSEDED = "superseded"
    RESOLVED = "resolved"


class FieldStateSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: AdministrativeFieldStateV2
    recommendation_permitted: bool
    abstention_required: bool
    confirmation_appropriate: bool
    retry_expected: bool
    suppress_duplicate_warning: bool
    resolved: bool


FIELD_STATE_SEMANTICS = {
    AdministrativeFieldStateV2.PRESENT: FieldStateSemantics(
        state=AdministrativeFieldStateV2.PRESENT,
        recommendation_permitted=False,
        abstention_required=False,
        confirmation_appropriate=False,
        retry_expected=False,
        suppress_duplicate_warning=True,
        resolved=True,
    ),
    AdministrativeFieldStateV2.ABSENT: FieldStateSemantics(
        state=AdministrativeFieldStateV2.ABSENT,
        recommendation_permitted=True,
        abstention_required=False,
        confirmation_appropriate=True,
        retry_expected=False,
        suppress_duplicate_warning=False,
        resolved=False,
    ),
    AdministrativeFieldStateV2.UNKNOWN: FieldStateSemantics(
        state=AdministrativeFieldStateV2.UNKNOWN,
        recommendation_permitted=False,
        abstention_required=True,
        confirmation_appropriate=False,
        retry_expected=True,
        suppress_duplicate_warning=False,
        resolved=False,
    ),
    AdministrativeFieldStateV2.NOT_APPLICABLE: FieldStateSemantics(
        state=AdministrativeFieldStateV2.NOT_APPLICABLE,
        recommendation_permitted=False,
        abstention_required=False,
        confirmation_appropriate=False,
        retry_expected=False,
        suppress_duplicate_warning=True,
        resolved=True,
    ),
    AdministrativeFieldStateV2.PENDING_SOURCE_UPDATE: FieldStateSemantics(
        state=AdministrativeFieldStateV2.PENDING_SOURCE_UPDATE,
        recommendation_permitted=False,
        abstention_required=False,
        confirmation_appropriate=True,
        retry_expected=True,
        suppress_duplicate_warning=False,
        resolved=False,
    ),
    AdministrativeFieldStateV2.UNSUPPORTED: FieldStateSemantics(
        state=AdministrativeFieldStateV2.UNSUPPORTED,
        recommendation_permitted=False,
        abstention_required=True,
        confirmation_appropriate=False,
        retry_expected=False,
        suppress_duplicate_warning=False,
        resolved=False,
    ),
    AdministrativeFieldStateV2.STALE: FieldStateSemantics(
        state=AdministrativeFieldStateV2.STALE,
        recommendation_permitted=False,
        abstention_required=True,
        confirmation_appropriate=False,
        retry_expected=True,
        suppress_duplicate_warning=False,
        resolved=False,
    ),
    AdministrativeFieldStateV2.CONFLICTING: FieldStateSemantics(
        state=AdministrativeFieldStateV2.CONFLICTING,
        recommendation_permitted=False,
        abstention_required=True,
        confirmation_appropriate=False,
        retry_expected=False,
        suppress_duplicate_warning=False,
        resolved=False,
    ),
    AdministrativeFieldStateV2.VERIFICATION_REQUIRED: FieldStateSemantics(
        state=AdministrativeFieldStateV2.VERIFICATION_REQUIRED,
        recommendation_permitted=True,
        abstention_required=False,
        confirmation_appropriate=False,
        retry_expected=False,
        suppress_duplicate_warning=False,
        resolved=False,
    ),
}
