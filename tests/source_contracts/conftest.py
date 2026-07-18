"""Small deterministic V2 contract fixtures."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from workflowtwin.source_contracts.generator import generate_v2_intake_artifacts
from workflowtwin.source_contracts.io import load_requirements, load_source_contract
from workflowtwin.source_contracts.models import (
    AdministrativeTruthRecord,
    IncomingReferralSnapshotV2,
    SourceContractDefinition,
)
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset


@pytest.fixture
def requirements() -> AdministrativeRequirementsContract:
    return load_requirements(Path("config/shadow/northstar-requirements-v2.json"))


@pytest.fixture
def source_definition() -> SourceContractDefinition:
    return load_source_contract(Path("config/shadow/source-contract-v2.json"))


@pytest.fixture
def v2_source(
    requirements: AdministrativeRequirementsContract,
) -> tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[AdministrativeTruthRecord, ...]]:
    dataset = SyntheticReferralGenerator(
        config_for_preset(
            GenerationPreset.TINY,
            case_count=40,
            seed=81,
            generation_run_id="source-contract-test",
        ),
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
    ).generate()
    return generate_v2_intake_artifacts(dataset, requirements)
