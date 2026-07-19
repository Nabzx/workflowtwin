"""Stable presentation contracts for the fictional recruiter demo."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DemoModel(BaseModel):
    """Forbid accidental response-shape drift."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DemoContext(DemoModel):
    fictional_data: Literal[True] = True
    organisation: str = "Northstar Clinics"
    declaration: str
    artefact_fingerprint: str


class HeadlineMetric(DemoModel):
    key: str
    label: str
    value: float
    unit: str
    note: str | None = None


class OverviewResponse(DemoModel):
    context: DemoContext
    proposition: str
    workflow_summary: str
    metrics: tuple[HeadlineMetric, ...]
    journey: tuple[str, ...]
    bottleneck: str
    opportunity: str
    simulation_result: str
    pilot_assessment: str
    authority: tuple[str, ...]


class ProcessNode(DemoModel):
    id: str
    label: str
    frequency: int
    manual_work_rate: float
    stage: str
    x: int
    y: int


class ProcessEdge(DemoModel):
    id: str
    source: str
    target: str
    frequency: int
    median_delay_hours: float
    handoff: bool = False
    rework: bool = False
    bottleneck: bool = False


class ProcessVariant(DemoModel):
    id: str
    case_count: int
    activities: tuple[str, ...]
    median_duration_hours: float
    outcome: str


class ConformanceSummary(DemoModel):
    model: str
    fully_conforming_rate: float
    average_fitness: float
    interpretation: str


class WorkflowResponse(DemoModel):
    context: DemoContext
    nodes: tuple[ProcessNode, ...]
    edges: tuple[ProcessEdge, ...]
    variants: tuple[ProcessVariant, ...]
    strict: ConformanceSummary
    governed: ConformanceSummary
    complexity: tuple[HeadlineMetric, ...]
    filters: dict[str, tuple[str, ...]]


class MetricPoint(DemoModel):
    cohort: str
    case_count: int
    value: float


class MetricSeries(DemoModel):
    key: str
    label: str
    unit: str
    status: Literal["calculated", "estimated"]
    denominator: int
    values: tuple[MetricPoint, ...]


class QualityMeasure(DemoModel):
    label: str
    value: float
    unit: str
    status: str


class Finding(DemoModel):
    title: str
    cohort: str
    observed: str
    comparison: str
    materiality: str


class MetricsResponse(DemoModel):
    context: DemoContext
    overall: tuple[HeadlineMetric, ...]
    referral_sources: tuple[MetricSeries, ...]
    service_lines: tuple[MetricSeries, ...]
    quality: tuple[QualityMeasure, ...]
    findings: tuple[Finding, ...]
    exclusions: tuple[str, ...]


class OpportunityCandidate(DemoModel):
    id: str
    title: str
    cohort: str
    affected_cases: int
    priority: float
    value: float
    readiness: float
    risk: float
    confidence: float
    result: str


class EvidenceLink(DemoModel):
    step: str
    title: str
    detail: str
    provenance: str


class OpportunityResponse(DemoModel):
    context: DemoContext
    selected: OpportunityCandidate
    problem_statement: str
    workflow_stage: str
    burden: tuple[HeadlineMetric, ...]
    evidence_chain: tuple[EvidenceLink, ...]
    controls: tuple[str, ...]
    success_metrics: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    candidates: tuple[OpportunityCandidate, ...]


class ScenarioMetric(DemoModel):
    key: str
    label: str
    baseline: float | None
    simulated: float
    unit: str


class SimulationScenario(DemoModel):
    id: Literal["conservative", "central", "optimistic", "adverse"]
    affected_cases: int
    review_overhead_hours: float
    fallbacks: int
    failures: int
    net_burden_hours: float
    decision: str
    metrics: tuple[ScenarioMetric, ...]


class SimulationResponse(DemoModel):
    context: DemoContext
    scenarios: tuple[SimulationScenario, ...]
    selected_scenario: str
    finding: str
    caveats: tuple[str, ...]


class ArchitectureStage(DemoModel):
    name: str
    responsibility: str
    technology: str


class EngineeringResponse(DemoModel):
    context: DemoContext
    product_path: tuple[str, ...]
    architecture: tuple[ArchitectureStage, ...]
    stack: tuple[str, ...]
    quality: tuple[HeadlineMetric, ...]
    evaluation_journey: tuple[EvidenceLink, ...]
    decisions: tuple[str, ...]
    limitations: tuple[str, ...]
    versions: dict[str, str]


class SystemStatusResponse(DemoModel):
    api_version: str
    application_version: str
    status: Literal["ready", "degraded"]
    demo_ready: bool
    artefact_available: bool
    detector_version: str
    source_contract_version: str
    database_status: str
    fictional_data_mode: Literal[True] = True
    uptime_seconds: float = Field(ge=0)
    pilot_artefact_fingerprint: str


class DemoResetRequest(DemoModel):
    token: str | None = Field(default=None, max_length=256)


class DemoResetResponse(DemoModel):
    status: Literal["reset"] = "reset"
    run_id: str
    declaration: str
