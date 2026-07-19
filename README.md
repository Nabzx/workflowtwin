# WorkflowTwin

WorkflowTwin is a process-intelligence and safe automation portfolio project. It reconstructs an
operational workflow, quantifies friction, links evidence to an automation opportunity, simulates
the expected effect, evaluates the recommendation in shadow mode, and demonstrates a reversible
human-approved action.

The initial customer, **Northstar Clinics**, is a fictional UK healthcare provider. Every referral,
person, organisation, metric, and result in this repository is fictional or synthetic. WorkflowTwin
handles administrative workflow evidence only. It does not diagnose, prioritise clinical urgency,
recommend treatment, or claim real clinical or commercial outcomes.

## Product story

```text
Operational data
  -> Process analysis
  -> Opportunity evidence
  -> Counterfactual simulation
  -> Shadow evaluation
  -> Human-approved fictional pilot
```

Northstar's fictional administrators receive referrals, check required information, request missing
items, categorise and assign work, schedule appointments, notify patients, and record outcomes. The
case study explores incomplete submissions, manual checks, repeated work, slow handoffs, inconsistent
categorisation, stuck referrals, and weak visibility into automation impact.

WorkflowTwin answers five practical questions:

1. What process actually occurred, including variants, loops, waits, and rework?
2. Which bottleneck has enough quantitative and qualitative evidence to act on?
3. What might improve under explicit counterfactual assumptions?
4. Does the detector meet quality, safety, and reviewer-capacity constraints?
5. Can an approved administrative action be executed locally, audited, deduplicated, and reversed?

## Quick start

```bash
uv sync --extra dev
uv run workflowtwin demo
uv run workflowtwin serve
```

Open `http://127.0.0.1:8000/docs` for the API. Use
`uv run workflowtwin demo --reset` to replace generated files or
`uv run workflowtwin demo --skip-heavy-analysis` to prepare only detector and pilot evidence.

The demo writes:

- `artifacts/demo/demo-seed.json`: compact stage lineage and the API command;
- `artifacts/demo/pilot-run.json`: typed policy, recommendations, drafts, decisions, actions,
  rollbacks, metrics, gates, audit records, fingerprints, and assessment;
- `artifacts/demo/pilot-report.md`: stakeholder-readable evidence and limitations.

Generated artifacts are ignored by Git. The command is deterministic for the fixed inputs.
A compact future-UI fixture is retained at
`data/demo/northstar-pilot-ui-seed-v1.json`.

## Supported product path

There is one current intake and one current detector:

| Product concept | Supported implementation |
|---|---|
| Intake | **Northstar intake contract**, implemented by `IncomingReferralSnapshotV2` |
| Detector | **completeness-review-detector-v1** |
| Detector lineage | unchanged strict-v3 rules and original fingerprint |
| Action | create a local administrative missing-information draft task |
| Authority | every action requires a permitted fictional human reviewer |
| Communication | none; no send endpoint or external adapter exists |

The product alias does not hide the experiment history. Strict-v3 failed its original pre-registered
detector-positive coverage gate, and its historical result remains
`strict_v3_validation_failed`. The separate pilot policy controls actual surfaced workload rather
than rewriting that result. Strict-v1, strict-v2, and strict-v3 evidence is summarized in the
[detector evolution](docs/experiments/shadow-detector-evolution.md); the complete implementation
history remains in Git and the annotated `shadow-evaluation-complete` tag.

## Fictional pilot

The supported action creates a deterministic draft from explicit missing administrative fields and
requirements rules. It uses no LLM. A draft includes a fictional case identifier, administrative
recipient role, form version, source and requirements references, expiry, immutable revisions, a
human-review warning, and a statement that it has not been sent.

A reviewer can edit, approve, approve with edits, reject, cancel, mark unnecessary, or request more
context. Approval is rejected unless the role, recommendation, current revision, provenance, policy
decision, conflict state, and expiry checks pass. A successful approval creates only an in-memory
mock task marked `ready_for_manual_sending`; it does not send anything or change referral events.

Stable idempotency keys derive from recommendation ID, draft revision, policy version, and action
type. Replays return a duplicate-suppressed action instead of another task. Rollback is idempotent,
preserves task history, records actor and reason, and restores a rolled-back mock state even after
cancellation.

The deterministic pilot seed reports:

| Measure | Fictional result |
|---|---:|
| Incoming cases | 120 |
| Detector precision | 96.6% |
| Detector recall | 80.0% |
| Detector-positive coverage | 24.2% |
| Surfaced recommendation coverage | 10.0% |
| Human reviews | 3 |
| Local task commits | 2 |
| Verified rollbacks | 1 |
| External messages | 0 |
| Operational event mutations | 0 |
| Assessment | `ready_for_fictional_pilot_demo` |

This assessment authorises only the fictional local demonstration. It is not production approval.

## Gates and metrics

The versioned `northstar-fictional-pilot-policy-v1` evaluates:

- **Safety:** no clinical-field access, automatic communication, unapproved action, rejection,
  routing, service-line change, or operational workflow mutation.
- **Detector quality:** precision at least 90%, recall at least 72% on evaluable labels, bounded
  false-positive review burden, cohort reporting, and no critical cohort failure.
