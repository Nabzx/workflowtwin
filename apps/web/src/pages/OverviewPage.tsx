import { ArrowRight, Check, GitBranch, RotateCcw, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { useOverview, usePilotSummary } from "../api/queries";
import { FictionalNotice } from "../components/FictionalNotice";
import { MetricCard } from "../components/MetricCard";
import { PageError, PageLoading } from "../components/PageState";
import { PageHeader, SectionHeading } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatMetric, sentenceCase } from "../lib/format";

export function OverviewPage() {
  const overview = useOverview();
  const pilot = usePilotSummary();
  if (overview.isPending || pilot.isPending) return <PageLoading label="Preparing the Northstar evidence" />;
  if (overview.error) return <PageError error={overview.error} retry={() => void overview.refetch()} />;
  if (pilot.error) return <PageError error={pilot.error} retry={() => void pilot.refetch()} />;
  const data = overview.data;

  return (
    <div className="page-container overview-page">
      <PageHeader eyebrow="Process intelligence · Human-controlled automation" title="WorkflowTwin" description={data.proposition} actions={<Link className="button" to="/workflow">Explore workflow <ArrowRight /></Link>} />
      <FictionalNotice />

      <section className="overview-intro" aria-labelledby="northstar-title">
        <div><p className="eyebrow">Initial customer</p><h2 id="northstar-title">Northstar Clinics</h2><p>{data.workflow_summary}</p></div>
        <div className="pilot-signal"><StatusBadge tone="success">{sentenceCase(data.pilot_assessment)}</StatusBadge><p>Ready for a fictional demonstration. This is not production approval.</p></div>
      </section>

      <section aria-labelledby="headline-metrics"><SectionHeading eyebrow="Prepared evidence" title="What the system observed" /><div className="metric-grid metric-grid--six" id="headline-metrics">{data.metrics.map((metric) => <MetricCard key={metric.key} label={metric.label} value={formatMetric(metric.value, metric.unit)} unit={metric.unit} note={metric.note} tone={metric.key === "messages" ? "positive" : "default"} />)}</div></section>

      <section className="journey-section" aria-labelledby="journey-title">
        <SectionHeading eyebrow="Supported product path" title="Evidence before action" description="Each step preserves its inputs, assumptions, and authority boundary." />
        <ol className="journey" id="journey-title">{data.journey.map((step, index) => <li key={step}><span>{String(index + 1).padStart(2, "0")}</span><strong>{step}</strong>{index < data.journey.length - 1 && <ArrowRight aria-hidden="true" />}</li>)}</ol>
      </section>

      <section className="finding-grid" aria-label="Decision evidence">
        <article className="finding-panel"><GitBranch aria-hidden="true" /><p className="eyebrow">Largest intake finding</p><h2>Completeness creates repeat work</h2><p>{data.bottleneck}</p><Link to="/evidence">Inspect evidence <ArrowRight /></Link></article>
        <article className="finding-panel"><ShieldCheck aria-hidden="true" /><p className="eyebrow">Selected opportunity</p><h2>Validate before staff re-check</h2><p>{data.opportunity}</p><Link to="/opportunity">Trace the decision <ArrowRight /></Link></article>
        <article className="finding-panel finding-panel--caution"><RotateCcw aria-hidden="true" /><p className="eyebrow">Simulation result</p><h2>Benefit was not assumed</h2><p>{data.simulation_result}</p><Link to="/simulation">Compare scenarios <ArrowRight /></Link></article>
      </section>

      <section className="authority-strip" aria-labelledby="authority-title"><div><p className="eyebrow">System authority</p><h2 id="authority-title">Human control stays explicit</h2></div><ul>{data.authority.map((item) => <li key={item}><Check aria-hidden="true" />{item}</li>)}</ul><Link className="button button--secondary" to="/pilot">Open pilot <ArrowRight /></Link></section>
    </div>
  );
}

