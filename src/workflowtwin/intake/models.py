"""Product names for the supported V2 administrative intake models."""

from workflowtwin.source_contracts.models import (
    FieldObservation,
    IncomingReferralSnapshotV2,
)

NorthstarIntakeSnapshot = IncomingReferralSnapshotV2
NorthstarFieldObservation = FieldObservation

__all__ = ["NorthstarFieldObservation", "NorthstarIntakeSnapshot"]
