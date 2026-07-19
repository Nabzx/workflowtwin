# WorkflowTwin demo script

Target duration: 3 minutes. Use the deployed demo at <https://workflowtwin.vercel.app>.

| Time | Page or action | Spoken narration | Emphasise |
| --- | --- | --- | --- |
| 0:00–0:20 | **Overview** | “WorkflowTwin finds where an operational workflow breaks, selects an evidence-backed automation opportunity, and tests it behind human controls. Northstar Clinics and every record and result here are fictional.” | This is process intelligence plus guarded action, not a chatbot or clinical tool. |
| 0:20–0:40 | Point to headline evidence and journey | “The prepared dataset contains 1,000 referrals, 10,085 events, and 57 observed variants. The supported path preserves provenance from events through simulation, review, rollback, and gates.” | Zero messages sent; no realised impact claim. |
| 0:40–1:00 | **Workflow**, select “Completeness checked” | “PM4Py reconstructed the observed process. I can switch frequency and performance modes, filter cohorts, and inspect loops and handoffs. Forty-one percent of cases contain loops and 93% contain handoffs.” | Intended and governed behaviour are different concepts. |
| 1:00–1:20 | **Evidence** | “Metric contracts make coverage and exclusions visible. GP-practice referrals had 51.8% first-pass completeness versus 67.8% overall, which is the main bottleneck signal.” | Units, denominators, and estimated metrics stay explicit. |
| 1:20–1:35 | **Opportunity** | “The selected opportunity is deterministic intake completeness review. The evidence chain links baseline, process evidence, fictional research, eligibility, controls, and portfolio decision. Higher-risk candidates remain visible but ineligible.” | Selection came from evidence and authority constraints. |
| 1:35–1:55 | **Simulation**, choose adverse | “Simulation did not manufacture a win. The central scenario added 0.4 hours of net burden once review and fallback were included. The adverse case remains visible, so the next step was shadow evaluation rather than deployment.” | Simulated effect is not customer impact. |
| 1:55–2:20 | **Pilot**, open an awaiting recommendation | “The detector sees an explicit administrative absence, not clinical content or a future label. The authority panel is persistent: the system may recommend and prepare bounded text, but it cannot send, change a referral, or decide clinical priority.” | Human approval is the control point. |
| 2:20–2:40 | **Edit draft**, change heading, save | “This deterministic draft has no address and is marked Not sent. Edits are bounded to administrative content. Clinical or identifying terms fail validation.” | Revision history and provenance are retained. |
| 2:40–2:55 | **Approve fictional task** | “Approval records a human review and creates a local mock task with an idempotency key. It is only ready for manual sending. Notice there is no send button or send API.” | Fictional local effect only. |
| 2:55–3:10 | **Roll back task**, confirm | “Rollback requires a reason, restores the mock state, and keeps both creation and rollback history.” | Reversibility is designed, not narrated. |
| 3:10–3:25 | **Inspect audit** | “The audit chain verifies sequence and fingerprints. Safety, quality, capacity, auditability, and reliability gates are inspectable. Prohibited action counts remain zero.” | `ready_for_fictional_pilot_demo` is not production approval. |
| 3:25–3:40 | **Engineering** | “The stack is FastAPI, PostgreSQL, SQLAlchemy, PM4Py, React and TypeScript, with strict typing, coverage, E2E tests, Docker, and deployment configuration. Failed detector gates and unopened holdouts remain documented.” | Engineering judgement is visible in negative results. |
| 3:40–3:50 | Return to **Overview** | “WorkflowTwin demonstrates the full decision path from ambiguous operations problem to evidence, a conservative pilot, and measurable human control.” | Close on the product outcome, not framework names. |

## Short fallback

For a two-minute version, skip the Evidence chart tour and Engineering page. Keep the negative
simulation result and full approve/rollback sequence; those two moments best demonstrate judgement
and safety.

## Demo recovery

The public runtime is ephemeral and can return to prepared state between requests. Reload Pilot and
select any `Draft awaiting review` row if another visitor has changed the visible row. Anonymous HTTP
reset is disabled. Locally, use `uv run workflowtwin demo --reset` or the token-protected reset API.
