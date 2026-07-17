"""File and PostgreSQL input adapters for process reconstruction."""

from dataclasses import replace
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workflowtwin.analytics.models import BaselineAnalysis
from workflowtwin.process_mining.models import ProcessAnalysisInput
from workflowtwin.services.baseline_analysis import input_from_database, input_from_dataset
from workflowtwin.synthetic.models import (
    GeneratedDataset,
    GenerationGroundTruth,
    GenerationManifest,
)


def load_baseline_analysis(path: Path) -> BaselineAnalysis:
    return BaselineAnalysis.model_validate_json(path.read_text(encoding="utf-8"))


def process_input_from_dataset(
    dataset: GeneratedDataset,
    *,
    manifest: GenerationManifest | None = None,
    ground_truth: GenerationGroundTruth | None = None,
    baseline: BaselineAnalysis | None = None,
) -> ProcessAnalysisInput:
    return ProcessAnalysisInput(
        operational=input_from_dataset(dataset, manifest=manifest, ground_truth=ground_truth),
        baseline=baseline,
    )


async def process_input_from_database(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: str,
    *,
    ground_truth: GenerationGroundTruth | None = None,
    baseline: BaselineAnalysis | None = None,
) -> ProcessAnalysisInput:
    operational = await input_from_database(session_factory, run_id)
    return ProcessAnalysisInput(
        operational=replace(operational, ground_truth=ground_truth),
        baseline=baseline,
    )
