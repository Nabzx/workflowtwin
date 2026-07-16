"""Idempotent transactional persistence for generated referral datasets."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workflowtwin.infrastructure.persistence.generation_runs import (
    GenerationRunStatus,
    SyntheticGenerationRunRecord,
)
from workflowtwin.infrastructure.persistence.models import ReferralCaseRecord, ReferralEventRecord
from workflowtwin.synthetic.manifest import GENERATOR_VERSION
from workflowtwin.synthetic.models import GeneratedDataset


class PersistenceStatus(StrEnum):
    PERSISTED = "persisted"
    ALREADY_COMPLETED = "already_completed"


@dataclass(frozen=True, slots=True)
class PersistenceResult:
    run_id: str
    status: PersistenceStatus
    case_count: int
    event_count: int


class GenerationPersistenceError(RuntimeError):
    """Raised when a run cannot be reserved or atomically persisted."""


class SyntheticGenerationService:
    """Persist one generated dataset in flushed batches and one transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        batch_size: int,
    ) -> None:
        self._session_factory = session_factory
        self._batch_size = batch_size
        self._logger = structlog.get_logger(__name__)

    async def persist(self, dataset: GeneratedDataset) -> PersistenceResult:
        """Persist once; return a no-op result for an identical completed run."""
        run_id = dataset.manifest.generation_run_id
        if await self._reserve_run(dataset):
            return PersistenceResult(
                run_id,
                PersistenceStatus.ALREADY_COMPLETED,
                len(dataset.cases),
                len(dataset.events),
            )

        self._logger.info(
            "synthetic_persistence_started",
            run_id=run_id,
            case_count=len(dataset.cases),
            event_count=len(dataset.events),
            batch_size=self._batch_size,
        )
        try:
            async with self._session_factory() as session, session.begin():
                for start in range(0, len(dataset.cases), self._batch_size):
                    case_batch = dataset.cases[start : start + self._batch_size]
                    session.add_all(ReferralCaseRecord.from_domain(case) for case in case_batch)
                    await session.flush()
                    session.expunge_all()
                for start in range(0, len(dataset.events), self._batch_size):
                    event_batch = dataset.events[start : start + self._batch_size]
                    session.add_all(ReferralEventRecord.from_domain(event) for event in event_batch)
                    await session.flush()
                    session.expunge_all()

                run = await session.get(SyntheticGenerationRunRecord, run_id, with_for_update=True)
                if run is None:
                    raise GenerationPersistenceError(f"generation run disappeared: {run_id}")
                run.status = GenerationRunStatus.COMPLETED.value
                run.generated_case_count = len(dataset.cases)
                run.generated_event_count = len(dataset.events)
                run.manifest_snapshot = dataset.manifest.model_dump(mode="json")
                run.dataset_fingerprint = dataset.manifest.dataset_fingerprint
                run.completed_at = datetime.now(UTC)
                run.failure_summary = None
        except Exception as error:
            await self._mark_failed(run_id, error)
            self._logger.exception("synthetic_persistence_failed", run_id=run_id)
            if isinstance(error, GenerationPersistenceError):
                raise
            raise GenerationPersistenceError(
                f"failed to persist generation run {run_id}"
            ) from error

        self._logger.info("synthetic_persistence_completed", run_id=run_id)
        return PersistenceResult(
            run_id,
            PersistenceStatus.PERSISTED,
            len(dataset.cases),
            len(dataset.events),
        )

    async def _reserve_run(self, dataset: GeneratedDataset) -> bool:
        run_id = dataset.manifest.generation_run_id
        async with self._session_factory() as session, session.begin():
            existing = await session.get(SyntheticGenerationRunRecord, run_id, with_for_update=True)
            if existing is not None:
                if existing.status == GenerationRunStatus.COMPLETED.value:
                    if existing.dataset_fingerprint != dataset.manifest.dataset_fingerprint:
                        raise GenerationPersistenceError(
                            f"completed run {run_id} has a different dataset fingerprint"
                        )
                    return True
                if existing.status == GenerationRunStatus.PENDING.value:
                    raise GenerationPersistenceError(f"generation run {run_id} is already pending")
                existing.status = GenerationRunStatus.PENDING.value
                existing.started_at = datetime.now(UTC)
                existing.completed_at = None
                existing.failure_summary = None
                return False

            session.add(
                SyntheticGenerationRunRecord(
                    run_id=run_id,
                    generator_version=GENERATOR_VERSION,
                    seed=dataset.config.seed,
                    status=GenerationRunStatus.PENDING.value,
                    requested_case_count=len(dataset.cases),
                    generated_case_count=0,
                    generated_event_count=0,
                    configuration_snapshot=dataset.config.model_dump(mode="json"),
                    manifest_snapshot=None,
                    dataset_fingerprint=None,
                    started_at=datetime.now(UTC),
                    completed_at=None,
                    failure_summary=None,
                )
            )
            return False

    async def _mark_failed(self, run_id: str, error: Exception) -> None:
        async with self._session_factory() as session, session.begin():
            run = await session.get(SyntheticGenerationRunRecord, run_id, with_for_update=True)
            if run is not None:
                run.status = GenerationRunStatus.FAILED.value
                run.completed_at = datetime.now(UTC)
                run.failure_summary = f"{type(error).__name__}: {error}"[:1_000]
