import { Check, Clock, Edit3, History, Save, ShieldAlert, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useApproveDraft, useCancelDraft, useEditDraft, useRejectDraft, useReviewRecommendation } from "../api/queries";
import type { Draft, PilotAction, Recommendation } from "../api/schemas";
import { ApiError } from "../api/client";
import { StatusBadge } from "./StatusBadge";

const REVIEWER = "fictional_admin_reviewer";
const FORBIDDEN_TERMS = ["diagnosis", "symptom", "treatment", "urgency", "nhs_number", "patient_name", "date_of_birth", "clinical_note", "protected_attribute"];

function fictionalTime(draft: Draft): string {
  return new Date(new Date(draft.created_at).getTime() + (30 + draft.revisions.length) * 60_000).toISOString();
}

function validateDraft(heading: string, body: string): string | null {
  const content = `${heading} ${body}`.toLowerCase();
  const forbidden = FORBIDDEN_TERMS.find((term) => content.includes(term));
  if (forbidden) return `Remove prohibited clinical or identifying term: ${forbidden}`;
  if (heading.trim().length < 3) return "Heading must contain at least three characters.";
  if (body.trim().length < 3) return "Body must contain at least three characters.";
  if (!body.includes("Human review is required")) return "Keep the required human-review statement in the draft.";
  return null;
}

export function DraftReview({ recommendation, draft, onAction }: { recommendation: Recommendation; draft: Draft; onAction: (action: PilotAction) => void }) {
  const current = useMemo(() => draft.revisions.find((item) => item.revision_id === draft.current_revision_id) ?? draft.revisions.at(-1)!, [draft]);
  const [editing, setEditing] = useState(false);
  const [heading, setHeading] = useState(current.heading);
  const [body, setBody] = useState(current.body);
  const [reason, setReason] = useState("Administrative source state verified");
  const [feedback, setFeedback] = useState<string | null>(null);
  const edit = useEditDraft();
  const approve = useApproveDraft();
  const reject = useRejectDraft();
  const cancel = useCancelDraft();
  const review = useReviewRecommendation();
  const busy = edit.isPending || approve.isPending || reject.isPending || cancel.isPending || review.isPending;
  const editable = ["draft_awaiting_review", "draft_edited"].includes(draft.status);

  useEffect(() => { setHeading(current.heading); setBody(current.body); }, [current]);

  const handleError = (error: unknown) => setFeedback(error instanceof ApiError ? error.message : "The review action failed. Retry after checking the draft state.");
  const save = async () => {
    const validation = validateDraft(heading, body);
    if (validation) { setFeedback(validation); return; }
    try {
      await edit.mutateAsync({ draftId: draft.draft_id, payload: { editor_role: REVIEWER, revised_at: fictionalTime(draft), change_reason: "Reviewer clarified administrative wording", heading, body } });
      setEditing(false); setFeedback("Draft revision saved. Nothing was sent.");
    } catch (error) { handleError(error); }
  };
  const decide = async (decision: "reject" | "cancel" | "request_more_context" | "mark_unnecessary") => {
    const common = { revision_id: draft.current_revision_id, reviewer_role: REVIEWER, decided_at: fictionalTime(draft), structured_reason: reason, review_minutes: 4 };
    try {
      if (decision === "reject") await reject.mutateAsync({ draftId: draft.draft_id, payload: common });
      else if (decision === "cancel") await cancel.mutateAsync({ draftId: draft.draft_id, payload: common });
      else await review.mutateAsync({ recommendationId: recommendation.recommendation_id, payload: { ...common, decision } });
      setFeedback(`${decision.replaceAll("_", " ")} recorded. Nothing was sent.`);
    } catch (error) { handleError(error); }
  };
  const approveDraft = async () => {
    const validation = validateDraft(current.heading, current.body);
    if (validation) { setFeedback(validation); return; }
    try {
      const action = await approve.mutateAsync({ draftId: draft.draft_id, payload: { revision_id: draft.current_revision_id, reviewer_role: REVIEWER, decided_at: fictionalTime(draft), structured_reason: reason, review_minutes: 4 } });
      onAction(action); setFeedback("Approved and committed to the fictional local task queue. No message was sent.");
    } catch (error) { handleError(error); }
  };

  return (
    <section className="draft-review" aria-labelledby="draft-review-title">
      <header><div><p className="eyebrow">Human review</p><h3 id="draft-review-title">Administrative draft</h3></div><div><StatusBadge tone="warning">Not sent</StatusBadge><StatusBadge tone="neutral">{`Revision ${draft.revisions.length}`}</StatusBadge></div></header>
      <div className="draft-recipient"><span>Fictional recipient role</span><strong>{draft.administrative_recipient_role.replaceAll("_", " ")}</strong><small>No address or external destination exists.</small></div>
      <div className="draft-editor">
        <label>Heading<input value={heading} onChange={(event) => setHeading(event.target.value)} disabled={!editing || busy} maxLength={120} /></label>
        <label>Draft body<textarea value={body} onChange={(event) => setBody(event.target.value)} disabled={!editing || busy} rows={10} maxLength={2000} aria-describedby="draft-boundary" /></label>
        <p id="draft-boundary"><ShieldAlert />Administrative wording only. Clinical or identifying content is rejected.</p>
        {editing ? <div className="editor-actions"><button className="button" onClick={() => void save()} disabled={busy}><Save />Save revision</button><button className="button button--secondary" onClick={() => { setEditing(false); setHeading(current.heading); setBody(current.body); }} disabled={busy}><XCircle />Discard</button></div> : editable && <button className="button button--secondary" onClick={() => setEditing(true)}><Edit3 />Edit draft</button>}
      </div>
      <details className="revision-history"><summary><History />Revision history ({draft.revisions.length})</summary>{[...draft.revisions].reverse().map((revision) => <article key={revision.revision_id}><div><strong>{revision.change_reason.replaceAll("_", " ")}</strong><span>{new Date(revision.revised_at).toLocaleString("en-GB", { timeZone: "Europe/London" })}</span></div><p>{revision.heading}</p><small>{revision.editor_role} · {revision.changed_fields.join(", ")}</small></article>)}</details>
      {editable && <div className="review-decision"><label>Structured review reason<input value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} maxLength={240} /></label><div className="review-actions"><button className="button" onClick={() => void approveDraft()} disabled={busy || editing}><Check />Approve fictional task</button><button className="button button--secondary" onClick={() => void decide("request_more_context")} disabled={busy}><Clock />Request context</button><button className="text-button text-button--danger" onClick={() => void decide("mark_unnecessary")} disabled={busy}>Mark unnecessary</button><button className="text-button text-button--danger" onClick={() => void decide("reject")} disabled={busy}>Reject</button><button className="text-button" onClick={() => void decide("cancel")} disabled={busy}>Cancel</button></div></div>}
      {feedback && <p className={feedback.includes("failed") || feedback.includes("Remove") ? "action-feedback action-feedback--error" : "action-feedback"} role="status">{feedback}</p>}
    </section>
  );
}
