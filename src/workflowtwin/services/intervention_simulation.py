"""File and PostgreSQL source adapters for intervention simulation."""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workflowtwin.analytics.models import BaselineAnalysis
from workflowtwin.opportunities.models import OpportunityAnalysis
from workflowtwin.process_mining.models import ProcessMiningAnalysis
from workflowtwin.services.baseline_analysis import input_from_database, input_from_dataset
from workflowtwin.simulation.models import SimulationInput
from workflowtwin.synthetic.artifacts import load_dataset, load_ground_truth, load_manifest
from workflowtwin.synthetic.models import GenerationGroundTruth


def _load_analyses(
    baseline_path: Path,
    process_path: Path,
    opportunity_path: Path,
) -> tuple[BaselineAnalysis, ProcessMiningAnalysis, OpportunityAnalysis]:
    return (
        BaselineAnalysis.model_validate_json(baseline_path.read_text(encoding="utf-8")),
        ProcessMiningAnalysis.model_validate_json(process_path.read_text(encoding="utf-8")),
        OpportunityAnalysis.model_validate_json(opportunity_path.read_text(encoding="utf-8")),
    )


def load_file_simulation_input(
    *,
    dataset_path: Path,
    manifest_path: Path,
    baseline_path: Path,
    process_path: Path,
    opportunity_path: Path,
    ground_truth_path: Path | None,
) -> SimulationInput:
    dataset = load_dataset(dataset_path)
    manifest = load_manifest(manifest_path)
    ground_truth = load_ground_truth(ground_truth_path) if ground_truth_path else None
    baseline, process, opportunities = _load_analyses(baseline_path, process_path, opportunity_path)
    return SimulationInput(
        source=input_from_dataset(
            dataset,
            manifest=manifest,
            ground_truth=None,
        ),
        baseline=baseline,
        process=process,
        opportunities=opportunities,
        manifest=manifest,
        ground_truth=ground_truth,
    )


async def load_database_simulation_input(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    generation_run_id: str,
    baseline_path: Path,
    process_path: Path,
    opportunity_path: Path,
    ground_truth_path: Path | None,
) -> SimulationInput:
    source = await input_from_database(session_factory, generation_run_id)
    if source.manifest is None:
        raise ValueError("persisted generation run has no manifest")
    baseline, process, opportunities = _load_analyses(baseline_path, process_path, opportunity_path)
    ground_truth: GenerationGroundTruth | None = (
        load_ground_truth(ground_truth_path) if ground_truth_path else None
    )
    return SimulationInput(
        source=source,
        baseline=baseline,
        process=process,
        opportunities=opportunities,
        manifest=source.manifest,
        ground_truth=ground_truth,
    )
