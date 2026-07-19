"""Deterministic supported-product pilot seed for local demos and API tests."""

from datetime import UTC, datetime, timedelta

from workflowtwin.core.fingerprint import fingerprint, stable_id
from workflowtwin.detector import CompletenessReviewDetector
from workflowtwin.intake.requirements import load_northstar_requirements
from workflowtwin.pilot.drafts import create_draft
from workflowtwin.pilot.evaluation import calculate_metrics, evaluate_gates
from workflowtwin.pilot.models import PilotRecommendation, PilotReviewDecisionType, PilotRun
from workflowtwin.pilot.policy import load_pilot_policy, pilot_policy_fingerprint
from workflowtwin.pilot.service import PilotService
from workflowtwin.shadow_v3.models import V3Outcome
from workflowtwin.source_contracts.generator import generate_v2_intake_artifacts
from workflowtwin.synthetic.generator import SyntheticReferralGenerator
from workflowtwin.synthetic.presets import GenerationPreset, config_for_preset

DEMO_CREATED_AT = datetime(2026, 7, 19, 9, 0, tzinfo=UTC)
DEMO_CASE_COUNT = 120
DEMO_SEED = 81
DEMO_SURFACED_LIMIT = 12


def build_demo_pilot() -> tuple[PilotRun, PilotService]:
    """Build a fixed fictional cohort and representative review lifecycle."""
    requirements = load_northstar_requirements()
    config = config_for_preset(
        GenerationPreset.TINY,
        case_count=DEMO_CASE_COUNT,
        seed=DEMO_SEED,
        generation_run_id="northstar-fictional-pilot-demo",
    )
    dataset = SyntheticReferralGenerator(config, generated_at=DEMO_CREATED_AT).generate()
    snapshots, truths = generate_v2_intake_artifacts(dataset, requirements)
    detector = CompletenessReviewDetector(requirements)
    detector_run = detector.run(snapshots, run_id="supported-detector-pilot-demo")
    snapshots_by_id = {item.snapshot_id: item for item in snapshots}
    latest_recommendations = {
        item.case_id: item
        for item in detector_run.results
        if item.outcome is V3Outcome.RECOMMEND and item.case_id in detector_run.active_case_ids
    }
    selected = tuple(
        latest_recommendations[key]
        for key in sorted(latest_recommendations, key=lambda value: value.hex)
    )[:DEMO_SURFACED_LIMIT]
    metadata = detector.lineage
    recommendations = tuple(
        PilotRecommendation(
            recommendation_id=stable_id(
                "pilot-recommendation", item.evaluation_id, metadata.supported_detector_fingerprint
            ),
            detector_evaluation_id=item.evaluation_id,
            case_id=item.case_id,
            snapshot_id=item.snapshot_id,
            detected_at=item.evaluated_at,
            missing_field_ids=("supporting_document",),
            source_references=item.source_references,
            requirement_references=("supporting-document",),
            detector_product_name=metadata.product_name,
            supported_detector_fingerprint=metadata.supported_detector_fingerprint,
            original_detector_fingerprint=metadata.original_detector_fingerprint,
        )
        for item in selected
    )
    drafts = tuple(
        create_draft(
            recommendation=recommendation,
            snapshot=snapshots_by_id[recommendation.snapshot_id],
        )
        for recommendation in recommendations
    )
    policy = load_pilot_policy()
    service = PilotService(policy=policy, recommendations=recommendations, drafts=drafts)
    first = drafts[0]
    first_review = service.review(
        first.draft_id,
        revision_id=first.current_revision_id,
        reviewer_role="fictional_admin_reviewer",
        decision=PilotReviewDecisionType.APPROVE,
        decided_at=first.created_at + timedelta(minutes=8),
        structured_reason="explicit administrative absence confirmed",
        review_minutes=4,
    )
    first_action = service.commit_approved(
        first.draft_id,
        review_id=first_review.review_id,
        acted_at=first.created_at + timedelta(minutes=9),
    )
    service.rollback(
        first_action.action_id,
        actor_role="fictional_pilot_supervisor",
        reason="demonstrate reversible local action",
        rolled_back_at=first.created_at + timedelta(minutes=12),
    )
    second = drafts[1]
    service.review(
        second.draft_id,
        revision_id=second.current_revision_id,
        reviewer_role="fictional_admin_reviewer",
        decision=PilotReviewDecisionType.REJECT,
        decided_at=second.created_at + timedelta(minutes=10),
        structured_reason="new source evidence requires re-check",
        review_minutes=3,
    )
    third = drafts[2]
    edited = service.edit_draft(
        third.draft_id,
        editor_role="fictional_admin_reviewer",
        revised_at=third.created_at + timedelta(minutes=5),
        change_reason="clarify administrative wording",
        heading="Administrative supporting document check",
    )
    third_review = service.review(
        third.draft_id,
        revision_id=edited.current_revision_id,
        reviewer_role="fictional_admin_reviewer",
        decision=PilotReviewDecisionType.APPROVE_WITH_EDITS,
        decided_at=third.created_at + timedelta(minutes=11),
        structured_reason="edited administrative draft verified",
        review_minutes=5,
    )
    service.commit_approved(
        third.draft_id,
        review_id=third_review.review_id,
        acted_at=third.created_at + timedelta(minutes=12),
    )
    positive_ids = set(detector_run.detector_positive_case_ids)
    true_ids = {item.case_id for item in truths if not item.supporting_document_present}
    final_drafts = tuple(service.drafts[key] for key in sorted(service.drafts))
    metrics = calculate_metrics(
        incoming_cases=len(dataset.cases),
        detector_positives=len(positive_ids),
        true_positives=len(positive_ids & true_ids),
        evaluable_positives=len(true_ids),
        drafts=final_drafts,
        reviews=tuple(service.reviews),
        actions=tuple(service.actions),
        rollbacks=tuple(service.rollbacks),
        audit_records=service.audit_records,
    )
    gates, stop_conditions, assessment = evaluate_gates(metrics, policy)
    run_content = {
        "policy_fingerprint": pilot_policy_fingerprint(policy),
        "detector_run_fingerprint": detector_run.run_fingerprint,
        "operational_dataset_fingerprint": dataset.manifest.dataset_fingerprint,
        "recommendations": [item.recommendation_id for item in recommendations],
        "drafts": [item.current_revision_id for item in final_drafts],
        "reviews": [item.review_id for item in service.reviews],
        "actions": [item.action_id for item in service.actions],
        "rollbacks": [item.rollback_id for item in service.rollbacks],
        "gates": [item.model_dump(mode="json") for item in gates],
        "assessment": assessment,
    }
    run = PilotRun(
        run_id="northstar-fictional-pilot-demo-v1",
        created_at=DEMO_CREATED_AT,
        policy=policy,
        policy_fingerprint=pilot_policy_fingerprint(policy),
        supported_detector_metadata=metadata.model_dump(mode="json"),
        input_fingerprints={
            "operational_dataset": dataset.manifest.dataset_fingerprint,
            "intake_snapshots": fingerprint(snapshots),
            "detector_run": detector_run.run_fingerprint,
        },
        recommendations=recommendations,
        drafts=final_drafts,
        reviews=tuple(service.reviews),
        actions=tuple(service.actions),
        rollbacks=tuple(service.rollbacks),
        mock_records=service.mock_system.list_tasks(),
        metrics=metrics,
        gates=gates,
        stop_conditions=stop_conditions,
        assessment=assessment,
        audit_records=service.audit_records,
        audit_root_fingerprint=(
            service.audit_records[-1].content_fingerprint if service.audit_records else None
        ),
        run_fingerprint=fingerprint(run_content),
    )
    return run, service
