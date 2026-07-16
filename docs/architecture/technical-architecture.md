# Technical architecture proposal

## Objective

Build the smallest production-minded platform that can turn synthetic referral events into an auditable operational bottleneck finding and a baseline-versus-simulation comparison. Northstar Clinics and all initial data are fictional.

## Architectural style

Start with a modular monolith deployed as one FastAPI service. Keep HTTP transport, application orchestration, domain rules, and infrastructure adapters separate in code. This offers clear ownership and testability without the operational cost of premature services or asynchronous infrastructure.

PostgreSQL is the source of truth for referral cases, immutable workflow events, analysis runs, recommendations, simulation runs, and metric snapshots. Long-running analysis can initially run behind an application service; a job queue should be introduced only when measured request duration or reliability requires it.

## Component boundaries

| Component | Responsibility | Must not own |
| --- | --- | --- |
| API | validation, status codes, transport schemas | process analysis or persistence rules |
| Services | use-case orchestration and transaction boundaries | framework-specific HTTP behavior |
| Domain | workflow vocabulary, invariants, metric definitions | SQLAlchemy sessions or provider SDKs |
| Infrastructure | repositories, PM4Py adapter, provider adapters | business decisions |
| PostgreSQL | durable operational and audit state | transient presentation state |

The boundaries are directories, not independent deployables. Interfaces should be added when there is a real adapter to substitute, especially persistence and LLM providers, rather than created speculatively.

## Initial data direction

The event model should preserve source facts and analysis provenance. A workflow event will eventually include a stable case identifier, activity, event time, actor or role, source, relevant administrative attributes, and ingestion metadata. Derived metrics and recommendations should reference an analysis run and input-data version so a finding can be reproduced.

Synthetic datasets must be visibly labelled, seeded for reproducibility, contain no real personal data, and describe the assumptions that created bottlenecks. Schema and metric definitions should avoid encoding the fictional customer's quirks as universal healthcare rules.

## API and execution

- FastAPI and Pydantic validate external contracts and publish OpenAPI documentation.
- Application settings load from environment variables with a `WORKFLOWTWIN_` prefix.
- Structured logs include event names and service context; correlation IDs and OpenTelemetry follow once multi-step use cases exist.
- SQLAlchemy 2 provides persistence; Alembic owns schema evolution.
- PM4Py will sit behind an analysis adapter once process reconstruction begins.
- LLM use is optional and provider-neutral. Deterministic computations and evidence retrieval remain outside prompts.

## Safety and auditability

The system is restricted to operational and administrative improvement. It must not diagnose, prioritise clinical urgency, or recommend treatment. A future recommendation record should include evidence, assumptions, expected effect, eligibility, confidence or uncertainty, approval state, model/provider metadata if applicable, and a link to observed outcomes. Automations require scoped permissions, input validation, idempotency, failure recovery, and human escalation paths.

## Deployment direction

Docker Compose supports local development with API and PostgreSQL containers. A production deployment should use a managed PostgreSQL service, externally managed secrets, TLS, least-privilege identities, automated migrations, backups, health/readiness probes, and separate worker processes if long-running work is introduced. The future React application can be deployed independently while consuming the versioned API.

## Quality strategy

- Unit-test domain metrics and recommendation rules with boundary cases.
- Integration-test repositories against PostgreSQL.
- Contract-test API schemas and error behavior.
- Use fixed synthetic scenarios as evaluation fixtures for known bottlenecks.
- Compare process reconstruction and metrics to hand-calculated expected values.
- Track recommendation precision, simulation error, automation reliability, adoption, and realised operational impact.

## Key risks

| Risk | Initial control |
| --- | --- |
| Synthetic findings presented as real evidence | persistent labelling in data, UI, and documentation |
| Incorrect event semantics produce misleading metrics | versioned schemas, metric definitions, validation, fixtures |
| Automation crosses into clinical decision-making | explicit scope policy, approval gates, audited actions |
| LLM output appears authoritative | evidence links, structured outputs, deterministic validation |
| Architecture becomes complex before value is proven | modular monolith and just-in-time abstractions |

