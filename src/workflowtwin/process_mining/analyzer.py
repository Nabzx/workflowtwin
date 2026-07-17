"""End-to-end deterministic process reconstruction orchestration."""

from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.fingerprint import dataset_fingerprint
from workflowtwin.process_mining.adapters.pm4py import Pm4pyAdapter
from workflowtwin.process_mining.bottlenecks import detect_bottleneck_candidates
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.conformance import replay_reference, summarize_conformance
from workflowtwin.process_mining.event_log import build_process_log
from workflowtwin.process_mining.fingerprint import (
    PROCESS_ANALYSIS_VERSION,
    process_fingerprint,
)
from workflowtwin.process_mining.graph_data import build_graph_data
from workflowtwin.process_mining.ground_truth_evaluation import (
    evaluate_process_ground_truth,
)
from workflowtwin.process_mining.models import (
    CaseProcessResult,
    ProcessAnalysisInput,
    ProcessLog,
    ProcessMiningAnalysis,
    ProcessMiningBundle,
    ProcessVariant,
    TraceConformanceResult,
)
from workflowtwin.process_mining.reconciliation import reconcile_baseline
from workflowtwin.process_mining.reference_models import (
    GOVERNED_REFERENCE,
    GOVERNED_REFERENCE_ID,
    STRICT_REFERENCE,
    STRICT_REFERENCE_ID,
)
from workflowtwin.process_mining.reporting import preflight_paths
from workflowtwin.process_mining.transitions import (
    calculate_process_statistics,
    transition_id,
)
from workflowtwin.process_mining.variants import build_variants, calculate_complexity

FICTIONAL_CONFIRMATION = (
    "Northstar Clinics, all process records, and every process finding are fictional; "
    "analysis covers administrative operations only."
)


