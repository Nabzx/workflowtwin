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

The current release includes the API foundation, versioned referral events, seeded synthetic data,
a deterministic baseline engine, explainable PM4Py-backed process reconstruction, an evidence-gated
administrative opportunity portfolio, and controlled counterfactual intervention simulation. It
also contains a recommendation-only, ingestion-ordered shadow detector with human-review contracts,
hidden-label evaluation, tamper-evident audit chaining, stop conditions, and promotion gates. It
contains no LLM calls, live recommendations, workflow automation, dashboard, authentication, or
external integration.

## Architecture

WorkflowTwin begins as a modular monolith: one FastAPI service with explicit domain, service, and infrastructure boundaries, backed by PostgreSQL. This keeps transactions and local development simple while leaving analysis work separable from HTTP and persistence concerns.

```text
Client / future React app
          |
      FastAPI API
          |
   Application services
      /          \
 Domain model   Analysis adapters (isolated PM4Py; future LLM provider)
          |
 SQLAlchemy repositories
          |
      PostgreSQL
```

- `src/workflowtwin/api`: HTTP routes and transport schemas.
- `src/workflowtwin/analytics`: timelines, metrics, cohorts, quality, findings, benchmark evaluation, and reports.
- `src/workflowtwin/process_mining`: event-log mapping, DFG and variant statistics, PM4Py adapter, reference conformance, process findings, graph data, and reports.
- `src/workflowtwin/opportunities`: evidence linking, fictional research, archetypes, candidate rules, safety gates, scoring, portfolio construction, benchmark evaluation, and reports.
- `src/workflowtwin/simulation`: intervention selection, policy, counterfactual overlays, analysis reuse, comparisons, sensitivity, decisions, and reports.
- `src/workflowtwin/shadow`: intake snapshots, as-of replay, deterministic detection, policy, recommendation lifecycle, reviews, audit chaining, quality, burden, stop conditions, and promotion gates.
- `src/workflowtwin/core`: runtime configuration and cross-cutting concerns.
- `src/workflowtwin/domain`: workflow concepts and invariants, added as the MVP requires them.
- `src/workflowtwin/services`: use-case orchestration, independent of HTTP.
- `src/workflowtwin/infrastructure`: persistence and external provider adapters.
- `apps/web`: reserved for the future React and TypeScript user interface.

The API uses Pydantic settings, structured JSON logging outside local development, SQLAlchemy and
Alembic for persistence, and dependency inversion at real provider boundaries. PM4Py is contained
behind a typed adapter; no LLM SDK or agent framework is present. See the
[technical architecture](docs/architecture/technical-architecture.md),
[process architecture](docs/architecture/process-reconstruction-and-conformance.md),
[opportunity architecture](docs/architecture/automation-opportunity-identification.md),
[simulation architecture](docs/architecture/intervention-design-and-simulation.md), and the
[shadow architecture](docs/architecture/recommendation-shadow-mode.md). Decisions are recorded in
[ADR 0007](docs/decisions/0007-counterfactual-simulation.md) and
[ADR 0008](docs/decisions/0008-recommendation-shadow-mode.md).

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

## Baseline analysis

The analyzer builds immutable case timelines ordered by `(event_at, event_id)`, deduplicates source identities, and calculates metrics from event semantics. Case results retain units, exact/estimated/partial status, source event IDs, assumptions, warnings, and exclusion reasons. Cohorts cover referral source, service line, source system, assigned team when structured metadata is present, and terminal outcome.

Supported measures include closed-case duration and cycle time, partial open-case age, business-hours waiting, a labelled manual-touch processing proxy, touches, internal handoffs, rework, first-pass completeness, completeness-check and booking times, assignment wait, scheduling failures, reassignments, stuck status, and ingestion quality. Missing boundaries remain unavailable or not applicable rather than becoming zero.

Analyze an exported bundle and optionally evaluate findings against separate synthetic labels:

```bash
uv run workflowtwin analyze \
  --dataset artifacts/generation/demo-dataset.json \
  --manifest artifacts/generation/northstar-demo-42-manifest.json \
  --ground-truth artifacts/generation/northstar-demo-42-ground-truth.json \
  --report-output artifacts/analysis/demo-report.md \
  --analysis-output artifacts/analysis/demo-analysis.json \
  --case-metrics-output artifacts/analysis/demo-cases.jsonl
```

Analyze the same completed generation run from PostgreSQL:

```bash
uv run workflowtwin analyze \
  --from-database \
  --generation-run northstar-demo-42 \
  --report-output artifacts/analysis/northstar-demo-42.md \
  --analysis-output artifacts/analysis/northstar-demo-42.json
```

