import { ArrowDown, CheckCircle2, Link2, ShieldAlert } from "lucide-react";

import { useOpportunity } from "../api/queries";
import { FictionalNotice } from "../components/FictionalNotice";
import { MetricCard } from "../components/MetricCard";
import { PageError, PageLoading } from "../components/PageState";
import { PageHeader, SectionHeading } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatMetric, shortId } from "../lib/format";

export function OpportunityPage() {
  const query = useOpportunity();
  if (query.isPending) return <PageLoading label="Tracing the opportunity evidence" />;
  if (query.error) return <PageError error={query.error} retry={() => void query.refetch()} />;
  const data = query.data;

  return (
    <div className="page-container opportunity-page">
      <PageHeader eyebrow="Evidence-backed opportunity · Intake completeness" title={data.selected.title} description={data.problem_statement} actions={<StatusBadge tone="success">Only selected controlled prototype</StatusBadge>} />
      <FictionalNotice compact />
      <section className="opportunity-score" aria-label="Opportunity score"><div><p className="eyebrow">Affected cohort</p><h2>{data.selected.cohort}</h2><p>{data.workflow_stage} · {data.selected.affected_cases} affected fictional referrals</p></div><Score label="Priority" value={data.selected.priority} /><Score label="Value" value={data.selected.value} /><Score label="Readiness" value={data.selected.readiness} /><Score label="Risk" value={data.selected.risk} inverse /><Score label="Confidence" value={data.selected.confidence} /></section>
      <section aria-labelledby="burden-title"><SectionHeading eyebrow="Observed burden" title="Association, not forecast impact" description="The current burden defines an upper bound. It is not assumed removable and is not a savings claim." /><div className="metric-grid" id="burden-title">{data.burden.map((metric) => <MetricCard key={metric.key} label={metric.label} value={formatMetric(metric.value, metric.unit)} unit={metric.unit} note={metric.note} />)}</div></section>
      <section aria-labelledby="chain-title"><SectionHeading eyebrow="Evidence chain" title="Every recommendation remains traceable" description="Quantitative findings, fictional research, eligibility, and controls stay linked to their source artefacts." /><ol className="evidence-chain" id="chain-title">{data.evidence_chain.map((link, index) => <li key={link.step}><div className="evidence-chain__index">{String(index + 1).padStart(2, "0")}</div><div><span>{link.step}</span><h3>{link.title}</h3><p>{link.detail}</p><small><Link2 aria-hidden="true" />{link.provenance}</small></div>{index < data.evidence_chain.length - 1 && <ArrowDown className="evidence-chain__arrow" aria-hidden="true" />}</li>)}</ol></section>
      <section className="control-evidence"><div><SectionHeading eyebrow="Required controls" title="Eligible only inside a narrow authority boundary" /><ul className="check-list">{data.controls.map((item) => <li key={item}><CheckCircle2 />{item}</li>)}</ul></div><div><SectionHeading eyebrow="Evidence gaps" title="What this analysis cannot claim" /><ul className="gap-list">{data.evidence_gaps.map((item) => <li key={item}><ShieldAlert />{item}</li>)}</ul><h3>Future success measures</h3><ul className="inline-list">{data.success_metrics.map((item) => <li key={item}>{item}</li>)}</ul></div></section>
      <section aria-labelledby="portfolio-title"><SectionHeading eyebrow="Opportunity portfolio" title="Why other candidates were not selected" /><div className="data-table-wrap"><table className="data-table" id="portfolio-title"><thead><tr><th>Candidate</th><th>Cohort</th><th>Cases</th><th>Priority</th><th>Readiness</th><th>Risk</th><th>Result</th></tr></thead><tbody>{data.candidates.map((candidate) => <tr key={candidate.id} className={candidate.id === data.selected.id ? "is-selected" : ""}><td><strong>{candidate.title}</strong><small>{shortId(candidate.id)}</small></td><td>{candidate.cohort}</td><td>{candidate.affected_cases}</td><td>{candidate.priority.toFixed(1)}</td><td>{candidate.readiness.toFixed(1)}</td><td>{candidate.risk.toFixed(1)}</td><td><StatusBadge tone={candidate.result === "Controlled prototype" ? "success" : "neutral"}>{candidate.result}</StatusBadge></td></tr>)}</tbody></table></div></section>
    </div>
  );
}

function Score({ label, value, inverse = false }: { label: string; value: number; inverse?: boolean }) {
  const tone = inverse ? value <= 40 : value >= 60;
  return <div className="score"><span>{label}</span><strong>{value.toFixed(1)}</strong><div aria-label={`${label}: ${value.toFixed(1)} out of 100`}><i style={{ width: `${value}%` }} className={tone ? "score__good" : "score__caution"} /></div></div>;
}

