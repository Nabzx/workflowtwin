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

This foundation release deliberately includes only the API shell, configuration, logging, tests, database tooling, containers, and architecture documentation. It contains no synthetic data generation, process mining, LLM calls, workflow automation, dashboard, authentication, or external integration.

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

1. **Foundation (current):** API skeleton, settings, structured logging, testing, PostgreSQL containers, migrations, documentation, and quality gates.
2. **Synthetic event model:** define referral cases and event contracts, create a reproducible scenario generator, persist events, and document data assumptions.
3. **Process intelligence:** reconstruct variants with PM4Py where useful, implement metric definitions, detect the leading bottleneck, and expose evidence through the API.
4. **Recommendation and simulation:** add a deterministic first recommendation, model its assumptions, simulate its operational effect, and compare metric snapshots.
5. **Decision interface:** build a focused React view for exploring flows, evidence, assumptions, and baseline-versus-simulated impact.
6. **Safe automation pilot:** add approval gates, idempotency, audit records, failure handling, and a narrow administrative automation in a controlled environment.
7. **Evaluation and observability:** instrument traces and model/provider calls, measure quality and adoption, monitor drift and failure modes, and report realised business impact.

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
mypy src tests
```

Or run the local stack:

```bash
docker compose up --build
```

PostgreSQL is reachable from the host on port `5432`; the API waits for its health check and starts on port `8000`. Development credentials in Compose are local defaults and must not be used in deployed environments.

## API foundation

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | service identity and documentation link |
| `GET` | `/health` | liveness status and service metadata |

The health endpoint is intentionally a liveness check in this release. Database readiness will be added when the application first depends on database access.

## Safety and evidence

WorkflowTwin analyses administrative workflow performance. Future automation recommendations must be explainable, auditable, reversible where practical, and subject to human approval when risk requires it. Patient-facing or clinical decisions are not delegated to this system. No result derived from fictional or synthetic Northstar Clinics data should be represented as evidence about a real provider or real clinical outcomes.

