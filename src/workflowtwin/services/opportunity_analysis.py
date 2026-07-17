"""Artifact loaders for opportunity identification."""

from pathlib import Path

from workflowtwin.analytics.models import BaselineAnalysis
from workflowtwin.opportunities.config import OpportunityConfig
from workflowtwin.opportunities.models import OpportunityAnalysisInput
from workflowtwin.opportunities.research import load_research_pack
from workflowtwin.process_mining.models import ProcessMiningAnalysis
from workflowtwin.synthetic.artifacts import load_ground_truth, load_manifest


def load_opportunity_input(
    *,
    baseline_path: Path,
    process_path: Path,
    research_path: Path,
    manifest_path: Path | None,
    ground_truth_path: Path | None,
    config: OpportunityConfig,
) -> OpportunityAnalysisInput:
    baseline = BaselineAnalysis.model_validate_json(baseline_path.read_text(encoding="utf-8"))
    process = ProcessMiningAnalysis.model_validate_json(process_path.read_text(encoding="utf-8"))
    research = load_research_pack(
        research_path, expected_version=config.expected_research_pack_version
    )
    return OpportunityAnalysisInput(
        baseline=baseline,
        process=process,
        research=research,
        manifest=load_manifest(manifest_path) if manifest_path else None,
        ground_truth=load_ground_truth(ground_truth_path) if ground_truth_path else None,
    )
