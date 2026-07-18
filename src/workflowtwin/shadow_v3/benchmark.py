"""New deterministic strict-v3 benchmark splits and complete lineage manifests."""

from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from workflowtwin.shadow.fingerprint import shadow_fingerprint
from workflowtwin.shadow.intake import generate_intake_artifacts, intake_snapshot_fingerprint
from workflowtwin.shadow.models import (
    IncomingReferralSnapshot,
    ShadowEvaluationLabel,
    ShadowLabelStatus,
)
from workflowtwin.shadow_v3.models import V3DatasetManifest, V3DatasetSpecification
from workflowtwin.source_contracts.fingerprint import source_contract_fingerprint
from workflowtwin.source_contracts.generator import (
    generate_v2_intake_artifacts,
    v2_snapshot_fingerprint,
)
from workflowtwin.source_contracts.models import (
    AdministrativeTruthRecord,
    IncomingReferralSnapshotV2,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.synthetic.config import GenerationConfig
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.models import GeneratedDataset

_GENERATED_AT = datetime(2026, 7, 18, 15, tzinfo=UTC)


def build_v3_dataset(
    specification: V3DatasetSpecification,
    requirements: AdministrativeRequirementsContract,
) -> tuple[
    GeneratedDataset,
    tuple[IncomingReferralSnapshot, ...],
    tuple[IncomingReferralSnapshotV2, ...],
    tuple[AdministrativeTruthRecord, ...],
    tuple[ShadowEvaluationLabel, ...],
    V3DatasetManifest,
]:
    config = GenerationConfig(
        seed=specification.seed,
        case_count=specification.case_count,
        operating_days=specification.operating_days,
        generation_run_id=specification.generation_run_id,
    )
    dataset = SyntheticReferralGenerator(config, generated_at=_GENERATED_AT).generate()
    v1_snapshots, labels = generate_intake_artifacts(dataset)
    v2_snapshots, truth = generate_v2_intake_artifacts(dataset, requirements)
    initial_labels: dict[UUID, ShadowEvaluationLabel] = {}
    for label in labels:
        initial_labels.setdefault(label.case_id, label)
    first_v2: dict[UUID, IncomingReferralSnapshotV2] = {}
    for snapshot in v2_snapshots:
        first_v2.setdefault(snapshot.case_id, snapshot)
    manifest = V3DatasetManifest(
        dataset_id=specification.dataset_id,
        role=specification.role,
        seed=specification.seed,
        case_count=specification.case_count,
        operational_dataset_fingerprint=dataset.manifest.dataset_fingerprint,
        v1_snapshot_fingerprint=intake_snapshot_fingerprint(v1_snapshots),
        v2_snapshot_fingerprint=v2_snapshot_fingerprint(v2_snapshots),
        requirements_contract_fingerprint=source_contract_fingerprint(requirements),
        hidden_label_fingerprint=shadow_fingerprint(
            [item.model_dump(mode="json") for item in labels]
        ),
        source_mix=dict(
            sorted(Counter(item.source_system.value for item in first_v2.values()).items())
        ),
        form_version_mix=dict(
            sorted(Counter(item.form_version for item in first_v2.values()).items())
        ),
        positive_prevalence=(
            sum(item.status is ShadowLabelStatus.POSITIVE for item in initial_labels.values())
            / specification.case_count
        ),
        generation_configuration=config.model_dump(mode="json"),
    )
    return dataset, v1_snapshots, v2_snapshots, truth, labels, manifest
