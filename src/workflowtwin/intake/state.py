"""Supported administrative state vocabulary."""

from workflowtwin.source_contracts.states import (
    FIELD_STATE_SEMANTICS,
    AdministrativeFieldStateV2,
    ConflictStatus,
    EvidenceStability,
    FreshnessStatus,
    ManualReviewState,
    UpdateType,
)

AdministrativeFieldState = AdministrativeFieldStateV2

__all__ = [
    "FIELD_STATE_SEMANTICS",
    "AdministrativeFieldState",
    "ConflictStatus",
    "EvidenceStability",
    "FreshnessStatus",
    "ManualReviewState",
    "UpdateType",
]
