"""Behavioral tests for coherent deterministic generation."""

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from statistics import mean
from uuid import uuid4

from workflowtwin.domain.referrals.enums import TERMINAL_STATUSES, EventType, ReferralStatus
from workflowtwin.domain.referrals.models import ReferralEvent
from workflowtwin.synthetic.config import DeviationRates, GenerationConfig
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.manifest import dataset_fingerprint
from workflowtwin.synthetic.models import BottleneckLabel, DefectType, GeneratedDataset
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset
from workflowtwin.synthetic.validation import validate_dataset

GENERATED_AT = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def _tiny(seed: int) -> GeneratedDataset:
    config = config_for_preset(GenerationPreset.TINY, seed=seed)
    return SyntheticReferralGenerator(config, generated_at=GENERATED_AT).generate()


def _events_by_case(dataset: GeneratedDataset) -> dict[object, list[ReferralEvent]]:
    result: dict[object, list[ReferralEvent]] = defaultdict(list)
    for event in dataset.events:
        result[event.referral_case_id].append(event)
    return result


def test_same_seed_and_config_produce_identical_logical_dataset() -> None:
    first = _tiny(42)
    second = _tiny(42)

    assert first.cases == second.cases
    assert first.events == second.events
    assert first.ground_truth == second.ground_truth
    assert first.manifest == second.manifest


def test_different_seed_changes_dataset() -> None:
    assert _tiny(42).manifest.dataset_fingerprint != _tiny(43).manifest.dataset_fingerprint


def test_generated_contracts_and_event_time_sequences_are_coherent(
    demo_dataset: GeneratedDataset,
) -> None:
    events_by_case = _events_by_case(demo_dataset)

    assert all(case.is_synthetic and case.schema_version == 1 for case in demo_dataset.cases)
    assert all(event.schema_version == 1 for event in demo_dataset.events)
    assert all(
        timestamp.tzinfo is not None and timestamp.utcoffset() is not None
        for event in demo_dataset.events
        for timestamp in (event.event_at, event.ingested_at)
    )
    for events in events_by_case.values():
        assert [event.event_at for event in events] == sorted(event.event_at for event in events)


def test_terminal_and_stuck_cases_follow_contract(demo_dataset: GeneratedDataset) -> None:
    events_by_case = _events_by_case(demo_dataset)
    terminal_events = {
        EventType.REFERRAL_COMPLETED,
        EventType.REFERRAL_CANCELLED,
        EventType.REFERRAL_REJECTED,
    }
    truth = {annotation.case_id: annotation for annotation in demo_dataset.ground_truth.cases}

    for case in demo_dataset.cases:
        case_event_types = {event.event_type for event in events_by_case[case.id]}
        if case.status in TERMINAL_STATUSES:
            assert case.closed_at is not None
            assert len(case_event_types & terminal_events) == 1
        else:
            assert case.status is ReferralStatus.AWAITING_INFORMATION
            assert case.closed_at is None
            assert not case_event_types & terminal_events
            assert truth[case.id].is_intentionally_stuck


def test_realised_outcome_rates_are_within_documented_tolerance(
    demo_dataset: GeneratedDataset,
) -> None:
    counts = Counter(case.status for case in demo_dataset.cases)
    total = len(demo_dataset.cases)

    assert 0.75 <= counts[ReferralStatus.COMPLETED] / total <= 0.89
    assert 0.04 <= counts[ReferralStatus.CANCELLED] / total <= 0.13
    assert 0.02 <= counts[ReferralStatus.REJECTED] / total <= 0.09
    assert 0.02 <= counts[ReferralStatus.AWAITING_INFORMATION] / total <= 0.09


def test_all_planted_bottlenecks_are_represented(demo_dataset: GeneratedDataset) -> None:
    labels = Counter(
        label for annotation in demo_dataset.ground_truth.cases for label in annotation.bottlenecks
    )

    assert set(labels) == set(BottleneckLabel)
    assert all(count >= 30 for count in labels.values())


