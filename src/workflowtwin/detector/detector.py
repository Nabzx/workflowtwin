"""Product adapter over the unchanged strict-v3 detector implementation."""

from workflowtwin.detector.models import SupportedDetectorMetadata, supported_detector_metadata
from workflowtwin.shadow_v3.config import StrictV3Config
from workflowtwin.shadow_v3.detector import StrictV3Detector
from workflowtwin.shadow_v3.models import V3Run
from workflowtwin.source_contracts.models import IncomingReferralSnapshotV2
from workflowtwin.source_contracts.requirements import AdministrativeRequirementsContract


class CompletenessReviewDetector:
    """Expose one supported identity while retaining strict-v3 audit lineage."""

    def __init__(
        self,
        requirements: AdministrativeRequirementsContract,
        config: StrictV3Config | None = None,
    ) -> None:
        self._config = config or StrictV3Config()
        self._runtime = StrictV3Detector(self._config, requirements)
        self.metadata = supported_detector_metadata(self._config)

    def run(
        self,
        snapshots: tuple[IncomingReferralSnapshotV2, ...],
        *,
        run_id: str,
    ) -> V3Run:
        return self._runtime.run(snapshots, run_id=run_id)

    @property
    def lineage(self) -> SupportedDetectorMetadata:
        return self.metadata
