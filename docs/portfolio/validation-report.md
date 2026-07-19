# WorkflowTwin v1.0 Validation Report

Validation was completed on 19 July 2026 against the release candidate built from
the 20-commit productisation milestone. Northstar Clinics, every referral, and all
reported outcomes are fictional. No test sent a message or changed a real workflow.

## Release acceptance

| Area | Result |
| --- | --- |
| Python tests | 212 passed and 16 PostgreSQL tests skipped in the default run; 91.84% coverage |
| PostgreSQL tests | 16 passed against PostgreSQL 17 after applying all Alembic migrations |
| Database schema | `alembic current`, `heads`, and `check` agreed on `20260716_0002 (head)` |
| Python quality | Ruff lint and format passed; strict mypy passed for 166 source files; lock file current |
| Frontend tests | 12 Vitest/Testing Library tests passed |
| Browser tests | 8 Playwright scenarios passed across desktop, mobile, accessibility, and recruiter flows; 2 project-specific scenarios were intentionally skipped |
| Frontend quality | ESLint, TypeScript type-checking, and the Vite production build passed |
| Docker | Fresh PostgreSQL, API, and web containers built and reached healthy state |
| Deployment | Public root, health, system status, API docs, and fictional demo endpoints responded successfully |
| Safety | Public reset returned `403`; no send endpoint, SMTP integration, credential, private key, or tracked local absolute path was found |
| Documentation | Every relative link referenced by the README resolves to a tracked file |

The default Python run collected 228 tests: 212 passed and the 16 tests marked
`postgres` were skipped as designed. Running that marker against the fresh container
database produced 16 further passes. Browser coverage includes the complete fictional
recommendation, draft edit, approval, mock task creation, audit verification, and
rollback journey.

## Performance observations

These are engineering smoke measurements from a local release build, not formal load
test results or service-level objectives.

| Observation | Result |
| --- | ---: |
| Supported full demo command | 5.44 s |
| Fast demo command | 0.58 s |
| Overview API, warm | 5.1 ms |
| Workflow API, warm | 5.1 ms |
| Pilot summary API, warm | 12.2 ms |
| Audit API, warm | 2.8 ms |
| Overview browser-ready time | 1,020 ms |
| Workflow graph navigation and render | 448 ms |
| Warm three-container Docker startup | 16.97 s |
| API container memory at idle | 50.04 MiB |
| Web container memory at idle | 7.32 MiB |
| PostgreSQL container memory at idle | 31.55 MiB |

The production frontend emits a 262.43 kB initial JavaScript bundle (82.39 kB gzip),
with the graph and chart libraries split into lazy chunks. A 390 x 844 browser check
reported a 390 px document width, and the dark theme resolved correctly. Lighthouse
was not added solely for this milestone; Playwright timing, accessibility scans, and
responsive screenshots provide the checked browser evidence.

## Public release

- Product: <https://workflowtwin.vercel.app>
- API documentation: <https://workflowtwin-api.vercel.app/docs>
- Health: <https://workflowtwin-api.vercel.app/health>
- Reported release version: `1.0.0`

The public frontend is a static Vite deployment and the separate API uses ephemeral
serverless process memory. The API accepts
bounded, validated revision and action replay data so the fictional multi-step review
journey survives execution on a fresh instance, while identifiers and idempotency
checks remain enforced. This is a portfolio deployment compromise, not the proposed
production persistence model. PostgreSQL-backed durable pilot state, authentication,
real tenant boundaries, message delivery, and production monitoring remain outside
the v1 scope.

## Residual limitations

- The fictional detector is evaluated on synthetic data and its results do not imply
  clinical effectiveness or real-world performance.
- The central simulation result remains negative; v1 correctly recommends controlled
  discovery rather than overstating automation value.
- Serverless cold starts vary and were not treated as a performance guarantee.
- The Vercel Python bundle is close to the provider's current function-size ceiling;
  a production deployment should split analytical workers from the product API.
- The React testing environment logs harmless zero-dimension chart warnings because
  jsdom does not perform layout; real-browser rendering is covered by Playwright.
