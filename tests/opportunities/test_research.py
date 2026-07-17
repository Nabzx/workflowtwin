"""Fictional research validation and traceability tests."""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from workflowtwin.opportunities.models import ResearchPack
from workflowtwin.opportunities.research import (
    FICTIONAL_DECLARATION,
    load_research_pack,
    validate_research_pack,
)


def _payload() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(Path("data/research/northstar-research-v1.json").read_text()),
    )


def test_research_pack_is_explicit_structured_and_varied() -> None:
    pack = load_research_pack(
        Path("data/research/northstar-research-v1.json"),
        expected_version="northstar-research-v1",
    )

    assert pack.fictional_data_declaration == FICTIONAL_DECLARATION
    assert len(pack.sessions) == 9
    assert sum(len(session.observations) for session in pack.sessions) == 10
    assert len({session.role for session in pack.sessions}) == 6
    contradiction_count = sum(
        bool(item.contradicts) for session in pack.sessions for item in session.observations
    )
    assert contradiction_count >= 4


def test_research_requires_declaration_and_supported_version() -> None:
    pack = ResearchPack.model_validate(_payload())

    with pytest.raises(ValueError, match="fictional-data declaration"):
        validate_research_pack(
            pack.model_copy(update={"fictional_data_declaration": "not declared"}),
            expected_version="northstar-research-v1",
        )
    with pytest.raises(ValueError, match="unsupported research pack version"):
        validate_research_pack(pack, expected_version="northstar-research-v2")


def test_research_rejects_patient_identifiers_and_clinical_claims() -> None:
    pack = ResearchPack.model_validate(_payload())
    session = pack.sessions[0]
    observation = session.observations[0]

    sensitive = observation.model_copy(update={"supporting_quote": "NHS number: 123 456 7890"})
    sensitive_pack = pack.model_copy(
        update={
            "sessions": (
                session.model_copy(update={"observations": (sensitive,)}),
                *pack.sessions[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="direct patient identifier"):
        validate_research_pack(sensitive_pack, expected_version=pack.pack_version)

    clinical = observation.model_copy(
        update={"reported_problem": "This would require diagnosis inference"}
    )
    clinical_pack = pack.model_copy(
        update={
            "sessions": (
                session.model_copy(update={"observations": (clinical,)}),
                *pack.sessions[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="prohibited clinical claim"):
        validate_research_pack(clinical_pack, expected_version=pack.pack_version)


def test_unknown_roles_and_archetypes_fail_typed_validation() -> None:
    payload = _payload()
    sessions = payload["sessions"]
    assert isinstance(sessions, list)
    sessions[0]["role"] = "unknown_role"

    with pytest.raises(ValidationError):
        ResearchPack.model_validate(payload)
