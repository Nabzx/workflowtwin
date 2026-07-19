"""Deterministic, compact presentation repository for the Northstar demo."""

from typing import Literal, cast

from workflowtwin.api.demo_schemas import (
    ArchitectureStage,
    ConformanceSummary,
    DemoContext,
    EngineeringResponse,
    EvidenceLink,
    Finding,
    HeadlineMetric,
    MetricPoint,
    MetricSeries,
    MetricsResponse,
    OpportunityCandidate,
    OpportunityResponse,
    OverviewResponse,
    ProcessEdge,
    ProcessNode,
    ProcessVariant,
    QualityMeasure,
    ScenarioMetric,
    SimulationResponse,
    SimulationScenario,
    WorkflowResponse,
)

FICTIONAL_DECLARATION = (
    "Fictional Northstar Clinics administrative data; no clinical decisions, messages, "
    "or real workflow changes."
)
ANALYTICS_FINGERPRINT = "b9e211d57073d474e58820040ea864f201ef32f08b3cbfcf4a77fbfbdde16870"
PROCESS_FINGERPRINT = "eadb8843d6ca11010de7233df990dcccf41f0ce82cb2ec1839db40c83eb62497"
OPPORTUNITY_FINGERPRINT = "7def8c82e8b589e5"
SIMULATION_FINGERPRINT = "central-7f91f343"


def _context(fingerprint: str) -> DemoContext:
    return DemoContext(declaration=FICTIONAL_DECLARATION, artefact_fingerprint=fingerprint)


def _metric(
    key: str, label: str, value: float, unit: str, note: str | None = None
) -> HeadlineMetric:
    return HeadlineMetric(key=key, label=label, value=value, unit=unit, note=note)


def overview() -> OverviewResponse:
    return OverviewResponse(
        context=_context(ANALYTICS_FINGERPRINT),
        proposition=(
            "Discover where operational workflows break, identify evidence-backed automation "
            "opportunities, and test them safely before deployment."
        ),
        workflow_summary=(
            "Northstar Clinics receives referrals, validates administrative completeness, routes "
            "them to clinical teams, schedules appointments, and records outcomes."
        ),
        metrics=(
            _metric("cases", "Referrals analysed", 1000, "cases"),
            _metric("events", "Events analysed", 10085, "events"),
            _metric("variants", "Observed variants", 57, "variants"),
            _metric("precision", "Detector precision", 96.6, "%", "Recommendation-only evaluation"),
            _metric("surfaced", "Surfaced coverage", 10, "%"),
            _metric("messages", "Messages sent", 0, "messages"),
        ),
        journey=(
            "Operational event data",
            "Workflow reconstruction",
            "Bottleneck evidence",
            "Counterfactual simulation",
            "Human-approved pilot",
            "Audit and rollback",
        ),
        bottleneck="GP-practice referrals had 51.8% first-pass completeness versus 67.8% overall.",
        opportunity="Deterministic intake completeness review for GP-practice referrals.",
        simulation_result=(
            "The central scenario added 0.4 hours of net burden after review and fallback overhead."
        ),
        pilot_assessment="ready_for_fictional_pilot_demo",
        authority=(
            "Recommendation only",
            "Human approval required",
            "No message sent",
            "No referral status changed",
            "No clinical decisions",
            "Reversible fictional action",
        ),
    )


