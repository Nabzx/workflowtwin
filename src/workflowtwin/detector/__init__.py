"""The single supported WorkflowTwin completeness-review detector."""

from workflowtwin.detector.detector import CompletenessReviewDetector
from workflowtwin.detector.models import SUPPORTED_DETECTOR_NAME, SupportedDetectorMetadata

__all__ = [
    "SUPPORTED_DETECTOR_NAME",
    "CompletenessReviewDetector",
    "SupportedDetectorMetadata",
]
