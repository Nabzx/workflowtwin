# Shadow detector refinement and reviewer capacity

Northstar Clinics, its cases, reviewers, schedules, capacity, and results are fictional. This module
evaluates administrative recommendations only. It performs no referral action, patient contact,
diagnosis, clinical prioritisation, or treatment recommendation.

## Boundary

`strict-v1` is the untouched existing strict completeness detector. `strict-v2` opens a pending
concern only for explicit supporting-document absence on supported contracts, waits 120 logical
minutes, and confirms only if a current snapshot has not resolved it. Inputs contain no evaluation
labels, future events, review outcomes, or operational writers.

```text
versioned snapshots -> as-of confirmation -> explainable priority -> fictional capacity queue
                             |                         |                    |
                      detector positive         active/observe       surfaced/deferred
                             +---------------- evaluation after run --------+
```

Priority uses administrative evidence strength and explicit overlap state. It never uses hidden
truth, referral source, service line, protected characteristics, or clinical content. Equal-priority
items are ordered by decision time and stable signal ID.

## Protocol and gates

`config/shadow/refinement-protocol.json` registers development seeds 101 and 202, validation seed
303, and untouched holdout seed 404. The selected configuration has a content fingerprint;
sensitivity variants have different fingerprints and are report-only.

Quality gates cover precision, recall, false-positive burden, compliance, audit completeness, and
recommendation-only authority. Capacity stop conditions cover queue size, backlog, deferral, expiry,
and surfaced coverage. Capacity success cannot promote a weak detector.

Reports include rule performance, root causes, redundancy, missed positives, cohorts, chronological
windows, capacity profiles, Pareto points, and sensitivity. Small cohorts are labelled.

## Commands

```bash
uv run workflowtwin shadow-refine --force
uv run workflowtwin shadow-holdout
```

The first command never opens the holdout. The second writes the registry lock before evaluating its
10,000 cases once. Repeating it returns the immutable result. Generated artifacts are ignored by Git.

## Evaluation decision

Development, validation, and the locked holdout all return `do_not_promote`. On the holdout,
`strict-v2` reduced detector positives from 2,048 to 1,686 and false-positive review time from 9.53
to 7.73 fictional hours. Precision was effectively flat (93.02% to 93.12%), while recall fell from
62.11% to 51.19% and recommendation latency increased from zero to 120 minutes. The recall gate
fails. The confirmation rule is therefore not a promotion candidate; it is retained only as an
auditable shadow comparison.
