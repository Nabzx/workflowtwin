import { Ban, CheckCircle2, ChevronRight, Clock3, FileCheck2, Shield, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useDrafts, usePilotSummary, useRecommendations } from "../api/queries";
import type { Draft, PilotAction, Recommendation } from "../api/schemas";
import { DraftReview } from "../components/DraftReview";
import { FictionalTask } from "../components/FictionalTask";
import { FictionalNotice } from "../components/FictionalNotice";
import { PageError, PageLoading } from "../components/PageState";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import { sentenceCase, shortId } from "../lib/format";

export function PilotPage() {
  const summary = usePilotSummary();
  const recommendations = useRecommendations();
  const drafts = useDrafts();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [latestAction, setLatestAction] = useState<PilotAction | null>(null);

  const rows = useMemo(() => {
    if (!recommendations.data || !drafts.data) return [];
    return recommendations.data.map((recommendation) => ({ recommendation, draft: drafts.data.find((item) => item.recommendation_id === recommendation.recommendation_id) }));
  }, [recommendations.data, drafts.data]);
  useEffect(() => {
    if (!selectedId && rows.length) {
      setSelectedId(rows.find((row) => row.draft?.status === "draft_awaiting_review")?.recommendation.recommendation_id ?? rows[0].recommendation.recommendation_id);
    }
  }, [rows, selectedId]);

  if (summary.isPending || recommendations.isPending || drafts.isPending) return <PageLoading label="Loading the human-approved pilot" />;
  const error = summary.error ?? recommendations.error ?? drafts.error;
  if (error) return <PageError error={error} retry={() => { void summary.refetch(); void recommendations.refetch(); void drafts.refetch(); }} />;
  if (!summary.data) return <PageLoading label="Loading pilot assessment" />;
  const selected = rows.find((row) => row.recommendation.recommendation_id === selectedId);
  const filtered = statusFilter === "all" ? rows : rows.filter((row) => row.draft?.status === statusFilter);

  return (
    <div className="page-container pilot-page">
      <PageHeader eyebrow="Guarded pilot · Recommendation only" title="Human-approved completeness review" description="Inspect structured evidence and a deterministic administrative draft before any fictional local task can be created." actions={<StatusBadge tone="success">{sentenceCase(summary.data.assessment)}</StatusBadge>} />
      <FictionalNotice compact />
      <AuthorityPanel />
      <section className="pilot-workspace" aria-label="Pilot recommendations">
        <div className="recommendation-pane">
          <header><div><p className="eyebrow">Review queue</p><h2>{rows.length} recommendations</h2></div><label>Status<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All states</option><option value="draft_awaiting_review">Awaiting review</option><option value="draft_committed_to_fictional_task_queue">Committed</option><option value="draft_rolled_back">Rolled back</option><option value="draft_rejected">Rejected</option></select></label></header>
          <div className="recommendation-list">{filtered.map(({ recommendation, draft }) => <RecommendationRow key={recommendation.recommendation_id} recommendation={recommendation} draft={draft} selected={recommendation.recommendation_id === selectedId} onClick={() => setSelectedId(recommendation.recommendation_id)} />)}</div>
        </div>
        <div className="recommendation-detail">{selected ? <RecommendationDetail recommendation={selected.recommendation} draft={selected.draft} latestAction={latestAction?.recommendation_id === selected.recommendation.recommendation_id ? latestAction : null} onAction={setLatestAction} /> : <p>Select a recommendation to inspect its evidence.</p>}</div>
      </section>
    </div>
  );
}

function AuthorityPanel() {
  const can = ["Read explicit administrative field state", "Recommend a completeness review", "Prepare bounded deterministic text", "Create a reversible fictional local task after approval"];
  const cannot = ["Send a message", "Change a referral status", "Infer missing clinical information", "Make a clinical or priority decision"];
  return <aside aria-label="Automation authority boundary" className="authority-panel"><div><Shield aria-hidden="true" /><div><p className="eyebrow">Persistent authority boundary</p><h2>Human approval is the control point</h2></div></div><div><h3><CheckCircle2 />System may</h3><ul>{can.map((item) => <li key={item}>{item}</li>)}</ul></div><div><h3><Ban />System cannot</h3><ul>{cannot.map((item) => <li key={item}>{item}</li>)}</ul></div></aside>;
}

function RecommendationRow({ recommendation, draft, selected, onClick }: { recommendation: Recommendation; draft?: Draft; selected: boolean; onClick: () => void }) {
  return <button className={`recommendation-row ${selected ? "is-selected" : ""}`} onClick={onClick}><div><span>{shortId(recommendation.recommendation_id)}</span><StatusBadge tone={draft?.status.includes("rolled_back") ? "warning" : draft?.status.includes("awaiting") ? "info" : draft?.status.includes("rejected") ? "danger" : "success"}>{sentenceCase(draft?.status ?? "No draft")}</StatusBadge></div><strong>Missing supporting document</strong><p>Case {shortId(recommendation.case_id)}</p><small><Clock3 />{new Date(recommendation.detected_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/London" })}</small><ChevronRight className="recommendation-row__arrow" /></button>;
}

function RecommendationDetail({ recommendation, draft, latestAction, onAction }: { recommendation: Recommendation; draft?: Draft; latestAction: PilotAction | null; onAction: (action: PilotAction) => void }) {
  return <article><header><div><p className="eyebrow">Recommendation detail</p><h2>Completeness review required</h2><code>{recommendation.recommendation_id}</code></div><StatusBadge tone="info">Recommendation only</StatusBadge></header><section className="detail-section"><h3>Administrative field state</h3><div className="field-state"><FileCheck2 /><div><span>Supporting document</span><strong>Explicitly absent</strong><small>Structured source state · not inferred</small></div></div></section><section className="detail-section"><h3>Detector rationale</h3><p>The supported detector found an explicit administrative absence under the Northstar requirements contract. It did not inspect clinical content or future outcome labels.</p><dl className="detail-grid"><div><dt>Case</dt><dd>{recommendation.case_id}</dd></div><div><dt>Snapshot</dt><dd>{shortId(recommendation.snapshot_id)}</dd></div><div><dt>Detector</dt><dd>{recommendation.detector_product_name}</dd></div><div><dt>Requirement</dt><dd>{recommendation.requirement_references.join(", ")}</dd></div></dl></section><section className="detail-section"><h3>Policy and provenance</h3><ul className="provenance-list">{recommendation.source_references.map((item) => <li key={item}><ShieldCheck />{item}</li>)}</ul><div className="safety-statement"><strong>No future leakage</strong><p>The decision uses the intake snapshot available at evaluation time. Historical outcome labels are not exposed to the detector.</p></div></section>{draft && <DraftReview recommendation={recommendation} draft={draft} onAction={onAction} />}{latestAction && <FictionalTask action={latestAction} />}</article>;
}
