"""Pre-registered strict-v3 runtime configuration and immutable fingerprints."""

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, model_validator

from workflowtwin.domain.referrals.enums import SourceSystem
from workflowtwin.shadow.fingerprint import shadow_fingerprint

SOURCE_CONTRACT_V2_FINGERPRINT = "2e1518711bb463056f004194642580e98b454f9e717f6f46a11ea230cd463cc8"
REQUIREMENTS_V2_FINGERPRINT = "45055eaf3cbdc0a65cab7d81c39dac103a75c16581ea131c946944897590d6d5"
STANDARD_CAPACITY_FINGERPRINT = "19557943cd7df72295a5db0dc114a7132d8942b0a06d35449555a6466d032d04"


class StrictV3Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detector_version: str = "strict-v3"
    detector_rule_version: str = "strict-v3-rules-1"
    policy_version: str = "strict-v3-policy-1"
    source_contract_version: str = "northstar-source-contract-v2"
    source_contract_fingerprint: str = SOURCE_CONTRACT_V2_FINGERPRINT
    requirements_contract_version: str = "northstar-requirements-v2"
    requirements_contract_fingerprint: str = REQUIREMENTS_V2_FINGERPRINT
    capacity_policy_version: str = "review-capacity-v1"
    capacity_fingerprint: str = STANDARD_CAPACITY_FINGERPRINT
    supported_form_versions: tuple[str, ...] = ("NS-INTAKE-1", "NS-INTAKE-2")
    supported_source_systems: tuple[SourceSystem, ...] = (
        SourceSystem.REFERRAL_PORTAL,
        SourceSystem.SECURE_EMAIL,
        SourceSystem.MANUAL_ENTRY,
    )
    stable_absence_confirmation: timedelta = timedelta(0)
    verification_required_confirmation: timedelta = timedelta(0)
    pending_update_confirmation: timedelta = timedelta(minutes=180)
    recommendation_expiry: timedelta = timedelta(hours=8)
    suppress_existing_source_warning: bool = True
    suppress_after_manual_review_start: bool = True
    abstain_on_stale: bool = True
    abstain_on_conflict: bool = True
    abstain_on_unknown: bool = True
    abstain_on_contract_mismatch: bool = True
    recommendation_only: bool = True
    rule_lock_version: str = "2026-07-18.v3.1"

    @model_validator(mode="after")
    def preserve_authority_and_identity(self) -> "StrictV3Config":
        if self.detector_version != "strict-v3":
            raise ValueError("StrictV3Config must retain strict-v3 identity")
        if not self.recommendation_only:
            raise ValueError("strict-v3 cannot acquire workflow authority")
        return self

    @property
    def detector_fingerprint(self) -> str:
        return shadow_fingerprint(self.model_dump(mode="json"))

    @property
    def policy_fingerprint(self) -> str:
        return shadow_fingerprint(
            {
                "policy_version": self.policy_version,
                "recommendation_only": self.recommendation_only,
                "suppress_existing_source_warning": self.suppress_existing_source_warning,
                "suppress_after_manual_review_start": self.suppress_after_manual_review_start,
                "abstain_on_stale": self.abstain_on_stale,
                "abstain_on_conflict": self.abstain_on_conflict,
                "abstain_on_unknown": self.abstain_on_unknown,
                "abstain_on_contract_mismatch": self.abstain_on_contract_mismatch,
            }
        )
