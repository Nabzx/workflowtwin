# WorkflowTwin

WorkflowTwin is an AI-powered process intelligence and automation platform. It is designed to reconstruct how operational workflows actually run, find bottlenecks and repeated manual work, recommend targeted automations, and measure whether those changes improve the process.

The initial case study uses **Northstar Clinics**, a fictional UK healthcare provider. All organisations, referrals, users, and results in this repository are fictional or synthetic. WorkflowTwin focuses on administrative operations; it does not diagnose patients, recommend treatment, or make clinical decisions.

## The problem

Referral operations often span inboxes, forms, handoffs, and scheduling systems. Teams can see individual cases but struggle to answer system-level questions:

- Where do referrals wait, and why?
- Which missing fields cause the most rework?
- Where do staff repeat manual checks or duplicate work?
- Which automation would remove friction without introducing unacceptable risk?
- Did a deployed change improve throughput, adoption, and cost in practice?

Northstar Clinics' fictional workflow receives a referral, checks it for required information, requests anything missing, categorises it, assigns a clinical team, schedules an appointment, notifies the patient, and records the final administrative outcome. Its current process has incomplete submissions, slow handoffs, inconsistent categorisation, duplicated work, stuck cases, and no reliable automation ROI measurement.

## Product vision

WorkflowTwin will combine event-log analysis, process mining, qualitative operational evidence, simulation, and auditable automation recommendations. Each recommendation should connect evidence to an expected operational effect, state its assumptions and safety constraints, and remain measurable after deployment.

The long-term product will:

1. Ingest workflow records and event logs.
2. Reconstruct observed process variants as a graph.
3. Measure processing time, waiting time, rework, and manual touches.
4. Surface bottlenecks, unusual cases, and supporting evidence.
5. Recommend and simulate a targeted administrative automation.
6. Deploy approved automations with human oversight and audit trails.
7. Compare baseline and post-change performance, including adoption and failures.

## Smallest credible MVP

The first end-to-end MVP will use clearly labelled synthetic referral events to answer one decision: **where is the largest operational bottleneck, and could one proposed administrative automation improve it?**

It will:

- generate or import a reproducible synthetic referral event log;
- validate and persist cases and events;
- reconstruct the observed referral flow and common variants;
- calculate cycle time, waiting time, rework, manual touches, and throughput;
- identify the largest evidence-backed bottleneck;
- present one rules-based automation recommendation with assumptions and an audit trail;
- simulate the recommendation's expected operational effect; and
- compare baseline and simulated metrics without presenting synthetic results as clinical evidence.

The current release includes the API foundation, the first versioned referral event model, and a seeded synthetic operational-data generator. It contains no process mining, bottleneck-detection engine, LLM calls, workflow automation, dashboard, authentication, or external integration.

## Architecture

WorkflowTwin begins as a modular monolith: one FastAPI service with explicit domain, service, and infrastructure boundaries, backed by PostgreSQL. This keeps transactions and local development simple while leaving analysis work separable from HTTP and persistence concerns.

```text
Client / future React app
          |
      FastAPI API
          |
   Application services
      /          \
 Domain model   Analysis adapters (future PM4Py / LLM provider)
          |
 SQLAlchemy repositories
          |
      PostgreSQL
```

- `src/workflowtwin/api`: HTTP routes and transport schemas.
- `src/workflowtwin/core`: runtime configuration and cross-cutting concerns.
- `src/workflowtwin/domain`: workflow concepts and invariants, added as the MVP requires them.
- `src/workflowtwin/services`: use-case orchestration, independent of HTTP.
- `src/workflowtwin/infrastructure`: persistence and external provider adapters.
- `apps/web`: reserved for the future React and TypeScript user interface.

The API uses Pydantic settings, structured JSON logging outside local development, SQLAlchemy and Alembic for planned persistence, and dependency inversion at real provider boundaries. PM4Py and an LLM provider abstraction will be introduced only when their first use cases are implemented. See the [technical architecture](docs/architecture/technical-architecture.md) and [initial ADR](docs/decisions/0001-initial-technology-choices.md).

## Referral data foundation

