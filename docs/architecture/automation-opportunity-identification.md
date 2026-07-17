# Evidence-backed automation opportunity identification

Northstar Clinics, its research sessions, and all operational results are fictional. This milestone
identifies bounded administrative opportunities for investigation. It does not diagnose, recommend
treatment, authorise automation, prescribe an intervention, or estimate an intervention's effect.

## Decision pipeline

```text
BaselineAnalysis + ProcessMiningAnalysis + fictional ResearchPack
                              |
                cross-artifact compatibility checks
                              |
          typed evidence registry + explicit contradictions
                              |
              versioned deterministic candidate rules
                              |
                     stable deduplication
                              |
 burden | eligibility | value | readiness | risk | confidence
                              |
              gated score + auditable portfolio
                              |
          optional synthetic benchmark evaluation last
```

The engine consumes aggregate baseline and process artifacts rather than raw case timelines. Stable
source pointers and artifact fingerprints connect every candidate to its supporting evidence. A
manifest can strengthen provenance checks; separate synthetic ground truth is optional and is never
used to create, score, rank, or gate candidates.

## Evidence and research

Evidence references normalise baseline findings and cohort metrics, process candidates, transitions,
marked variants, deviations, quality summaries, manifest quality, and research observations into a
WorkflowTwin-owned contract. Each reference has a stable content-derived identifier, source type,
logical pointer, observed value and unit, population, direction, confidence, and limitations.

The versioned research pack contains nine synthetic sessions across referral administration,
scheduling, operations, service coordination, data integration, and governance. Observations are
structured rather than free-form: role, workflow stage, archetype, reported frequency and severity,
quote, desired outcome, constraints, and contradiction links. Validation rejects missing fictional
declarations, unknown vocabulary, direct patient identifiers, and clinical claims. Conflicting views
remain visible and reduce confidence; they are not averaged away.

## Candidate rules and archetypes

Seven versioned administrative archetypes define purpose, applicable evidence, eligibility,
oversight, success measures, failure modes, and safety restrictions. Six deterministic rules can
currently trigger candidates for intake completeness, assignment routing, scheduling coordination,
handoff reduction, stuck-case monitoring, and data-quality monitoring. Administrative classification
assistance is defined for future evidence but is intentionally not triggered by the current inputs.

Rules require explicit typed evidence and minimum sample support. Deduplication uses archetype,
cohort, and workflow stage; it unions evidence and rule identifiers without changing the underlying
observations. Opportunity identifiers are content-derived and stable across analysis time and score
weight changes.

## Assessment and portfolio semantics

The engine keeps six questions separate:

| Assessment | Question |
| --- | --- |
| Observed burden | What administrative friction is actually measured? |
| Eligibility | Is this candidate permitted to progress at all? |
| Value | How material is the observed operational burden? |
| Readiness | Are the process, data, and controls ready for further work? |
| Risk | What can fail and what controls would be required? |
| Confidence | How strong, varied, and internally consistent is the evidence? |

Eligibility is a hard gate outside the weighted score. Clinical judgement, treatment or
prioritisation, prohibited sensitive-data use, missing evidence, governance blocks, and insufficient
data can prevent a priority score regardless of apparent value. Eligible scores use:

```text
priority = 0.40 * value + 0.25 * readiness + 0.25 * confidence - 0.10 * risk
```

The portfolio has three honest sections: eligible for a controlled prototype, needs further
discovery, and blocked or out of scope. A controlled prototype label still requires the candidate's
listed human oversight, audit trail, manual fallback, reversibility, rate limits, or observe-only
constraints. It is not permission to execute an automation.

Burden calculations report current observed counts, time proxies, and transparent administrative
cost assumptions. Addressable burden is an upper bound, not a forecast. Expected benefit remains
unavailable because no intervention or counterfactual simulation exists in this milestone.

## Reproducibility and outputs

The analysis fingerprint covers input fingerprints, contract and rule versions, effective scoring
configuration, evidence, contradictions, candidates, portfolio, and graph data. It excludes analysis
time, output paths, and benchmark labels. Outputs include full JSON, stakeholder Markdown, a compact
portfolio dataset, and an evidence-network dataset. Existing artifacts are protected unless the
caller explicitly enables overwrite.

The fixed demo identifies seven raw and six deduplicated candidates. One qualifies only for a
controlled prototype and five need further discovery. All four planted administrative patterns are
found after candidate construction. Unexpected stuck-case and ingestion-quality candidates remain
visible rather than being deleted to improve benchmark precision.

## Limitations

- Rules surface associations and operational hypotheses, not causal claims or recommendations.
- Research is deliberately synthetic and cannot establish real user needs or provider performance.
- Manual-touch time and administrative hourly cost are visible proxies, not realised savings.
- Aggregate inputs support portfolio decisions but not case-level intervention.
- Thresholds and weights are versioned product choices that need sensitivity testing with real,
  governed deployments.
- No LLM, predictive model, intervention design, simulation, autonomous action, or clinical logic is
  present.
