"""Evaluation-only missed-positive taxonomy and source observability ceilings."""

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from statistics import mean
from uuid import UUID

from workflowtwin.shadow.models import ShadowEvaluationLabel, ShadowLabelStatus
from workflowtwin.shadow.oracle import ShadowEvaluationOracle
from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2, SourceContractModel
from workflowtwin.source_contracts.precedence import SourcePrecedencePolicy
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import (
    AdministrativeFieldStateV2,
    ConflictStatus,
    FreshnessStatus,
    ManualReviewState,
)


class MissedPositiveCategory(StrEnum):
    SOURCE_EVIDENCE_UNAVAILABLE = "source_evidence_unavailable"
    EVIDENCE_ARRIVED_TOO_LATE = "evidence_arrived_too_late"
    UNKNOWN_ABSENT_AMBIGUITY = "unknown_versus_absent_ambiguity"
    CONDITIONAL_APPLICABILITY_UNKNOWN = "conditional_applicability_unknown"
    UNSUPPORTED_FORM_CONTRACT = "unsupported_form_contract"
    STALE_SOURCE_STATE = "stale_source_state"
    CONFLICTING_SOURCE_STATE = "conflicting_source_state"
    CONFIRMATION_WINDOW_MISS = "confirmation_window_miss"
    POLICY_ABSTENTION = "policy_abstention"
    REVIEW_ALREADY_UNDERWAY = "review_already_underway"
    CAPACITY_NOT_SURFACED = "capacity_not_surfaced"
    DETECTOR_RULE_MISS = "detector_rule_miss"
    LABEL_UNCERTAINTY = "label_uncertainty"


class ObservabilityStatus(StrEnum):
    OBSERVABLE_AND_DETECTED = "observable_and_detected"
    OBSERVABLE_BUT_MISSED = "observable_but_missed"
    PARTIALLY_OBSERVABLE = "partially_observable"
    OBSERVABLE_TOO_LATE = "observable_too_late"
    UNOBSERVABLE = "unobservable_from_current_contract"
    POLICY_PROHIBITED = "policy_prohibited"
    NOT_EVALUABLE = "not_evaluable"


class AvailabilityPoint(SourceContractModel):
    snapshot_id: str
    available_at: datetime
    state: str
    freshness: str
    conflict_status: str
    manual_review_state: str


class MissedPositiveAssessment(SourceContractModel):
    case_id: UUID
    primary_category: MissedPositiveCategory
    secondary_categories: tuple[MissedPositiveCategory, ...]
    observability_status: ObservabilityStatus
    supporting_source_references: tuple[str, ...]
    availability_timeline: tuple[AvailabilityPoint, ...]
    latest_useful_recommendation_at: datetime
    theoretically_recoverable: bool
    requires_source_contract_change: bool
    requires_detector_change: bool
    increases_latency: bool
    may_increase_false_positives: bool
    acceptable_under_policy: bool


class RecallCeiling(SourceContractModel):
    cohort_dimension: str
    cohort_value: str
    total_hidden_positives: int
    observable_under_contract: int
    observable_within_useful_window: int
    permitted_under_policy: int
    detectable_by_explicit_rules: int
    surfaced_under_capacity: int
    contract_ceiling: float | None
    useful_time_ceiling: float | None
    detected_recall: float | None
    surfaced_recall: float | None


class ObservabilityAnalysis(SourceContractModel):
    source_contract_version: str
    total_hidden_positives: int
    assessments: tuple[MissedPositiveAssessment, ...]
    ceilings: tuple[RecallCeiling, ...]
    category_counts: dict[str, int]
    status_counts: dict[str, int]
    analysis_fingerprint: str


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _support_state(snapshot: IncomingReferralSnapshotV2) -> str:
    field = snapshot.field("supporting_document")
    return field.state.value if field is not None else "missing"


