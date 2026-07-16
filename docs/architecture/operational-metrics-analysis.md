# Operational metrics and baseline analysis

Northstar Clinics, its referral records, and every analytical result in this project are fictional.
The engine measures administrative workflow performance only. It must not be used for clinical
prioritisation, treatment decisions, individual staff surveillance, or claims about real healthcare
outcomes.

## Pipeline

```text
ReferralCase + ReferralEvent contracts
               |
 canonical event-time timelines
               |
 case metrics with provenance and status
               |
 cohort aggregation + quality coverage
               |
 transparent baseline finding rules
               |
 baseline JSON / Markdown / optional case JSONL
               |
 optional synthetic ground-truth evaluation
```

Core analysis never imports or reads synthetic labels. Ground truth is supplied only after findings
exist and produces a separate benchmark evaluation.

## Timeline construction

Events are grouped by case identifier and sorted by `(event_at, event_id)`. UUID text is the stable
tie-breaker when event timestamps are equal; the tie-breaker gives reproducibility but does not claim
causal order. Ingestion timestamps remain unchanged and are used only for latency and ordering-quality
measures.

Duplicate policy is configurable. The default keeps the first event in canonical order for each
`(source_system, external_event_id)` identity and records later identities as excluded duplicates.
Repeated activities with different source identities remain in the timeline as legitimate rework.

## Version 1 duration semantics

- Operational duration values use elapsed UTC hours unless explicitly named business hours.
- Waiting time is an estimated sum of non-overlapping business-calendar intervals: received to first
  completeness check, missing-information request to its matching response, latest assignment or
  reassignment to the next scheduling start, and scheduling failure to the next scheduling start.
- An unmatched wait in an open case may extend to the configured cutoff and is marked partial. An
  unmatched terminal-case wait is omitted with a warning.
- Processing time is a configurable manual-touch proxy (`manual touches * minutes per touch`). Point
  events do not contain observed effort duration, so this value is always estimated.
- Open-case age is a partial duration from receipt to analysis cutoff. It is never mixed into
  closed-case duration summaries.
- Assignment waiting is estimated business time from the latest categorisation/recategorisation to
  the first team assignment.

Missing boundaries produce unavailable or not-applicable results, never a zero. Zero is valid only
when the metric is observable and no qualifying event occurred, such as zero rework.

## Cohorts

The engine always produces an overall cohort and can group by referral source, service line, primary
source system, assigned team, and terminal outcome. Primary source system is the system on the first
`REFERRAL_RECEIVED` event. Assigned team comes from the structured `assigned_team_identifier` field
on assignment events; older inputs without that attribute remain ungrouped.

Outcome rates use terminal cases as the denominator for completion, cancellation, and rejection.
Stuck rate uses all open cases as its denominator. First-pass completeness uses cases with an
observable first completeness check. Duration summaries contain exact closed-case duration only;
partial open ages remain visible in case results and quality counts.

Percentiles use deterministic linear interpolation between adjacent ordered observations. Comparative
findings require the configured minimum cohort size, though smaller cohorts remain in the artifact
with `eligible_for_comparison=false`.

## Baseline findings

Rules compare eligible cohorts with the overall eligible baseline. Version 1 surfaces materially
lower first-pass completeness, longer assignment or booking time, elevated failed scheduling,
reassignment/handoff cost, longer duration, elevated stuck rate, and delayed ingestion. Materiality
uses configured absolute rate and relative difference thresholds. No statistical-significance claim
is made.

Each finding records its cohort, metric, observed and baseline values, differences, sample sizes,
materiality, supporting case identifiers, and caveats. Findings describe observed fictional data;
they are not AI recommendations.

## Quality and reproducibility

Quality output reports unsupported schemas, excluded cases, timeline ambiguity, identical timestamps,
late and out-of-order ingestion, missing event boundaries, and availability/estimated/partial counts
for every metric. An analysis fingerprint hashes canonical JSON containing the source fingerprint,
analysis version, normalised configuration excluding output paths, overall/cohort metrics, findings,
and quality summary. Wall-clock analysis time and synthetic evaluation are excluded.

File and database loaders both return the same typed cases, events, manifest context, and deterministic
ordering. The current in-memory implementation is intended for the 10,000-case benchmark, not
distributed or streaming analysis.

