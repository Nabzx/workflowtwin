import { CheckCircle2, CircleAlert, CircleDashed } from "lucide-react";

export function StatusBadge({ children, tone = "neutral" }: { children: string; tone?: "success" | "warning" | "danger" | "neutral" | "info" }) {
  const Icon = tone === "success" ? CheckCircle2 : tone === "warning" || tone === "danger" ? CircleAlert : CircleDashed;
  return <span className={`status-badge status-badge--${tone}`}><Icon aria-hidden="true" />{children}</span>;
}

