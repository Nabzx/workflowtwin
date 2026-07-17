"""End-to-end controlled intervention simulation orchestration."""

from datetime import UTC, datetime

from workflowtwin.analytics.fingerprint import dataset_fingerprint
from workflowtwin.simulation.analysis import (
    analyze_counterfactual_baseline,
    analyze_counterfactual_process,
)
from workflowtwin.simulation.benchmark import evaluate_simulation
from workflowtwin.simulation.comparisons import (
    compare_burden,
    compare_metrics,
    compare_process,
    summarize_baseline,
    summarize_process,
)
from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.counterfactuals import (
    FICTIONAL_COUNTERFACTUAL_DECLARATION,
    CounterfactualSimulator,
)
from workflowtwin.simulation.decision import decide_shadow_mode, shadow_mode_requirements
from workflowtwin.simulation.fingerprint import stable_hash
from workflowtwin.simulation.graph_data import build_graph_data
from workflowtwin.simulation.interventions import define_intervention
from workflowtwin.simulation.models import (
    BurdenComparison,
    EffectClassification,
    MetricComparison,
    ScenarioResult,
    SimulationAnalysis,
    SimulationInput,
    SimulationManifest,
)
from workflowtwin.simulation.selection import validate_selected_opportunity
from workflowtwin.simulation.sensitivity import (
    run_sensitivity,
    run_threshold_analysis,
)


