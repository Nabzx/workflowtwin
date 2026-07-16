"""File and PostgreSQL input adapters for the baseline analyzer."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workflowtwin.analytics.models import AnalysisInput
from workflowtwin.infrastructure.persistence.generation_runs import (
    GenerationRunStatus,
    SyntheticGenerationRunRecord,
)
from workflowtwin.infrastructure.persistence.models import ReferralCaseRecord, ReferralEventRecord
from workflowtwin.synthetic.models import (
    GeneratedDataset,
    GenerationGroundTruth,
    GenerationManifest,
)


class AnalysisInputError(RuntimeError):
    """Raised when an analysis source cannot provide a trustworthy input set."""


def input_from_dataset(
    dataset: GeneratedDataset,
    *,
    manifest: GenerationManifest | None = None,
    ground_truth: GenerationGroundTruth | None = None,
) -> AnalysisInput:
    """Adapt an exported dataset without implicitly using embedded labels."""
    selected_manifest = manifest or dataset.manifest
    return AnalysisInput(
        cases=dataset.cases,
        events=dataset.events,
        dataset_fingerprint=selected_manifest.dataset_fingerprint,
        generation_run_id=selected_manifest.generation_run_id,
        manifest=selected_manifest,
        ground_truth=ground_truth,
    )


async def input_from_database(
    session_factory: async_sessionmaker[AsyncSession], run_id: str
) -> AnalysisInput:
    """Load only one completed generation run with explicit stable ordering."""
    async with session_factory() as session:
        run = await session.get(SyntheticGenerationRunRecord, run_id)
        if run is None:
            raise AnalysisInputError(f"generation run does not exist: {run_id}")
        if run.status != GenerationRunStatus.COMPLETED.value:
            raise AnalysisInputError(f"generation run is not completed: {run_id}")
        if run.manifest_snapshot is None or run.dataset_fingerprint is None:
            raise AnalysisInputError(f"generation run has no completed manifest: {run_id}")
        manifest = GenerationManifest.model_validate(run.manifest_snapshot)
        event_statement = (
            select(ReferralEventRecord)
            .where(ReferralEventRecord.event_metadata["generation_run_id"].as_string() == run_id)
            .order_by(
                ReferralEventRecord.referral_case_id,
                ReferralEventRecord.event_at,
                ReferralEventRecord.id,
            )
        )
        event_records = tuple((await session.scalars(event_statement)).all())
        case_ids = sorted({event.referral_case_id for event in event_records})
        if not case_ids:
            raise AnalysisInputError(f"generation run has no persisted events: {run_id}")
        case_statement = (
            select(ReferralCaseRecord)
            .where(ReferralCaseRecord.id.in_(case_ids))
            .order_by(ReferralCaseRecord.id)
        )
        case_records = tuple((await session.scalars(case_statement)).all())
    if len(case_records) != manifest.generated_case_count:
        raise AnalysisInputError(
            f"generation run case count mismatch: expected {manifest.generated_case_count}, "
            f"loaded {len(case_records)}"
        )
    if len(event_records) != manifest.generated_event_count:
        raise AnalysisInputError(
            f"generation run event count mismatch: expected {manifest.generated_event_count}, "
            f"loaded {len(event_records)}"
        )
    return AnalysisInput(
        cases=tuple(record.to_domain() for record in case_records),
        events=tuple(record.to_domain() for record in event_records),
        dataset_fingerprint=run.dataset_fingerprint,
        generation_run_id=run_id,
        manifest=manifest,
        ground_truth=None,
    )
