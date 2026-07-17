"""Shared test fixtures."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.core.config import Settings
from workflowtwin.main import create_app
from workflowtwin.opportunities.analyzer import OpportunityIdentifier
from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import OpportunityAnalysis, OpportunityAnalysisInput
from workflowtwin.opportunities.research import load_research_pack
from workflowtwin.process_mining.analyzer import ProcessMiningAnalyzer
from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.services.baseline_analysis import input_from_dataset
from workflowtwin.services.process_analysis import process_input_from_dataset
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


@pytest.fixture
def anyio_backend() -> str:
    """Run async endpoint tests on the application's asyncio backend."""
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Create an API client with deterministic test configuration."""
    settings = Settings(
        _env_file=None,
        environment="test",
        log_level="ERROR",
        service_name="workflowtwin-api-test",
    )
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.fixture(scope="session")
def demo_opportunity_input() -> OpportunityAnalysisInput:
    """Build linked baseline, process, research, and benchmark inputs."""
    dataset = SyntheticReferralGenerator(
        config_for_preset(GenerationPreset.DEMO, seed=42),
        generated_at=datetime(2026, 7, 16, 12, tzinfo=UTC),
    ).generate()
    baseline = (
        BaselineAnalyzer(
            AnalysisConfig(
                source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
                generation_run_id=dataset.manifest.generation_run_id,
                minimum_cohort_size=20,
            )
        )
        .analyze(input_from_dataset(dataset))
        .baseline
    )
    process = ProcessMiningAnalyzer(
        ProcessMiningConfig(
            source_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
            baseline_analysis_fingerprint=baseline.analysis_fingerprint,
            generation_run_id=dataset.manifest.generation_run_id,
        )
    ).analyze(
        process_input_from_dataset(dataset, baseline=baseline),
        analysed_at=datetime(2026, 7, 17, tzinfo=UTC),
    ).analysis
    research = load_research_pack(
        Path("data/research/northstar-research-v1.json"),
        expected_version="northstar-research-v1",
    )
    return OpportunityAnalysisInput(
        baseline=baseline,
        process=process,
        research=research,
        manifest=dataset.manifest,
        ground_truth=dataset.ground_truth,
    )


@pytest.fixture(scope="session")
def demo_opportunity_analysis(
    demo_opportunity_input: OpportunityAnalysisInput,
) -> OpportunityAnalysis:
    """Identify opportunities from the fixed demo inputs."""
    return OpportunityIdentifier(OpportunityConfig()).analyze(
        demo_opportunity_input,
        analysed_at=datetime(2026, 7, 17, 12, tzinfo=UTC),
    )