The primary JSON contains configuration, overall and cohort metrics, quality coverage, findings, optional benchmark evaluation, and a SHA-256 fingerprint that excludes wall-clock time and synthetic labels. Markdown is a concise stakeholder view; optional JSONL holds case results. Existing files are protected unless `--force` is supplied.

Finding rules report only cohorts meeting the configured minimum size and use explicit absolute or relative materiality thresholds. They surface descriptive differences such as lower completeness or longer waits; they do not claim statistical significance and are not AI-generated recommendations. With the fixed demo seed, all four planted patterns are detected, with GP rework also appearing as an expected overlapping effect.

See the [analysis architecture](docs/architecture/operational-metrics-analysis.md), [metric definitions](docs/architecture/metric-definitions.md), and [ADR 0004](docs/decisions/0004-operational-metrics.md).
Local tiny, demo, and 10,000-case measurements are recorded in the [baseline benchmark](docs/architecture/baseline-analysis-benchmark.md).

## Process reconstruction and conformance

WorkflowTwin maps all 18 version 1 referral event types to stable administrative activities and
builds canonical traces ordered by `(event_at, event_id)`. Source retries are deduplicated, genuine
repeats remain visible, and ingestion order is retained only as quality evidence. Owned statistics
cover activities, start/end states, transitions, elapsed and business-time delay, variants, loops,
manual-work context, handoffs, complexity, deviations, and candidate bottlenecks.

The isolated PM4Py 2.7.23.2 adapter verifies a directly-follows graph, discovers one structured
model with Inductive Miner, and performs token-based replay against two versioned Petri nets:

- `northstar-strict-v1`: the nine-step successful path from submission to completion.
- `northstar-governed-v1`: documented information loops, limited rerouting, scheduling retries,
  cancellation, rejection, non-response, completion, and other administrative closure.

Governed conformance does not imply speed, quality, or desirability. Non-conformance can represent
missing data, a legitimate exception, or reference-model scope rather than an operational error.
Candidate bottlenecks describe observed associations and always require human investigation.

Run process analysis on an exported dataset:

```bash
uv run workflowtwin process-mine \
  --dataset artifacts/generation/demo-dataset.json \
  --manifest artifacts/generation/northstar-demo-42-manifest.json \
  --baseline-analysis artifacts/analysis/demo-analysis.json \
  --ground-truth artifacts/generation/northstar-demo-42-ground-truth.json \
  --analysis-output artifacts/process/demo-process-analysis.json \
  --report-output artifacts/process/demo-process-report.md \
  --graph-output artifacts/process/demo-process-graph.json \
  --case-output artifacts/process/demo-process-cases.jsonl \
  --visualisation-directory artifacts/process/demo-visualisations
```

Use `--from-database --generation-run northstar-demo-42` for a completed persisted run. Existing
outputs are protected unless `--force` is supplied. SVG generation is optional and reports a
warning if Graphviz is unavailable; core JSON and Markdown analysis remains valid.

For the fixed 1,000-case seed, process mining reconstructs 17 activities, 23 transitions, and 57
variants. Strict/governed fully conforming rates are 36.3%/87.1%, and all four planted patterns are
detected after discovery. See the
[process benchmark](docs/architecture/process-mining-benchmark.md) for demo and 10,000-case results.

## Evidence-backed automation opportunities

WorkflowTwin combines the baseline and process artifacts with a versioned, explicitly fictional
research pack. It validates artifact lineage, creates stable evidence references, preserves
contradictory user evidence, and applies six transparent administrative candidate rules. Seven
archetypes define eligibility, oversight, success measures, known failure modes, and safety limits.

Each candidate reports observed burden, eligibility, value, readiness, risk, confidence, evidence
gaps, assumptions, controls, and future success metrics separately. Clinical judgement, treatment,
clinical prioritisation, prohibited data use, and governance failures are hard exclusions outside the
weighted priority score. Addressable burden is only an upper bound; expected benefit remains
unavailable until a later intervention and counterfactual milestone.

Run opportunity identification after producing compatible baseline and process artifacts:

```bash
uv run workflowtwin identify-opportunities \
  --baseline-analysis artifacts/analysis/demo-analysis.json \
  --process-analysis artifacts/process/demo-process-analysis.json \
  --research-pack data/research/northstar-research-v1.json \
  --manifest artifacts/generation/northstar-demo-42-manifest.json \
  --ground-truth artifacts/generation/northstar-demo-42-ground-truth.json
```

The command writes full analysis JSON, stakeholder Markdown, compact portfolio JSON, and an
evidence-network dataset under `artifacts/opportunities/`. Existing files are protected unless
`--force` is supplied. Ground truth is optional and is consulted only after the portfolio exists.

