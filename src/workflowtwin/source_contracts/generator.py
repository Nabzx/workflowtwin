"""Deterministic imperfect V2 publication, separated from synthetic truth."""

from collections import defaultdict
from datetime import timedelta
from random import Random

from workflowtwin.domain.referrals.enums import EventType
from workflowtwin.shadow.fingerprint import shadow_fingerprint, shadow_id
from workflowtwin.shadow.intake import generate_intake_artifacts
from workflowtwin.shadow.models import FieldAvailability
from workflowtwin.source_contracts.models import (
    AdministrativeTruthRecord,
    FieldObservation,
    IncomingReferralSnapshotV2,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import (
    AdministrativeFieldStateV2,
    ConflictStatus,
    FreshnessStatus,
    ManualReviewState,
    UpdateType,
)
from workflowtwin.synthetic.models import GeneratedDataset


def _rng(seed: int, *parts: object) -> Random:
    digest = shadow_fingerprint({"seed": seed, "parts": [str(item) for item in parts]})
    return Random(int(digest[:16], 16))


def _published_support_state(
    *,
    original: FieldAvailability,
    genuinely_incomplete: bool,
    corrected: bool,
    random: Random,
) -> AdministrativeFieldStateV2:
    if corrected:
        return AdministrativeFieldStateV2.PRESENT
    if original is FieldAvailability.ABSENT:
        return AdministrativeFieldStateV2.ABSENT
    if original is FieldAvailability.UNKNOWN:
        draw = random.random()
        if genuinely_incomplete and draw < 0.62:
            return AdministrativeFieldStateV2.ABSENT
        if genuinely_incomplete and draw < 0.82:
            return AdministrativeFieldStateV2.PENDING_SOURCE_UPDATE
        if not genuinely_incomplete and draw < 0.80:
            return AdministrativeFieldStateV2.PRESENT
        return AdministrativeFieldStateV2.UNKNOWN
    if original is FieldAvailability.PRESENT and genuinely_incomplete and random.random() < 0.48:
        return AdministrativeFieldStateV2.VERIFICATION_REQUIRED
    return AdministrativeFieldStateV2.PRESENT


def _state(value: FieldAvailability) -> AdministrativeFieldStateV2:
    return {
        FieldAvailability.PRESENT: AdministrativeFieldStateV2.PRESENT,
        FieldAvailability.ABSENT: AdministrativeFieldStateV2.ABSENT,
        FieldAvailability.UNKNOWN: AdministrativeFieldStateV2.UNKNOWN,
        FieldAvailability.NOT_APPLICABLE: AdministrativeFieldStateV2.NOT_APPLICABLE,
        FieldAvailability.UNSUPPORTED: AdministrativeFieldStateV2.UNSUPPORTED,
    }[value]


def generate_v2_intake_artifacts(
    dataset: GeneratedDataset,
    requirements: AdministrativeRequirementsContract,
) -> tuple[
    tuple[IncomingReferralSnapshotV2, ...],
    tuple[AdministrativeTruthRecord, ...],
]:
    """Publish plausible imperfect source facts; never attach truth to a snapshot."""
    v1_snapshots, _ = generate_intake_artifacts(dataset)
    truth_by_case = {item.case_id: item for item in dataset.ground_truth.cases}
    events_by_case = defaultdict(list)
    events_by_id = {}
    for event in dataset.events:
        events_by_case[event.referral_case_id].append(event)
        events_by_id[event.id] = event
    first_check_at = {}
    for case_id, events in events_by_case.items():
        check = next(
            item
            for item in sorted(events, key=lambda event: (event.ingested_at, event.id.hex))
            if item.event_type is EventType.COMPLETENESS_CHECK_COMPLETED
        )
        first_check_at[case_id] = check.ingested_at

    output = []
    truths = []
    seen_delivery: defaultdict[str, int] = defaultdict(int)
    for case in dataset.cases:
        intended = truth_by_case[case.id].intended_path
        incomplete = "incomplete" in intended
        truths.append(
            AdministrativeTruthRecord(
                case_id=case.id,
                supporting_document_required=True,
                supporting_document_present=not incomplete,
                acknowledgement_required=True,
                routing_contact_required=True,
                valid_from=case.received_at,
                provenance_reference=shadow_id(
                    "admin-truth", dataset.manifest.generation_run_id, case.id
                ),
            )
        )

    for original in v1_snapshots:
        seen_delivery[original.snapshot_id] += 1
        delivery = seen_delivery[original.snapshot_id]
        random = _rng(dataset.config.seed, original.snapshot_id, delivery, "source-v2")
        truth = truth_by_case[original.case_id]
        incomplete = "incomplete" in truth.intended_path
        form = requirements.requirements_for(
            form_identifier="northstar-referral-intake",
            form_version=original.form_version,
            source_system=original.source_system,
            as_of=original.available_at,
        )
        corrected = original.source_record_version > 1
        support_state = _published_support_state(
            original=original.supporting_document,
            genuinely_incomplete=incomplete,
            corrected=corrected,
            random=random,
        )
        conflict = random.random() < 0.018
        stale = random.random() < 0.025
        if conflict:
            support_state = AdministrativeFieldStateV2.CONFLICTING
        applicable = True if form is not None else None
        observed_at = (
            events_by_id[original.source_event_id].event_at
            if original.source_event_id in events_by_id
            else original.available_at - timedelta(minutes=1)
        )
        producer = f"northstar-{original.source_system.value}-adapter-v2"
        fields = (
            FieldObservation(
                field_id="referral_form",
                state=_state(original.referral_form),
                applicable=True,
                observed_at=observed_at,
                producer_system=producer,
                provenance_references=(original.snapshot_id,),
            ),
            FieldObservation(
                field_id="supporting_document",
                state=support_state,
                applicable=applicable,
                observed_at=observed_at,
                producer_system=producer,
                provenance_references=(original.snapshot_id,),
            ),
            FieldObservation(
                field_id="source_acknowledgement",
                state=_state(original.source_acknowledgement),
                applicable=applicable,
                observed_at=observed_at,
                producer_system=producer,
                provenance_references=(original.snapshot_id,),
            ),
            FieldObservation(
                field_id="routing_contact",
                state=_state(original.contact_route),
                applicable=applicable,
                observed_at=observed_at,
                producer_system=producer,
                provenance_references=(original.snapshot_id,),
            ),
        )
        warnings: tuple[str, ...] = ()
        if support_state is AdministrativeFieldStateV2.ABSENT and random.random() < 0.22:
            warnings = ("supporting_document_missing",)
        review_available = random.random() < 0.72
        review_state = (
            ManualReviewState.UNAVAILABLE
            if not review_available
            else ManualReviewState.STARTED
            if original.available_at >= first_check_at[original.case_id]
            else ManualReviewState.NOT_STARTED
        )
        snapshot_id = shadow_id(
            "snapshot-v2", dataset.manifest.generation_run_id, original.snapshot_id, delivery
        )
        previous_id = None
        if original.source_record_version > 1:
            previous_id = shadow_id(
                "snapshot-v2",
                dataset.manifest.generation_run_id,
                shadow_id("snapshot", dataset.manifest.generation_run_id, original.case_id, 1),
                1,
            )
        output.append(
            IncomingReferralSnapshotV2(
                snapshot_id=snapshot_id,
                case_id=original.case_id,
                available_at=original.available_at,
                source_event_at=observed_at,
                source_system=original.source_system,
                source_record_identifier=shadow_id(
                    "source-record", original.source_system, original.case_id, length=24
                ),
                source_record_version=original.source_record_version,
                referral_source=original.referral_source,
                requested_service_line=original.requested_service_line,
                form_identifier="northstar-referral-intake",
                form_version=original.form_version,
                requirements_contract_version=(
                    "mismatched-contract-v1"
                    if random.random() < 0.015
                    else requirements.contract_version
                ),
                fields=fields,
                source_warning_codes=warnings,
                manual_review_state=review_state,
                freshness=FreshnessStatus.STALE if stale else FreshnessStatus.FRESH,
                conflict_status=(ConflictStatus.DETECTED if conflict else ConflictStatus.NONE),
                update_type=(
                    UpdateType.RETRY
                    if delivery > 1 or original.is_source_retry
                    else UpdateType.SUPERSESSION
                    if corrected
                    else UpdateType.INITIAL
                ),
                superseded_snapshot_id=previous_id,
                producer_system=producer,
                provenance_references=(
                    original.snapshot_id,
                    dataset.manifest.dataset_fingerprint,
                ),
            )
        )
    ordered = tuple(sorted(output, key=lambda item: (item.available_at, item.snapshot_id)))
    return ordered, tuple(sorted(truths, key=lambda item: item.case_id.hex))


def v2_snapshot_fingerprint(snapshots: tuple[IncomingReferralSnapshotV2, ...]) -> str:
    return shadow_fingerprint([item.model_dump(mode="json") for item in snapshots])
