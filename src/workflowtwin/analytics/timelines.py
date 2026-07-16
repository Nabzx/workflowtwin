"""Canonical non-mutating referral timeline construction."""

from collections import defaultdict
from dataclasses import dataclass
from itertools import groupby, pairwise
from uuid import UUID

from workflowtwin.analytics.config import AnalysisConfig, DuplicatePolicy
from workflowtwin.domain.referrals.enums import EventType
from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent


@dataclass(frozen=True, slots=True)
class CaseTimeline:
    referral_case: ReferralCase
    events: tuple[ReferralEvent, ...]
    excluded_duplicate_event_ids: tuple[UUID, ...]
    warnings: tuple[str, ...]
    identical_event_timestamps: bool
    out_of_order_ingestion: bool
    supported_schema: bool
    primary_source_system: str | None
    assigned_team: str | None


@dataclass(frozen=True, slots=True)
class TimelineBuildResult:
    timelines: tuple[CaseTimeline, ...]
    orphan_event_count: int
    period_excluded_case_count: int


def build_timelines(
    cases: tuple[ReferralCase, ...],
    events: tuple[ReferralEvent, ...],
    config: AnalysisConfig,
) -> TimelineBuildResult:
    """Build deterministic event-time timelines without reading synthetic labels."""
    case_ids = {case.id for case in cases}
    orphan_count = sum(event.referral_case_id not in case_ids for event in events)
    events_by_case: dict[UUID, list[ReferralEvent]] = defaultdict(list)
    for event in events:
        if event.referral_case_id in case_ids:
            events_by_case[event.referral_case_id].append(event)

    timelines = []
    period_excluded = 0
    for referral_case in sorted(cases, key=lambda item: item.id.hex):
        if config.period_start and referral_case.received_at < config.period_start:
            period_excluded += 1
            continue
        if config.period_end and referral_case.received_at >= config.period_end:
            period_excluded += 1
            continue
        ordered = sorted(
            events_by_case[referral_case.id], key=lambda item: (item.event_at, item.id.hex)
        )
        canonical = []
        duplicates = []
        seen_source_identities: set[tuple[str, str]] = set()
        for event in ordered:
            identity = (event.source_system.value, event.external_event_id)
            if identity in seen_source_identities:
                duplicates.append(event.id)
                continue
            seen_source_identities.add(identity)
            canonical.append(event)
        warnings = []
        if duplicates:
            warnings.append(f"excluded {len(duplicates)} duplicate source event(s)")
            if config.duplicate_policy is DuplicatePolicy.REJECT:
                warnings.append("duplicate policy rejects this timeline")
        identical = any(
            sum(1 for _ in group) > 1
            for _, group in groupby(canonical, key=lambda item: item.event_at)
        )
        if identical:
            warnings.append("identical event timestamps use event-id tie-breaking")
        out_of_order = any(
            current.ingested_at < previous.ingested_at for previous, current in pairwise(canonical)
        )
        if out_of_order:
            warnings.append("ingestion order differs from event-time order")
        if not canonical:
            warnings.append("case has no events")
        unsupported = referral_case.schema_version != config.expected_schema_version or any(
            event.schema_version != config.expected_schema_version for event in canonical
        )
        if unsupported:
            warnings.append("unsupported event schema version")
        received_event = next(
            (event for event in canonical if event.event_type is EventType.REFERRAL_RECEIVED), None
        )
        assigned_team = next(
            (
                str(event.metadata["assigned_team_identifier"])
                for event in reversed(canonical)
                if event.event_type
                in {EventType.CLINICAL_TEAM_ASSIGNED, EventType.CLINICAL_TEAM_REASSIGNED}
                and "assigned_team_identifier" in event.metadata
            ),
            None,
        )
        timelines.append(
            CaseTimeline(
                referral_case=referral_case,
                events=tuple(canonical),
                excluded_duplicate_event_ids=tuple(duplicates),
                warnings=tuple(warnings),
                identical_event_timestamps=identical,
                out_of_order_ingestion=out_of_order,
                supported_schema=not unsupported,
                primary_source_system=(
                    received_event.source_system.value if received_event else None
                ),
                assigned_team=assigned_team,
            )
        )
    return TimelineBuildResult(tuple(timelines), orphan_count, period_excluded)
