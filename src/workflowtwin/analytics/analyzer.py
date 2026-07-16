"""Application-independent orchestration for deterministic baseline analysis."""

from datetime import UTC, datetime

from workflowtwin.analytics.case_metrics import calculate_case_metrics
from workflowtwin.analytics.cohort_metrics import aggregate_cohorts
from workflowtwin.analytics.config import AnalysisConfig, DuplicatePolicy
from workflowtwin.analytics.findings import detect_findings
from workflowtwin.analytics.fingerprint import (
    ANALYSIS_VERSION,
    analysis_fingerprint,
    dataset_fingerprint,
    normalized_configuration,
)
from workflowtwin.analytics.ground_truth_evaluation import evaluate_findings
from workflowtwin.analytics.models import AnalysisBundle, AnalysisInput, BaselineAnalysis
from workflowtwin.analytics.quality import build_quality_report
from workflowtwin.analytics.timelines import build_timelines

FICTIONAL_CONFIRMATION = (
    "Northstar Clinics, every input record, and every reported finding are fictional; "
    "metrics describe administrative operations only."
)


class BaselineAnalyzer:
    """Run the versioned baseline pipeline over validated domain contracts."""

    def __init__(self, config: AnalysisConfig) -> None:
        self._config = config

    def analyze(
        self, analysis_input: AnalysisInput, *, analysed_at: datetime | None = None
    ) -> AnalysisBundle:
        actual_fingerprint = dataset_fingerprint(analysis_input.cases, analysis_input.events)
        if actual_fingerprint != analysis_input.dataset_fingerprint:
            raise ValueError("input dataset fingerprint does not match its operational records")
        if (
            self._config.source_dataset_fingerprint is not None
            and self._config.source_dataset_fingerprint != actual_fingerprint
        ):
            raise ValueError("configured source dataset fingerprint does not match input")
        if analysis_input.manifest is not None:
            if analysis_input.manifest.dataset_fingerprint != actual_fingerprint:
                raise ValueError("manifest dataset fingerprint does not match input")
            if analysis_input.manifest.generation_run_id != analysis_input.generation_run_id:
                raise ValueError("manifest generation run does not match input")
        timeline_result = build_timelines(analysis_input.cases, analysis_input.events, self._config)
        analysed_timelines = tuple(
            timeline
            for timeline in timeline_result.timelines
            if timeline.supported_schema
            and not (
                self._config.duplicate_policy is DuplicatePolicy.REJECT
                and timeline.excluded_duplicate_event_ids
            )
        )
        case_metrics = tuple(
            calculate_case_metrics(timeline, self._config) for timeline in analysed_timelines
        )
        overall, cohorts = aggregate_cohorts(case_metrics, self._config)
        quality = build_quality_report(
            cases_received=len(analysis_input.cases),
            timeline_result=timeline_result,
            analysed_timelines=analysed_timelines,
            case_metrics=case_metrics,
            config=self._config,
        )
        findings = detect_findings(overall, cohorts, case_metrics, self._config)
        evaluation = evaluate_findings(
            findings,
            analysis_input.ground_truth,
            analysis_input.generation_run_id,
        )
        fingerprint = analysis_fingerprint(
            source_dataset_fingerprint=actual_fingerprint,
            config=self._config,
            overall=overall,
            cohorts=cohorts,
            findings=findings,
            quality=quality,
        )
        event_times = [event.event_at for event in analysis_input.events]
        case_times = [case.received_at for case in analysis_input.cases]
        period_start = self._config.period_start or (min(case_times) if case_times else None)
        period_end = self._config.period_end or (max(event_times) if event_times else None)
        baseline = BaselineAnalysis(
            analysis_version=ANALYSIS_VERSION,
            analysis_id=self._config.analysis_id,
            configuration=normalized_configuration(self._config),
            source_dataset_fingerprint=actual_fingerprint,
            generation_run_id=analysis_input.generation_run_id,
            event_schema_version=self._config.expected_schema_version,
            analysed_at=(analysed_at or datetime.now(UTC)).astimezone(UTC),
            reporting_period_start=period_start,
            reporting_period_end=period_end,
            case_count=len(case_metrics),
            event_count=sum(len(timeline.events) for timeline in analysed_timelines),
            overall=overall,
            cohorts=cohorts,
            quality=quality,
            findings=findings,
            ground_truth_evaluation=evaluation,
            assumptions=(
                "event time is operational truth; ingestion time is used only for data quality",
                "processing time is estimated from configured minutes per manual touch",
                "waiting time is estimated from documented point-event boundaries",
                "comparative rules describe material differences, not statistical significance",
            ),
            exclusions=(
                "unsupported schema timelines are excluded entirely",
                "missing metric boundaries are unavailable rather than zero",
                "open-case age is excluded from closed duration summaries",
                "clinical, protected-attribute, and individual staff analysis is out of scope",
            ),
            warnings=quality.data_validation_warnings + quality.configuration_warnings,
            analysis_fingerprint=fingerprint,
            fictional_data_confirmation=FICTIONAL_CONFIRMATION,
        )
        return AnalysisBundle(baseline=baseline, case_metrics=case_metrics)