def workflow() -> WorkflowResponse:
    raw_nodes = (
        ("submitted", "Referral submitted", 1000, 0.0, "Intake", 0, 140),
        ("received", "Referral received", 1000, 0.0, "Intake", 190, 140),
        ("checked", "Completeness checked", 1378, 1.0, "Validation", 390, 140),
        ("requested", "Missing information requested", 353, 1.0, "Validation", 390, 300),
        ("returned", "Missing information received", 340, 0.0, "Validation", 610, 300),
        ("categorised", "Referral categorised", 931, 1.0, "Routing", 610, 140),
        ("assigned", "Clinical team assigned", 931, 1.0, "Routing", 820, 140),
        ("reassigned", "Clinical team reassigned", 138, 1.0, "Routing", 820, 300),
        ("scheduling", "Scheduling started", 1098, 1.0, "Scheduling", 1030, 140),
        ("failed", "Scheduling failed", 167, 1.0, "Scheduling", 1030, 300),
        ("booked", "Appointment booked", 837, 1.0, "Outcome", 1240, 140),
        ("complete", "Referral completed", 837, 1.0, "Outcome", 1450, 140),
    )
    nodes = tuple(
        ProcessNode(id=i, label=label, frequency=f, manual_work_rate=m, stage=s, x=x, y=y)
        for i, label, f, m, s, x, y in raw_nodes
    )
    raw_edges = (
        ("submitted", "received", 1000, 0.5, False, False, False),
        ("received", "checked", 1000, 17.8, False, False, True),
        ("checked", "requested", 353, 1.2, False, False, False),
        ("requested", "returned", 340, 47.8, False, False, True),
        ("returned", "checked", 340, 9.1, False, True, True),
        ("checked", "categorised", 931, 2.1, False, False, False),
        ("categorised", "assigned", 857, 22.3, True, False, True),
        ("assigned", "reassigned", 138, 26.3, True, True, True),
        ("reassigned", "assigned", 138, 3.1, True, True, False),
        ("assigned", "scheduling", 793, 3.0, True, False, False),
        ("scheduling", "failed", 167, 79.7, False, True, True),
        ("failed", "scheduling", 167, 77.2, False, True, True),
        ("scheduling", "booked", 837, 144.3, False, False, True),
        ("booked", "complete", 837, 1.0, False, False, False),
    )
    edges = tuple(
        ProcessEdge(
            id=f"{a}-{b}",
            source=a,
            target=b,
            frequency=f,
            median_delay_hours=d,
            handoff=h,
            rework=r,
            bottleneck=k,
        )
        for a, b, f, d, h, r, k in raw_edges
    )
    variants = (
        ProcessVariant(
            id="variant-428216a35a374ffe",
            case_count=363,
            activities=(
                "Referral submitted",
                "Referral received",
                "Completeness checked",
                "Referral categorised",
                "Clinical team assigned",
                "Scheduling started",
                "Appointment booked",
                "Referral completed",
            ),
            median_duration_hours=199.1,
            outcome="completed",
        ),
        ProcessVariant(
            id="variant-ca2f39460af8d5f1",
            case_count=155,
            activities=(
                "Referral submitted",
                "Referral received",
                "Completeness checked",
                "Missing information requested",
                "Missing information received",
                "Completeness checked",
                "Referral categorised",
                "Clinical team assigned",
                "Scheduling started",
                "Appointment booked",
                "Referral completed",
            ),
            median_duration_hours=260.1,
            outcome="completed",
        ),
        ProcessVariant(
            id="variant-ab90a08314c0ce92",
            case_count=58,
            activities=(
                "Referral submitted",
                "Referral received",
                "Completeness checked",
                "Referral categorised",
                "Clinical team assigned",
                "Clinical team reassigned",
                "Scheduling started",
                "Appointment booked",
                "Referral completed",
            ),
            median_duration_hours=236.1,
            outcome="completed",
        ),
    )
    return WorkflowResponse(
        context=_context(PROCESS_FINGERPRINT),
        nodes=nodes,
        edges=edges,
        variants=variants,
        strict=ConformanceSummary(
            model="northstar-strict-v1",
            fully_conforming_rate=0.363,
            average_fitness=0.922,
            interpretation="Flags real governed exceptions as deviations.",
        ),
        governed=ConformanceSummary(
            model="northstar-governed-v1",
            fully_conforming_rate=0.871,
            average_fitness=0.991,
            interpretation="Allows documented retries, rework, and terminal paths.",
        ),
        complexity=(
            _metric("activities", "Activities", 17, "count"),
            _metric("transitions", "Transitions", 23, "count"),
            _metric("loops", "Cases with loops", 40.8, "%"),
            _metric("handoffs", "Cases with handoffs", 93.1, "%"),
        ),
        filters={
            "service_lines": (
                "All",
                "Cardiology",
                "Dermatology",
                "Musculoskeletal",
                "Neurology",
                "Respiratory",
            ),
            "referral_sources": (
                "All",
                "Community clinic",
                "GP practice",
                "Healthcare professional",
                "Internal transfer",
            ),
        },
    )


