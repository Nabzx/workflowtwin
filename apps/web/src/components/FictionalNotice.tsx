import { ShieldCheck } from "lucide-react";

export function FictionalNotice({ compact = false }: { compact?: boolean }) {
  return (
    <aside aria-label="Fictional data notice" className={`fictional-notice ${compact ? "fictional-notice--compact" : ""}`}>
      <ShieldCheck aria-hidden="true" />
      <div><strong>Fictional demonstration</strong>{!compact && <span>Northstar Clinics and every record, person, action, and result are fictional.</span>}</div>
    </aside>
  );
}
