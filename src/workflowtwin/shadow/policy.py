"""Recommendation-only administrative policy enforcement."""

from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.fingerprint import shadow_id
from workflowtwin.shadow.models import (
    DetectorInput,
    FieldAvailability,
    PolicyEvaluation,
    PolicyStatus,
)

ALLOWED_DETECTOR_FIELDS = (
    "case_id",
    "as_of",
    "state_version",
    "referral_source",
    "requested_service_line",
    "source_system",
    "form_version",
    "fields.referral_form",
    "fields.supporting_document",
    "fields.source_acknowledgement",
    "fields.contact_route",
    "source_snapshot_ids",
)
SUPPORTED_FORMS = frozenset({"NS-INTAKE-2"})


class ShadowPolicy:
    def __init__(self, config: ShadowConfig) -> None:
        self.config = config

    def evaluate(self, detector_input: DetectorInput) -> PolicyEvaluation:
        reasons: list[str] = []
        status = PolicyStatus.PERMITTED
        if detector_input.form_version not in SUPPORTED_FORMS:
            reasons.append("unsupported_form_version")
            status = PolicyStatus.ABSTAIN_REQUIRED
        if detector_input.fields.referral_form is FieldAvailability.UNSUPPORTED:
            reasons.append("unsupported_schema_field")
            status = PolicyStatus.BLOCKED
        if (
            any(
                field is FieldAvailability.UNKNOWN
                for field in (
                    detector_input.fields.referral_form,
                    detector_input.fields.supporting_document,
                    detector_input.fields.source_acknowledgement,
                )
            )
            and status is PolicyStatus.PERMITTED
        ):
            status = PolicyStatus.PERMITTED_WITH_WARNING
            reasons.append("incomplete_source_support")
        if not reasons:
            reasons.append("structured_administrative_scope_confirmed")
        return PolicyEvaluation(
            evaluation_id=shadow_id(
                "policy",
                self.config.shadow_run_id,
                detector_input.case_id,
                detector_input.state_version,
            ),
            case_id=detector_input.case_id,
            evaluated_at=detector_input.as_of,
            status=status,
            reason_codes=tuple(reasons),
            allowed_fields=ALLOWED_DETECTOR_FIELDS,
        )
