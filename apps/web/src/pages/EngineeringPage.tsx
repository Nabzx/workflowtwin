import { ArrowRight, Box, CheckCircle2, ExternalLink, FileText, GitBranch, ShieldCheck } from "lucide-react";

import { useEngineering } from "../api/queries";
import { FictionalNotice } from "../components/FictionalNotice";
import { MetricCard } from "../components/MetricCard";
import { PageError, PageLoading } from "../components/PageState";
import { PageHeader, SectionHeading } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatMetric } from "../lib/format";

const REPOSITORY = "https://github.com/Nabzx/workflowtwin";

export function EngineeringPage() {
  const query = useEngineering();
  if (query.isPending) return <PageLoading label="Loading engineering evidence" />;
  if (query.error) return <PageError error={query.error} retry={() => void query.refetch()} />;
  const data = query.data;

  return (
    <div className="page-container engineering-page">
      <PageHeader eyebrow="Production-minded portfolio system" title="Engineering and architecture" description="A traceable Python analytics core, typed HTTP boundary, human-controlled pilot, and focused React product surface built around one supported path." actions={<a className="button button--secondary" href={REPOSITORY} target="_blank" rel="noreferrer">Source repository <ExternalLink /></a>} />
      <FictionalNotice compact />
      <section aria-labelledby="quality-title"><SectionHeading eyebrow="Quality evidence" title="Validated as a system, not a notebook" /><div className="metric-grid" id="quality-title">{data.quality.map((metric) => <MetricCard key={metric.key} label={metric.label} value={formatMetric(metric.value, metric.unit)} unit={metric.unit} tone={metric.key === "schema" ? "positive" : "default"} />)}</div></section>
      <section aria-labelledby="product-path"><SectionHeading eyebrow="Supported product path" title="Evidence lineage from events to rollback" description="Fingerprints link prepared artefacts; the interface never exposes raw hidden labels or local paths." /><div className="engineering-flow" id="product-path">{data.product_path.map((stage, index) => <div key={stage}><span>{String(index + 1).padStart(2, "0")}</span><strong>{stage}</strong>{index < data.product_path.length - 1 && <ArrowRight />}</div>)}</div></section>
      <section aria-labelledby="runtime-title"><SectionHeading eyebrow="Runtime architecture" title="Simple boundaries with replaceable infrastructure" /><div className="runtime-diagram" id="runtime-title"><div className="runtime-layer runtime-layer--client"><span>Experience</span><strong>React frontend</strong><small>TanStack Query · React Flow · Recharts</small></div><ArrowRight /><div className="runtime-layer"><span>Contract</span><strong>FastAPI</strong><small>Pydantic v1 responses · request telemetry</small></div><ArrowRight /><div className="runtime-services">{data.architecture.slice(2).map((stage) => <article key={stage.name}><Box /><div><span>{stage.name}</span><strong>{stage.responsibility}</strong><small>{stage.technology}</small></div></article>)}</div></div></section>
      <section className="authority-diagram" aria-labelledby="boundary-title"><div><p className="eyebrow">Pilot authority boundary</p><h2 id="boundary-title">Structured evidence enters. Only a reversible local task leaves.</h2><p>The recommendation, policy, human review, and draft are linked. Communication, workflow mutation, and clinical decisions terminate at explicit prohibited boundaries.</p></div><div className="authority-flow"><span>Structured intake</span><ArrowRight /><span>Detector</span><ArrowRight /><span>Policy</span><ArrowRight /><strong>Human reviewer</strong><ArrowRight /><span>Draft</span><ArrowRight /><span>Mock task</span></div><div className="prohibited-grid"><span>External communication <b>prohibited</b></span><span>Referral event mutation <b>prohibited</b></span><span>Clinical decisions <b>prohibited</b></span></div></section>
      <section aria-labelledby="evaluation-title"><SectionHeading eyebrow="Evaluation journey" title="Failed gates became design input" description="Historical detector versions stay concise here; only the supported product path appears in primary workflows." /><div className="evaluation-timeline" id="evaluation-title">{data.evaluation_journey.map((item, index) => <article key={item.step}><div>{index + 1}</div><span>{item.step}</span><h3>{item.title}</h3><p>{item.detail}</p><small><GitBranch />{item.provenance}</small></article>)}</div></section>
      <section className="engineering-details"><div><SectionHeading eyebrow="Technology" title="Purposeful stack" /><ul className="stack-list">{data.stack.map((item) => <li key={item}>{item}</li>)}</ul><h3>Release contracts</h3><dl className="version-list">{Object.entries(data.versions).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value}</dd></div>)}</dl></div><div><SectionHeading eyebrow="Architecture decisions" title="The constraints are deliberate" /><ul className="decision-list">{data.decisions.map((item) => <li key={item}><CheckCircle2 />{item}</li>)}</ul><div className="adr-links"><a href={`${REPOSITORY}/blob/main/docs/decisions/0012-frontend-productisation.md`} target="_blank" rel="noreferrer"><FileText />ADR 0012 · Frontend productisation <ExternalLink /></a><a href={`${REPOSITORY}/blob/main/docs/architecture/frontend-and-deployment.md`} target="_blank" rel="noreferrer"><FileText />Frontend and deployment architecture <ExternalLink /></a></div></div></section>
      <section className="limitations-band"><ShieldCheck /><div><SectionHeading eyebrow="Known limitations" title="Portfolio evidence, not production infrastructure" /><ul>{data.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div><StatusBadge tone="warning">Fictional demonstration</StatusBadge></section>
    </div>
  );
}

