"""V2 state, provenance, requirements, and prohibited-field contracts."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from workflowtwin.source_contracts.models import FieldObservation, IncomingReferralSnapshotV2
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract
from workflowtwin.source_contracts.states import (
    FIELD_STATE_SEMANTICS,
    AdministrativeFieldStateV2,
)


def test_unknown_is_not_absent_and_requires_abstention() -> None:
    unknown = FIELD_STATE_SEMANTICS[AdministrativeFieldStateV2.UNKNOWN]
    absent = FIELD_STATE_SEMANTICS[AdministrativeFieldStateV2.ABSENT]
    assert unknown.abstention_required is True
    assert unknown.recommendation_permitted is False
    assert absent.recommendation_permitted is True


def test_snapshot_rejects_forbidden_field_and_bad_supersession(
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    snapshot = v2_source[0][0]
    with pytest.raises(ValidationError, match="unsupported or prohibited"):
        FieldObservation(
            field_id="diagnosis",
            state=AdministrativeFieldStateV2.PRESENT,
            applicable=True,
            observed_at=snapshot.available_at,
            producer_system="invalid",
            provenance_references=("invalid",),
        )
    with pytest.raises(ValidationError, match="supersede itself"):
        snapshot.model_copy(update={"superseded_snapshot_id": snapshot.snapshot_id}).model_validate(
            snapshot.model_copy(
                update={"superseded_snapshot_id": snapshot.snapshot_id}
            ).model_dump()
        )


def test_requirements_honour_form_version_and_effective_date(
    requirements: AdministrativeRequirementsContract,
    v2_source: tuple[tuple[IncomingReferralSnapshotV2, ...], tuple[object, ...]],
) -> None:
    snapshot = v2_source[0][0]
    form = requirements.requirements_for(
        form_identifier="northstar-referral-intake",
        form_version="NS-INTAKE-2",
        source_system=snapshot.source_system,
        as_of=snapshot.available_at,
    )
    assert form is not None
    assert "supporting_document" in {
        item.field_id for item in requirements.required_rules(form, {"referral_form": "present"})
    }
    assert (
        requirements.requirements_for(
            form_identifier="northstar-referral-intake",
            form_version="NS-INTAKE-2",
            source_system=snapshot.source_system,
            as_of=form.effective_from - timedelta(seconds=1),
        )
        is None
    )
