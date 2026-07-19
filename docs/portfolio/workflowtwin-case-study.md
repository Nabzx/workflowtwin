# WorkflowTwin: from process evidence to a human-controlled pilot

## Summary

WorkflowTwin is a fictional process-intelligence and safe-automation product built around a simple
question: how should an engineering team decide what to automate when the real workflow is messy,
the evidence is incomplete, and a bad action would create operational risk?

The initial customer, Northstar Clinics, is fictional. So are every referral, staff role, event,
interview, recommendation, review, action, and result in this repository. The domain is healthcare
administration, but the system performs no diagnosis, triage, treatment recommendation, or clinical
prioritisation. Its scope is the operational path from referral receipt to recorded outcome.

The project was approached as a forward-deployed engagement rather than a model demo. It moves from
event-data contracts through process reconstruction, operational metrics, opportunity selection,
counterfactual simulation, shadow evaluation, and finally a tightly bounded fictional pilot. The
React product makes that evidence chain inspectable and allows a recruiter to exercise human review,
draft editing, approval, mock task creation, and rollback without any send capability.

## The operational problem

Northstar receives referrals from several source types. Administrators check required fields,
request missing information, categorise the referral, assign a clinical team, schedule an
appointment, notify the patient, and record the outcome. The intended path sounds linear. The
observed synthetic event log is not: missing-information loops, reassignments, failed scheduling,
manual touches, and long handoffs create 57 variants across 1,000 fictional referrals and 10,085
events.

The business ambiguity mattered. "Automate referrals" was not treated as a specification. Before
choosing an intervention, WorkflowTwin needed to establish which measurements were supported, where
the workflow diverged, which cohorts were affected, and whether an intervention could remain inside
an administrative authority boundary.

## Discovery and the event model

The synthetic generator encodes a versioned fictional operating model rather than producing random
rows. Cases, events, actors, timestamps, sources, and service lines have stable schemas. Generation
is seeded, fingerprints bind artefacts to their inputs, and ground truth is isolated from the
runtime detector path. Tiny, demo, and full presets support fast feedback and representative
evaluation without pretending to be customer data.

The event model separates case identity from event identity and preserves event time, ingestion
time, activity, lifecycle, actor role, referral source, service line, manual-work markers, and
structured administrative attributes. That enables replay, lateness checks, duplicate detection,
and deterministic reconstruction. PostgreSQL persistence uses SQLAlchemy and Alembic; analyses also
emit immutable JSON artefacts with fingerprints for a portable portfolio demonstration.

## Metrics before models

Operational definitions were written before conclusions. Processing time, waiting time, rework,
manual touches, handoffs, completeness, retries, and stuck cases each carry units, denominators,
availability status, source-event references, and exclusion reasons. Waiting time is labelled as an
estimate where point events cannot prove continuous work state. Missing endpoints are excluded or
reported as partial rather than silently imputed.

That discipline exposed a concrete cohort: GP-practice referrals had 51.8% first-pass completeness,
compared with 67.8% overall in the prepared demonstration. The interface lets a reviewer compare
sources and service lines, examine exact and estimated metrics, and see ingestion-quality measures.
These are synthetic operational findings, not realised customer outcomes.

## Reconstructing the actual workflow

PM4Py supports directly-follows discovery, variant analysis, and conformance. WorkflowTwin converts
the validated event log into a compact API graph with activity and transition frequencies,
performance durations, loops, handoffs, and bottleneck markers. The browser uses React Flow for
progressive inspection: frequency and performance modes, service-line and source filters, node and
edge selection, and variant details.

Conformance has two views. Strict conformance compares cases with the intended successful sequence.
Governed conformance recognises legitimate operational paths such as missing-information and retry
loops. This distinction avoids calling every non-happy path a failure while still quantifying
complexity. In the prepared process, 40.8% of cases contain loops and 93.1% contain handoffs.

## Selecting an opportunity

Opportunity analysis combines baseline metrics, process evidence, synthetic research observations,
technical eligibility, risk, and measurable controls. Candidate interventions remain visible even
when rejected. The selected candidate was a deterministic intake completeness review for
GP-practice referrals because the source state was explicit, the affected cohort was measurable,
and the action could be recommendation-only.

The evidence chain is deliberately inspectable:

```text
Baseline finding
-> process evidence
-> fictional user-research observation
-> eligibility
-> risk controls
-> portfolio decision
```

Other candidates required higher-risk integrations, weaker evidence, or clinical judgement and were
not eligible for controlled prototyping. The selected recommendation still did not authorise an
automation. It only justified simulation.

## Simulation did not manufacture a win

The intervention simulator compares baseline with conservative, central, optimistic, and adverse
assumptions. It models completeness-check delay, manual-touch changes, review overhead, fallback
burden, failures, waiting time, and net fictional burden. The central prepared scenario added 0.4
hours of net burden after review and fallback costs. That is intentionally visible on the Overview
and Simulation pages.

The result changed the product plan. Instead of claiming savings, WorkflowTwin required shadow
evaluation. Simulated effects are counterfactual estimates, not realised impact, and adverse cases
remain present. A real engagement would calibrate assumptions with observed staff time, arrival
patterns, and a pre-registered measurement plan.

