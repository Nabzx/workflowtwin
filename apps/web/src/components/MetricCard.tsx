import type { ReactNode } from "react";

export interface MetricCardProps {
  label: string;
  value: ReactNode;
  unit?: string;
  note?: string | null;
  tone?: "default" | "positive" | "warning";
}

export function MetricCard({ label, value, unit, note, tone = "default" }: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <p>{label}</p>
      <div className="metric-card__value"><strong>{value}</strong>{unit && <span>{unit}</span>}</div>
      {note && <small>{note}</small>}
    </article>
  );
}

