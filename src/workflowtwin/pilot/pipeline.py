"""Deterministic analytical stages behind the supported end-to-end demo."""

from datetime import timedelta
from pathlib import Path

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.opportunities.analyzer import OpportunityIdentifier
from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import OpportunityAnalysisInput
from workflowtwin.opportunities.research import load_research_pack
from workflowtwin.pilot.demo import DEMO_CREATED_AT
from workflowtwin.process_mining.analyzer import ProcessMiningAnalyzer
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.services.baseline_analysis import input_from_dataset
from workflowtwin.services.process_analysis import process_input_from_dataset
from workflowtwin.simulation.analyzer import InterventionSimulator
from workflowtwin.simulation.config import ScenarioId, config_for_scenario
from workflowtwin.simulation.models import SimulationInput
from workflowtwin.simulation.selection import select_controlled_prototype
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset

ANALYSIS_CASE_COUNT = 1000
ANALYSIS_SEED = 42


def run_supported_analysis_pipeline() -> dict[str, str | int | bool]:
    """Execute baseline through simulation for the fixed fictional demo cohort."""
    dataset = SyntheticReferralGenerator(
        config_for_preset(
            GenerationPreset.DEMO,
            case_count=ANALYSIS_CASE_COUNT,
            seed=ANALYSIS_SEED,
            generation_run_id="northstar-supported-analysis-demo",
        ),
        generated_at=DEMO_CREATED_AT,
    ).generate()
    baseline = (
        BaselineAnalyzer(
            AnalysisConfig(
                source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
                generation_run_id=dataset.manifest.generation_run_id,
                minimum_cohort_size=10,
            )
        )
        .analyze(input_from_dataset(dataset))
        .baseline
    )
    process = (
        ProcessMiningAnalyzer(
            ProcessMiningConfig(
                source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
                baseline_analysis_fingerprint=baseline.analysis_fingerprint,
                generation_run_id=dataset.manifest.generation_run_id,
                minimum_cohort_size=10,
            )
        )
        .analyze(
            process_input_from_dataset(dataset, baseline=baseline),
            analysed_at=DEMO_CREATED_AT + timedelta(hours=1),
        )
        .analysis
    )
    research = load_research_pack(
        Path("data/research/northstar-research-v1.json"),
        expected_version="northstar-research-v1",
    )
    opportunities = OpportunityIdentifier(OpportunityConfig(minimum_sample_size=10)).analyze(
        OpportunityAnalysisInput(
            baseline=baseline,
            process=process,
            research=research,
            manifest=dataset.manifest,
            ground_truth=dataset.ground_truth,
        ),
        analysed_at=DEMO_CREATED_AT + timedelta(hours=2),
    )
    selected = select_controlled_prototype(opportunities)
    simulation_input = SimulationInput(
        source=input_from_dataset(dataset, ground_truth=None),
        baseline=baseline,
        process=process,
        opportunities=opportunities,
        manifest=dataset.manifest,
        ground_truth=dataset.ground_truth,
    )
    simulation = InterventionSimulator(
        config_for_scenario(
            scenario_id=ScenarioId.CENTRAL,
            selected_opportunity_id=selected.opportunity_id,
            source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
            baseline_analysis_fingerprint=baseline.analysis_fingerprint,
            process_analysis_fingerprint=process.process_analysis_fingerprint,
            opportunity_analysis_fingerprint=(opportunities.opportunity_analysis_fingerprint),
            generation_run_id=dataset.manifest.generation_run_id,
            simulation_seed=ANALYSIS_SEED,
        )
    ).analyze(
        simulation_input,
        analysed_at=DEMO_CREATED_AT + timedelta(hours=3),
        include_sensitivity=False,
    )
    return {
        "heavy_analysis_completed": True,
        "fictional_case_count": len(dataset.cases),
        "operational_dataset_fingerprint": dataset.manifest.dataset_fingerprint,
        "baseline_analysis_fingerprint": baseline.analysis_fingerprint,
        "process_analysis_fingerprint": process.process_analysis_fingerprint,
        "opportunity_analysis_fingerprint": (opportunities.opportunity_analysis_fingerprint),
        "selected_opportunity_id": selected.opportunity_id,
        "simulation_analysis_fingerprint": simulation.simulation_analysis_fingerprint,
    }