The version 1 operational model is intentionally small and excludes direct patient identifiers, diagnoses, clinical narrative, treatment decisions, risk scores, and clinical prioritisation.

### Current entities

- `referral_cases` stores one current, queryable projection for each process instance: stable internal and external identities, referral source, service line, lifecycle status, receipt and closure times, synthetic marker, schema version, and audit timestamps.
- `referral_events` stores immutable recorded facts: case and source identities, event and ingestion times, operational activity, actor, source system, channel, manual-work flag, structured reason, bounded metadata, and schema version.
- `synthetic_generation_runs` records generation configuration, status, counts, fingerprint, manifest, timestamps, and failure context for idempotent persistence.

`event_at` is the source system's claim about when an activity happened. `ingested_at` is when WorkflowTwin accepted the fact. Keeping both allows later analysis to reconstruct event-time flow while retaining delayed and out-of-order arrivals and reproducing what was known at an ingestion watermark.

Events are append-only in ordinary operation. Frozen domain contracts, SQLAlchemy mutation hooks, a PostgreSQL update/delete trigger, and `ON DELETE RESTRICT` protect audit history. `(source_system, external_event_id)` detects duplicate source facts. These controls are practical safeguards rather than cryptographic tamper evidence or protection from a database owner.

Ten deterministic, fictional fixtures cover straight-through completion, one and repeated information loops, recategorisation and reassignment, scheduling failures, cancellation, rejection, inactivity, duplicate source identity, and delayed ingestion. They are compact evaluation cases for the next analytical stages, not the full synthetic dataset generator.

See the [Northstar workflow](docs/architecture/northstar-referral-workflow.md), [metric definitions](docs/architecture/metric-definitions.md), and [event-model decision](docs/decisions/0002-event-data-model.md).

## Synthetic data generator

The generator produces coherent `ReferralCase` and `ReferralEvent` contracts from one explicitly seeded `random.Random` instance. UUID5 identifiers, case paths, timing, labels, and the SHA-256 operational-data fingerprint are stable for the same effective configuration and run identifier.

Administrative timing follows configurable working hours and weekend handling. External information responses use elapsed time, while subsequent staff activity waits for the next working period. Background variation includes weekday volumes, source and service mixes, processing ranges, outcomes, repeated work, handoffs, and data latency.

The default Northstar assumptions plant four detectable but probabilistic signals:

| Segment | Intended signal |
| --- | --- |
| GP practice referrals | higher initial incompleteness, information waits, and manual touches |
| Neurology | longer categorisation-to-team-assignment waiting time |
| Respiratory | more failed scheduling attempts and longer booking time |
| Dermatology reassignment path | more handoffs, rework, touches, and cycle time |

Valid controlled defects include delayed and out-of-order ingestion, missing optional actor identifiers, unexpected valid channels, structurally valid source inconsistencies, and source retries. Duplicate-source attempts are labelled in ground truth but excluded from canonical events, preserving the database uniqueness constraint.

Ground truth is exported separately and never added to operational event metadata. The machine-readable manifest distinguishes configured probabilities, realised counts and rates, planted signals, expected qualitative findings, and the stable dataset fingerprint. All output is fictional and must not be represented as evidence about real providers or clinical outcomes.

Generate the small development preset:

```bash
uv run workflowtwin generate --preset tiny
```

Generate an independently loadable demonstration bundle:

```bash
uv run workflowtwin generate \
  --preset demo \
  --seed 42 \
  --run-id northstar-demo-42 \
  --dataset-output artifacts/generation/demo-dataset.json \
  --validation-output artifacts/generation/demo-validation.json

uv run workflowtwin validate \
  --dataset artifacts/generation/demo-dataset.json \
  --report-output artifacts/generation/demo-independent-validation.json
```

Persist a run after applying migrations:

```bash
uv run alembic upgrade head
uv run workflowtwin generate --preset demo --run-id northstar-demo-42 --persist
```

Replaying a completed run with the same fingerprint returns `already_completed`; using its identifier for different data fails. Cases and canonical events flush in configurable batches inside one transaction. A failure rolls back all operational rows and records the run as failed.

