"""Versioned WorkflowTwin descriptions of strict and governed references."""

from workflowtwin.process_mining.models import ReferenceProcess

STRICT_REFERENCE_ID = "northstar-strict-v1"
GOVERNED_REFERENCE_ID = "northstar-governed-v1"

STRICT_SEQUENCE = (
    "Referral submitted",
    "Referral received",
    "Completeness checked",
    "Referral categorised",
    "Clinical team assigned",
    "Scheduling started",
    "Appointment booked",
    "Patient notified",
    "Referral completed",
)

GOVERNED_ACTIVITIES = (
    "Referral submitted",
    "Referral received",
    "Completeness checked",
    "Missing information requested",
    "Missing information received",
    "Referral categorised",
    "Referral recategorised",
    "Clinical team assigned",
    "Clinical team reassigned",
    "Scheduling started",
    "Scheduling failed",
    "Appointment booked",
    "Patient notified",
    "Patient no response",
    "Referral completed",
    "Referral cancelled",
    "Referral rejected",
    "Referral closed other",
)
TERMINALS = (
    "Referral completed",
    "Referral cancelled",
    "Referral rejected",
    "Referral closed other",
)

STRICT_REFERENCE = ReferenceProcess(
    reference_id=STRICT_REFERENCE_ID,
    version="1.0.0",
    description="Simplest intended successful administrative referral path.",
    activities=STRICT_SEQUENCE,
    terminal_activities=("Referral completed",),
)
GOVERNED_REFERENCE = ReferenceProcess(
    reference_id=GOVERNED_REFERENCE_ID,
    version="1.0.0",
    description="Governed administrative variation with explicit exception and retry paths.",
    activities=GOVERNED_ACTIVITIES,
    terminal_activities=TERMINALS,
)
