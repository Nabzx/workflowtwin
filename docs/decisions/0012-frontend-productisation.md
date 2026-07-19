# ADR 0012: Productise the supported fictional pilot with React

- **Status:** Accepted
- **Date:** 2026-07-19

## Context

WorkflowTwin has completed its backend research and validation path. The remaining
need is to make its operational evidence, trade-offs, and safety controls legible to
a recruiter or stakeholder without exposing raw research artefacts or reopening
detector development.

## Decision

Build a static React and TypeScript application with Vite, React Router, TanStack
Query, React Flow, Recharts, Vitest, React Testing Library, and Playwright.

The frontend will consume compact prepared demo artefacts through typed FastAPI
endpoints. Existing pilot endpoints will retain mutation ownership. React local
state is sufficient for UI concerns; a heavyweight global store is not justified.

The product will show only the supported V2 intake contract and
`completeness-review-detector-v1`. Earlier strict-contract experiments will appear
only as a concise evaluation journey.

No LLM will be added. The selected use case depends on deterministic requirements,
traceable field state, and bounded administrative text. Generative behaviour would
increase risk and make the evidence chain less clear without improving the demo.

Public-demo changes will remain fictional, bounded, reversible, and resettable. No
send route, real integration, arbitrary recipient, clinical decision, or referral
event mutation will exist.

Observability will use structured application logs, request identifiers, timings,
health/readiness routes, and a safe system-status response. A commercial telemetry
service is unnecessary for this portfolio deployment.

Deployment will be intentionally simple: one production container can serve the
compiled frontend and FastAPI API, while local Compose retains separate frontend,
API, and PostgreSQL services. Prepared evidence is immutable; shared pilot state is
ephemeral and resettable.

Backend feature development stops after the read API, reset safety, and lightweight
observability needed to present the completed product.

## Consequences

- The interface is independently testable and strongly typed at its HTTP boundary.
- Prepared responses are fast, deterministic, small, and free of internal paths and
  hidden labels.
- The demo tells one coherent product story instead of surfacing every experiment.
- A shared public pilot session is not durable or isolated between visitors; the UI
  and documentation state this limitation.
- React Flow, Recharts, and PM4Py require dependency and licence review before any
  commercial distribution.
- Future work can replace the prepared artefact repository or pilot state store
  behind existing service boundaries without redesigning the frontend.

## Alternatives considered

- **Server-rendered templates:** smaller dependency surface, but weaker fit for the
  interactive graph and mutation workflow.
- **Next.js:** unnecessary server and deployment complexity for a static portfolio
  client.
- **A global state framework:** duplicates TanStack Query and component state.
- **Directly serving large research artefacts:** leaks internal detail and creates an
  unstable, slow public contract.
- **Separate hosted frontend and API:** valid, but adds cross-origin and two-service
  operational overhead without improving this demonstration.
