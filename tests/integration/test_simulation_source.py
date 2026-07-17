"""PostgreSQL source simulation remains read-only and matches file execution."""

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from workflowtwin.services.baseline_analysis import input_from_database
from workflowtwin.services.synthetic_generation import SyntheticGenerationService
from workflowtwin.simulation.config import SimulationConfig
from workflowtwin.simulation.counterfactuals import CounterfactualSimulator
from workflowtwin.simulation.interventions import define_intervention
from workflowtwin.simulation.models import SimulationInput
from workflowtwin.simulation.selection import select_controlled_prototype
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.models import GeneratedDataset

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


@pytest.fixture
async def simulation_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.getenv("WORKFLOWTWIN_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("set WORKFLOWTWIN_TEST_DATABASE_URL to run PostgreSQL integration tests")
    engine = create_async_engine(database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


async def test_database_source_matches_file_and_source_rows_remain_unchanged(
    simulation_engine: AsyncEngine,
    demo_simulation_input: SimulationInput,
    central_simulation_config: SimulationConfig,
) -> None:
    sessions = async_sessionmaker[AsyncSession](simulation_engine, expire_on_commit=False)
    source = demo_simulation_input.source
    assert demo_simulation_input.ground_truth is not None
    dataset = GeneratedDataset(
        config=GenerationConfig.model_validate(demo_simulation_input.manifest.configuration),
        cases=source.cases,
        events=source.events,
        ground_truth=demo_simulation_input.ground_truth,
        manifest=demo_simulation_input.manifest,
    )
    async with sessions.begin() as session:
        await session.execute(
            text(
                "TRUNCATE referral_events, referral_cases, synthetic_generation_runs "
                "RESTART IDENTITY"
            )
        )
    await SyntheticGenerationService(sessions, batch_size=500).persist(dataset)
    database_source = await input_from_database(
        sessions, demo_simulation_input.manifest.generation_run_id
    )
    database_input = SimulationInput(
        source=database_source,
        baseline=demo_simulation_input.baseline,
        process=demo_simulation_input.process,
        opportunities=demo_simulation_input.opportunities,
        manifest=demo_simulation_input.manifest,
        ground_truth=None,
    )
    definition = define_intervention(
        select_controlled_prototype(demo_simulation_input.opportunities)
    )

    file_result = CounterfactualSimulator(central_simulation_config).simulate(
        demo_simulation_input, definition
    )
    database_result = CounterfactualSimulator(central_simulation_config).simulate(
        database_input, definition
    )
    reloaded = await input_from_database(sessions, demo_simulation_input.manifest.generation_run_id)

    assert database_source.dataset_fingerprint == source.dataset_fingerprint
    assert database_result.manifest == file_result.manifest
    assert database_result.case_results == file_result.case_results
    assert reloaded.events == database_source.events