class ProcessMiningAnalyzer:
    """Coordinate owned calculations and the isolated PM4Py adapter."""

    def __init__(self, config: ProcessMiningConfig, adapter: Pm4pyAdapter | None = None) -> None:
        self._config = config
        self._adapter = adapter or Pm4pyAdapter()

    def analyze(
        self,
        analysis_input: ProcessAnalysisInput,
        *,
        analysed_at: datetime | None = None,
    ) -> ProcessMiningBundle:
        operational = analysis_input.operational
        actual_fingerprint = dataset_fingerprint(operational.cases, operational.events)
        if actual_fingerprint != operational.dataset_fingerprint:
            raise ValueError("process input dataset fingerprint does not match operational records")
        if (
            self._config.generation_run_id is not None
            and self._config.generation_run_id != operational.generation_run_id
        ):
            raise ValueError("configured generation run does not match process input")
        if operational.manifest is not None:
            if operational.manifest.dataset_fingerprint != actual_fingerprint:
                raise ValueError("generation manifest fingerprint does not match process input")
            if (
                operational.generation_run_id is not None
                and operational.manifest.generation_run_id != operational.generation_run_id
            ):
                raise ValueError("generation manifest run does not match process input")
        if (
            self._config.source_dataset_fingerprint is not None
            and self._config.source_dataset_fingerprint != actual_fingerprint
        ):
            raise ValueError("configured process source fingerprint does not match input")
        baseline = analysis_input.baseline
        if baseline is not None:
            if baseline.source_dataset_fingerprint != actual_fingerprint:
                raise ValueError(
                    "baseline analysis source fingerprint does not match process input"
                )
            if (
                self._config.baseline_analysis_fingerprint is not None
                and self._config.baseline_analysis_fingerprint != baseline.analysis_fingerprint
            ):
                raise ValueError("configured baseline analysis fingerprint does not match input")
        process_log = build_process_log(operational, self._config)
        if not process_log.traces:
            raise ValueError("process input contains no usable traces")
        baseline_input = replace(operational, ground_truth=None)
        baseline_bundle = BaselineAnalyzer(
            AnalysisConfig(
                source_dataset_fingerprint=actual_fingerprint,
                generation_run_id=operational.generation_run_id,
                period_start=self._config.period_start,
                period_end=self._config.period_end,
                duplicate_policy=self._config.duplicate_policy,
                minimum_cohort_size=self._config.minimum_cohort_size,
            )
        ).analyze(baseline_input)
        statistics = calculate_process_statistics(process_log, self._config)
        canonical_dfg = {
            (transition.source_activity, transition.target_activity): transition.frequency
            for transition in statistics.transitions
        }
        discovery = self._adapter.discover(process_log, self._config, canonical_dfg).result
        strict_results = (
            replay_reference(process_log, STRICT_REFERENCE_ID, self._config, self._adapter)
            if self._config.strict_reference_enabled
            else None
        )
        governed_results = (
            replay_reference(process_log, GOVERNED_REFERENCE_ID, self._config, self._adapter)
            if self._config.governed_reference_enabled
            else None
        )
        conformance_by_case = self._conformance_by_case(strict_results, governed_results)
        variants = build_variants(
            process_log,
            baseline_bundle.case_metrics,
            self._config,
            conformance_by_case,
        )
        complexity = calculate_complexity(
            process_log,
            variants,
            len(statistics.transitions),
            baseline_bundle.case_metrics,
        )
        strict_summary = (
            summarize_conformance(STRICT_REFERENCE_ID, strict_results, process_log)
            if strict_results is not None
            else None
        )
        governed_summary = (
            summarize_conformance(GOVERNED_REFERENCE_ID, governed_results, process_log)
            if governed_results is not None
            else None
        )
        candidates = detect_bottleneck_candidates(
            process_log,
            statistics.transitions,
            variants,
            governed_results,
            self._config,
        )
        reconciliation = reconcile_baseline(baseline, candidates)
        evaluation = evaluate_process_ground_truth(
            candidates,
            operational.ground_truth,
            operational.generation_run_id,
        )
        graph_data = build_graph_data(
            process_log,
            statistics.activities,
            statistics.transitions,
            variants,
            candidates,
            governed_results,
        )
        reference_versions = tuple(
            reference.reference_id
            for reference, enabled in (
                (STRICT_REFERENCE, self._config.strict_reference_enabled),
                (GOVERNED_REFERENCE, self._config.governed_reference_enabled),
            )
            if enabled
        )
        fingerprint = process_fingerprint(
            source_dataset_fingerprint=actual_fingerprint,
            baseline_analysis_fingerprint=(
                baseline.analysis_fingerprint if baseline is not None else None
            ),
            config=self._config,
            reference_versions=reference_versions,
            transitions=statistics.transitions,
            variants=variants,
            complexity=complexity,
            discovery=discovery,
            strict=strict_summary,
            governed=governed_summary,
            candidates=candidates,
            graph_data=graph_data,
        )
        visualisation_artifacts, visualisation_warnings = self._visualise_if_requested()
        selected_deviations = governed_results or strict_results or ()
        deviation_summary = Counter(
            deviation.category.value
            for result in selected_deviations
            for deviation in result.deviations
        )
        warnings = tuple(
            sorted(set(process_log.quality.warnings + discovery.warnings + visualisation_warnings))
        )
        analysis = ProcessMiningAnalysis(
            analysis_version=PROCESS_ANALYSIS_VERSION,
            analysis_id=self._config.analysis_id,
            source_dataset_fingerprint=actual_fingerprint,
            baseline_analysis_fingerprint=(
                baseline.analysis_fingerprint if baseline is not None else None
            ),
            generation_run_id=operational.generation_run_id,
            activity_mapping_version=process_log.activity_mapping_version,
            reference_model_versions=reference_versions,
            configuration=self._config.model_dump(mode="json"),
            analysed_at=(analysed_at or datetime.now(UTC)).astimezone(UTC),
            case_count=len(process_log.traces),
            event_count=process_log.quality.events_included,
            log_quality=process_log.quality,
            activity_statistics=statistics.activities,
            transition_statistics=statistics.transitions,
            start_activity_counts=statistics.starts,
            end_activity_counts=statistics.ends,
            loops=statistics.loops,
            variants=variants,
            complexity=complexity,
            discovery=discovery,
            strict_conformance=strict_summary,
            governed_conformance=governed_summary,
            deviation_summary=dict(sorted(deviation_summary.items())),
            bottleneck_candidates=candidates,
            baseline_reconciliation=reconciliation,
            ground_truth_evaluation=evaluation,
            graph_data=graph_data,
            visualisation_artifacts=visualisation_artifacts,
            warnings=warnings,
            assumptions=(
                "event time and event-id tie-breaking define observed process order",
                "transition durations are elapsed or business delay, not active work",
                "token replay measures structural fitness separately from performance",
                "candidate bottlenecks are associations requiring human investigation",
            ),
            process_analysis_fingerprint=fingerprint,
            fictional_data_confirmation=FICTIONAL_CONFIRMATION,
        )
        case_results = self._case_results(process_log, variants, strict_results, governed_results)
        return ProcessMiningBundle(
            analysis=analysis,
            case_results=case_results,
            process_log=process_log,
            case_metrics=baseline_bundle.case_metrics,
            visualisation_warnings=visualisation_warnings,
        )

    @staticmethod
    def _conformance_by_case(
        strict: tuple[TraceConformanceResult, ...] | None,
        governed: tuple[TraceConformanceResult, ...] | None,
    ) -> dict[UUID, tuple[float | None, float | None, bool | None, bool | None]]:
        strict_by_case = {result.case_id: result for result in strict or ()}
        governed_by_case = {result.case_id: result for result in governed or ()}
        return {
            case_id: (
                strict_by_case[case_id].fitness if case_id in strict_by_case else None,
                governed_by_case[case_id].fitness if case_id in governed_by_case else None,
                strict_by_case[case_id].status.value == "fully_conforming"
                if case_id in strict_by_case
                else None,
                governed_by_case[case_id].status.value == "fully_conforming"
                if case_id in governed_by_case
                else None,
            )
            for case_id in strict_by_case.keys() | governed_by_case.keys()
        }

    def _visualise_if_requested(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        directory = self._config.visualisation_directory
        if directory is None:
            return (), ()
        names = (
            "frequency-dfg.svg",
            "performance-dfg.svg",
            "discovered-process-tree.svg",
            "discovered-petri-net.svg",
            "northstar-strict-v1.svg",
            "northstar-governed-v1.svg",
        )
        preflight_paths(
            tuple(directory / name for name in names),
            overwrite=self._config.overwrite,
        )
        paths, warnings = self._adapter.export_visualisations(directory, self._config)
        return tuple(str(path) for path in paths), warnings

    @staticmethod
    def _case_results(
        process_log: ProcessLog,
        variants: tuple[ProcessVariant, ...],
        strict: tuple[TraceConformanceResult, ...] | None,
        governed: tuple[TraceConformanceResult, ...] | None,
    ) -> tuple[CaseProcessResult, ...]:
        variant_by_sequence = {variant.activities: variant.variant_id for variant in variants}
        strict_by_case = {result.case_id: result for result in strict or ()}
        governed_by_case = {result.case_id: result for result in governed or ()}
        return tuple(
            CaseProcessResult(
                case_id=trace.case_id,
                variant_id=variant_by_sequence[trace.activities],
                strict_conformance=strict_by_case.get(trace.case_id),
                governed_conformance=governed_by_case.get(trace.case_id),
                transition_ids=tuple(
                    transition_id(source, target)
                    for source, target in zip(trace.activities, trace.activities[1:], strict=False)
                ),
                warnings=trace.warnings,
            )
            for trace in process_log.traces
        )
