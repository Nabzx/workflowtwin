import { CheckCircle2, Fingerprint, Link2, ShieldCheck, XCircle } from "lucide-react";
import { useMemo, useState } from "react";

import { useAudit, useGates, usePilotSummary } from "../api/queries";
import { FictionalNotice } from "../components/FictionalNotice";
import { MetricCard } from "../components/MetricCard";
import { PageError, PageLoading } from "../components/PageState";
import { PageHeader, SectionHeading } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { sentenceCase, shortId } from "../lib/format";

export function AuditPage() {
  const audit = useAudit();
  const gates = useGates();
  const summary = usePilotSummary();
  const [category, setCategory] = useState("all");
  const [auditLimit, setAuditLimit] = useState(12);
  const chainValid = useMemo(() => audit.data?.every((record, index, records) => record.sequence_number === index + 1 && record.previous_record_fingerprint === (index === 0 ? null : records[index - 1].content_fingerprint)) ?? false, [audit.data]);
  if (audit.isPending || gates.isPending || summary.isPending) return <PageLoading label="Verifying audit and promotion gates" />;
  const error = audit.error ?? gates.error ?? summary.error;
  if (error) return <PageError error={error} retry={() => { void audit.refetch(); void gates.refetch(); void summary.refetch(); }} />;
  if (!audit.data || !gates.data || !summary.data) return <PageLoading />;
  const categories = [...new Set(gates.data.map((gate) => gate.category))];
  const filteredGates = category === "all" ? gates.data : gates.data.filter((gate) => gate.category === category);
  const recent = [...audit.data].reverse().slice(0, auditLimit);
  const metrics = summary.data.metrics;

  return (
    <div className="page-container audit-page">
      <PageHeader eyebrow="Tamper-evident evidence · Fictional pilot" title="Audit and promotion gates" description="Trace every recommendation, review, mock action, and rollback, then inspect the policy evidence behind the pilot assessment." actions={<StatusBadge tone="success">{sentenceCase(summary.data.assessment)}</StatusBadge>} />
      <FictionalNotice compact />
      <section className="audit-verification"><div className={chainValid ? "verification-mark" : "verification-mark verification-mark--failed"}>{chainValid ? <ShieldCheck /> : <XCircle />}</div><div><p className="eyebrow">Audit chain verification</p><h2>{chainValid ? "All record links verified" : "Chain verification failed"}</h2><p>Sequence and previous-record links were checked across the current API response.</p></div><dl><div><dt>Records</dt><dd>{audit.data.length}</dd></div><div><dt>Root fingerprint</dt><dd>{shortId(audit.data.at(-1)?.content_fingerprint ?? "Unavailable")}</dd></div><div><dt>Policy</dt><dd>{summary.data.policy_version}</dd></div></dl></section>
      <section aria-labelledby="safety-measures"><SectionHeading eyebrow="Authority evidence" title="Prohibited actions remained at zero" /><div className="metric-grid" id="safety-measures"><MetricCard label="External communication attempts" value={metrics.external_communication_attempts} unit="attempts" tone="positive" /><MetricCard label="Operational workflow mutations" value={metrics.operational_workflow_mutations} unit="mutations" tone="positive" /><MetricCard label="Policy compliance" value={(metrics.policy_compliance * 100).toFixed(0)} unit="%" tone="positive" /><MetricCard label="Audit completeness" value={(metrics.audit_completeness * 100).toFixed(0)} unit="%" tone="positive" /></div></section>
      <section aria-labelledby="gates-title"><div className="section-heading-row"><SectionHeading eyebrow="Promotion evidence" title="Safety, quality, capacity, auditability, reliability" description="These gates support a fictional demonstration only. They do not approve production use." /><div className="gate-filter"><label>Gate category<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((item) => <option key={item} value={item}>{sentenceCase(item)}</option>)}</select></label></div></div><div className="gate-summary">{categories.map((item) => { const group = gates.data.filter((gate) => gate.category === item); return <button key={item} className={category === item ? "is-active" : ""} onClick={() => setCategory(category === item ? "all" : item)}><span>{sentenceCase(item)}</span><strong>{group.filter((gate) => gate.status === "pass").length}/{group.length}</strong><small>passed</small></button>; })}</div><div className="gate-list" id="gates-title">{filteredGates.map((gate) => <article key={gate.gate_id}>{gate.status === "pass" ? <CheckCircle2 /> : <XCircle />}<div><span>{sentenceCase(gate.category)}</span><h3>{sentenceCase(gate.gate_id.replace(`${gate.category}-`, ""))}</h3><p>{gate.explanation}</p></div><dl><div><dt>Actual</dt><dd>{gate.actual === null ? "n/a" : String(gate.actual)}</dd></div><div><dt>Threshold</dt><dd>{gate.threshold === null ? "n/a" : String(gate.threshold)}</dd></div></dl><StatusBadge tone={gate.status === "pass" ? "success" : gate.status === "fail" ? "danger" : "neutral"}>{sentenceCase(gate.status)}</StatusBadge></article>)}</div></section>
      <section aria-labelledby="audit-title"><SectionHeading eyebrow="Append-only activity" title="Recent audit records" description="Actor roles, linked objects, reasons, and content fingerprints remain visible after rollback." /><div className="audit-list" id="audit-title">{recent.map((record) => <article key={record.audit_id}><div className="audit-sequence">{record.sequence_number}</div><div><span>{new Date(record.occurred_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/London" })}</span><h3>{sentenceCase(record.action)}</h3><p>{record.actor_role} · {shortId(record.object_id)}</p>{record.reason_codes.length > 0 && <small>{record.reason_codes.join(" · ")}</small>}</div><div className="audit-fingerprint"><Fingerprint /><code>{shortId(record.content_fingerprint)}</code><span><Link2 />{record.previous_record_fingerprint ? "linked" : "root"}</span></div></article>)}</div>{auditLimit < audit.data.length && <button className="button button--secondary load-more" onClick={() => setAuditLimit((value) => value + 12)}>Show earlier records</button>}</section>
      <section className="assessment-band"><ShieldCheck /><div><p className="eyebrow">Final assessment</p><h2>{summary.data.assessment}</h2><p>Ready for a controlled fictional portfolio demonstration. Not production approval, clinical validation, or evidence of realised customer impact.</p></div></section>
    </div>
  );
}

