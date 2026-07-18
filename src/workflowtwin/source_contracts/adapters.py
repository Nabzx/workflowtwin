"""Read-only compatibility projections for V1 and V2 intake snapshots."""

from datetime import datetime
from uuid import UUID

from workflowtwin.domain.referrals.enums import SourceSystem
from workflowtwin.shadow.models import IncomingReferralSnapshot
from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2, SourceContractModel


class AdministrativeSnapshotView(SourceContractModel):
    case_id: UUID
    snapshot_id: str
    schema_version: int
    available_at: datetime
    source_system: SourceSystem
    form_version: str
    supporting_document_state: str
    requirements_contract_version: str | None


def view_v1(snapshot: IncomingReferralSnapshot) -> AdministrativeSnapshotView:
    """Expose V1 faithfully; unknown remains unknown and never becomes V2 absence."""
    return AdministrativeSnapshotView(
        case_id=snapshot.case_id,
        snapshot_id=snapshot.snapshot_id,
        schema_version=1,
        available_at=snapshot.available_at,
        source_system=snapshot.source_system,
        form_version=snapshot.form_version,
        supporting_document_state=snapshot.supporting_document.value,
        requirements_contract_version=None,
    )


def view_v2(snapshot: IncomingReferralSnapshotV2) -> AdministrativeSnapshotView:
    support = snapshot.field("supporting_document")
    return AdministrativeSnapshotView(
        case_id=snapshot.case_id,
        snapshot_id=snapshot.snapshot_id,
        schema_version=2,
        available_at=snapshot.available_at,
        source_system=snapshot.source_system,
        form_version=snapshot.form_version,
        supporting_document_state=support.state.value if support is not None else "unsupported",
        requirements_contract_version=snapshot.requirements_contract_version,
    )
