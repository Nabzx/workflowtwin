# Process reconstruction and conformance

Northstar Clinics, its referral events, and every process result are fictional. This analysis covers
administrative operations only. Conformance is structural evidence: it does not imply speed,
quality, clinical benefit, or employee performance.

## Pipeline and boundary

```text
ReferralCase + ReferralEvent
        |
canonical WorkflowTwin ProcessLog
        |
transitions + variants + complexity
        |
PM4Py adapter: DFG + Inductive Miner + token replay + optional SVG
        |
typed conformance + bottleneck candidates + graph data
        |
optional baseline reconciliation and synthetic benchmark evaluation
```

Core models never expose pandas, PM4Py event logs, Petri nets, process trees, alignments, or
visualisation objects. The adapter converts at the boundary and returns WorkflowTwin-owned values.
Ground truth is supplied only after discovery, conformance, candidates, and reconciliation exist.

## Activity mapping

Mapping version `northstar-activity-map-v1` is one-to-one and complete for event schema version 1.
Ingestion metadata and source retries never become activities.

| Event type | Activity |
| --- | --- |
| `referral_submitted` | Referral submitted |
| `referral_received` | Referral received |
| `completeness_check_completed` | Completeness checked |
| `missing_information_requested` | Missing information requested |
| `missing_information_received` | Missing information received |
| `referral_categorised` | Referral categorised |
| `referral_recategorised` | Referral recategorised |
| `clinical_team_assigned` | Clinical team assigned |
| `clinical_team_reassigned` | Clinical team reassigned |
| `appointment_scheduling_started` | Scheduling started |
| `appointment_scheduling_failed` | Scheduling failed |
| `appointment_booked` | Appointment booked |
| `patient_notified` | Patient notified |
| `patient_no_response` | Patient no response |
| `referral_completed` | Referral completed |
| `referral_cancelled` | Referral cancelled |
| `referral_rejected` | Referral rejected |
| `referral_closed_other` | Referral closed other |

Events are grouped by case, deduplicated by `(source_system, external_event_id)`, then ordered by
`(event_at, event_id)`. Event time drives sequence and transition delays. Ingestion time remains
quality metadata. Repeated distinct events remain repeated activities. Unsupported schema versions
or unmapped event types exclude the affected trace with a visible warning.

## Discovery and timing

The directly-follows graph is calculated from canonical traces and reconciled with PM4Py's public
DFG discovery output. Transition statistics retain frequency, distinct cases, elapsed and configured
business-time delay, manual-touch context, actor/team handoff rate, and supporting cases. Delay is
not active work duration. Self-loops and `A -> B -> A` loops are reported separately.

PM4Py Inductive Miner discovers one structured process tree using the configured noise threshold;
the tree is converted to an accepting Petri net. It is selected because it produces a sound,
understandable block-structured model and handles infrequent behaviour without comparing many
algorithms. Discovery summaries are canonicalised before persistence.

Variants are exact activity tuples. Their identifier is the first 16 hexadecimal characters of a
SHA-256 digest over canonical JSON containing the activity-map version and sequence. Common,
uncommon, and rare classifications use configured case-frequency thresholds, never generator labels.

## Reference workflows

Strict reference `northstar-strict-v1` is the nine-activity successful sequence:

```text
Submitted -> Received -> Checked -> Categorised -> Assigned -> Scheduling started
-> Appointment booked -> Patient notified -> Completed
```

Governed reference `northstar-governed-v1` is an explicit Petri net. It permits information-request
and response loops, rejection before routing, cancellation at documented open stages,
recategorisation, reassignment, scheduling failure and retry, patient non-response, completion,
rejection, cancellation, and other administrative closure. A first recategorisation or reassignment
is permitted; subsequent occurrences are classified as excessive-loop deviations even though token
replay can still traverse the structural loop. Governed conformance therefore does not mean an
efficient or desirable path.

Token-based replay is used for case and dataset fitness because it is deterministic and practical
for the 10,000-case in-memory benchmark. Fitness `1.0` is fully conforming, positive lower fitness is
partial, and zero is non-conforming. Missing values remain unavailable. Stable deviations are
derived from replay diagnostics plus transparent sequence checks: unexpected/missing activity,
repeat, order, early or missing terminal, unexpected terminal, excessive loop, reassignment,
recategorisation, and scheduling retry. Timeouts or malformed external output affect only the
relevant conformance result.

## Findings, graphs, and reproducibility

Candidate rules describe associations, never causality: frequent slow transitions, extreme delays,
costly loops, slow handoffs, long/touch-heavy variants, slow non-conforming paths, stuck-associated
transitions, and cohort-specific delay or rework. Existing baseline findings are linked to supporting
transitions or variants without recalculating or changing baseline metrics.

Graph JSON contains stable activity nodes and transition edges with explicit units and no colours or
coordinates. Optional SVG exports cover frequency/performance DFGs, discovered process tree/Petri
net, and both references. Graphviz or rendering failure adds a warning and leaves analysis valid.

The process fingerprint hashes source and optional baseline fingerprints, analysis/config versions,
activity/reference versions, canonical activities, transitions, variants, conformance summaries,
candidates, and graph data. It excludes wall time, output paths, raw PM4Py objects, SVG bytes and
metadata, benchmark labels, and dictionary insertion order. File and database loaders share the
same typed input and deterministic ordering.

## Limitations

- Point events show observed order and elapsed delay, not continuous work or causal mechanisms.
- Token replay is less diagnostic than optimal alignments; transparent sequence deviations provide
  readable context while the configured computational limit protects benchmark execution.
- The governed reference is a versioned policy assumption, not proof that every permitted path is
  operationally desirable.
- In-memory analysis targets the current 10,000-case benchmark, not streaming or distributed logs.
- Non-conformance can reflect missing source data, legitimate exceptions, or model scope rather than
  an operational error. Every candidate requires human investigation.
