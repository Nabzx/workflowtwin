# Operational metric definitions

These definitions apply to fictional or synthetic Northstar Clinics administrative referral data.
They are not clinical quality measures. Durations use UTC instants and event-time ordering. Duplicate
source events are excluded after identity-based deduplication. Negative durations caused by corrupt
source clocks are invalid observations and must be surfaced rather than coerced to zero.

Version 1 events are point observations. Metrics labelled **exact** are exact relative to the recorded
events, not proof that the source system captured every real-world action.

| Metric | Definition and event boundaries | Exclusions, missing data, and status |
| --- | --- | --- |
| Case duration | Elapsed time from `REFERRAL_RECEIVED` to the terminal event (`REFERRAL_COMPLETED`, `REFERRAL_CANCELLED`, `REFERRAL_REJECTED`, or `REFERRAL_CLOSED_OTHER`). For an open-case age view, end at the stated analysis cutoff instead. | Exclude cases without a received event from duration aggregates and report them as data-quality failures. Closed cases missing a terminal event are invalid. **Exact from recorded boundaries.** |
| Cycle time | Elapsed time from `REFERRAL_RECEIVED` until the first terminal event. This is the closed-case flow time and is intentionally equal to case duration in version 1. | Open cases are right-censored and excluded from completed-cycle aggregates. Report the open population separately. **Exact from recorded boundaries.** |
| Waiting time | Union of business-calendar intervals explicitly classified as waiting: received to first completeness check, missing-information request to its next received response, latest team assignment/reassignment before scheduling start, and failed scheduling attempt to the next scheduling start. | Unmatched open-case waits end at the analysis cutoff and are **partial**. Unmatched terminal-case waits are omitted with a warning. Overlaps are merged before summation. Otherwise **estimated**, because point events do not record continuous work state. |
| Processing time estimate | Manual-touch count multiplied by the configured minutes-per-touch proxy, 10 minutes by default. | Version 1 has no action-duration boundaries. This is always **estimated**, is not observed staff effort, and is not cycle time minus waiting time. |
| Manual touches | Count of deduplicated events where `requires_manual_work=true`. | Exclude duplicate source identities. Missing flags make the case incomplete for this metric. A touch is not a duration. **Exact from recorded flags.** |
| Handoffs | Count of transitions between consecutive event-time-ordered events whose non-null responsible actor identifiers differ and represent internal operational responsibility. | Exclude patient/referrer communications and system-only transitions. Unknown actor identifiers produce an unobservable transition rather than an assumed handoff. **Estimated** when actor coverage is incomplete. |
| Rework count | Sum completeness checks after the first, missing-information requests after the first, `REFERRAL_RECATEGORISED`, `CLINICAL_TEAM_REASSIGNED`, and `APPOINTMENT_SCHEDULING_FAILED`. One case may contribute several categories. | Source duplicates are excluded. A result is **estimated** when it contains inferred repeated checks or requests; otherwise explicit corrective-event counts are **exact**. |
| Completion rate | Cases with terminal status `COMPLETED` divided by all cases reaching any terminal status during the reporting window. | Exclude still-open cases from the denominator; publish their count. Group by terminal event time, not ingestion time. **Exact from valid terminal states.** |
| Cancellation rate | Cases with terminal status `CANCELLED` divided by all cases reaching any terminal status during the reporting window. | Same terminal-population and missing-event rules as completion rate. No clinical meaning is inferred from the cancellation. **Exact.** |
| Rejection rate | Cases with terminal status `REJECTED` divided by all cases reaching any terminal status during the reporting window. | Same terminal-population and missing-event rules as completion rate. Reasons are administrative structured codes only. **Exact.** |
| Stuck-case rate | Open cases with time since their last qualifying progress event greater than the configured stage threshold, divided by all open cases at the analysis cutoff. | Requires a documented cutoff and threshold set. Exclude cases with no trustworthy event time and report them separately. Thresholds are assumptions, so this is **estimated/configuration-dependent**. |
| First-pass completeness rate | Cases whose first `COMPLETENESS_CHECK_COMPLETED` is not followed by `MISSING_INFORMATION_REQUESTED` before categorisation, divided by cases with a first completeness check. | Exclude cases without a completeness check. A late-arriving missing-information event may revise the result; analysis runs must retain their input watermark. **Inferred, therefore estimated.** |
| Time to first completeness check | Elapsed time from `REFERRAL_RECEIVED` to the earliest event-time `COMPLETENESS_CHECK_COMPLETED`. | Exclude and count cases missing either boundary. Negative results are data-quality errors. **Exact from recorded boundaries.** |
| Time to appointment booking | Elapsed time from `REFERRAL_RECEIVED` to the earliest `APPOINTMENT_BOOKED`. | Exclude cases not yet booked from completed-booking aggregates; optionally report them as right-censored in later survival analysis. Cancellation and rejection before booking are separate outcomes. **Exact from recorded boundaries.** |
| Assignment wait | Business time from the latest categorisation/recategorisation preceding the first `CLINICAL_TEAM_ASSIGNED`. | Missing either boundary is unavailable. Point events make the interval **estimated**. |
| Failed scheduling attempts | Count `APPOINTMENT_SCHEDULING_FAILED` events. | Observable zero is valid; source duplicates are excluded. **Exact from recorded events.** |
| Reassignments | Count `CLINICAL_TEAM_REASSIGNED` events. | Observable zero is valid; source duplicates are excluded. **Exact from recorded events.** |
| Maximum ingestion delay | Maximum `ingested_at - event_at` in hours for canonical case events. | Empty timelines return zero only for this event-count quality view. This is data quality, not workflow performance. **Exact from recorded timestamps.** |
| Delayed event count | Canonical events whose ingestion delay exceeds the configured threshold, 24 hours by default. | The threshold is configuration-dependent. This is a data-quality count. **Exact from recorded timestamps.** |
| Out-of-order ingestion | Whether ingestion order differs from canonical event-time order. | Identical event times use the UUID tie-break. This is a data-quality flag. **Exact from recorded timestamps.** |

## Population and reproducibility rules

Every metric result must record its reporting window, timezone, analysis cutoff, schema version,
deduplication rule, eligible population, excluded count, and input watermark. Event time selects and
orders operational activity; ingestion time determines which facts were available to an analysis
run. Re-running with a later ingestion watermark may legitimately revise historical metrics when
late events arrive.

All definitions above use calculation version `1.0.0`. Cohort duration, waiting, processing,
touch, handoff, rework, and boundary-time summaries exclude unavailable, partial, not-applicable,
excluded, and invalid results. Outcome-rate denominators contain terminal cases; stuck-rate
denominators contain open cases; first-pass denominators contain observable first checks; ingestion
rates contain all analysed cases. Summary exclusions and every case-level status remain visible.
