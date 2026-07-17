"""Stable merging of evidence that describes one cohort opportunity."""

from collections import defaultdict

from workflowtwin.opportunities.rules import OpportunitySeed


def deduplicate_seeds(seeds: tuple[OpportunitySeed, ...]) -> tuple[OpportunitySeed, ...]:
    grouped: dict[tuple[str, str, str, str], list[OpportunitySeed]] = defaultdict(list)
    for seed in seeds:
        grouped[
            (
                seed.archetype.value,
                seed.cohort_dimension,
                seed.cohort_value,
                seed.workflow_stage,
            )
        ].append(seed)
    merged = []
    for _key, members in sorted(grouped.items()):
        merged.append(
            OpportunitySeed(
                rule_ids=tuple(sorted({item for member in members for item in member.rule_ids})),
                archetype=members[0].archetype,
                cohort_dimension=members[0].cohort_dimension,
                cohort_value=members[0].cohort_value,
                workflow_stage=members[0].workflow_stage,
                problem_statement=members[0].problem_statement,
                quantitative_evidence_ids=tuple(
                    sorted(
                        {item for member in members for item in member.quantitative_evidence_ids}
                    )
                ),
                qualitative_evidence_ids=tuple(
                    sorted({item for member in members for item in member.qualitative_evidence_ids})
                ),
            )
        )
    return tuple(merged)
