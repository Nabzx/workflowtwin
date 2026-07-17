"""Deterministic high-precision administrative completeness detector."""

from workflowtwin.shadow.config import DetectorProfile, ShadowConfig
from workflowtwin.shadow.fingerprint import shadow_id
from workflowtwin.shadow.models import (
    ConfidenceClass,
    DetectorInput,
    DetectorOutcome,
    DetectorResult,
    FieldAvailability,
    PolicyEvaluation,
    PolicyStatus,
)

RATIONALES = {
    "required_supporting_document_absent": (
        "The structured intake snapshot marks a required supporting document as absent."
    ),
    "source_acknowledgement_absent": (
        "The structured intake snapshot marks the source acknowledgement as absent."
    ),
    "contact_route_absent": (
        "The structured intake snapshot has no supported administrative contact route."
    ),
    "ambiguous_required_field": "Required structured intake evidence is not yet available.",
    "unsupported_form_version": "The form version is not supported by this detector.",
    "no_explicit_concern": "No explicit structured administrative completeness concern was found.",
}


class CompletenessReviewDetector:
    def __init__(self, config: ShadowConfig) -> None:
        self.config = config

    def evaluate(self, detector_input: DetectorInput, policy: PolicyEvaluation) -> DetectorResult:
        outcome = DetectorOutcome.NO_RECOMMENDATION
        reasons: list[str] = []
        fields: list[str] = []
        uncertainty: list[str] = []
        confidence: ConfidenceClass | None = None

        if policy.status is PolicyStatus.BLOCKED:
            outcome = DetectorOutcome.BLOCKED
            reasons.extend(policy.reason_codes)
        elif policy.status is PolicyStatus.ABSTAIN_REQUIRED:
            outcome = DetectorOutcome.ABSTAIN
            reasons.extend(policy.reason_codes)
            uncertainty.append("unsupported_form")
        else:
            state = detector_input.fields
            if state.supporting_document is FieldAvailability.ABSENT:
                reasons.append("required_supporting_document_absent")
                fields.append("supporting_document")
            if state.source_acknowledgement is FieldAvailability.ABSENT:
                reasons.append("source_acknowledgement_absent")
                fields.append("source_acknowledgement")
            if (
                self.config.detector_profile is not DetectorProfile.STRICT
                and state.contact_route is FieldAvailability.ABSENT
            ):
                reasons.append("contact_route_absent")
                fields.append("contact_route")
            unknown_required = any(
                value is FieldAvailability.UNKNOWN
                for value in (
                    state.referral_form,
                    state.supporting_document,
                    state.source_acknowledgement,
                )
            )
            if unknown_required:
                uncertainty.append("required_input_unknown")
                if self.config.detector_profile is DetectorProfile.EXPLORATORY:
                    reasons.append("ambiguous_required_field")
                    fields.append("supported_required_fields")
                elif not reasons:
                    outcome = DetectorOutcome.ABSTAIN
                    reasons.append("ambiguous_required_field")
            if reasons and outcome is not DetectorOutcome.ABSTAIN:
                outcome = DetectorOutcome.RECOMMEND
                confidence = (
                    ConfidenceClass.HIGH
                    if "required_supporting_document_absent" in reasons
                    else ConfidenceClass.MODERATE
                )
            elif not reasons:
                reasons.append("no_explicit_concern")

        rationale = " ".join(RATIONALES.get(reason, reason.replace("_", " ")) for reason in reasons)
        return DetectorResult(
            evaluation_id=shadow_id(
                "detector",
                self.config.shadow_run_id,
                detector_input.case_id,
                detector_input.state_version,
                self.config.detector_profile,
            ),
            case_id=detector_input.case_id,
            evaluated_at=detector_input.as_of,
            detector_version=self.config.detector_version,
            profile=self.config.detector_profile,
            outcome=outcome,
            reason_codes=tuple(reasons),
            relevant_fields=tuple(fields),
            confidence=confidence,
            uncertainty_factors=tuple(uncertainty),
            rationale=rationale,
            accessed_fields=(
                "form_version",
                "fields.referral_form",
                "fields.supporting_document",
                "fields.source_acknowledgement",
                "fields.contact_route",
            ),
        )
