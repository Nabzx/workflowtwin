# Controlled intervention design and counterfactual simulation

Northstar Clinics, all records, research, decisions, and results are fictional. This subsystem
models administrative workflow behavior under explicit assumptions. It has not deployed an
automation, changed a production workflow, achieved a saving, or established a clinical conclusion.

## Selection and intervention boundary

The fixed 1,000-case portfolio contains one controlled-prototype candidate:
`opportunity-7def8c82e8b589e5`, GP-practice intake completeness validation. Selection first requires
the controlled-prototype portfolio section and no hard eligibility failure. If several candidates
exist during initial selection, lower risk, greater readiness, stronger confidence, higher priority,
and stable identifier form the documented tie-break sequence. The 10,000-case scale benchmark keeps
the already selected intervention fixed rather than selecting a different opportunity from the
larger portfolio.

The version 1 intervention observes versioned structured administrative fields, recommends a
completeness review, requests approval from a referral administrator, and records a simulated
system-assisted validation only after approval. It cannot interpret clinical text, infer diagnosis
or urgency, change service line or team, reject or discard a referral, send external communication,
use protected attributes, rank staff, or alter source facts.

```text
Observed baseline and process evidence
        |
eligible opportunity portfolio
        |
versioned intervention + policy
        |
case eligibility + isolated simulation oracle
        |
recommendation -> human review -> approval / rejection / timeout
        |
immutable counterfactual event overlay or unchanged manual fallback
        |
existing baseline and process engines
        |
comparisons + scenarios + sensitivity + decision
```

## Eligibility and policy

Case eligibility requires the GP-practice cohort, schema version 1, referral-received and
completeness-check events in a coherent sequence, the configured period, and no earlier intervention
marker. Every excluded case retains reason codes. Historical terminal cases can be evaluated because
the policy decision is placed retrospectively at referral receipt; their current status is not used
to imply that a live terminal case could be changed.

The policy emits explicit final states: not eligible, observe only, approved simulated action,
reviewer rejection, manual fallback, policy block, simulation failure, or rollback. Review turnaround
and manual-touch overhead remain present when no workflow event changes. A high detector confidence
cannot skip review. False positives that pass simulated review are rolled back before an external
request; no new patient-facing event is inserted.

The source dataset does not contain deployable structured missing-field values. For detector
evaluation only, a private simulation oracle labels a historical missing-information path as
incomplete. The oracle drives a probabilistic detector outcome but is never passed to the policy.
Generator ground truth is not required and produces identical decisions when omitted.

## Counterfactual event overlay

Operational `ReferralEvent` objects are immutable. Approved true-positive paths produce replacement
events in a separate in-memory `AnalysisInput`:

- the first completeness check becomes a system-assisted validation after modelled system and review
  delay;
- an existing missing-information request remains a staff-controlled event and can move only after
  approval;
- downstream intervals shift with that existing request so event order stays coherent;
- repeated completeness checks can become system-assisted under the sampled effectiveness rule;
- terminal case projections follow their counterfactual terminal event time.

Each replacement has a UUID5 identifier derived from simulation run, source event, and rule; a new
external identity; source and counterfactual records; change types; timing adjustment; reviewer
action; warning; and provenance. Audit-only review and failure decisions remain outside the process
activity vocabulary, avoiding a false business activity or a new PM4Py mapping. Source ingestion
timestamps are retained only as provenance.

Validation checks domain contracts, unique identifiers, case relationships, timezone awareness,
event order, forbidden metadata, provenance, policy/change agreement, and source immutability.
Expected failures and adverse paths are separated from invalid output.

## Determinism and analysis reuse

Every case owns a `random.Random` stream seeded from SHA-256 content containing simulation seed,
case UUID, intervention version, and scenario. Reordering cases cannot move another case's random
draws. Stable simulation, scenario, counterfactual dataset, baseline, process, intervention, policy,
and complete-analysis fingerprints exclude wall time, local paths, Markdown, and object identity.

The counterfactual contracts pass through the existing `BaselineAnalyzer` and
`ProcessMiningAnalyzer`. Metric and process summaries are never edited directly. The original
baseline configuration is reused with a counterfactual source fingerprint; the existing PM4Py
adapter reconstructs variants, transitions, conformance, deviations, complexity, and bottlenecks.

## Comparison semantics

Comparisons preserve unavailable values and omit relative change when baseline is zero. Effects are
labelled intended direct, secondary operational, control overhead, adverse, or unchanged. First-pass
completeness is intentionally unchanged: validation cannot invent missing information. Manual
touches and time to first completeness check are direct measures; duration and waiting are secondary;
review, fallback, and recovery touches are control overhead.

Burden uses the opportunity's visible five-minute touch and GBP 24/hour assumptions. Review queue
delay is elapsed time, not staff labour. Baseline workflow-touch burden, simulated workflow burden,
review/fallback/recovery burden, gross difference, net difference, addressable upper bound, and
fictional cost proxies stay separate. A result above the upper bound is warned, never presented as a
guaranteed saving or ROI.

## Scenarios, sensitivity, and thresholds

Conservative, central, optimistic, and adverse presets specify rollout, effectiveness, detector
error, review acceptance and timeout, review/system delay, fallback, failure, rollback, and recovery.
Even the optimistic scenario retains error and failure. One-at-a-time sensitivity tests low/high
effectiveness, false positives, fallback, and reviewer delay. A coarse threshold sweep covers false
positives, fallback, and effectiveness. Boundaries are modelled assumption-dependent observations,
not production break-even guarantees.

## Shadow-mode decision

Decision criteria cover safety, counterfactual validity, direct effect, net burden, upper bound,
reversibility, observability, sensitivity, human review, and failure recovery. Statuses are proceed
to shadow mode, proceed only with controls, revise design, gather evidence, or do not proceed.
Negative conservative/adverse results require revision. The central scenario can proceed only with
additional controls when sensitivity contains a plausible positive region. No status approves live
deployment.

Future shadow mode must be recommendation-only and define versioned inputs/outputs, decision logs,
review states, approval, audit, rollback, fallback, metrics, alerting, bounded cohort and observation
period, promotion gates, and stop conditions. It must never modify the workflow.

## Outputs and limitations

The CLI writes full analysis JSON, stakeholder Markdown, visualisation-ready comparison JSON, and
optional case JSONL. Comparison data contains no UI colours or coordinates. Existing files are
protected unless `--force` is supplied.

- Historical path labels are useful for software evaluation but are not deployable features.
- Point events support deterministic flow reconstruction, not causal inference.
- Review behavior and costs are assumptions, not observations from real staff.
- Replaced events preserve the version 1 vocabulary; control activity performance is reported
  separately rather than mined as workflow behavior.
- The in-memory 10,000-case benchmark is not a production scalability target.
- No LLM, predictive model, external integration, live agent, production action, or realised impact
  exists.