class InterventionSimulator:
    """Validate sources, simulate behavior, reuse analysis, and assess shadow mode."""

    def __init__(self, config: SimulationConfig) -> None:
        self._config = config

    def analyze(
        self,
        simulation_input: SimulationInput,
        *,
        analysed_at: datetime | None = None,
        include_sensitivity: bool = True,
    ) -> SimulationAnalysis:
        self._validate_sources(simulation_input)
        candidate = validate_selected_opportunity(
            simulation_input.opportunities, self._config.selected_opportunity_id
        )
        definition = define_intervention(candidate)
        if definition.intervention_version != self._config.intervention_definition_version:
            raise ValueError("configured intervention version does not match definition")

        counterfactual = CounterfactualSimulator(self._config).simulate(
            simulation_input, definition
        )
        if not counterfactual.quality.is_valid:
            raise ValueError("counterfactual dataset failed simulation validation")
        baseline_bundle = analyze_counterfactual_baseline(simulation_input, counterfactual)
        process_bundle = analyze_counterfactual_process(
            simulation_input, counterfactual, baseline_bundle
        )
        metric_comparisons = compare_metrics(
            simulation_input.baseline, baseline_bundle.baseline, candidate
        )
        process_comparisons = compare_process(simulation_input.process, process_bundle.analysis)
        burden = compare_burden(
            simulation_input.baseline,
            baseline_bundle.baseline,
            candidate,
            counterfactual.case_results,
            self._config,
        )
        scenario_payload = {
            "scenario": self._config.scenario_id.value,
            "manifest": counterfactual.manifest,
            "quality": counterfactual.quality,
            "decisions": counterfactual.case_results,
            "baseline": baseline_bundle.baseline.analysis_fingerprint,
            "process": process_bundle.analysis.process_analysis_fingerprint,
            "metrics": metric_comparisons,
            "process_comparisons": process_comparisons,
            "burden": burden,
        }
        scenario = ScenarioResult(
            scenario_id=self._config.scenario_id.value,
            scenario_fingerprint=stable_hash(scenario_payload),
            manifest=counterfactual.manifest,
            quality=counterfactual.quality,
            case_results=counterfactual.case_results,
            baseline_summary=summarize_baseline(simulation_input.baseline, candidate),
            counterfactual_summary=summarize_baseline(baseline_bundle.baseline, candidate),
            baseline_process_summary=summarize_process(simulation_input.process),
            counterfactual_process_summary=summarize_process(process_bundle.analysis),
            metric_comparisons=metric_comparisons,
            process_comparisons=process_comparisons,
            burden_comparison=burden,
            direct_effects=self._effects(metric_comparisons, EffectClassification.INTENDED_DIRECT),
            secondary_effects=self._effects(metric_comparisons, EffectClassification.SECONDARY),
            control_overhead=(
                f"{counterfactual.manifest.review_required_count} cases entered review",
                f"{burden.simulated_operating_burden_hours:.3f} modelled control hours",
            ),
            adverse_effects=self._adverse_effects(counterfactual.manifest, burden),
            counterfactual_baseline_fingerprint=baseline_bundle.baseline.analysis_fingerprint,
            counterfactual_process_fingerprint=(
                process_bundle.analysis.process_analysis_fingerprint
            ),
        )
        sensitivity = (
            run_sensitivity(
                simulation_input,
                definition,
                self._config,
                burden.net_simulated_difference_hours,
            )
            if include_sensitivity
            else ()
        )
        thresholds = (
            run_threshold_analysis(simulation_input, definition, self._config)
            if include_sensitivity
            else ()
        )
        decision = decide_shadow_mode(candidate, scenario, sensitivity)
        benchmark = evaluate_simulation(
            scenario,
            decision,
            expected_opportunity_id=candidate.opportunity_id,
        )
        graph_data = build_graph_data(scenario, sensitivity)
        stable_payload = {
            "simulation_version": self._config.simulation_version,
            "simulation_id": self._config.simulation_id,
            "source_fingerprints": {
                "dataset": simulation_input.source.dataset_fingerprint,
                "baseline": simulation_input.baseline.analysis_fingerprint,
                "process": simulation_input.process.process_analysis_fingerprint,
                "opportunities": simulation_input.opportunities.opportunity_analysis_fingerprint,
            },
            "definition": definition,
            "policy_version": self._config.policy_version,
            "scenario": scenario,
            "sensitivity": sensitivity,
            "thresholds": thresholds,
            "decision": decision,
            "benchmark": benchmark,
            "graph_data": graph_data,
        }
        return SimulationAnalysis(
            simulation_version=self._config.simulation_version,
            simulation_id=self._config.simulation_id,
            analysed_at=(analysed_at or datetime.now(UTC)).astimezone(UTC),
            selected_opportunity=candidate,
            intervention_definition=definition,
            policy_version=self._config.policy_version,
            scenario_result=scenario,
            sensitivity_results=sensitivity,
            threshold_results=thresholds,
            decision=decision,
            shadow_mode_requirements=shadow_mode_requirements(),
            benchmark_evaluation=benchmark,
            graph_data=graph_data,
            assumptions=(
                "all probabilities, timings, burden, and cost inputs are fictional assumptions",
                "historical missing-information paths act as a simulation-only detector oracle",
                "baseline and process metrics are recalculated by existing engines",
            ),
            exclusions=(
                "no live workflow action or external communication",
                "no clinical inference, prioritisation, diagnosis, or treatment",
                "no realised savings, ROI, or production impact",
            ),
            warnings=(
                "counterfactual associations are not causal or production-performance evidence",
            ),
            simulation_analysis_fingerprint=stable_hash(stable_payload),
            fictional_counterfactual_declaration=FICTIONAL_COUNTERFACTUAL_DECLARATION,
        )

    def _validate_sources(self, simulation_input: SimulationInput) -> None:
        source = simulation_input.source
        actual = dataset_fingerprint(source.cases, source.events)
        if actual != self._config.source_dataset_fingerprint:
            raise ValueError("configured source dataset fingerprint mismatch")
        if simulation_input.manifest.dataset_fingerprint != actual:
            raise ValueError("simulation manifest dataset fingerprint mismatch")
        if simulation_input.baseline.source_dataset_fingerprint != actual:
            raise ValueError("baseline source fingerprint mismatch")
        if simulation_input.baseline.analysis_fingerprint != (
            self._config.baseline_analysis_fingerprint
        ):
            raise ValueError("baseline analysis fingerprint mismatch")
        if simulation_input.process.source_dataset_fingerprint != actual:
            raise ValueError("process source fingerprint mismatch")
        if simulation_input.process.process_analysis_fingerprint != (
            self._config.process_analysis_fingerprint
        ):
            raise ValueError("process analysis fingerprint mismatch")
        if simulation_input.process.baseline_analysis_fingerprint != (
            simulation_input.baseline.analysis_fingerprint
        ):
            raise ValueError("process analysis references a different baseline")
        opportunities = simulation_input.opportunities
        if opportunities.source_dataset_fingerprint != actual:
            raise ValueError("opportunity source fingerprint mismatch")
        if opportunities.opportunity_analysis_fingerprint != (
            self._config.opportunity_analysis_fingerprint
        ):
            raise ValueError("opportunity analysis fingerprint mismatch")
        if opportunities.baseline_analysis_fingerprint != (
            simulation_input.baseline.analysis_fingerprint
        ) or opportunities.process_analysis_fingerprint != (
            simulation_input.process.process_analysis_fingerprint
        ):
            raise ValueError("opportunity analysis references incompatible source analyses")
        if self._config.generation_run_id != source.generation_run_id:
            raise ValueError("configured generation run mismatch")
        if simulation_input.ground_truth is not None and (
            simulation_input.ground_truth.run_id != source.generation_run_id
        ):
            raise ValueError("ground truth generation run mismatch")

    @staticmethod
    def _effects(
        comparisons: tuple[MetricComparison, ...], classification: EffectClassification
    ) -> tuple[str, ...]:
        return tuple(
            f"{item.metric_name}: {item.absolute_difference:+.6g} {item.unit} simulated"
            for item in comparisons
            if item.effect_classification is classification and item.absolute_difference is not None
        )

    @staticmethod
    def _adverse_effects(manifest: SimulationManifest, burden: BurdenComparison) -> tuple[str, ...]:
        effects = [
            f"{manifest.rejected_action_count} reviewer rejections",
            f"{manifest.fallback_count} manual fallbacks",
            f"{manifest.rollback_count} rollbacks",
            f"{manifest.intervention_failure_count} simulated service failures",
        ]
        if burden.net_simulated_difference_hours < 0:
            effects.append("modelled control burden exceeds workflow-touch difference")
        return tuple(effects)
