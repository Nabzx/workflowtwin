import { CheckCircle2, RotateCcw, ShieldCheck, X } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useRollbackDraft } from "../api/queries";
import type { PilotAction, PilotRollback } from "../api/schemas";
import { ApiError } from "../api/client";
import { StatusBadge } from "./StatusBadge";

export function FictionalTask({ action }: { action: PilotAction }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reason, setReason] = useState("Reviewer requested demonstration rollback");
  const [rollback, setRollback] = useState<PilotRollback | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const mutation = useRollbackDraft();

  const submit = async () => {
    if (reason.trim().length < 3) { setError("Provide a rollback reason of at least three characters."); return; }
    try {
      const result = await mutation.mutateAsync({ draftId: action.draft_id, payload: { actor_role: "fictional_pilot_supervisor", rolled_back_at: new Date(new Date(action.acted_at).getTime() + 3 * 60_000).toISOString(), reason, action_replay: action } });
      setRollback(result); setDialogOpen(false); setError(null);
    } catch (failure) { setError(failure instanceof ApiError ? failure.message : "Rollback failed. The fictional task remains unchanged."); }
  };

  return (
    <section className={`fictional-task ${rollback ? "fictional-task--rolled-back" : ""}`} aria-live="polite">
      <div>{rollback ? <RotateCcw /> : <CheckCircle2 />}<div><p className="eyebrow">Mock referral system</p><h3>{rollback ? "Fictional task rolled back" : "Fictional task ready for manual sending"}</h3></div><StatusBadge tone={rollback ? "warning" : "success"}>{rollback ? "Rolled back" : "Created locally"}</StatusBadge></div>
      <dl><div><dt>Mock task</dt><dd>{action.mock_task_id}</dd></div><div><dt>Idempotency key</dt><dd>{action.idempotency_key}</dd></div><div><dt>External communication</dt><dd>None</dd></div><div><dt>Operational events mutated</dt><dd>{action.operational_events_mutated ? "Yes" : "No"}</dd></div>{rollback && <><div><dt>Rollback</dt><dd>{rollback.rollback_id}</dd></div><div><dt>Restored state</dt><dd>{rollback.restored_status.replaceAll("_", " ")}</dd></div></>}</dl>
      <p>{rollback ? "The local task state changed; its creation and rollback history remain auditable." : "No send control exists. A staff member would need to use an external approved process."}</p>
      <div className="task-actions">{!rollback && <button className="button button--danger" onClick={() => { setDialogOpen(true); setTimeout(() => cancelRef.current?.focus(), 0); }}><RotateCcw />Roll back task</button>}<Link className="button button--secondary" to="/audit"><ShieldCheck />Inspect audit</Link></div>
      {dialogOpen && <div className="dialog-backdrop" role="presentation"><div className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="rollback-title" onKeyDown={(event) => { if (event.key === "Escape") setDialogOpen(false); }}><button className="icon-button" onClick={() => setDialogOpen(false)} aria-label="Close rollback dialog"><X /></button><p className="eyebrow">Reversible fictional action</p><h2 id="rollback-title">Roll back this local task?</h2><p>The task will be marked rolled back. Its history and audit record will be preserved. No external system is contacted.</p><label>Rollback reason<textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} maxLength={240} /></label>{error && <p className="dialog-error" role="alert">{error}</p>}<div><button ref={cancelRef} className="button button--secondary" onClick={() => setDialogOpen(false)}>Keep task</button><button className="button button--danger" onClick={() => void submit()} disabled={mutation.isPending}><RotateCcw />Confirm rollback</button></div></div></div>}
    </section>
  );
}