## Shadow evaluation and failed gates

The detector history demonstrates learning without rewriting evidence. `strict-v1` achieved 93.02%
precision and 62.11% recall on its immutable 10,000-case holdout. `strict-v2` introduced a
confirmation window that reduced false-positive burden, but recall fell to 51.19%, below the
registered 72% gate. It remained `do_not_promote`; the holdout result was not used for another tuning
round.

That failure prompted a source-contract investigation. The system distinguished explicit absence,
present evidence, not applicable, unsupported, unknown, stale, and contradictory administrative
states. A new V2 source contract made more positives observable at decision time. `strict-v3`
reached 93.16% precision and 78.39% recall on validation, but detector-positive coverage was 25.83%,
above its 25% capacity cap. Its validation assessment remained `strict_v3_validation_failed`, no
lock was created, and its holdout stayed unopened.

The supported product does not erase that history. It aliases the deterministic logic as
`completeness-review-detector-v1` and uses a separate pilot policy to cap surfaced workload at 10%.
This separates detector evaluation from operational rollout rather than weakening a failed
pre-registered gate after seeing results.

## The guarded fictional pilot

The pilot starts with explicit administrative source state and a deterministic recommendation. It
cannot read clinical fields or future labels. A human reviewer can request context, mark a
recommendation unnecessary, reject, cancel, approve, or edit a bounded administrative draft.
Forbidden clinical and identifying terms are rejected in both the browser and API.

Approval creates only a local fictional task marked ready for manual sending. There is no recipient
address and no send endpoint or button. Idempotency keys prevent duplicate creation. Rollback
requires a reason, changes the mock task state, preserves history, and appends a tamper-evident audit
record. The pilot reports 96.6% precision, 80.0% recall, 24.2% detector-positive coverage, 10.0%
surfaced coverage, three human reviews, two fictional commits, one verified rollback, zero messages,
zero clinical fields accessed, and zero operational event mutations.

The final assessment, `ready_for_fictional_pilot_demo`, means exactly that. It is not production
approval or proof of operational benefit.

## Product and architecture

The product uses React, TypeScript, Vite, React Router, TanStack Query, Zod, Recharts, and React
Flow. Eight routes tell one supported story: Overview, Workflow, Evidence, Opportunity, Simulation,
Pilot, Audit and Gates, and Engineering. A central API client handles cancellation, schema
validation, request errors, and query invalidation. Local state is limited to presentation controls
and unsaved form input.

FastAPI exposes versioned, typed, compact demo contracts and reuses pilot mutation endpoints. The
application includes structured request logs, request identifiers, duration and status, readiness,
and a non-sensitive system-status endpoint. Docker Compose runs PostgreSQL, FastAPI, and an
Nginx-served production SPA. A unified image supports container deployment; the public Vercel setup
deploys `apps/web` as a static Vite project and FastAPI as a separate backend project with an
explicit CORS allowlist.

Vercel functions can recycle between calls. To keep the public demonstration safe, approval and
rollback accept only bounded fictional replay data and verify deterministic revision, action,
idempotency, and mock-task identifiers atomically. Anonymous reset remains disabled. This is a
portfolio compromise, not a multi-user persistence architecture.

## Engineering quality and trade-offs

The repository uses strict mypy, Ruff, pytest with branch coverage, Vitest, React Testing Library,
Playwright, Axe, Alembic validation, schema-drift checks, Docker health checks, and deterministic
demo commands. Critical browser tests cover the recruiter walkthrough, forbidden content, API
failure and retry, accessibility, and tablet navigation. Route-level code splitting keeps the
initial JavaScript at about 262 KB, or 82 KB gzip; graphing and charting code loads only when needed.

No LLM was added because the supported task does not need open-ended generation. A deterministic
template is easier to validate, reproduce, audit, and constrain. An LLM could become relevant for
summarising unstructured operational interviews, but only with a measured evaluation set and no
authority to act.

## What would change with a real customer

A real engagement would begin with data-governance approval, workflow-owner interviews, identity
and access controls, retention policies, data-quality profiling, and a jointly signed metric
contract. Real patient data would require appropriate privacy, security, and clinical-safety
governance beyond this portfolio system. Pilot state would move to durable transactional storage,
mutations would use authenticated roles, and deployment would have rate limits, monitoring,
incident response, and change control.

The rollout would remain staged: offline replay, shadow recommendations, reviewer-only surfacing,
then a controlled operational experiment if quality, capacity, and safety gates pass. Impact would
be measured against a pre-registered comparison using waiting time, rework, first-pass completeness,
staff burden, failures, adoption, override reasons, and cost. No benefit would be claimed from this
fictional benchmark.

## Lessons

The hardest part was not selecting a model. It was preserving the distinction between available
evidence, hidden evaluation truth, simulated effect, operational capacity, and authority to act.
The detector iterations show why a good precision score is insufficient: recall, source
observability, workload, and governance can still stop promotion.

WorkflowTwin's main result is therefore the product path itself. It shows how an AI engineer can
turn an ambiguous workflow problem into typed data, inspectable evidence, honest negative results,
a bounded recommendation, and a reversible human-controlled demonstration without pretending that
fictional performance is a customer outcome.