On the fixed demo, seven raw candidates become six after stable deduplication: one is eligible only
for a controlled prototype and five need further discovery. All four planted administrative
patterns are detected, while two additional quality-monitoring candidates remain visible. See the
[opportunity architecture](docs/architecture/automation-opportunity-identification.md),
[ADR 0006](docs/decisions/0006-opportunity-identification.md), and
[local benchmark](docs/architecture/opportunity-identification-benchmark.md).

## Controlled counterfactual simulation

WorkflowTwin converts the sole fixed-demo controlled-prototype opportunity into a versioned,
recommendation-only structured completeness intervention. It evaluates GP-practice cases at referral
receipt, models detector errors and delayed administrator review, and creates a separate event overlay
only after simulated approval. Source events remain unchanged. False positives, rejections, timeouts,
service failures, fallback, and rollback remain visible and add control burden.

Run the central fixed-demo scenario:

```bash
uv run workflowtwin simulate-intervention \
  --dataset artifacts/generation/demo-dataset.json \
  --manifest artifacts/generation/northstar-demo-42-manifest.json \
  --baseline-analysis artifacts/analysis/demo-analysis.json \
  --process-analysis artifacts/process/demo-process-analysis.json \
  --opportunity-analysis artifacts/opportunities/demo-opportunities.json \
  --ground-truth artifacts/generation/northstar-demo-42-ground-truth.json \
  --scenario central
```

The command writes analysis JSON, stakeholder Markdown, visualisation-ready comparison JSON, and
optional case JSONL. It supports a completed PostgreSQL generation run with `--from-database` and
`--generation-run RUN_ID`; simulated events are never written to operational tables.

The fixed central scenario models fewer manual touches and a faster first completeness check, but
control overhead leaves net burden slightly negative. Conservative and adverse scenarios are more
negative; only the optimistic scenario is positive. The central decision is therefore **proceed only
with additional controls** for a future shadow-mode study, not deployment approval. See the
[simulation architecture](docs/architecture/intervention-design-and-simulation.md),
[ADR 0007](docs/decisions/0007-counterfactual-simulation.md), and
[benchmark](docs/architecture/intervention-simulation-benchmark.md).

## Recommendation-only shadow mode

The next evidence step is deliberately narrower than the simulated intervention. WorkflowTwin
replays separate, versioned fictional intake snapshots in source-availability order and recommends a
human administrative completeness review only when current structured evidence names a concrete
concern. GP-practice membership alone cannot trigger. Unknown or unsupported required evidence causes
abstention, and later structured corrections can retract a recommendation.

Detector inputs contain no operational future events, hidden labels, outcomes, reviews, clinical
fields, protected attributes, or free text. Hidden timing-aware labels and the deterministic fictional
benchmark reviewer live behind an evaluation-only oracle boundary. Recommendations never update
referral cases or events, change status or routing, reject or approve a case, or communicate
externally.

Generate separate intake and label artefacts when creating a bundle:

```bash
uv run workflowtwin generate \
  --preset demo \
  --seed 42 \
  --run-id northstar-demo-42 \
  --dataset-output artifacts/generation/demo-dataset.json \
  --intake-snapshots-output artifacts/generation/demo-intake-snapshots.jsonl \
  --shadow-labels-output artifacts/generation/demo-shadow-labels.jsonl
```

Run, review, and evaluate shadow outputs as separate stages:

```bash
uv run workflowtwin shadow-run \
  --dataset artifacts/generation/demo-dataset.json \
  --manifest artifacts/generation/northstar-demo-42-manifest.json \
  --intake-snapshots artifacts/generation/demo-intake-snapshots.jsonl \
  --opportunity-analysis artifacts/opportunities/demo-opportunities.json \
  --simulation-analysis artifacts/simulation/demo-central.json

uv run workflowtwin shadow-review \
  --run artifacts/shadow/northstar-demo-shadow-v1-strict-run.json \
  --recommendations artifacts/shadow/northstar-demo-shadow-v1-strict-recommendations.jsonl \
  --benchmark-labels artifacts/generation/demo-shadow-labels.jsonl \
  --validated-reviews-output artifacts/shadow/demo-reviews.jsonl

uv run workflowtwin shadow-evaluate \
  --run artifacts/shadow/northstar-demo-shadow-v1-strict-run.json \
  --recommendations artifacts/shadow/northstar-demo-shadow-v1-strict-recommendations.jsonl \
  --reviews artifacts/shadow/demo-reviews.jsonl \
  --audit artifacts/shadow/northstar-demo-shadow-v1-strict-audit.jsonl \
  --intake-snapshots artifacts/generation/demo-intake-snapshots.jsonl \
  --evaluation-labels artifacts/generation/demo-shadow-labels.jsonl \
  --evaluation-output artifacts/shadow/demo-evaluation.json \
  --report-output artifacts/shadow/demo-report.md \
  --visualisation-output artifacts/shadow/demo-visualisation.json
```

