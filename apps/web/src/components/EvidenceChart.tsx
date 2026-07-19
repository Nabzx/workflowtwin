import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Metrics } from "../api/schemas";
import { StatusBadge } from "./StatusBadge";

type Series = Metrics["referral_sources"][number];

export function EvidenceChart({ series }: { series: Series }) {
  const maxValue = Math.max(...series.values.map((point) => point.value));
  return (
    <article className="chart-panel">
      <header><div><h3>{series.label}</h3><p>{series.unit} · denominator {series.denominator.toLocaleString("en-GB")}</p></div><StatusBadge tone={series.status === "calculated" ? "success" : "info"}>{series.status}</StatusBadge></header>
      <div className="chart-canvas" aria-hidden="true"><ResponsiveContainer width="100%" height="100%"><BarChart data={series.values} margin={{ top: 8, right: 8, left: -12, bottom: 32 }}><CartesianGrid stroke="var(--border)" vertical={false} /><XAxis dataKey="cohort" stroke="var(--text-muted)" tick={{ fontSize: 10 }} angle={-18} textAnchor="end" interval={0} /><YAxis stroke="var(--text-muted)" tick={{ fontSize: 10 }} domain={[0, Math.ceil(maxValue * 1.15)]} /><Tooltip cursor={{ fill: "var(--surface-muted)" }} contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 12 }} formatter={(value) => [`${Number(value).toFixed(2)} ${series.unit}`, series.label]} /><Bar dataKey="value" fill="var(--accent)" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div>
      <details className="chart-summary"><summary>Accessible data summary</summary><ul>{series.values.map((point) => <li key={point.cohort}><strong>{point.cohort}:</strong> {point.value.toFixed(2)} {series.unit}, {point.case_count} cases</li>)}</ul></details>
    </article>
  );
}