def _series(
    key: str,
    label: str,
    unit: str,
    status: Literal["calculated", "estimated"],
    denominator: int,
    values: tuple[tuple[str, int, float], ...],
) -> MetricSeries:
    return MetricSeries(
        key=key,
        label=label,
        unit=unit,
        status=status,
        denominator=denominator,
        values=tuple(MetricPoint(cohort=c, case_count=n, value=v) for c, n, v in values),
    )


def metrics() -> MetricsResponse:
    sources = (
        _series(
            "completeness",
            "First-pass completeness",
            "%",
            "estimated",
            944,
            (
                ("Community clinic", 231, 83.2),
                ("GP practice", 422, 51.8),
                ("Healthcare professional", 235, 78.6),
                ("Internal transfer", 112, 67.0),
            ),
        ),
        _series(
            "manual",
            "Manual touches",
            "per case",
            "calculated",
            1000,
            (
                ("Community clinic", 231, 6.52),
                ("GP practice", 422, 7.23),
                ("Healthcare professional", 235, 6.61),
                ("Internal transfer", 112, 7.12),
            ),
        ),
        _series(
            "rework",
            "Rework events",
            "per case",
            "estimated",
            1000,
            (
                ("Community clinic", 231, 0.55),
                ("GP practice", 422, 1.00),
                ("Healthcare professional", 235, 0.61),
                ("Internal transfer", 112, 0.93),
            ),
        ),
    )
    services = (
        _series(
            "assignment",
            "Assignment wait",
            "business hours",
            "estimated",
            931,
            (
                ("Cardiology", 194, 7.8),
                ("Dermatology", 176, 8.9),
                ("Musculoskeletal", 237, 6.7),
                ("Neurology", 222, 20.7),
                ("Respiratory", 171, 7.4),
            ),
        ),
        _series(
            "scheduling",
            "Failed scheduling attempts",
            "per case",
            "calculated",
            1000,
            (
                ("Cardiology", 194, 0.13),
                ("Dermatology", 176, 0.14),
                ("Musculoskeletal", 237, 0.09),
                ("Neurology", 222, 0.15),
                ("Respiratory", 171, 0.39),
            ),
        ),
        _series(
            "handoffs",
            "Handoffs",
            "per case",
            "estimated",
            1000,
            (
                ("Cardiology", 194, 2.02),
                ("Dermatology", 176, 2.36),
                ("Musculoskeletal", 237, 1.96),
                ("Neurology", 222, 2.12),
                ("Respiratory", 171, 2.01),
            ),
        ),
    )
    return MetricsResponse(
        context=_context(ANALYTICS_FINGERPRINT),
        overall=(
            _metric("duration", "Mean case duration", 226.3, "hours"),
            _metric("waiting", "Mean waiting time", 15.9, "business hours", "Estimated"),
            _metric("touches", "Mean manual touches", 6.91, "per case"),
            _metric("rework", "Mean rework", 0.81, "per case", "Mixed calculated/estimated"),
            _metric("stuck", "Stuck referrals", 42, "cases"),
        ),
        referral_sources=sources,
        service_lines=services,
        quality=(
            QualityMeasure(label="Metric availability", value=98.1, unit="%", status="calculated"),
            QualityMeasure(label="Cases analysed", value=1000, unit="cases", status="calculated"),
            QualityMeasure(label="Delayed ingestion", value=5.6, unit="%", status="calculated"),
            QualityMeasure(
                label="Out-of-order ingestion", value=3.3, unit="%", status="calculated"
            ),
        ),
        findings=(
            Finding(
                title="Lower intake completeness",
                cohort="GP practice",
                observed="51.8% first-pass complete",
                comparison="67.8% overall",
                materiality="material",
            ),
            Finding(
                title="Longer assignment wait",
                cohort="Neurology",
                observed="20.7 business hours",
                comparison="9.8 hours overall",
                materiality="strong",
            ),
            Finding(
                title="Scheduling retries",
                cohort="Respiratory",
                observed="0.39 attempts per case",
                comparison="0.17 overall",
                materiality="strong",
            ),
        ),
        exclusions=(
            "Unsupported schema timelines are excluded.",
            "Missing boundaries are unavailable, not zero.",
            "Open cases are excluded from closed-duration summaries.",
            "Clinical, protected-attribute, and individual staff analysis is out of scope.",
        ),
    )


