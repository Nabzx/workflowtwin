# ADR 0001: Initial technology choices

- **Status:** Accepted
- **Date:** 2026-07-16

## Context

WorkflowTwin needs a credible foundation for an operational process-intelligence MVP. It must support typed APIs, event and analysis persistence, repeatable schema changes, process-mining experiments, future model providers, and a future browser interface. The current repository has no legacy constraints and the first release contains only foundation code.

## Decision

Use Python 3.12 with FastAPI, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL, pytest, Ruff, mypy, Docker, and Docker Compose.

Adopt a `src`-layout modular monolith with API, core, domain, services, and infrastructure packages. Keep one deployable API until scale, workload isolation, or team ownership creates evidence for another service.

Use `pydantic-settings` for environment-based configuration and `structlog` for structured logs. Reserve PM4Py for the process-analysis phase and introduce it only with process-mining code. Place any future LLM access behind a small provider interface owned by the application, not a framework-specific agent abstraction. Reserve React and TypeScript for the decision interface phase.

## Rationale

- Python has strong process-mining, data, and AI libraries; FastAPI provides typed HTTP contracts with little ceremony.
- PostgreSQL supports transactional operational data, JSON metadata where needed, and mature local and managed deployment options.
- SQLAlchemy separates persistence from business logic, while Alembic makes schema history reviewable.
- Ruff, mypy, and pytest provide fast, familiar quality gates appropriate for a portfolio project and a growing production codebase.
- A modular monolith keeps development and transactions simple while preserving meaningful boundaries.
- Delaying PM4Py, LLM SDKs, queues, and agent frameworks avoids dependencies without a current execution path.

## Consequences

The team must maintain boundary discipline inside one codebase. PostgreSQL is required for persistence integration tests and deployed use, though endpoint unit tests do not need it yet. CPU-heavy or long-running process analysis may later require a worker. Provider adapters and interfaces will be added only when actual model-backed use cases arrive.

This decision does not select a cloud, LLM vendor, job queue, frontend framework details beyond React and TypeScript, or production authentication scheme. Those require separate decisions when their constraints are known.