def analyse_observability(
    *,
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
    labels: tuple[ShadowEvaluationLabel, ...],
    requirements: AdministrativeRequirementsContract,
    detected_case_ids: set[UUID] | None = None,
    surfaced_case_ids: set[UUID] | None = None,
    confirmation_miss_ids: set[UUID] | None = None,
    useful_window: timedelta = timedelta(minutes=120),
) -> ObservabilityAnalysis:
    """Use labels only after source publication is frozen to estimate the ceiling."""
    from workflowtwin.shadow.fingerprint import shadow_fingerprint

    detected = detected_case_ids or set()
    surfaced = surfaced_case_ids or set()
    confirmation_misses = confirmation_miss_ids or set()
    oracle = ShadowEvaluationOracle(labels)
    by_case: dict[UUID, list[IncomingReferralSnapshotV2]] = defaultdict(list)
    for snapshot in snapshots:
        by_case[snapshot.case_id].append(snapshot)
    positive_cases = {
        case_id
        for case_id, values in by_case.items()
        if oracle.label_at(case_id, min(item.available_at for item in values))
        is ShadowLabelStatus.POSITIVE
    }
    assessments = []
    observable: set[UUID] = set()
    timely: set[UUID] = set()
    permitted: set[UUID] = set()
    explicit: set[UUID] = set()
    precedence = SourcePrecedencePolicy()

    for case_id in sorted(positive_cases, key=lambda item: item.hex):
        ordered = sorted(by_case[case_id], key=lambda item: (item.available_at, item.snapshot_id))
        first = ordered[0]
        latest_useful = first.available_at + useful_window
        review_starts = [
            item.available_at
            for item in ordered
            if item.manual_review_state in {ManualReviewState.STARTED, ManualReviewState.COMPLETED}
        ]
        if review_starts:
            latest_useful = min(latest_useful, min(review_starts))
        timeline = tuple(
            AvailabilityPoint(
                snapshot_id=item.snapshot_id,
                available_at=item.available_at,
                state=_support_state(item),
                freshness=item.freshness.value,
                conflict_status=item.conflict_status.value,
                manual_review_state=item.manual_review_state.value,
            )
            for item in ordered
        )
        supported = requirements.requirements_for(
            form_identifier=first.form_identifier,
            form_version=first.form_version,
            source_system=first.source_system,
            as_of=first.available_at,
        )
        support = first.field("supporting_document")
        usable_evidence = next(
            (
                item
                for item in ordered
                if (field := item.field("supporting_document")) is not None
                and field.applicable is True
                and field.state
                in {
                    AdministrativeFieldStateV2.ABSENT,
                    AdministrativeFieldStateV2.VERIFICATION_REQUIRED,
                }
                and item.requirements_contract_version == requirements.contract_version
                and precedence.usable(item.freshness, item.conflict_status)
            ),
            None,
        )
        secondary = []
        if (
            supported is None
            or first.requirements_contract_version != requirements.contract_version
        ):
            primary = MissedPositiveCategory.UNSUPPORTED_FORM_CONTRACT
        elif first.conflict_status is ConflictStatus.DETECTED:
            primary = MissedPositiveCategory.CONFLICTING_SOURCE_STATE
        elif first.freshness is not FreshnessStatus.FRESH:
            primary = MissedPositiveCategory.STALE_SOURCE_STATE
        elif support is None or support.applicable is None:
            primary = MissedPositiveCategory.CONDITIONAL_APPLICABILITY_UNKNOWN
        elif support.state in {
            AdministrativeFieldStateV2.UNKNOWN,
            AdministrativeFieldStateV2.PENDING_SOURCE_UPDATE,
        }:
            primary = MissedPositiveCategory.UNKNOWN_ABSENT_AMBIGUITY
        elif usable_evidence is None:
            primary = MissedPositiveCategory.SOURCE_EVIDENCE_UNAVAILABLE
        elif usable_evidence.available_at > latest_useful:
            primary = MissedPositiveCategory.EVIDENCE_ARRIVED_TOO_LATE
        elif case_id in confirmation_misses:
            primary = MissedPositiveCategory.CONFIRMATION_WINDOW_MISS
        elif case_id not in detected:
            primary = MissedPositiveCategory.DETECTOR_RULE_MISS
        elif case_id not in surfaced:
            primary = MissedPositiveCategory.CAPACITY_NOT_SURFACED
        else:
            primary = MissedPositiveCategory.DETECTOR_RULE_MISS

        if first.manual_review_state in {ManualReviewState.STARTED, ManualReviewState.COMPLETED}:
            secondary.append(MissedPositiveCategory.REVIEW_ALREADY_UNDERWAY)
        if case_id in confirmation_misses and primary is not (
            MissedPositiveCategory.CONFIRMATION_WINDOW_MISS
        ):
            secondary.append(MissedPositiveCategory.CONFIRMATION_WINDOW_MISS)
        if usable_evidence is not None:
            observable.add(case_id)
            permitted.add(case_id)
            explicit.add(case_id)
            if usable_evidence.available_at <= latest_useful:
                timely.add(case_id)
        status = (
            ObservabilityStatus.OBSERVABLE_AND_DETECTED
            if case_id in detected
            else ObservabilityStatus.OBSERVABLE_BUT_MISSED
            if case_id in timely
            else ObservabilityStatus.OBSERVABLE_TOO_LATE
            if case_id in observable
            else ObservabilityStatus.PARTIALLY_OBSERVABLE
            if primary
            in {
                MissedPositiveCategory.UNKNOWN_ABSENT_AMBIGUITY,
                MissedPositiveCategory.CONDITIONAL_APPLICABILITY_UNKNOWN,
            }
            else ObservabilityStatus.UNOBSERVABLE
        )
        source_change = primary not in {
            MissedPositiveCategory.CONFIRMATION_WINDOW_MISS,
            MissedPositiveCategory.DETECTOR_RULE_MISS,
            MissedPositiveCategory.CAPACITY_NOT_SURFACED,
        }
        detector_change = primary in {
            MissedPositiveCategory.CONFIRMATION_WINDOW_MISS,
            MissedPositiveCategory.DETECTOR_RULE_MISS,
        }
        assessments.append(
            MissedPositiveAssessment(
                case_id=case_id,
                primary_category=primary,
                secondary_categories=tuple(secondary),
                observability_status=status,
                supporting_source_references=tuple(item.snapshot_id for item in ordered),
                availability_timeline=timeline,
                latest_useful_recommendation_at=latest_useful,
                theoretically_recoverable=case_id in timely or source_change,
                requires_source_contract_change=source_change,
                requires_detector_change=detector_change,
                increases_latency=primary is MissedPositiveCategory.EVIDENCE_ARRIVED_TOO_LATE,
                may_increase_false_positives=primary
                in {
                    MissedPositiveCategory.UNKNOWN_ABSENT_AMBIGUITY,
                    MissedPositiveCategory.DETECTOR_RULE_MISS,
                },
                acceptable_under_policy=primary
                not in {
                    MissedPositiveCategory.CONFLICTING_SOURCE_STATE,
                    MissedPositiveCategory.STALE_SOURCE_STATE,
                },
            )
        )

    dimensions: dict[str, Callable[[IncomingReferralSnapshotV2], str]] = {
        "overall": lambda item: "all",
        "source_system": lambda item: item.source_system.value,
        "form_version": lambda item: item.form_version,
        "freshness": lambda item: item.freshness.value,
        "form_support": lambda item: (
            "supported"
            if requirements.requirements_for(
                form_identifier=item.form_identifier,
                form_version=item.form_version,
                source_system=item.source_system,
                as_of=item.available_at,
            )
            else "unsupported"
        ),
        "manual_review": lambda item: item.manual_review_state.value,
    }
    first_by_case = {
        case_id: min(values, key=lambda item: item.available_at)
        for case_id, values in by_case.items()
    }
    ceilings = []
    for dimension, getter in dimensions.items():
        groups: dict[str, set[UUID]] = defaultdict(set)
        for case_id in positive_cases:
            groups[getter(first_by_case[case_id])].add(case_id)
        for value, cases in sorted(groups.items()):
            total = len(cases)
            ceilings.append(
                RecallCeiling(
                    cohort_dimension=dimension,
                    cohort_value=value,
                    total_hidden_positives=total,
                    observable_under_contract=len(cases & observable),
                    observable_within_useful_window=len(cases & timely),
                    permitted_under_policy=len(cases & permitted),
                    detectable_by_explicit_rules=len(cases & explicit & detected),
                    surfaced_under_capacity=len(cases & surfaced),
                    contract_ceiling=_ratio(len(cases & observable), total),
                    useful_time_ceiling=_ratio(len(cases & timely), total),
                    detected_recall=_ratio(len(cases & detected), total),
                    surfaced_recall=_ratio(len(cases & surfaced), total),
                )
            )
    category_counts = Counter(item.primary_category.value for item in assessments)
    status_counts = Counter(item.observability_status.value for item in assessments)
    content = {
        "contract": requirements.contract_version,
        "positives": len(positive_cases),
        "assessments": [item.model_dump(mode="json") for item in assessments],
        "ceilings": [item.model_dump(mode="json") for item in ceilings],
    }
    return ObservabilityAnalysis(
        source_contract_version=requirements.contract_version,
        total_hidden_positives=len(positive_cases),
        assessments=tuple(assessments),
        ceilings=tuple(ceilings),
        category_counts=dict(sorted(category_counts.items())),
        status_counts=dict(sorted(status_counts.items())),
        analysis_fingerprint=shadow_fingerprint(content),
    )


