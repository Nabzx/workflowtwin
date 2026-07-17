"""Canonical process-analysis fingerprinting."""

import hashlib
import json
from typing import Any

from workflowtwin.process_mining.config import ProcessMiningConfig
from workflowtwin.process_mining.models import (
    ConformanceSummary,
    ProcessBottleneckCandidate,
    ProcessComplexity,
    ProcessDiscoveryResult,
    ProcessGraphData,
    ProcessVariant,
    TransitionStatistics,
)

PROCESS_ANALYSIS_VERSION = "1.0.0"
TRANSPORT_FIELDS = {
    "analysis_output",
    "report_output",
    "graph_output",
    "case_output",
    "visualisation_directory",
    "overwrite",
    "source_dataset_fingerprint",
    "baseline_analysis_fingerprint",
    "generation_run_id",
}


def normalized_configuration(config: ProcessMiningConfig) -> dict[str, Any]:
    return config.model_dump(mode="json", exclude=TRANSPORT_FIELDS)


def process_fingerprint(
    *,
    source_dataset_fingerprint: str,
    baseline_analysis_fingerprint: str | None,
    config: ProcessMiningConfig,
    reference_versions: tuple[str, ...],
    transitions: tuple[TransitionStatistics, ...],
    variants: tuple[ProcessVariant, ...],
    complexity: ProcessComplexity,
    discovery: ProcessDiscoveryResult,
    strict: ConformanceSummary | None,
    governed: ConformanceSummary | None,
    candidates: tuple[ProcessBottleneckCandidate, ...],
    graph_data: ProcessGraphData,
) -> str:
    payload = {
        "process_analysis_version": PROCESS_ANALYSIS_VERSION,
        "source_dataset_fingerprint": source_dataset_fingerprint,
        "baseline_analysis_fingerprint": baseline_analysis_fingerprint,
        "configuration": normalized_configuration(config),
        "activity_mapping_version": config.activity_mapping_version,
        "reference_versions": reference_versions,
        "transitions": [item.model_dump(mode="json") for item in transitions],
        "variants": [item.model_dump(mode="json") for item in variants],
        "complexity": complexity.model_dump(mode="json"),
        "discovery": discovery.model_dump(mode="json"),
        "strict": strict.model_dump(mode="json") if strict else None,
        "governed": governed.model_dump(mode="json") if governed else None,
        "candidates": [item.model_dump(mode="json") for item in candidates],
        "graph_data": graph_data.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