On the fixed 1,000-case replay, strict mode produced 224 recommendations at 92.86% precision,
83.20% recall, and 1.153 fictional false-positive review hours. Balanced and exploratory increased
coverage but reduced precision and increased burden. Strict passed safety, audit, precision,
false-positive burden, rejection, completion, and latency gates but exceeded the 20% recommendation
capacity threshold at 22.4%. The 10,000-case strict run repeated that result at 94.21% precision and
20.72% coverage. The deterministic assessment is therefore **pause due to stop condition**, requiring
detector revision rather than a pilot.

See the [shadow architecture](docs/architecture/recommendation-shadow-mode.md),
[ADR 0008](docs/decisions/0008-recommendation-shadow-mode.md), and
[benchmark](docs/architecture/shadow-mode-benchmark.md). All reported review time and cost are
fictional capacity proxies. Promotion readiness would not authorise production or autonomous action,
and no clinical or real-world impact conclusion can be drawn.

### Versioned detector refinement

The original strict detector is frozen as `strict-v1`. A separately fingerprinted `strict-v2`
confirms explicit document absence after a 120-minute logical window, then passes confirmed signals
to explainable priority and fictional reviewer-capacity controls. Detector positives remain distinct
from active, surfaced, reviewed, deferred, and observe-only recommendations, so capacity cannot be
mistaken for better detector quality.

```bash
uv run workflowtwin shadow-refine --force  # development and validation only
uv run workflowtwin shadow-holdout         # locked 10,000-case split, once
```

The pre-registered development and validation result is `do_not_promote`: confirmation reduces
volume and false-positive review time but breaches the recall gate and adds 120 minutes of latency.
The untouched 10,000-case holdout confirmed that decision: `strict-v2` produced 1,686 positives at
93.12% precision and 51.19% recall, versus 2,048 positives at 93.02% precision and 62.11% recall for
`strict-v1`. WorkflowTwin therefore remains recommendation-only shadow software. See the
[refinement architecture](docs/architecture/shadow-detector-refinement.md) and
[ADR 0009](docs/decisions/0009-shadow-detector-refinement.md).

## Metrics roadmap

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
4. **Operational metrics and baseline analysis (completed):** deterministic timelines and metrics, cohort summaries, quality coverage, material findings, synthetic benchmark evaluation, reproducible reports, and file/database CLI analysis.
5. **Process intelligence (completed):** reconstruct DFGs and structured models, identify stable variants and loops, compare strict/governed conformance, reconcile baseline evidence, and export process artefacts.
6. **Evidence-backed automation opportunities (completed):** link baseline, process, quality, and fictional research evidence; preserve contradictions; apply hard safety gates; rank bounded administrative opportunities; and export an auditable portfolio without recommending, automating, or simulating.
7. **Controlled intervention simulation (completed):** select the eligible completeness opportunity, define a guarded policy, model human review and failure paths, create immutable event overlays, rerun baseline/process analysis, compare four scenarios, test sensitivity, and decide shadow-mode suitability.
8. **Shadow-mode intervention prototype (completed):** replay ingestion-ordered structured snapshots; generate recommendation-only outputs; validate fictional reviews; measure precision, recall, abstention, false-positive burden, latency, audit and policy quality; and enforce stop conditions and promotion gates.
9. **Detector revision and continued shadow evaluation (completed, not promoted):** freeze `strict-v1`; compare fingerprinted `strict-v2` on registered splits; separate detector quality from fictional capacity; report missed positives, cohorts, chronology, Pareto trade-offs, and sensitivity; remain in recommendation-only shadow mode because recall fails the gate.
10. **Decision interface:** build a focused React view for exploring flows, evidence, assumptions, and observed-versus-simulated results.
11. **Safe automation pilot:** only after every mandatory shadow gate passes, add approvals, idempotency, failure handling, and one reversible fictional administrative action.
12. **Evaluation and observability:** instrument traces and provider calls, measure quality and adoption, monitor observed variation and failure modes, and report realised business impact only when it exists.

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
pytest --cov
ruff check .
ruff format --check .
mypy src tests alembic scripts
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

PM4Py's community distribution is licensed under AGPL-3.0. This portfolio uses it through an
isolated adapter; any commercial distribution or network deployment must complete an appropriate
license review and obtain a commercial license where required.
