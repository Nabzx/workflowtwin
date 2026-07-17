"""Canonical typed process-log construction from operational contracts."""

from workflowtwin.analytics.config import AnalysisConfig, DuplicatePolicy
from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.analytics.timelines import build_timelines
from workflowtwin.process_mining.activity_mapping import (
    ACTIVITY_MAPPING_VERSION,
    activity_for,
    validate_activity_mapping,
)
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import (
    EventLogRecord,
    ProcessLog,
    ProcessLogQuality,
    ProcessTrace,
)


def build_process_log(analysis_input: AnalysisInput, config: ProcessMiningConfig) -> ProcessLog:
    """Build a deterministic PM4Py-independent log without synthetic labels."""
    validate_activity_mapping()
    if config.activity_mapping_version != ACTIVITY_MAPPING_VERSION:
        raise ValueError(f"unsupported activity mapping: {config.activity_mapping_version}")
    timeline_config = AnalysisConfig(
        expected_schema_version=config.expected_schema_version,
        period_start=config.period_start,
        period_end=config.period_end,
        duplicate_policy=config.duplicate_policy,
    )
    timeline_result = build_timelines(analysis_input.cases, analysis_input.events, timeline_config)
    traces = []
    empty_count = 0
    unsupported_schema = 0
    unsupported_mapping = 0
    duplicate_count = 0
    warnings = set()
    for timeline in timeline_result.timelines:
        duplicate_count += len(timeline.excluded_duplicate_event_ids)
        if (
            config.duplicate_policy is DuplicatePolicy.REJECT
            and timeline.excluded_duplicate_event_ids
        ):
            warnings.add("duplicate policy rejected affected traces")
            continue
        if not timeline.supported_schema:
            unsupported_schema += 1
            warnings.add("unsupported schema traces were excluded")
            continue
        records = []
        trace_warnings = list(timeline.warnings)
        for event in timeline.events:
            activity = activity_for(event.event_type)
            if activity is None:
                unsupported_mapping += 1
                trace_warnings.append(f"unsupported event mapping: {event.event_type.value}")
                continue
            team_identifier = event.metadata.get("assigned_team_identifier")
            records.append(
                EventLogRecord(
                    case_id=timeline.referral_case.id,
                    event_id=event.id,
                    activity=activity,
                    event_at=event.event_at,
                    ingested_at=event.ingested_at,
                    lifecycle_status=timeline.referral_case.status.value,
                    actor_type=event.actor_type.value,
                    actor_identifier=event.actor_identifier,
                    team_identifier=str(team_identifier) if team_identifier is not None else None,
                    source_system=event.source_system.value,
                    referral_source=timeline.referral_case.referral_source.value,
                    service_line=timeline.referral_case.service_line.value,
                    channel=event.channel.value,
                    requires_manual_work=event.requires_manual_work,
                    reason_code=event.reason_code.value if event.reason_code else None,
                    is_synthetic=timeline.referral_case.is_synthetic,
                )
            )
        if not records:
            empty_count += 1
            warnings.add("cases without usable mapped events were excluded")
            continue
        traces.append(
            ProcessTrace(
                case_id=timeline.referral_case.id,
                events=tuple(records),
                warnings=tuple(sorted(set(trace_warnings))),
            )
        )
    for timeline in timeline_result.timelines:
        warnings.update(timeline.warnings)
    quality = ProcessLogQuality(
        cases_received=len(analysis_input.cases),
        traces_included=len(traces),
        traces_excluded=len(analysis_input.cases) - len(traces),
        events_received=len(analysis_input.events),
        events_included=sum(len(trace.events) for trace in traces),
        duplicate_events_excluded=duplicate_count,
        orphan_event_count=timeline_result.orphan_event_count,
        empty_case_count=empty_count,
        unsupported_schema_cases=unsupported_schema,
        unsupported_mapping_count=unsupported_mapping,
        identical_timestamp_cases=sum(
            timeline.identical_event_timestamps for timeline in timeline_result.timelines
        ),
        out_of_order_ingestion_cases=sum(
            timeline.out_of_order_ingestion for timeline in timeline_result.timelines
        ),
        warnings=tuple(sorted(warnings)),
    )
    return ProcessLog(
        activity_mapping_version=ACTIVITY_MAPPING_VERSION,
        traces=tuple(sorted(traces, key=lambda trace: trace.case_id.hex)),
        quality=quality,
    )
