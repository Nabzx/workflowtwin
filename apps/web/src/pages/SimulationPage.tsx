import { AlertTriangle, ArrowRight, FlaskConical } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useSimulation } from "../api/queries";
import { FictionalNotice } from "../components/FictionalNotice";
import { MetricCard } from "../components/MetricCard";
import { PageError, PageLoading } from "../components/PageState";
import { PageHeader, SectionHeading } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";

export function SimulationPage() {
  const query = useSimulation();
  const [scenarioId, setScenarioId] = useState("central");
  if (query.isPending) return <PageLoading label="Loading counterfactual scenarios" />;
  if (query.error) return <PageError error={query.error} retry={() => void query.refetch()} />;
  const data = query.data;
  const scenario = data.scenarios.find((item) => item.id === scenarioId) ?? data.scenarios[0];

  return (
    <div className="page-container simulation-page">
      <PageHeader eyebrow="Counterfactual analysis · Not realised impact" title="Intervention simulation" description="Compare conservative, central, optimistic, and adverse assumptions without hiding review overhead or failure burden." />
      <FictionalNotice compact />
      <section className="scenario-tabs" aria-label="Simulation scenario">{data.scenarios.map((item) => <button key={item.id} className={item.id === scenario.id ? "is-active" : ""} onClick={() => setScenarioId(item.id)}><span>{item.id}</span><strong>{item.net_burden_hours > 0 ? "+" : ""}{item.net_burden_hours.toFixed(2)}h</strong><small>net burden difference</small></button>)}</section>
      <section className="simulation-finding"><FlaskConical aria-hidden="true" /><div><p className="eyebrow">Central finding</p><h2>Workflow reduction did not equal net benefit</h2><p>{data.finding}</p></div><StatusBadge tone="warning">Shadow evaluation required</StatusBadge></section>
      <section aria-labelledby="scenario-title"><div className="section-heading-row"><SectionHeading eyebrow={`${scenario.id} scenario`} title="Baseline versus simulated operation" description="All duration measures are cohort means; the controls below are aggregate fictional burden." /><StatusBadge tone={scenario.net_burden_hours > 0 ? "success" : "warning"}>{scenario.decision}</StatusBadge></div><div className="simulation-layout" id="scenario-title"><article className="chart-panel simulation-chart"><header><div><h3>Operational measures</h3><p>GP-practice cohort · exact fictional simulation</p></div></header><div className="chart-canvas"><ResponsiveContainer width="100%" height="100%"><BarChart data={scenario.metrics.map((metric) => ({ name: metric.label, baseline: metric.baseline, simulated: metric.simulated }))} margin={{ top: 10, right: 10, left: -10, bottom: 46 }}><CartesianGrid stroke="var(--border)" vertical={false} /><XAxis dataKey="name" angle={-16} textAnchor="end" interval={0} tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4 }} /><Legend verticalAlign="top" /><Bar dataKey="baseline" fill="var(--text-muted)" radius={[3, 3, 0, 0]} /><Bar dataKey="simulated" fill="var(--accent)" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div><details className="chart-summary"><summary>Accessible data summary</summary><ul>{scenario.metrics.map((metric) => <li key={metric.key}>{metric.label}: baseline {metric.baseline?.toFixed(2)}, simulated {metric.simulated.toFixed(2)} {metric.unit}</li>)}</ul></details></article><div className="scenario-metrics"><MetricCard label="Affected cases" value={scenario.affected_cases} unit="cases" /><MetricCard label="Human review overhead" value={scenario.review_overhead_hours.toFixed(2)} unit="hours" tone="warning" /><MetricCard label="Manual fallbacks" value={scenario.fallbacks} unit="cases" /><MetricCard label="Service failures" value={scenario.failures} unit="events" tone={scenario.failures > 10 ? "warning" : "default"} /><MetricCard label="Net burden difference" value={`${scenario.net_burden_hours > 0 ? "+" : ""}${scenario.net_burden_hours.toFixed(2)}`} unit="hours" tone={scenario.net_burden_hours > 0 ? "positive" : "warning"} /></div></div></section>
      <section aria-labelledby="scenario-table"><SectionHeading eyebrow="Sensitivity" title="All scenarios remain visible" description="The optimistic result does not erase conservative or adverse outcomes." /><div className="scenario-comparison" id="scenario-table">{data.scenarios.map((item) => <article key={item.id}><div><span>{item.id}</span><StatusBadge tone={item.net_burden_hours > 0 ? "success" : item.id === "adverse" ? "danger" : "warning"}>{item.decision}</StatusBadge></div><dl><div><dt>Affected</dt><dd>{item.affected_cases}</dd></div><div><dt>Review</dt><dd>{item.review_overhead_hours.toFixed(1)}h</dd></div><div><dt>Fallbacks</dt><dd>{item.fallbacks}</dd></div><div><dt>Failures</dt><dd>{item.failures}</dd></div></dl><strong>{item.net_burden_hours > 0 ? "+" : ""}{item.net_burden_hours.toFixed(2)} hours</strong></article>)}</div></section>
      <section className="caveat-band"><AlertTriangle aria-hidden="true" /><div><h2>Decision boundary</h2><ul>{data.caveats.map((item) => <li key={item}><ArrowRight aria-hidden="true" />{item}</li>)}</ul></div></section>
    </div>
  );
}

