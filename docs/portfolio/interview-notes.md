# WorkflowTwin interview notes

## What problem does WorkflowTwin solve?

It turns operational event data into an evidence-backed decision about where automation may help,
then tests that decision behind explicit human and policy controls. It addresses the gap between a
dashboard that only describes problems and an agent that acts before value and risk are understood.
The Northstar scenario is entirely fictional and administrative.

## Why use append-only events and audit records?

Operational events let me reconstruct what happened without overwriting prior state. Append-only
pilot audit records provide the same property for recommendations, reviews, edits, actions, and
rollbacks. Each record includes the previous fingerprint, so sequence and content linkage can be
verified. PostgreSQL rows are the operational store; immutable artefacts make analysis reproducible.

## Why PM4Py?

Process discovery, variants, directly-follows graphs, and conformance have established semantics and
edge cases. PM4Py is a proven process-mining library, so using it was more credible than inventing a
partial engine. WorkflowTwin owns validation, domain mapping, compact API contracts, metric
interpretation, and product UX around it. PM4Py is AGPL-licensed, which requires commercial licensing
review for some uses.

## How did you prevent data leakage?

The detector receives versioned intake snapshots limited to information published by decision time.
Ground truth and future operational outcomes are separate inputs used only by evaluation. Snapshot,
requirements, detector, and evaluation artefacts have fingerprints. Tests check chronology and
source references, and the API does not expose hidden labels.

## Why did you not use an LLM?

The supported task is an explicit administrative completeness rule and a bounded deterministic
template. An LLM would add variability, evaluation cost, prompt-injection surface, and a misleading
“AI” label without improving the decision. I would consider an LLM for summarising unstructured
interviews, with a gold evaluation set and no action authority.

## Why did detector versions fail?

`strict-v1` had strong precision but insufficient recall. `strict-v2` reduced false-positive burden
with a confirmation window, but recall fell further to 51.19% on its frozen holdout. A V2 source
contract improved observability; `strict-v3` reached 78.39% validation recall but exceeded its 25%
coverage capacity gate at 25.83%. I kept each registered result and did not tune on an opened
holdout.

## Why continue to a fictional pilot after a failed V3 gate?

The pilot answers a different question. Detector-positive coverage measures all positives;
operational policy can cap how many recommendations are surfaced. The supported pilot limits
surfaced coverage to 10% and stays recommendation-only. This does not change the V3 result or
authorise production. It demonstrates controls and measurement under a smaller fictional workload.

## How did you handle reviewer capacity?

Capacity is a first-class gate: surfaced coverage, review minutes, false-positive minutes per 100
cases, queue depth, latency, expiry, and unresolved work are measured. The policy has thresholds,
and the UI shows them. High model quality cannot override an overloaded review queue.

## How does rollback work?

Approval creates a task only in a mock referral system. The task, review, revision, policy, and
recommendation generate a deterministic idempotency key. Rollback requires an actor and reason,
transitions the mock task to rolled back, preserves history, and appends an audit record. In the
ephemeral public runtime, bounded replay data must reproduce the same identifiers before rollback is
accepted.

## What would change with a real customer?

I would add governance and data-processing agreements, source-system profiling, authenticated roles,
durable pilot state, customer-specific requirements, operational ownership, monitoring, incident
response, and a staged rollout. Real healthcare data would require privacy, security, and clinical
safety work beyond this portfolio. I would not reuse fictional thresholds as customer policy.

## What are the biggest limitations?

The data and research are synthetic, so no commercial or clinical outcome is established. Point
events only estimate some waiting time. The public service has ephemeral shared state and cold
starts. There is no authentication, multi-tenancy, real integration, or production queue. The mock
task proves a control pattern, not deployment readiness.

## What would you build next in a real engagement?

Not another detector. I would validate the event and metric contracts with workflow owners, connect
a read-only historical source under governance, run the supported detector in shadow mode, measure
reviewer workload and override reasons, and design a pre-registered controlled pilot. Durable state
and authentication would precede any operational integration.

## What was the hardest engineering decision?

Keeping failed evaluation evidence visible while presenting one understandable product path. It was
tempting to optimise a metric or hide historical versions. Instead, I froze results, left the V3
holdout unopened, separated detector coverage from surfaced workload, and made those distinctions
visible in the product.

## How would you deploy this safely?

The portfolio deployment uses separate static frontend and FastAPI origins, an explicit CORS
allowlist, fictional data, no send capability, bounded validation, and disabled anonymous reset.
A production deployment would use an authenticated container service,
durable PostgreSQL transactions, secrets management, rate limits, audit export, alerting, backups,
least-privilege network access, and controlled release gates. External actions would require a new
threat model and customer approval.

## How would you measure real impact?

Agree on baseline definitions first, then pre-register a comparison. Measure first-pass
completeness, waiting time, rework, manual touches, review minutes, false positives, fallbacks,
failures, adoption, overrides, and cost. Segment results by operational cohort without using them for
clinical decisions. Report confidence intervals and guardrails, and stop if safety or capacity gates
fail. The fictional simulation is a planning input, never a realised-savings claim.

## How is this an AI engineering project without an LLM?

AI engineering includes data contracts, behavioural evaluation, process discovery, decision logic,
safe deployment, human feedback, and monitoring. WorkflowTwin uses process mining and a deterministic
recommendation detector because they fit the evidence. Choosing not to add a generative model is part
of the engineering judgement the project is intended to demonstrate.