class ContractQualityMetrics(SourceContractModel):
    snapshot_count: int
    field_state_completeness: float
    applicability_coverage: float
    supported_form_rate: float
    stale_snapshot_rate: float
    conflict_rate: float
    unknown_state_rate: float
    unsupported_state_rate: float
    source_warning_coverage: float
    manual_review_state_availability: float
    requirements_version_agreement: float
    supersession_integrity: float
    mean_update_delay_minutes: float | None
    usable_input_coverage: float
    contract_related_abstention_rate: float
    by_source_system: dict[str, dict[str, float]]
    by_form_version: dict[str, dict[str, float]]
    by_logical_period: dict[str, dict[str, float]]
    by_producer_system: dict[str, dict[str, float]]


def contract_quality(
    snapshots: tuple[IncomingReferralSnapshotV2, ...],
    requirements: AdministrativeRequirementsContract,
) -> ContractQualityMetrics:
    total = len(snapshots) or 1
    observations = [field for item in snapshots for field in item.fields]
    field_total = len(observations) or 1

    def group_metrics(values: list[IncomingReferralSnapshotV2]) -> dict[str, float]:
        size = len(values) or 1
        return {
            "snapshot_count": float(len(values)),
            "supported_form_rate": sum(
                requirements.requirements_for(
                    form_identifier=item.form_identifier,
                    form_version=item.form_version,
                    source_system=item.source_system,
                    as_of=item.available_at,
                )
                is not None
                for item in values
            )
            / size,
            "fresh_rate": sum(item.freshness is FreshnessStatus.FRESH for item in values) / size,
            "conflict_rate": sum(item.conflict_status is ConflictStatus.DETECTED for item in values)
            / size,
        }

    def grouped(
        key: Callable[[IncomingReferralSnapshotV2], str],
    ) -> dict[str, dict[str, float]]:
        values: dict[str, list[IncomingReferralSnapshotV2]] = defaultdict(list)
        for snapshot in snapshots:
            values[key(snapshot)].append(snapshot)
        return {name: group_metrics(items) for name, items in sorted(values.items())}

    usable = sum(
        item.freshness is FreshnessStatus.FRESH
        and item.conflict_status is ConflictStatus.NONE
        and item.requirements_contract_version == requirements.contract_version
        and requirements.requirements_for(
            form_identifier=item.form_identifier,
            form_version=item.form_version,
            source_system=item.source_system,
            as_of=item.available_at,
        )
        is not None
        for item in snapshots
    )
    abstain = sum(
        item.freshness is not FreshnessStatus.FRESH
        or item.conflict_status is ConflictStatus.DETECTED
        or item.requirements_contract_version != requirements.contract_version
        for item in snapshots
    )
    delays = [(item.available_at - item.source_event_at).total_seconds() / 60 for item in snapshots]
    return ContractQualityMetrics(
        snapshot_count=len(snapshots),
        field_state_completeness=sum(bool(item.provenance_references) for item in observations)
        / field_total,
        applicability_coverage=sum(item.applicable is not None for item in observations)
        / field_total,
        supported_form_rate=sum(
            requirements.requirements_for(
                form_identifier=item.form_identifier,
                form_version=item.form_version,
                source_system=item.source_system,
                as_of=item.available_at,
            )
            is not None
            for item in snapshots
        )
        / total,
        stale_snapshot_rate=sum(item.freshness is FreshnessStatus.STALE for item in snapshots)
        / total,
        conflict_rate=sum(item.conflict_status is ConflictStatus.DETECTED for item in snapshots)
        / total,
        unknown_state_rate=sum(
            item.state
            in {
                AdministrativeFieldStateV2.UNKNOWN,
                AdministrativeFieldStateV2.PENDING_SOURCE_UPDATE,
            }
            for item in observations
        )
        / field_total,
        unsupported_state_rate=sum(
            item.state is AdministrativeFieldStateV2.UNSUPPORTED for item in observations
        )
        / field_total,
        source_warning_coverage=sum(bool(item.source_warning_codes) for item in snapshots) / total,
        manual_review_state_availability=sum(
            item.manual_review_state is not ManualReviewState.UNAVAILABLE for item in snapshots
        )
        / total,
        requirements_version_agreement=sum(
            item.requirements_contract_version == requirements.contract_version
            for item in snapshots
        )
        / total,
        supersession_integrity=sum(
            item.source_record_version == 1 or item.superseded_snapshot_id is not None
            for item in snapshots
        )
        / total,
        mean_update_delay_minutes=mean(delays) if delays else None,
        usable_input_coverage=usable / total,
        contract_related_abstention_rate=abstain / total,
        by_source_system=grouped(lambda item: item.source_system.value),
        by_form_version=grouped(lambda item: item.form_version),
        by_logical_period=grouped(lambda item: item.available_at.strftime("%Y-%m")),
        by_producer_system=grouped(lambda item: item.producer_system),
    )