def _candidate(
    id_: str,
    title: str,
    cohort: str,
    cases: int,
    priority: float,
    value: float,
    readiness: float,
    risk: float,
    confidence: float,
    result: str,
) -> OpportunityCandidate:
    return OpportunityCandidate(
        id=id_,
        title=title,
        cohort=cohort,
        affected_cases=cases,
        priority=priority,
        value=value,
        readiness=readiness,
        risk=risk,
        confidence=confidence,
        result=result,
    )


def opportunity() -> OpportunityResponse:
    candidates = (
        _candidate(
            "opportunity-7def8c82e8b589e5",
            "Intake completeness validation",
            "GP practice",
            191,
            62.7,
            76.8,
            78.8,
            40,
            65,
            "Controlled prototype",
        ),
        _candidate(
            "opportunity-ea3ffae90d868f6f",
            "Handoff reduction",
            "Dermatology",
            64,
            56.5,
            57.7,
            75.6,
            58,
            81,
            "Further discovery",
        ),
        _candidate(
            "opportunity-ac1aa4eaf5222ae9",
            "Scheduling coordination",
            "Respiratory",
            67,
            51.7,
            58.4,
            76.3,
            75,
            67,
            "Further discovery",
        ),
        _candidate(
            "opportunity-021a3047cd3559f4",
            "Ingestion monitoring",
            "All sources",
            56,
            46.2,
            22.6,
            83.8,
            18,
            72,
            "Further discovery",
        ),
        _candidate(
            "opportunity-a462bc4a5426e107",
            "Stuck-case monitoring",
            "All cases",
            42,
            45.5,
            21.3,
            83.8,
            22,
            73,
            "Further discovery",
        ),
        _candidate(
            "opportunity-8bc8f53be8ee6d78",
            "Assignment routing assistance",
            "Neurology",
            209,
            43.5,
            52.9,
            75,
            72,
            43,
            "Further discovery",
        ),
    )
    chain = (
        EvidenceLink(
            step="Baseline finding",
            title="Lower completeness",
            detail="51.8% of eligible GP-practice referrals were complete first pass.",
            provenance="baseline finding gp-practice-lower-first-pass-completeness",
        ),
        EvidenceLink(
            step="Process evidence",
            title="Repeated checks",
            detail="Completeness was checked 1,378 times across 1,000 referrals.",
            provenance="process graph / activity frequency",
        ),
        EvidenceLink(
            step="User research",
            title="Repeated administrative verification",
            detail="Fictional interviews described repeated checks and unclear ownership.",
            provenance="northstar-research-v1",
        ),
        EvidenceLink(
            step="Eligibility",
            title="Bounded administrative scope",
            detail="All ten safety and measurability gates passed.",
            provenance="opportunity eligibility gates",
        ),
        EvidenceLink(
            step="Risk controls",
            title="Human review and rollback",
            detail="Recommendations cannot communicate or change referral state.",
            provenance="northstar pilot policy v1",
        ),
        EvidenceLink(
            step="Portfolio result",
            title="Selected for controlled prototyping",
            detail="Highest evidence-adjusted priority in the prepared portfolio.",
            provenance="opportunity portfolio v1",
        ),
    )
    return OpportunityResponse(
        context=_context(OPPORTUNITY_FINGERPRINT),
        selected=candidates[0],
        problem_statement=(
            "The referral-source cohort contains lower completeness and repeated "
            "administrative information work."
        ),
        workflow_stage="Intake completeness",
        burden=(
            _metric("affected", "Affected referrals", 191, "cases"),
            _metric("touches", "Associated manual touches", 1380, "touches"),
            _metric(
                "hours", "Manual-touch proxy", 115.0, "hours", "Upper bound, not removable work"
            ),
            _metric("cost", "Associated cost proxy", 2761, "GBP", "Not forecast savings"),
        ),
        evidence_chain=chain,
        controls=(
            "Administrative structured fields only",
            "Named human reviewer",
            "Recommendation-only detector",
            "Automatic stop on policy or audit failure",
            "Manual fallback",
            "Rollback after fictional commit",
        ),
        success_metrics=(
            "Precision and recall",
            "Review minutes per 100 referrals",
            "Recommendation coverage",
            "Policy compliance",
            "Duplicate action rate",
            "Rollback success",
        ),
        evidence_gaps=(
            "Real reviewer capacity has not been observed.",
            "No realised time or cost impact exists.",
            "A live customer data-quality assessment would be required.",
        ),
        candidates=candidates,
    )


