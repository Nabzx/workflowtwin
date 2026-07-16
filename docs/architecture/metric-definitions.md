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
| Waiting time | Sum of elapsed intervals explicitly classified as waiting: received to first completeness check, missing-information request to its next received response, team assignment/reassignment to scheduling start, and failed scheduling attempt to the next attempt or booking. | Do not guess a closing boundary for an unmatched wait; report it as open at the analysis cutoff. Overlapping waits must not be double-counted. **Estimated**, because point events do not record continuous work state. |
| Processing time | Sum of observed or configured active-work intervals, initially completeness-check activity and scheduling-start to booking intervals where a valid pair exists. | Instantaneous manual events without duration contribute a touch but zero known processing duration. Do not derive it as cycle time minus waiting time until interval coverage is complete. **Estimated.** |
| Manual touches | Count of deduplicated events where `requires_manual_work=true`. | Exclude duplicate source identities. Missing flags make the case incomplete for this metric. A touch is not a duration. **Exact from recorded flags.** |
| Handoffs | Count of transitions between consecutive event-time-ordered events whose non-null responsible actor identifiers differ and represent internal operational responsibility. | Exclude patient/referrer communications and system-only transitions. Unknown actor identifiers produce an unobservable transition rather than an assumed handoff. **Estimated** when actor coverage is incomplete. |
| Rework count | Count repeated or corrective work: completeness checks after the first, additional requests within one missing-information loop, `REFERRAL_RECATEGORISED`, `CLINICAL_TEAM_REASSIGNED`, and scheduling failures after the first scheduling start. | Source duplicates are excluded. A new legitimate information loop after a completed response remains rework only when the analysis rule identifies a correction. **Exact for explicit corrective events; estimated for inferred repeats.** |
| Completion rate | Cases with terminal status `COMPLETED` divided by all cases reaching any terminal status during the reporting window. | Exclude still-open cases from the denominator; publish their count. Group by terminal event time, not ingestion time. **Exact from valid terminal states.** |
| Cancellation rate | Cases with terminal status `CANCELLED` divided by all cases reaching any terminal status during the reporting window. | Same terminal-population and missing-event rules as completion rate. No clinical meaning is inferred from the cancellation. **Exact.** |
| Rejection rate | Cases with terminal status `REJECTED` divided by all cases reaching any terminal status during the reporting window. | Same terminal-population and missing-event rules as completion rate. Reasons are administrative structured codes only. **Exact.** |
| Stuck-case rate | Open cases with time since their last qualifying progress event greater than the configured stage threshold, divided by all open cases at the analysis cutoff. | Requires a documented cutoff and threshold set. Exclude cases with no trustworthy event time and report them separately. Thresholds are assumptions, so this is **estimated/configuration-dependent**. |
| First-pass completeness rate | Cases whose first `COMPLETENESS_CHECK_COMPLETED` is not followed by `MISSING_INFORMATION_REQUESTED` before categorisation, divided by cases with a first completeness check. | Exclude cases without a completeness check. A late-arriving missing-information event may revise the result; analysis runs must retain their input watermark. **Inferred, therefore estimated.** |
| Time to first completeness check | Elapsed time from `REFERRAL_RECEIVED` to the earliest event-time `COMPLETENESS_CHECK_COMPLETED`. | Exclude and count cases missing either boundary. Negative results are data-quality errors. **Exact from recorded boundaries.** |
| Time to appointment booking | Elapsed time from `REFERRAL_RECEIVED` to the earliest `APPOINTMENT_BOOKED`. | Exclude cases not yet booked from completed-booking aggregates; optionally report them as right-censored in later survival analysis. Cancellation and rejection before booking are separate outcomes. **Exact from recorded boundaries.** |

## Population and reproducibility rules

Every metric result must record its reporting window, timezone, analysis cutoff, schema version,
deduplication rule, eligible population, excluded count, and input watermark. Event time selects and
orders operational activity; ingestion time determines which facts were available to an analysis
run. Re-running with a later ingestion watermark may legitimately revise historical metrics when
late events arrive.

