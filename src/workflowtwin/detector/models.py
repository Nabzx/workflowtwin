"""Supported detector identity and lineage contracts."""

from pydantic import BaseModel, ConfigDict

from workflowtwin.core.fingerprint import fingerprint
from workflowtwin.shadow_v3.config import StrictV3Config

SUPPORTED_DETECTOR_NAME = "completeness-review-detector-v1"
INTERNAL_LINEAGE = "strict-v3"


class SupportedDetectorMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_name: str
    derived_from: str
    original_detector_fingerprint: str
    supported_detector_fingerprint: str
    source_contract_version: str
    source_contract_fingerprint: str
    requirements_contract_version: str
    requirements_contract_fingerprint: str
    recommendation_only: bool


def supported_detector_metadata(
    config: StrictV3Config | None = None,
) -> SupportedDetectorMetadata:
    runtime = config or StrictV3Config()
    identity = {
        "product_name": SUPPORTED_DETECTOR_NAME,
        "derived_from": INTERNAL_LINEAGE,
        "original_detector_fingerprint": runtime.detector_fingerprint,
        "source_contract_fingerprint": runtime.source_contract_fingerprint,
        "requirements_contract_fingerprint": runtime.requirements_contract_fingerprint,
    }
    return SupportedDetectorMetadata(
        product_name=SUPPORTED_DETECTOR_NAME,
        derived_from=INTERNAL_LINEAGE,
        original_detector_fingerprint=runtime.detector_fingerprint,
        supported_detector_fingerprint=fingerprint(identity),
        source_contract_version=runtime.source_contract_version,
        source_contract_fingerprint=runtime.source_contract_fingerprint,
        requirements_contract_version=runtime.requirements_contract_version,
        requirements_contract_fingerprint=runtime.requirements_contract_fingerprint,
        recommendation_only=True,
    )