def simulation() -> SimulationResponse:
    rows = (
        ("conservative", 28, 9.92, 43, 17, -6.58, "Do not act"),
        ("central", 67, 10.37, 23, 11, -0.37, "Additional controls required"),
        ("optimistic", 125, 13.83, 12, 2, 6.08, "Shadow only"),
        ("adverse", 28, 13.33, 89, 61, -10.0, "Do not act"),
    )
    scenarios = tuple(
        SimulationScenario(
            id=cast(Literal["conservative", "central", "optimistic", "adverse"], id_),
            affected_cases=affected,
            review_overhead_hours=overhead,
            fallbacks=fallbacks,
            failures=failures,
            net_burden_hours=net,
            decision=decision,
            metrics=(
                ScenarioMetric(
                    key="manual",
                    label="Manual touches",
                    baseline=7.23,
                    simulated={
                        "conservative": 7.11,
                        "central": 6.94,
                        "optimistic": 6.71,
                        "adverse": 7.18,
                    }[id_],
                    unit="per case",
                ),
                ScenarioMetric(
                    key="check",
                    label="Completeness-check delay",
                    baseline=18.36,
                    simulated={
                        "conservative": 17.2,
                        "central": 16.0,
                        "optimistic": 14.1,
                        "adverse": 18.0,
                    }[id_],
                    unit="hours",
                ),
                ScenarioMetric(
                    key="duration",
                    label="Case duration",
                    baseline=229.83,
                    simulated={
                        "conservative": 229.1,
                        "central": 227.02,
                        "optimistic": 224.4,
                        "adverse": 230.2,
                    }[id_],
                    unit="hours",
                ),
                ScenarioMetric(
                    key="waiting",
                    label="Waiting time",
                    baseline=17.97,
                    simulated={
                        "conservative": 17.8,
                        "central": 17.23,
                        "optimistic": 16.5,
                        "adverse": 18.1,
                    }[id_],
                    unit="business hours",
                ),
            ),
        )
        for id_, affected, overhead, fallbacks, failures, net, decision in rows
    )
    return SimulationResponse(
        context=_context(SIMULATION_FINGERPRINT),
        scenarios=scenarios,
        selected_scenario="central",
        finding=(
            "The central scenario reduced workflow touches but review, fallback, and recovery "
            "overhead produced 0.4 additional burden hours."
        ),
        caveats=(
            "Counterfactual results are simulated, not realised impact.",
            "The full benchmark did not justify workflow action.",
            "Human-review overhead is included.",
            "Adverse results are retained.",
            "Shadow evaluation was required before the fictional pilot.",
        ),
    )