Presets are `tiny` (30 cases), `demo` (1,000), and `full` (10,000). Generated files under `artifacts/generation/` are ignored and should not be committed. See the [generator architecture](docs/architecture/synthetic-data-generation.md) and [ADR 0003](docs/decisions/0003-deterministic-synthetic-generation.md).

## Planned metrics

Operational metrics will be defined with explicit timestamps, populations, and units:

| Area | Metrics |
| --- | --- |
| Flow | end-to-end cycle time, active processing time, waiting time, throughput |
| Friction | rework loops, repeat activity rate, manual touches, handoff count |
| Reliability | stuck-case rate, automation failure rate, human override rate |
| Adoption | eligible cases, automation acceptance, usage, completion rate |
| Impact | staff time avoided, cost per referral, capacity released, estimated savings |

Clinical outcomes and treatment quality are outside the product's decision scope. Simulated improvements will be labelled as estimates and kept distinct from observed production performance.

## Roadmap

1. **Foundation (completed):** API skeleton, settings, structured logging, testing, PostgreSQL containers, migration tooling, documentation, and quality gates.
2. **Referral event model (completed):** versioned contracts, explicit vocabulary, UTC timestamps, append-only PostgreSQL persistence, first migration, metric semantics, and ten deterministic fixtures.
3. **Synthetic dataset (completed):** seeded configuration, business-time generation, planted bottlenecks, controlled defects, separate ground truth, manifests, validation, CLI presets, and idempotent batch persistence.
4. **Operational metrics and baseline analysis:** implement the documented deterministic metrics, produce case and cohort summaries, and establish a reproducible baseline before process mining.
5. **Process intelligence:** reconstruct variants with PM4Py where useful, detect the leading bottleneck, and expose evidence through the API.
6. **Recommendation and simulation:** add a deterministic first recommendation, model its assumptions, simulate its operational effect, and compare metric snapshots.
7. **Decision interface:** build a focused React view for exploring flows, evidence, assumptions, and baseline-versus-simulated impact.
8. **Safe automation pilot:** add approval gates, idempotency, audit records, failure handling, and a narrow administrative automation in a controlled environment.
9. **Evaluation and observability:** instrument traces and model/provider calls, measure quality and adoption, monitor drift and failure modes, and report realised business impact.

## Repository layout

```text
apps/                       deployable application notes and future web app
docs/architecture/          system design documentation
docs/decisions/             architecture decision records
src/workflowtwin/           Python application package
tests/                      automated tests
alembic/                    database migrations
Dockerfile                  API image
docker-compose.yml          local API and PostgreSQL stack
pyproject.toml              dependencies and quality-tool configuration
```

## Getting started

Prerequisites: Python 3.12 and either `uv` or standard `pip`. Docker is optional.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn workflowtwin.main:app --reload
```

The API is available at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`.

Run the quality gates:

```bash
pytest
ruff check .
ruff format --check .
mypy src tests alembic
```

Or run the local stack:

```bash
docker compose up --build
```

PostgreSQL is reachable from the host on `POSTGRES_PORT` (default `5432`); the API waits for its health check and starts on port `8000`. Development credentials in Compose are local defaults and must not be used in deployed environments.

Apply or inspect database migrations:

```bash
uv run alembic upgrade head
uv run alembic current
```

PostgreSQL integration tests are opt-in so the normal unit suite remains self-contained. Point them at an isolated, migrated database:

```bash
WORKFLOWTWIN_TEST_DATABASE_URL=postgresql+asyncpg://workflowtwin:workflowtwin@localhost:5432/workflowtwin \
  uv run pytest -m postgres
```

## API foundation

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | service identity and documentation link |
| `GET` | `/health` | liveness status and service metadata |

The health endpoint is intentionally a liveness check in this release. Database readiness will be added when the application first depends on database access.

## Safety and evidence

WorkflowTwin analyses administrative workflow performance. Future automation recommendations must be explainable, auditable, reversible where practical, and subject to human approval when risk requires it. Patient-facing or clinical decisions are not delegated to this system. No result derived from fictional or synthetic Northstar Clinics data should be represented as evidence about a real provider or real clinical outcomes.
