"""Deterministic strict-v3 recommendation-only detector over V2 snapshots."""

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from workflowtwin.shadow.fingerprint import shadow_fingerprint, shadow_id
from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.shadow_v3.models import (
    V3AuditRecord,
    V3DetectorResult,
    V3Outcome,
    V3Run,
)
from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2
from workflowtwin.source_contracts.precedence import SourcePrecedencePolicy
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import (
    AdministrativeFieldStateV2,
    ConflictStatus,
    EvidenceStability,
    FreshnessStatus,
    ManualReviewState,
    UpdateType,
)

ACCESSED_FIELDS = (
    "available_at",
    "source_system",
    "source_record_identifier",
    "source_record_version",
    "form_identifier",
    "form_version",
    "requirements_contract_version",
    "fields.field_id",
    "fields.state",
    "fields.applicable",
    "source_warning_codes",
    "manual_review_state",
    "freshness",
    "conflict_status",
    "update_type",
    "superseded_snapshot_id",
    "producer_system",
    "provenance_references",
)


class StrictV3Detector:
    """No labels, future events, reviews, outcomes, or operational writers are accepted."""

    def __init__(
        self,
        config: StrictV3Config,
        requirements: AdministrativeRequirementsContract,
    ) -> None:
        self.config = config
        self.requirements = requirements
        self.precedence = SourcePrecedencePolicy()

    def run(
        self,
        snapshots: tuple[IncomingReferralSnapshotV2, ...],
        *,
        run_id: str,
    ) -> V3Run:
        by_case: dict[UUID, list[IncomingReferralSnapshotV2]] = defaultdict(list)
        for snapshot in snapshots:
            by_case[snapshot.case_id].append(snapshot)
        results = []
        active: set[UUID] = set()
        positive: set[UUID] = set()
        observe: set[UUID] = set()
        retracted: set[UUID] = set()

        for case_id in sorted(by_case, key=lambda item: item.hex):
            ordered = sorted(
                by_case[case_id], key=lambda item: (item.available_at, item.snapshot_id)
            )
            first_available = ordered[0].available_at
            seen_versions: set[tuple[str, int]] = set()
            pending: tuple[IncomingReferralSnapshotV2, datetime] | None = None
            for snapshot in ordered:
                if pending is not None and snapshot.available_at > pending[1]:
                    pending_snapshot, due_at = pending
                    results.append(
                        self._result(
                            snapshot=pending_snapshot,
                            evaluated_at=due_at,
                            outcome=V3Outcome.ABSTAIN,
                            reasons=("pending_update_not_confirmed",),
                            stability=EvidenceStability.PENDING,
                            first_available=first_available,
                            confirmation_due_at=due_at,
                        )
                    )
                    pending = None
                delivery_key = (
                    snapshot.source_record_identifier,
                    snapshot.source_record_version,
                )
                if delivery_key in seen_versions and snapshot.update_type is UpdateType.RETRY:
                    results.append(
                        self._result(
                            snapshot=snapshot,
                            evaluated_at=snapshot.available_at,
                            outcome=V3Outcome.NO_RECOMMENDATION,
                            reasons=("duplicate_delivery_suppressed",),
                            stability=EvidenceStability.SUPERSEDED,
                            first_available=first_available,
                        )
                    )
                    continue
                seen_versions.add(delivery_key)
                result = self._evaluate_snapshot(
                    snapshot,
                    first_available=first_available,
                    has_active_recommendation=case_id in active or case_id in observe,
                )
                results.append(result)
                if result.outcome is V3Outcome.PENDING:
                    assert result.confirmation_due_at is not None
                    pending = (snapshot, result.confirmation_due_at)
                elif result.outcome in {V3Outcome.RECOMMEND, V3Outcome.OBSERVE_ONLY}:
                    pending = None
                    positive.add(case_id)
                    if result.outcome is V3Outcome.RECOMMEND:
                        active.add(case_id)
                    else:
                        observe.add(case_id)
                elif result.outcome is V3Outcome.RETRACT:
                    pending = None
                    active.discard(case_id)
                    observe.discard(case_id)
                    retracted.add(case_id)
            if pending is not None:
                pending_snapshot, due_at = pending
                results.append(
                    self._result(
                        snapshot=pending_snapshot,
                        evaluated_at=due_at,
                        outcome=V3Outcome.ABSTAIN,
                        reasons=("pending_update_not_confirmed",),
                        stability=EvidenceStability.PENDING,
                        first_available=first_available,
                        confirmation_due_at=due_at,
                    )
                )

        ordered_results = tuple(
            sorted(results, key=lambda item: (item.evaluated_at, item.evaluation_id))
        )
        audits = self._audit(run_id, ordered_results)
        content = {
            "run_id": run_id,
            "detector_fingerprint": self.config.detector_fingerprint,
            "results": [item.content_fingerprint for item in ordered_results],
            "audit_root": audits[-1].content_fingerprint if audits else None,
        }
        return V3Run(
            run_id=run_id,
            detector_fingerprint=self.config.detector_fingerprint,
            source_contract_fingerprint=self.config.source_contract_fingerprint,
            requirements_contract_fingerprint=self.config.requirements_contract_fingerprint,
            results=ordered_results,
            audit_records=audits,
            detector_positive_case_ids=tuple(sorted(positive, key=lambda item: item.hex)),
            active_case_ids=tuple(sorted(active, key=lambda item: item.hex)),
            observe_only_case_ids=tuple(sorted(observe, key=lambda item: item.hex)),
            retracted_case_ids=tuple(sorted(retracted, key=lambda item: item.hex)),
            run_fingerprint=shadow_fingerprint(content),
        )

    def _evaluate_snapshot(
        self,
        snapshot: IncomingReferralSnapshotV2,
        *,
        first_available: datetime,
        has_active_recommendation: bool,
    ) -> V3DetectorResult:
        form = self.requirements.requirements_for(
            form_identifier=snapshot.form_identifier,
            form_version=snapshot.form_version,
            source_system=snapshot.source_system,
            as_of=snapshot.available_at,
        )
        if (
            form is None
            or snapshot.form_version not in self.config.supported_form_versions
            or snapshot.source_system not in self.config.supported_source_systems
            or snapshot.requirements_contract_version != self.config.requirements_contract_version
        ):
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=V3Outcome.ABSTAIN,
                reasons=("unsupported_or_mismatched_requirements_contract",),
                stability=EvidenceStability.UNSUPPORTED,
                first_available=first_available,
            )
        if snapshot.conflict_status is ConflictStatus.DETECTED:
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=V3Outcome.ABSTAIN,
                reasons=("conflicting_source_state",),
                stability=EvidenceStability.CONFLICTING,
                first_available=first_available,
            )
        if snapshot.freshness is not FreshnessStatus.FRESH:
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=V3Outcome.ABSTAIN,
                reasons=("source_state_not_fresh",),
                stability=EvidenceStability.STALE,
                first_available=first_available,
            )
        support = snapshot.field("supporting_document")
        if support is None or support.applicable is None:
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=V3Outcome.ABSTAIN,
                reasons=("document_applicability_unknown",),
                stability=EvidenceStability.UNKNOWN,
                first_available=first_available,
            )
        if support.state in {
            AdministrativeFieldStateV2.UNKNOWN,
            AdministrativeFieldStateV2.UNSUPPORTED,
        }:
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=V3Outcome.ABSTAIN,
                reasons=("required_document_state_uncertain",),
                stability=(
                    EvidenceStability.UNKNOWN
                    if support.state is AdministrativeFieldStateV2.UNKNOWN
                    else EvidenceStability.UNSUPPORTED
                ),
                first_available=first_available,
            )
        if support.state is AdministrativeFieldStateV2.PENDING_SOURCE_UPDATE:
            due_at = snapshot.available_at + self.config.pending_update_confirmation
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=V3Outcome.PENDING,
                reasons=("pending_source_update",),
                stability=EvidenceStability.PENDING,
                first_available=first_available,
                confirmation_due_at=due_at,
            )
        if support.state in {
            AdministrativeFieldStateV2.PRESENT,
            AdministrativeFieldStateV2.NOT_APPLICABLE,
        }:
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=(
                    V3Outcome.RETRACT
                    if snapshot.superseded_snapshot_id and has_active_recommendation
                    else V3Outcome.NO_RECOMMENDATION
                ),
                reasons=("current_source_state_resolved",),
                stability=EvidenceStability.RESOLVED,
                first_available=first_available,
            )
        if support.state is AdministrativeFieldStateV2.CONFLICTING:
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=V3Outcome.ABSTAIN,
                reasons=("field_level_source_conflict",),
                stability=EvidenceStability.CONFLICTING,
                first_available=first_available,
            )
        if support.state is AdministrativeFieldStateV2.STALE:
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=V3Outcome.ABSTAIN,
                reasons=("field_level_stale_state",),
                stability=EvidenceStability.STALE,
                first_available=first_available,
            )
        if support.state in {
            AdministrativeFieldStateV2.ABSENT,
            AdministrativeFieldStateV2.VERIFICATION_REQUIRED,
        }:
            reasons: tuple[str, ...] = (
                (
                    "required_supporting_document_explicitly_absent"
                    if support.state is AdministrativeFieldStateV2.ABSENT
                    else "administrative_verification_explicitly_required"
                ),
            )
            outcome = V3Outcome.RECOMMEND
            if (
                snapshot.manual_review_state
                in {ManualReviewState.STARTED, ManualReviewState.COMPLETED}
                and self.config.suppress_after_manual_review_start
            ):
                outcome = V3Outcome.OBSERVE_ONLY
                reasons = (*reasons, "manual_review_already_underway")
            elif snapshot.source_warning_codes and self.config.suppress_existing_source_warning:
                outcome = V3Outcome.OBSERVE_ONLY
                reasons = (*reasons, "overlapping_source_warning")
            return self._result(
                snapshot=snapshot,
                evaluated_at=snapshot.available_at,
                outcome=outcome,
                reasons=reasons,
                stability=EvidenceStability.STABLE_EXPLICIT_ABSENCE,
                first_available=first_available,
            )
        return self._result(
            snapshot=snapshot,
            evaluated_at=snapshot.available_at,
            outcome=V3Outcome.ABSTAIN,
            reasons=("unhandled_administrative_state",),
            stability=EvidenceStability.UNKNOWN,
            first_available=first_available,
        )

    def _result(
        self,
        *,
        snapshot: IncomingReferralSnapshotV2,
        evaluated_at: datetime,
        outcome: V3Outcome,
        reasons: tuple[str, ...],
        stability: EvidenceStability,
        first_available: datetime,
        confirmation_due_at: datetime | None = None,
    ) -> V3DetectorResult:
        evaluation_id = shadow_id(
            "strict-v3-evaluation",
            snapshot.case_id,
            snapshot.snapshot_id,
            evaluated_at.isoformat(),
            outcome,
        )
        content = {
            "evaluation_id": evaluation_id,
            "case_id": snapshot.case_id,
            "snapshot_id": snapshot.snapshot_id,
            "evaluated_at": evaluated_at,
            "detector_version": self.config.detector_version,
            "outcome": outcome,
            "reason_codes": reasons,
            "stability": stability,
            "source_references": snapshot.provenance_references,
        }
        positive = outcome in {V3Outcome.RECOMMEND, V3Outcome.OBSERVE_ONLY}
        return V3DetectorResult(
            evaluation_id=evaluation_id,
            case_id=snapshot.case_id,
            snapshot_id=snapshot.snapshot_id,
            evaluated_at=evaluated_at,
            detector_version=self.config.detector_version,
            outcome=outcome,
            reason_codes=reasons,
            relevant_fields=("supporting_document",),
            evidence_stability=stability,
            confirmation_due_at=confirmation_due_at,
            recommendation_latency_minutes=(
                (evaluated_at - first_available).total_seconds() / 60 if positive else None
            ),
            source_references=(snapshot.snapshot_id, *snapshot.provenance_references),
            accessed_fields=ACCESSED_FIELDS,
            recommendation_only=True,
            content_fingerprint=shadow_fingerprint(content),
        )

    def _audit(
        self, run_id: str, results: tuple[V3DetectorResult, ...]
    ) -> tuple[V3AuditRecord, ...]:
        records = []
        previous = None
        for sequence, result in enumerate(results, start=1):
            audit_id = shadow_id("strict-v3-audit", run_id, sequence, result.evaluation_id)
            content = {
                "audit_id": audit_id,
                "run_id": run_id,
                "sequence_number": sequence,
                "occurred_at": result.evaluated_at,
                "case_id": result.case_id,
                "action": result.outcome.value,
                "reason_codes": result.reason_codes,
                "input_references": result.source_references,
                "output_references": (result.evaluation_id,),
                "previous_record_fingerprint": previous,
            }
            record = V3AuditRecord.model_validate(
                {**content, "content_fingerprint": shadow_fingerprint(content)}
            )
            records.append(record)
            previous = record.content_fingerprint
        return tuple(records)


def verify_v3_audit(records: tuple[V3AuditRecord, ...]) -> tuple[bool, int]:
    previous = None
    broken = 0
    for sequence, record in enumerate(records, start=1):
        content = record.model_dump(mode="python", exclude={"content_fingerprint"})
        if (
            record.sequence_number != sequence
            or record.previous_record_fingerprint != previous
            or shadow_fingerprint(content) != record.content_fingerprint
        ):
            broken += 1
        previous = record.content_fingerprint
    return broken == 0, broken
