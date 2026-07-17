"""Canonical opportunity-analysis fingerprinting."""

import hashlib
import json
from typing import Any

from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import (
    EvidenceReference,
    OpportunityBenchmarkEvaluation,
    OpportunityCandidate,
    PortfolioSummary,
    ResearchContradiction,
)

OPPORTUNITY_ANALYSIS_VERSION = "1.0.0"
TRANSPORT_FIELDS = {
    "analysis_output",
    "report_output",
    "portfolio_output",
    "evidence_output",
    "overwrite",
}


def normalized_configuration(config: OpportunityConfig) -> dict[str, Any]:
    return config.model_dump(mode="json", exclude=TRANSPORT_FIELDS)


def opportunity_fingerprint(
    *,
    source_dataset_fingerprint: str,
    baseline_fingerprint: str,
    process_fingerprint: str,
    research_fingerprint: str,
    archetype_version: str,
    rule_version: str,
    scoring_version: str,
    config: OpportunityConfig,
    evidence: tuple[EvidenceReference, ...],
    contradictions: tuple[ResearchContradiction, ...],
    candidates: tuple[OpportunityCandidate, ...],
    portfolio: PortfolioSummary,
    benchmark: OpportunityBenchmarkEvaluation,
) -> str:
    payload = {
        "analysis_version": OPPORTUNITY_ANALYSIS_VERSION,
        "source_dataset_fingerprint": source_dataset_fingerprint,
        "baseline_fingerprint": baseline_fingerprint,
        "process_fingerprint": process_fingerprint,
        "research_fingerprint": research_fingerprint,
        "archetype_version": archetype_version,
        "rule_version": rule_version,
        "scoring_version": scoring_version,
        "configuration": normalized_configuration(config),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "contradictions": [item.model_dump(mode="json") for item in contradictions],
        "candidates": [item.model_dump(mode="json") for item in candidates],
        "portfolio": portfolio.model_dump(mode="json"),
        "benchmark": benchmark.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
