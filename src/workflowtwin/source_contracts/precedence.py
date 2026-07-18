"""Explicit source precedence without outcome-label resolution."""

from pydantic import Field

from workflowtwin.domain.referrals.enums import SourceSystem
from workflowtwin.source_contracts.models import SourceContractModel
from workflowtwin.source_contracts.states import ConflictStatus, FreshnessStatus


class SourcePrecedencePolicy(SourceContractModel):
    policy_version: str = "northstar-source-precedence-v2"
    priority: tuple[SourceSystem, ...] = (
        SourceSystem.REFERRAL_PORTAL,
        SourceSystem.SECURE_EMAIL,
        SourceSystem.MANUAL_ENTRY,
    )
    require_fresh: bool = True
    require_monotonic_version: bool = True
    abstain_on_conflict: bool = True
    manual_verification_on_equal_version_conflict: bool = True
    freshness_tolerance_minutes: int = Field(default=240, gt=0)

    def usable(self, freshness: FreshnessStatus, conflict: ConflictStatus) -> bool:
        if self.require_fresh and freshness is not FreshnessStatus.FRESH:
            return False
        return not (self.abstain_on_conflict and conflict is ConflictStatus.DETECTED)

    def rank(self, source: SourceSystem) -> int:
        try:
            return self.priority.index(source)
        except ValueError:
            return len(self.priority)
