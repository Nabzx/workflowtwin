"""Stable version 1 vocabulary for the fictional Northstar referral workflow."""

from enum import StrEnum


class ReferralStatus(StrEnum):
    """Current administrative state of a referral case."""

    RECEIVED = "received"
    AWAITING_INFORMATION = "awaiting_information"
    READY_FOR_CATEGORISATION = "ready_for_categorisation"
    CATEGORISED = "categorised"
    ASSIGNED = "assigned"
    SCHEDULING = "scheduling"
    APPOINTMENT_BOOKED = "appointment_booked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    CLOSED_OTHER = "closed_other"


TERMINAL_STATUSES = frozenset(
    {
        ReferralStatus.COMPLETED,
        ReferralStatus.CANCELLED,
        ReferralStatus.REJECTED,
        ReferralStatus.CLOSED_OTHER,
    }
)


class EventType(StrEnum):
    """Recorded administrative activities; repeats and corrections are permitted."""

    REFERRAL_SUBMITTED = "referral_submitted"
    REFERRAL_RECEIVED = "referral_received"
    COMPLETENESS_CHECK_COMPLETED = "completeness_check_completed"
    MISSING_INFORMATION_REQUESTED = "missing_information_requested"
    MISSING_INFORMATION_RECEIVED = "missing_information_received"
    REFERRAL_CATEGORISED = "referral_categorised"
    REFERRAL_RECATEGORISED = "referral_recategorised"
    CLINICAL_TEAM_ASSIGNED = "clinical_team_assigned"
    CLINICAL_TEAM_REASSIGNED = "clinical_team_reassigned"
    APPOINTMENT_SCHEDULING_STARTED = "appointment_scheduling_started"
    APPOINTMENT_SCHEDULING_FAILED = "appointment_scheduling_failed"
    APPOINTMENT_BOOKED = "appointment_booked"
    PATIENT_NOTIFIED = "patient_notified"
    PATIENT_NO_RESPONSE = "patient_no_response"
    REFERRAL_COMPLETED = "referral_completed"
    REFERRAL_CANCELLED = "referral_cancelled"
    REFERRAL_REJECTED = "referral_rejected"
    REFERRAL_CLOSED_OTHER = "referral_closed_other"


class ActorType(StrEnum):
    """Operational role responsible for a recorded event."""

    REFERRER = "referrer"
    ADMIN_STAFF = "admin_staff"
    CLINICAL_TEAM = "clinical_team"
    SCHEDULING_STAFF = "scheduling_staff"
    PATIENT = "patient"
    SYSTEM = "system"


class ReferralSource(StrEnum):
    """Organisation category that submitted the referral."""

    GP_PRACTICE = "gp_practice"
    COMMUNITY_CLINIC = "community_clinic"
    HEALTHCARE_PROFESSIONAL = "healthcare_professional"
    INTERNAL_TRANSFER = "internal_transfer"


class ServiceLine(StrEnum):
    """Administrative routing destination, not a diagnosis or treatment decision."""

    CARDIOLOGY = "cardiology"
    DERMATOLOGY = "dermatology"
    MUSCULOSKELETAL = "musculoskeletal"
    NEUROLOGY = "neurology"
    RESPIRATORY = "respiratory"


class SourceSystem(StrEnum):
    """System that supplied an event to WorkflowTwin."""

    REFERRAL_PORTAL = "referral_portal"
    SECURE_EMAIL = "secure_email"
    ADMIN_SYSTEM = "admin_system"
    SCHEDULING_SYSTEM = "scheduling_system"
    MANUAL_ENTRY = "manual_entry"
    SYNTHETIC_GENERATOR = "synthetic_generator"


class CommunicationChannel(StrEnum):
    """Channel through which an activity occurred."""

    PORTAL = "portal"
    SECURE_EMAIL = "secure_email"
    PHONE = "phone"
    SMS = "sms"
    LETTER = "letter"
    INTERNAL_SYSTEM = "internal_system"
    NOT_APPLICABLE = "not_applicable"


class ReasonCode(StrEnum):
    """Non-clinical structured explanation for an exception or correction."""

    MISSING_ADMINISTRATIVE_DETAILS = "missing_administrative_details"
    INVALID_ADMINISTRATIVE_DETAILS = "invalid_administrative_details"
    INCORRECT_CATEGORY = "incorrect_category"
    ROUTING_CORRECTION = "routing_correction"
    CAPACITY_REBALANCE = "capacity_rebalance"
    NO_APPOINTMENT_SLOT = "no_appointment_slot"
    SCHEDULING_SYSTEM_ERROR = "scheduling_system_error"
    PATIENT_UNAVAILABLE = "patient_unavailable"
    PATIENT_UNREACHABLE = "patient_unreachable"
    REFERRER_WITHDREW = "referrer_withdrew"
    PATIENT_CANCELLED = "patient_cancelled"
    DUPLICATE_REFERRAL = "duplicate_referral"
    OUT_OF_SCOPE_SERVICE = "out_of_scope_service"
    INVALID_REFERRAL_SOURCE = "invalid_referral_source"
    OTHER_OPERATIONAL = "other_operational"


REASON_CODES_BY_EVENT: dict[EventType, frozenset[ReasonCode]] = {
    EventType.MISSING_INFORMATION_REQUESTED: frozenset(
        {
            ReasonCode.MISSING_ADMINISTRATIVE_DETAILS,
            ReasonCode.INVALID_ADMINISTRATIVE_DETAILS,
        }
    ),
    EventType.REFERRAL_RECATEGORISED: frozenset({ReasonCode.INCORRECT_CATEGORY}),
    EventType.CLINICAL_TEAM_REASSIGNED: frozenset(
        {ReasonCode.ROUTING_CORRECTION, ReasonCode.CAPACITY_REBALANCE}
    ),
    EventType.APPOINTMENT_SCHEDULING_FAILED: frozenset(
        {
            ReasonCode.NO_APPOINTMENT_SLOT,
            ReasonCode.SCHEDULING_SYSTEM_ERROR,
            ReasonCode.PATIENT_UNAVAILABLE,
        }
    ),
    EventType.PATIENT_NO_RESPONSE: frozenset({ReasonCode.PATIENT_UNREACHABLE}),
    EventType.REFERRAL_CANCELLED: frozenset(
        {
            ReasonCode.REFERRER_WITHDREW,
            ReasonCode.PATIENT_CANCELLED,
            ReasonCode.PATIENT_UNREACHABLE,
            ReasonCode.OTHER_OPERATIONAL,
        }
    ),
    EventType.REFERRAL_REJECTED: frozenset(
        {
            ReasonCode.DUPLICATE_REFERRAL,
            ReasonCode.OUT_OF_SCOPE_SERVICE,
            ReasonCode.INVALID_REFERRAL_SOURCE,
        }
    ),
    EventType.REFERRAL_CLOSED_OTHER: frozenset({ReasonCode.OTHER_OPERATIONAL}),
}