- **Reviewer capacity:** surfaced coverage at most 20%, bounded review minutes and queue depth,
  P95 latency within SLO, and controlled expiry/backlog.
- **Auditability:** complete provenance, policy, reviewer, action, rollback, and valid audit-chain
  linkage.
- **Reliability:** deterministic replay, action idempotency, local adapter availability, and
  successful rollback.

Raw detector-positive coverage remains visible, but it is not treated as work that a reviewer
actually received. Stop conditions pause or revise the pilot when any mandatory safety, quality,
capacity, audit, or reliability gate fails.

The system does not report messages sent, referrals resolved, realised staff hours, cost reduction,
production ROI, or clinical outcomes.

## Architecture

WorkflowTwin is a typed Python 3.12 modular monolith. FastAPI owns transport, application modules
coordinate use cases, deterministic domain modules own analysis and policy, PM4Py is isolated behind
an adapter, and SQLAlchemy/Alembic own the existing operational event store. The pilot deliberately
uses an isolated in-memory adapter and never writes to operational event tables.

```mermaid
flowchart LR
    Events[Immutable synthetic events] --> Baseline[Baseline metrics]
    Events --> Process[PM4Py process analysis]
    Baseline --> Opportunity[Evidence-backed opportunity]
    Process --> Opportunity
    Opportunity --> Simulation[Counterfactual simulation]
    Simulation --> Intake[Northstar intake contract V2]
    Intake --> Detector[completeness-review-detector-v1]
    Detector --> Queue[Capacity-limited review queue]
    Queue --> Human{Human decision}
    Human -->|approve current revision| Mock[Local mock task]
    Human -->|edit/reject/cancel| Audit[Append-only audit]
    Mock --> Rollback[Idempotent rollback]
    Mock --> Audit
    Rollback --> Audit
```

Key modules:

- `analytics`, `process_mining`, `opportunities`, `simulation`: operational evidence pipeline;
- `intake`: supported V2 product contract and requirements;
- `detector`: supported alias and auditable strict-v3 lineage adapter;
- `pilot`: drafts, policy, review coordination, mock actions, rollback, metrics, gates, reports;
- `api`: service and versioned fictional-pilot routes;
- `experiments`: compact historical golden readers only;
- `infrastructure`: PostgreSQL persistence for immutable operational data.

See [human-approved pilot architecture](docs/architecture/human-approved-pilot.md),
[technical architecture](docs/architecture/technical-architecture.md), and
[ADR 0011](docs/decisions/0011-supported-product-and-pilot.md).

## API

The local fictional API exposes:

```text
GET  /api/v1/pilot/summary
GET  /api/v1/pilot/recommendations
GET  /api/v1/pilot/recommendations/{id}
POST /api/v1/pilot/recommendations/{id}/review
GET  /api/v1/pilot/drafts
GET  /api/v1/pilot/drafts/{id}
POST /api/v1/pilot/drafts/{id}/edit
POST /api/v1/pilot/drafts/{id}/approve
POST /api/v1/pilot/drafts/{id}/reject
POST /api/v1/pilot/drafts/{id}/cancel
POST /api/v1/pilot/drafts/{id}/rollback
GET  /api/v1/pilot/audit
GET  /api/v1/pilot/gates
```

There is intentionally no send, contact, referral-status, routing, or service-line endpoint.
Authentication is out of scope for this local portfolio demo.

## Other commands

```bash
uv run workflowtwin --help
uv run workflowtwin generate --preset demo --dataset-output artifacts/generation/demo.json
uv run workflowtwin analyze --help
uv run workflowtwin process-mine --help
uv run workflowtwin identify-opportunities --help
uv run workflowtwin simulate-intervention --help
uv run workflowtwin shadow-run --dataset artifacts/generation/demo.json
uv run workflowtwin pilot-run --reset
```

Historical refinement and holdout commands are not part of the product CLI.

## Development

```bash
uv run pytest --cov
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests alembic scripts
uv lock --check
docker compose config
docker compose build api
```

The current local suite passes 199 tests with 16 PostgreSQL integration tests available separately
and 91.73% branch coverage.
The fixed 1,000-case analytical demo reconstructs 17 activities, 23 transitions, and 57 variants;
strict/governed conformance rates are 36.3%/87.1%. See the focused
[benchmarks](docs/architecture/pilot-benchmark.md) and existing architecture benchmark documents.

Run PostgreSQL integration tests with a migrated disposable database:

```bash
docker compose up -d db
uv run alembic upgrade head
WORKFLOWTWIN_TEST_DATABASE_URL=postgresql+asyncpg://workflowtwin:workflowtwin@localhost:5432/workflowtwin \
  uv run pytest -m postgres
```

## Limitations

- All results are synthetic and specific to the fictional Northstar assumptions.
- The pilot store is process-local and resets when the API restarts.
- Reviewer identity is a validated role string, not authenticated identity.
- The demo has no frontend, deployment, telemetry, live integrations, email, or message delivery.
- Counterfactual results describe assumptions, not observed causal impact.
- No LLM or agent framework is used; deterministic rules are appropriate for this milestone.

The final productisation milestone is the recruiter-facing React/TypeScript frontend, deployment of
this fictional demo, stronger visual presentation, observability, and a concise portfolio walkthrough.
