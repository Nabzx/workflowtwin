"""Reuse baseline and process engines on counterfactual operational contracts."""

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.models import AnalysisBundle
from workflowtwin.process_mining.analyzer import ProcessMiningAnalyzer
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import ProcessAnalysisInput, ProcessMiningBundle
from workflowtwin.simulation.models import CounterfactualResult, SimulationInput


def analyze_counterfactual_baseline(
    simulation_input: SimulationInput, counterfactual: CounterfactualResult
) -> AnalysisBundle:
    configuration = dict(simulation_input.baseline.configuration)
    configuration.update(
        {
            "analysis_id": "northstar-counterfactual-baseline",
            "source_dataset_fingerprint": counterfactual.operational.dataset_fingerprint,
            "generation_run_id": counterfactual.operational.generation_run_id,
        }
    )
    return BaselineAnalyzer(AnalysisConfig.model_validate(configuration)).analyze(
        counterfactual.operational
    )


def analyze_counterfactual_process(
    simulation_input: SimulationInput,
    counterfactual: CounterfactualResult,
    baseline: AnalysisBundle,
) -> ProcessMiningBundle:
    configuration = dict(simulation_input.process.configuration)
    configuration.update(
        {
            "analysis_id": "northstar-counterfactual-process",
            "source_dataset_fingerprint": counterfactual.operational.dataset_fingerprint,
            "baseline_analysis_fingerprint": baseline.baseline.analysis_fingerprint,
            "generation_run_id": counterfactual.operational.generation_run_id,
            "analysis_output": None,
            "report_output": None,
            "graph_output": None,
            "case_output": None,
            "visualisation_directory": None,
            "overwrite": False,
        }
    )
    config = ProcessMiningConfig.model_validate(configuration)
    return ProcessMiningAnalyzer(config).analyze(
        ProcessAnalysisInput(
            operational=counterfactual.operational,
            baseline=baseline.baseline,
        )
    )
