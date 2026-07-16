"""Canonical dataset and baseline analysis fingerprints."""

import hashlib
import json
from typing import Any

from workflowtwin.analytics.config import AnalysisConfig
from workflowtwin.analytics.models import (
    AnalysisQuality,
    BaselineFinding,
    CohortMetrics,
)
from workflowtwin.domain.referrals.models import ReferralCase, ReferralEvent

ANALYSIS_VERSION = "1.0.0"
TRANSPORT_CONFIG_FIELDS = {
    "analysis_output",
    "report_output",
    "case_metrics_output",
    "source_dataset_fingerprint",
    "generation_run_id",
}


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dataset_fingerprint(cases: tuple[ReferralCase, ...], events: tuple[ReferralEvent, ...]) -> str:
    """Hash stable operational contracts in deterministic identity order."""
    payload = {
        "cases": [
            case.model_dump(mode="json") for case in sorted(cases, key=lambda item: item.id.hex)
        ],
        "events": [
            event.model_dump(mode="json") for event in sorted(events, key=lambda item: item.id.hex)
        ],
    }
    return _hash(payload)


def normalized_configuration(config: AnalysisConfig) -> dict[str, Any]:
    return config.model_dump(mode="json", exclude=TRANSPORT_CONFIG_FIELDS)


def analysis_fingerprint(
    *,
    source_dataset_fingerprint: str,
    config: AnalysisConfig,
    overall: CohortMetrics,
    cohorts: tuple[CohortMetrics, ...],
    findings: tuple[BaselineFinding, ...],
    quality: AnalysisQuality,
) -> str:
    """Hash stable analytical content, excluding wall time and benchmark labels."""
    return _hash(
        {
            "analysis_version": ANALYSIS_VERSION,
            "source_dataset_fingerprint": source_dataset_fingerprint,
            "configuration": normalized_configuration(config),
            "overall": overall.model_dump(mode="json"),
            "cohorts": [cohort.model_dump(mode="json") for cohort in cohorts],
            "findings": [finding.model_dump(mode="json") for finding in findings],
            "quality": quality.model_dump(mode="json"),
        }
    )
