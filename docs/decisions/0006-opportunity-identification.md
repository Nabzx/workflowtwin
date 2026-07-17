# ADR 0006: Deterministic evidence-gated opportunity identification

- **Status:** Accepted
- **Date:** 2026-07-17

## Context

WorkflowTwin needs to move from descriptive process findings to a defensible portfolio of possible
administrative improvement areas. A single opaque score or LLM-generated recommendation would hide
evidence gaps, contradictions, safety exclusions, and the difference between current burden and
future benefit. Synthetic benchmark labels could also leak into candidate creation and make the
evaluation circular.

## Decision

Use a versioned deterministic engine over typed baseline, process, and fictional research artifacts.
Create stable evidence references and explicit contradiction records before applying named candidate
rules. Keep burden, value, readiness, risk, confidence, and eligibility as distinct contracts.

Apply eligibility as a hard gate outside the weighted priority score. Candidates involving clinical
judgement, treatment, clinical prioritisation, prohibited sensitive-data use, or missing governance
cannot become eligible through a high numerical score. Require controls such as human approval,
audit trails, manual fallback, reversible action, and prohibited autonomous execution according to
the archetype and risk assessment.

Treat calculated addressable burden as an upper bound and leave expected benefit unavailable. Use
synthetic ground truth only after candidate creation, assessment, ranking, and graph construction.
Keep rules and archetypes explicit rather than introducing an LLM or agent framework.

## Consequences

Every portfolio position is reproducible and traceable to source artifacts, and disagreements lower
confidence without disappearing. Safety constraints remain inspectable and cannot be compensated for
by value. The system can be tested against planted patterns without training or tuning on labels.

The approach is less flexible than semantic generation and depends on maintained mappings,
thresholds, and research vocabulary. It identifies areas for investigation rather than designing an
intervention. Real deployment would require governed user research, sensitivity analysis, privacy
review, and prospective evaluation before any automation could be authorised.