def engineering() -> EngineeringResponse:
    return EngineeringResponse(
        context=_context("engineering-v1"),
        product_path=(
            "Synthetic event data",
            "Baseline metrics",
            "Process mining",
            "Opportunity analysis",
            "Simulation",
            "Shadow detector",
            "Human review",
            "Fictional pilot action",
            "Audit and gates",
        ),
        architecture=(
            ArchitectureStage(
                name="Web client",
                responsibility="Evidence exploration and human review",
                technology="React, TypeScript, Vite",
            ),
            ArchitectureStage(
                name="API",
                responsibility="Typed presentation and pilot contracts",
                technology="FastAPI, Pydantic",
            ),
            ArchitectureStage(
                name="Analytics",
                responsibility="Metrics, process, opportunity, simulation",
                technology="Python, PM4Py",
            ),
            ArchitectureStage(
                name="Pilot",
                responsibility="Policy, draft, mock task, rollback",
                technology="Deterministic domain services",
            ),
            ArchitectureStage(
                name="Persistence",
                responsibility="Operational records where configured",
                technology="SQLAlchemy, PostgreSQL, Alembic",
            ),
        ),
        stack=(
            "Python 3.12",
            "FastAPI",
            "Pydantic",
            "PostgreSQL",
            "SQLAlchemy",
            "Alembic",
            "PM4Py",
            "React",
            "TypeScript",
            "TanStack Query",
            "React Flow",
            "Recharts",
            "Docker",
        ),
        quality=(
            _metric("tests", "Backend tests", 199, "local tests"),
            _metric("postgres", "PostgreSQL tests", 16, "tests"),
            _metric("coverage", "Backend coverage", 91.7, "%"),
            _metric("schema", "Schema drift", 0, "differences"),
        ),
        evaluation_journey=(
            EvidenceLink(
                step="Strict v1",
                title="Useful failure",
                detail="Contract mismatch exposed missing source semantics.",
                provenance="evaluation history",
            ),
            EvidenceLink(
                step="Strict v2",
                title="Capacity learning",
                detail="Reviewer burden blocked promotion.",
                provenance="capacity holdout",
            ),
            EvidenceLink(
                step="Strict v3",
                title="Supported source contract",
                detail="Independent validation established a bounded detector path.",
                provenance="source contract v2",
            ),
            EvidenceLink(
                step="Pilot",
                title="Human-controlled product",
                detail="Three reviews, two commits, one rollback, zero prohibited actions.",
                provenance="pilot run v1",
            ),
        ),
        decisions=(
            "Prepared artefacts make the public contract compact and deterministic.",
            "No LLM: structured rules are safer and more explainable for this use case.",
            "One supported detector path is shown; failed experiments remain evidence.",
            "Public mutations are fictional, bounded, ephemeral, and reversible.",
            "Observability is local and dependency-free.",
        ),
        limitations=(
            "All organisations, people, records, and results are fictional.",
            "Simulation is not evidence of realised benefit.",
            "Shared demo state is not production multi-user infrastructure.",
            "The prepared process graph is filtered for presentation.",
            "No authentication or external integration is included.",
        ),
        versions={
            "application": "1.0.0",
            "api": "v1",
            "detector": "completeness-review-detector-v1",
            "source_contract": "northstar-source-contract-v2",
            "requirements": "northstar-requirements-v2",
            "presentation_schema": "demo-presentation-v1",
        },
    )
