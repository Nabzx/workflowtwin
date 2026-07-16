"""PostgreSQL integration tests for idempotent generated-data persistence."""

import os
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from workflowtwin.analytics.analyzer import BaselineAnalyzer
from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.infrastructure.persistence.generation_runs import (
    GenerationRunStatus,
    SyntheticGenerationRunRecord,
)
from workflowtwin.infrastructure.persistence.models import ReferralCaseRecord, ReferralEventRecord
from workflowtwin.services.baseline_analysis import input_from_database, input_from_dataset
from workflowtwin.services.synthetic_generation import (
    GenerationPersistenceError,
    PersistenceStatus,
    SyntheticGenerationService,
)
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.models import GeneratedDataset

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
GENERATED_AT = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
async def generation_engine() -> AsyncIterator[AsyncEngine]:
    database_url = os.getenv("WORKFLOWTWIN_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("set WORKFLOWTWIN_TEST_DATABASE_URL to run PostgreSQL integration tests")
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE referral_events, referral_cases, synthetic_generation_runs "
                "RESTART IDENTITY"
            )
        )
    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE referral_events, referral_cases, synthetic_generation_runs "
                    "RESTART IDENTITY"
                )
            )
        await engine.dispose()


@pytest.fixture(scope="module")
def generation_sessions(
    generation_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(generation_engine, expire_on_commit=False)


def _dataset(run_id: str, *, seed: int = 42, case_count: int = 8) -> GeneratedDataset:
    config = GenerationConfig(
        seed=seed,
        case_count=case_count,
        generation_run_id=run_id,
        batch_size=3,
    )
    return SyntheticReferralGenerator(config, generated_at=GENERATED_AT).generate()


async def test_batched_persistence_is_idempotent(
    generation_sessions: async_sessionmaker[AsyncSession],
) -> None:
    dataset = _dataset("integration-idempotent")
    service = SyntheticGenerationService(generation_sessions, batch_size=3)

    first = await service.persist(dataset)
    second = await service.persist(dataset)

    assert first.status is PersistenceStatus.PERSISTED
    assert second.status is PersistenceStatus.ALREADY_COMPLETED
    async with generation_sessions() as session:
        case_count = await session.scalar(select(func.count()).select_from(ReferralCaseRecord))
        event_count = await session.scalar(select(func.count()).select_from(ReferralEventRecord))
        run = await session.get(SyntheticGenerationRunRecord, "integration-idempotent")
    assert case_count == len(dataset.cases)
    assert event_count == len(dataset.events)
    assert run is not None
    assert run.status == GenerationRunStatus.COMPLETED.value
    assert run.dataset_fingerprint == dataset.manifest.dataset_fingerprint


async def test_completed_run_id_rejects_different_fingerprint(
    generation_sessions: async_sessionmaker[AsyncSession],
) -> None:
    service = SyntheticGenerationService(generation_sessions, batch_size=2)
    await service.persist(_dataset("integration-fingerprint", seed=10, case_count=3))

    with pytest.raises(GenerationPersistenceError, match="different dataset fingerprint"):
        await service.persist(_dataset("integration-fingerprint", seed=11, case_count=3))


async def test_failed_batch_rolls_back_data_and_marks_run_failed(
    generation_sessions: async_sessionmaker[AsyncSession],
) -> None:
    dataset = _dataset("integration-rollback", case_count=4)
    orphan = dataset.events[-1].model_copy(update={"referral_case_id": uuid4()})
    invalid_dataset = replace(dataset, events=(*dataset.events[:-1], orphan))
    service = SyntheticGenerationService(generation_sessions, batch_size=2)

    with pytest.raises(GenerationPersistenceError, match="failed to persist"):
        await service.persist(invalid_dataset)

    case_ids = [case.id for case in dataset.cases]
    async with generation_sessions() as session:
        case_count = await session.scalar(
            select(func.count()).where(ReferralCaseRecord.id.in_(case_ids))
        )
        event_count = await session.scalar(
            select(func.count()).where(ReferralEventRecord.referral_case_id.in_(case_ids))
        )
        run = await session.get(SyntheticGenerationRunRecord, "integration-rollback")
    assert case_count == 0
    assert event_count == 0
    assert run is not None
    assert run.status == GenerationRunStatus.FAILED.value
    assert "IntegrityError" in (run.failure_summary or "")


async def test_file_and_database_analysis_have_same_logical_fingerprint(
    generation_sessions: async_sessionmaker[AsyncSession],
) -> None:
    dataset = _dataset("integration-analysis", case_count=20)
    await SyntheticGenerationService(generation_sessions, batch_size=5).persist(dataset)
    config = AnalysisConfig(minimum_cohort_size=2)

    file_bundle = BaselineAnalyzer(config).analyze(input_from_dataset(dataset))
    database_input = await input_from_database(generation_sessions, "integration-analysis")
    database_bundle = BaselineAnalyzer(config).analyze(database_input)

    assert database_bundle.baseline.analysis_fingerprint == (
        file_bundle.baseline.analysis_fingerprint
    )
    assert database_bundle.case_metrics == file_bundle.case_metrics
