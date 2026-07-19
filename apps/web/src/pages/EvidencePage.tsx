import { AlertCircle, CheckCircle2, Database, Info } from "lucide-react";
import { useState } from "react";

import { useMetrics } from "../api/queries";
import { EvidenceChart } from "../components/EvidenceChart";
import { FictionalNotice } from "../components/FictionalNotice";
import { MetricCard } from "../components/MetricCard";
import { PageError, PageLoading } from "../components/PageState";
import { PageHeader, SectionHeading } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { formatMetric } from "../lib/format";

type CohortView = "source" | "service";

export function EvidencePage() {
  const query = useMetrics();
  const [view, setView] = useState<CohortView>("source");
  if (query.isPending) return <PageLoading label="Calculating operational evidence" />;
  if (query.error) return <PageError error={query.error} retry={() => void query.refetch()} />;
  const data = query.data;
  const series = view === "source" ? data.referral_sources : data.service_lines;

  return (
    <div className="page-container evidence-page">
      <PageHeader eyebrow="Baseline evidence · Fictional administrative workflow" title="Operational evidence" description="Inspect where time and repeated work accumulate, with measurement quality and exclusions kept beside the result." />
      <FictionalNotice compact />
      <section aria-labelledby="overall-metrics"><SectionHeading eyebrow="Overall baseline" title="1,000 referrals across 10,085 events" /><div className="metric-grid" id="overall-metrics">{data.overall.map((metric) => <MetricCard key={metric.key} label={metric.label} value={formatMetric(metric.value, metric.unit)} unit={metric.unit} note={metric.note} tone={metric.key === "stuck" ? "warning" : "default"} />)}</div></section>

      <section className="cohort-section" aria-labelledby="cohort-title"><div className="section-heading-row"><SectionHeading eyebrow="Cohort comparison" title="Where does operational burden differ?" description="Descriptive comparisons identify investigation targets; they do not establish causality." /><div className="segmented-control"><button aria-pressed={view === "source"} onClick={() => setView("source")}>Referral source</button><button aria-pressed={view === "service"} onClick={() => setView("service")}>Service line</button></div></div><div className="chart-grid" id="cohort-title">{series.map((item) => <EvidenceChart key={item.key} series={item} />)}</div></section>

      <section aria-labelledby="findings-title"><SectionHeading eyebrow="Material findings" title="Three signals worth investigating" /><div className="finding-table" id="findings-title">{data.findings.map((finding) => <article key={finding.title}><AlertCircle aria-hidden="true" /><div><span>{finding.cohort}</span><h3>{finding.title}</h3><p><strong>{finding.observed}</strong> compared with {finding.comparison}.</p></div><StatusBadge tone={finding.materiality === "strong" ? "warning" : "info"}>{finding.materiality}</StatusBadge></article>)}</div></section>

      <section className="quality-section" aria-labelledby="quality-title"><SectionHeading eyebrow="Measurement quality" title="Coverage, status, and exclusions" description="Unavailable measures remain unavailable rather than silently becoming zero." /><div className="quality-layout"><div className="quality-grid" id="quality-title">{data.quality.map((measure) => <article key={measure.label}><Database aria-hidden="true" /><span>{measure.label}</span><strong>{formatMetric(measure.value, measure.unit)} <small>{measure.unit}</small></strong><StatusBadge tone={measure.status === "calculated" ? "success" : "info"}>{measure.status}</StatusBadge></article>)}</div><aside className="exclusion-panel"><h3><Info aria-hidden="true" /> Interpretation boundaries</h3><ul>{data.exclusions.map((item) => <li key={item}><CheckCircle2 aria-hidden="true" />{item}</li>)}</ul></aside></div></section>
    </div>
  );
}

