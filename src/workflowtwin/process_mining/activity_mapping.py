"""Versioned mapping from event vocabulary to stable process activities."""

from workflowtwin.domain.referrals.enums import EventType

ACTIVITY_MAPPING_VERSION = "northstar-activity-map-v1"
ACTIVITY_BY_EVENT_TYPE: dict[EventType, str] = {
    EventType.REFERRAL_SUBMITTED: "Referral submitted",
    EventType.REFERRAL_RECEIVED: "Referral received",
    EventType.COMPLETENESS_CHECK_COMPLETED: "Completeness checked",
    EventType.MISSING_INFORMATION_REQUESTED: "Missing information requested",
    EventType.MISSING_INFORMATION_RECEIVED: "Missing information received",
    EventType.REFERRAL_CATEGORISED: "Referral categorised",
    EventType.REFERRAL_RECATEGORISED: "Referral recategorised",
    EventType.CLINICAL_TEAM_ASSIGNED: "Clinical team assigned",
    EventType.CLINICAL_TEAM_REASSIGNED: "Clinical team reassigned",
    EventType.APPOINTMENT_SCHEDULING_STARTED: "Scheduling started",
    EventType.APPOINTMENT_SCHEDULING_FAILED: "Scheduling failed",
    EventType.APPOINTMENT_BOOKED: "Appointment booked",
    EventType.PATIENT_NOTIFIED: "Patient notified",
    EventType.PATIENT_NO_RESPONSE: "Patient no response",
    EventType.REFERRAL_COMPLETED: "Referral completed",
    EventType.REFERRAL_CANCELLED: "Referral cancelled",
    EventType.REFERRAL_REJECTED: "Referral rejected",
    EventType.REFERRAL_CLOSED_OTHER: "Referral closed other",
}

TERMINAL_ACTIVITIES = frozenset(
    {
        "Referral completed",
        "Referral cancelled",
        "Referral rejected",
        "Referral closed other",
    }
)


def activity_for(event_type: EventType) -> str | None:
    return ACTIVITY_BY_EVENT_TYPE.get(event_type)


def validate_activity_mapping() -> None:
    missing = set(EventType) - set(ACTIVITY_BY_EVENT_TYPE)
    if missing:
        names = ", ".join(sorted(event_type.value for event_type in missing))
        raise ValueError(f"activity mapping is incomplete: {names}")