def test_bottleneck_cases_have_measurable_operational_effects(
    demo_dataset: GeneratedDataset,
) -> None:
    events_by_case = _events_by_case(demo_dataset)
    truth = {annotation.case_id: annotation for annotation in demo_dataset.ground_truth.cases}
    cases = {case.id: case for case in demo_dataset.cases}

    def duration(case_id: object) -> float:
        events = events_by_case[case_id]
        return (events[-1].event_at - events[0].event_at).total_seconds() / 3600

    completed_background = [
        case.id
        for case in demo_dataset.cases
        if case.status is ReferralStatus.COMPLETED and not truth[case.id].bottlenecks
    ]
    background_duration = mean(duration(case_id) for case_id in completed_background)
    for label in BottleneckLabel:
        affected = [
            case_id for case_id, annotation in truth.items() if label in annotation.bottlenecks
        ]
        assert mean(duration(case_id) for case_id in affected) > background_duration

    incomplete_cases = [
        case_id
        for case_id, annotation in truth.items()
        if BottleneckLabel.INCOMPLETE_REFERRALS in annotation.bottlenecks
    ]
    assert mean(
        sum(event.requires_manual_work for event in events_by_case[case_id])
        for case_id in incomplete_cases
    ) > mean(
        sum(event.requires_manual_work for event in events_by_case[case_id])
        for case_id in completed_background
    )

    congested = [
        case_id
        for case_id, annotation in truth.items()
        if BottleneckLabel.ASSIGNMENT_CONGESTION in annotation.bottlenecks
    ]

    def assignment_wait(case_id: object) -> float:
        by_type = {event.event_type: event for event in events_by_case[case_id]}
        return (
            by_type[EventType.CLINICAL_TEAM_ASSIGNED].event_at
            - by_type[EventType.REFERRAL_CATEGORISED].event_at
        ).total_seconds() / 3600

    assert mean(assignment_wait(case_id) for case_id in congested) > mean(
        assignment_wait(case_id)
        for case_id in completed_background
        if EventType.CLINICAL_TEAM_ASSIGNED
        in {event.event_type for event in events_by_case[case_id]}
    )
    scheduling_cases = [
        case_id
        for case_id, annotation in truth.items()
        if BottleneckLabel.SCHEDULING_FRICTION in annotation.bottlenecks
    ]
    assert all(
        sum(
            event.event_type is EventType.APPOINTMENT_SCHEDULING_FAILED
            for event in events_by_case[case_id]
        )
        >= 1
        for case_id in scheduling_cases
    )
    handoff_cases = [
        case_id
        for case_id, annotation in truth.items()
        if BottleneckLabel.HANDOFF_COST in annotation.bottlenecks
    ]
    assert all(truth[case_id].has_handoff for case_id in handoff_cases)
    assert all(cases[case_id].service_line.value == "dermatology" for case_id in handoff_cases)


def test_ingestion_disorder_occurs_only_when_configured() -> None:
    deviations = DeviationRates(
        duplicate_source_event=0,
        delayed_ingestion=0,
        out_of_order_ingestion=0,
        missing_optional_actor=0,
        unexpected_channel=0,
        source_identifier_inconsistency=0,
        source_retry=0,
    )
    config = GenerationConfig(case_count=200, seed=17, deviations=deviations)
    dataset = SyntheticReferralGenerator(config, generated_at=GENERATED_AT).generate()
    report = validate_dataset(dataset)

    assert report.out_of_order_ingestion_count == 0
    assert report.delayed_ingestion_count == 0
    assert not dataset.ground_truth.duplicate_attempts


def test_duplicate_attempts_remain_outside_canonical_events(
    demo_dataset: GeneratedDataset,
) -> None:
    identities = [
        (event.source_system.value, event.external_event_id) for event in demo_dataset.events
    ]
    events = {event.id: event for event in demo_dataset.events}

    assert len(identities) == len(set(identities))
    assert demo_dataset.ground_truth.duplicate_attempts
    for attempt in demo_dataset.ground_truth.duplicate_attempts:
        canonical = events[attempt.canonical_event_id]
        assert attempt.external_event_id == canonical.external_event_id
        assert attempt.attempted_event_id not in events


def test_ground_truth_manifest_and_fingerprint_match_output(
    demo_dataset: GeneratedDataset,
) -> None:
    assert {annotation.case_id for annotation in demo_dataset.ground_truth.cases} == {
        case.id for case in demo_dataset.cases
    }
    assert demo_dataset.manifest.generated_case_count == len(demo_dataset.cases)
    assert demo_dataset.manifest.generated_event_count == len(demo_dataset.events)
    assert demo_dataset.manifest.dataset_fingerprint == dataset_fingerprint(
        demo_dataset.cases, demo_dataset.events
    )
    assert demo_dataset.manifest.fictional_data_confirmation.startswith("Northstar Clinics")


def test_validation_reports_expected_defects_without_invalidating_dataset(
    demo_dataset: GeneratedDataset,
) -> None:
    report = validate_dataset(demo_dataset)

    assert report.is_valid
    assert report.duplicate_external_event_count == 0
    assert (
        report.delayed_ingestion_count
        == demo_dataset.manifest.realised_defect_counts[DefectType.DELAYED_INGESTION.value]
    )
    assert any(finding.code == "duplicate_source_attempts" for finding in report.findings)


def test_validation_detects_an_orphan_event(demo_dataset: GeneratedDataset) -> None:
    orphan = demo_dataset.events[0].model_copy(update={"referral_case_id": uuid4()})
    invalid_dataset = replace(demo_dataset, events=(orphan, *demo_dataset.events[1:]))

    report = validate_dataset(invalid_dataset)

    assert not report.is_valid
    assert report.orphan_event_count == 1
