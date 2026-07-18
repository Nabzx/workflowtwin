"""Versioned strict-v2 confirmation detector using only as-of intake facts."""

from collections import defaultdict
from datetime import timedelta

from workflowtwin.shadow.fingerprint import shadow_id
from workflowtwin.shadow.models import FieldAvailability, IncomingReferralSnapshot
from workflowtwin.shadow_refinement.config import DetectorVersion, StrictV2Config
from workflowtwin.shadow_refinement.models import (
    ConfirmationStatus,
    PriorityLevel,
    RefinedSignal,
    RefinementContext,
)


def _priority(
    *, context: RefinementContext, evidence_strength: int
) -> tuple[PriorityLevel, tuple[str, ...]]:
    """Explain priority from administrative evidence, never outcome labels."""
    if context.conflicting_source_state:
        return PriorityLevel.ABSTAIN, ("explicit_source_conflict",)
    if context.source_warning_codes:
        return PriorityLevel.OBSERVE_ONLY, ("overlapping_source_warning",)
    if context.manual_review_started is True:
        return PriorityLevel.OBSERVE_ONLY, ("manual_review_already_started",)
    if evidence_strength >= 3:
        return PriorityLevel.ADMINISTRATIVE_HIGH, ("multiple_explicit_admin_gaps",)
    return PriorityLevel.STANDARD, ("explicit_supporting_document_absence",)


class StrictV2Detector:
    """Confirm explicit document absence after a fixed logical-time window."""

    def __init__(self, config: StrictV2Config | None = None) -> None:
        self.config = config or StrictV2Config()

    def run(
        self,
        snapshots: tuple[IncomingReferralSnapshot, ...],
        *,
        contexts: dict[str, RefinementContext] | None = None,
    ) -> tuple[RefinedSignal, ...]:
        context_by_snapshot = contexts or {}
        by_case: dict[object, list[IncomingReferralSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            by_case[snapshot.case_id].append(snapshot)

        signals: list[RefinedSignal] = []
        for case_snapshots in by_case.values():
            ordered = sorted(case_snapshots, key=lambda item: (item.available_at, item.snapshot_id))
            first = ordered[0]
            if (
                first.form_version not in self.config.supported_form_versions
                or first.source_system not in self.config.supported_source_systems
                or first.supporting_document is not FieldAvailability.ABSENT
            ):
                continue
            due_at = first.available_at + self.config.confirmation_window
            correction = next(
                (
                    item
                    for item in ordered[1:]
                    if item.available_at <= due_at
                    and item.supporting_document is FieldAvailability.PRESENT
                ),
                None,
            )
            context = context_by_snapshot.get(
                first.snapshot_id, RefinementContext(snapshot_id=first.snapshot_id)
            )
            status = (
                ConfirmationStatus.RESOLVED
                if correction is not None
                else ConfirmationStatus.CONFIRMED
            )
            decided_at = correction.available_at if correction is not None else due_at
            priority, priority_reasons = _priority(context=context, evidence_strength=2)
            if context.conflicting_source_state:
                status = ConfirmationStatus.INELIGIBLE
            reason_codes = ["required_supporting_document_absent"]
            if correction is not None:
                reason_codes.append("resolved_during_confirmation_window")
            if context.source_warning_codes:
                reason_codes.append("overlapping_source_warning")
            if context.manual_review_started is True:
                reason_codes.append("manual_review_already_started")
            if context.conflicting_source_state:
                reason_codes.append("explicit_source_conflict")
            signal_id = shadow_id(
                "strict-v2-signal", first.case_id, first.snapshot_id, due_at.isoformat()
            )
            signals.append(
                RefinedSignal(
                    signal_id=signal_id,
                    case_id=first.case_id,
                    detector_version=DetectorVersion.STRICT_V2,
                    rule_id="strict-v2-confirm-supporting-document",
                    detected_at=first.available_at,
                    confirmation_due_at=due_at,
                    decided_at=decided_at,
                    status=status,
                    reason_codes=tuple(reason_codes),
                    source_snapshot_ids=tuple(item.snapshot_id for item in ordered),
                    evidence_strength=2,
                    priority=priority,
                    priority_reasons=priority_reasons,
                    source_warning_overlap=bool(context.source_warning_codes),
                    manual_review_started=context.manual_review_started,
                    additional_latency_minutes=(decided_at - first.available_at).total_seconds()
                    / 60,
                    audit_reference=shadow_id("strict-v2-audit", signal_id),
                )
            )
        return tuple(sorted(signals, key=lambda item: (item.decided_at, item.signal_id)))


def with_confirmation_window(config: StrictV2Config, minutes: int) -> StrictV2Config:
    """Create an explicitly fingerprinted sensitivity variant."""
    return config.model_copy(update={"confirmation_window": timedelta(minutes=minutes)})
