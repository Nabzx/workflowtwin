"""Deterministic source-availability replay and recommendation lifecycle."""

from datetime import datetime
from typing import Any

from workflowtwin.shadow.audit import AuditTrail
from workflowtwin.shadow.config import ShadowConfig
from workflowtwin.shadow.detector import CompletenessReviewDetector
from workflowtwin.shadow.fingerprint import shadow_fingerprint, shadow_id
from workflowtwin.shadow.intake import intake_snapshot_fingerprint
from workflowtwin.shadow.models import (
    AuditActor,
    ConfidenceClass,
    DetectorInput,
    DetectorOutcome,
    DetectorResult,
    IncomingReferralSnapshot,
    PolicyEvaluation,
    Recommendation,
    RecommendationStatus,
    ReplayCheckpoint,
    ShadowRun,
    ShadowRunManifest,
)
from workflowtwin.shadow.policy import ShadowPolicy
from workflowtwin.shadow.state import CaseStateProjector

SOURCE_PRIORITY = {
    "referral_portal": 10,
    "secure_email": 20,
    "manual_entry": 30,
    "admin_system": 40,
    "scheduling_system": 50,
    "synthetic_generator": 90,
}
PROHIBITED_ACTIONS = (
    "change workflow state",
    "reject or approve referral",
    "change service line or assignment",
    "contact patient or referrer",
    "infer clinical content or urgency",
)


class ShadowModeRunner:
    """Replay fictional intake without importing future outcomes or operational writers."""

    def __init__(self, config: ShadowConfig) -> None:
        self.config = config
        self.policy = ShadowPolicy(config)
        self.detector = CompletenessReviewDetector(config)

    def run(
        self,
        snapshots: tuple[IncomingReferralSnapshot, ...],
        *,
        checkpoint: ReplayCheckpoint | None = None,
        max_source_items: int | None = None,
    ) -> ShadowRun:
        source_fingerprint = intake_snapshot_fingerprint(snapshots)
        ordered = tuple(
            sorted(
                (
                    item
                    for item in snapshots
                    if (
                        self.config.replay_start is None
                        or item.available_at >= self.config.replay_start
                    )
                    and (
                        self.config.replay_end is None
                        or item.available_at <= self.config.replay_end
                    )
                ),
                key=lambda item: (
                    item.available_at,
                    SOURCE_PRIORITY.get(item.source_system.value, 99),
                    item.snapshot_id,
                ),
            )
        )
        projector = CaseStateProjector()
        recommendations: list[Recommendation] = []
        policies: list[PolicyEvaluation] = []
        results: list[DetectorResult] = []
        start_position = 0
        audit = AuditTrail(self.config)
        active: dict[object, Recommendation] = {}

        if checkpoint is not None:
            self._validate_checkpoint(checkpoint, source_fingerprint)
            start_position = checkpoint.last_source_position
            projector.restore(checkpoint.case_states)
            recommendations.extend(checkpoint.recommendations)
            policies.extend(checkpoint.policy_evaluations)
            results.extend(checkpoint.detector_results)
            restored_audit = checkpoint.audit_records
            if restored_audit and restored_audit[-1].action == "shadow_run_paused":
                restored_audit = restored_audit[:-1]
            audit = AuditTrail(self.config, restored_audit)
            active_ids = set(checkpoint.active_recommendation_ids)
            for recommendation in recommendations:
                if recommendation.recommendation_id in active_ids and recommendation.status in {
                    RecommendationStatus.CREATED,
                    RecommendationStatus.UPDATED,
                }:
                    active[recommendation.case_id] = recommendation

        end_position = len(ordered)
        if max_source_items is not None:
            end_position = min(end_position, start_position + max_source_items)

        for position in range(start_position, end_position):
            snapshot = ordered[position]
            if snapshot.available_at.tzinfo is None or snapshot.available_at.utcoffset() is None:
                raise ValueError("snapshot available_at must be timezone-aware")
            self._expire_before(snapshot.available_at, active, recommendations, audit)
            source_audit = audit.append(
                occurred_at=snapshot.available_at,
                actor=AuditActor.SOURCE,
                action="source_item_received",
                case_id=snapshot.case_id,
                input_references=(snapshot.snapshot_id,),
            )
            state, state_action = projector.apply(snapshot)
            if state is None:
                audit.append(
                    occurred_at=snapshot.available_at,
                    actor=AuditActor.SYSTEM,
                    action=(
                        "source_item_ignored_as_duplicate"
                        if state_action == "duplicate_source_item"
                        else "source_item_ignored_as_stale"
                    ),
                    case_id=snapshot.case_id,
                    reason_codes=(state_action,),
                    input_references=(source_audit.audit_id, snapshot.snapshot_id),
                )
                continue
            state_audit = audit.append(
                occurred_at=state.as_of,
                actor=AuditActor.SYSTEM,
                action="case_state_updated",
                case_id=state.case_id,
                input_references=(snapshot.snapshot_id,),
                output_references=(shadow_fingerprint(state),),
            )
            detector_input = DetectorInput(
                case_id=state.case_id,
                as_of=state.as_of,
                state_version=state.state_version,
                referral_source=state.referral_source,
                requested_service_line=state.requested_service_line,
                source_system=state.source_system,
                form_version=state.form_version,
                fields=state.fields,
                source_snapshot_ids=state.source_snapshot_ids,
            )
            if any(
                snapshot_item.available_at > detector_input.as_of
                for snapshot_item in snapshots
                if snapshot_item.snapshot_id in detector_input.source_snapshot_ids
            ):
                raise AssertionError("detector input includes a source item after its as-of cutoff")
            policy = self.policy.evaluate(detector_input)
            policies.append(policy)
            audit.append(
                occurred_at=state.as_of,
                actor=AuditActor.POLICY,
                action="policy_allowed"
                if policy.status.value.startswith("permitted")
                else "policy_blocked",
                case_id=state.case_id,
                reason_codes=policy.reason_codes,
                input_references=(state_audit.audit_id,),
                output_references=(policy.evaluation_id,),
            )
            result = self.detector.evaluate(detector_input, policy)
            results.append(result)
            audit.append(
                occurred_at=state.as_of,
                actor=AuditActor.DETECTOR,
                action="detector_abstained"
                if result.outcome is DetectorOutcome.ABSTAIN
                else "detector_evaluated",
                case_id=state.case_id,
                reason_codes=result.reason_codes,
                input_references=state.source_snapshot_ids,
                output_references=(result.evaluation_id,),
            )
            self._apply_lifecycle(result, state, policy, active, recommendations, audit)

        complete = end_position == len(ordered)
        if complete and ordered:
            final_at = ordered[-1].available_at
            self._expire_before(final_at, active, recommendations, audit)
            audit.append(
                occurred_at=final_at,
                actor=AuditActor.SYSTEM,
                action="shadow_run_completed",
                output_references=(self.config.shadow_run_id,),
            )
        elif ordered:
            audit.append(
                occurred_at=ordered[max(0, end_position - 1)].available_at,
                actor=AuditActor.SYSTEM,
                action="shadow_run_paused",
                output_references=(self.config.shadow_run_id,),
            )

        states = tuple(sorted(projector.current.values(), key=lambda item: item.case_id.hex))
        records = tuple(audit.records)
        checkpoint_result = self._checkpoint(
            position=end_position,
            source_fingerprint=source_fingerprint,
            states=states,
            active=active,
            recommendations=tuple(recommendations),
            policies=tuple(policies),
            results=tuple(results),
            audit_records=records,
            audit_root=audit.root_fingerprint,
            complete=complete,
        )
        manifest = self._manifest(
            snapshots=ordered,
            processed=end_position,
            states=states,
            policies=tuple(policies),
            results=tuple(results),
            recommendations=tuple(recommendations),
            audit_records=records,
            audit_root=audit.root_fingerprint,
            complete=complete,
            source_fingerprint=source_fingerprint,
        )
        return ShadowRun(
            config=self.config.model_dump(mode="json"),
            manifest=manifest,
            case_states=states,
            policy_evaluations=tuple(policies),
            detector_results=tuple(results),
            recommendations=tuple(recommendations),
            audit_records=records,
            checkpoint=checkpoint_result,
        )

    def _apply_lifecycle(
        self,
        result: object,
        state: object,
        policy: PolicyEvaluation,
        active: dict[object, Recommendation],
        recommendations: list[Recommendation],
        audit: AuditTrail,
    ) -> None:
        from workflowtwin.shadow.models import DetectorResult, ShadowCaseState

        assert isinstance(result, DetectorResult)
        assert isinstance(state, ShadowCaseState)
        previous = active.get(state.case_id)
        if result.outcome is DetectorOutcome.RECOMMEND:
            if previous and previous.reason_codes == result.reason_codes:
                unchanged = previous.model_copy(
                    update={
                        "recommendation_at": state.as_of,
                        "source_state_version": state.state_version,
                        "lifecycle_version": previous.lifecycle_version + 1,
                        "status": RecommendationStatus.UNCHANGED,
                        "source_snapshot_ids": state.source_snapshot_ids,
                    }
                )
                recommendations.append(unchanged)
                audit.append(
                    occurred_at=state.as_of,
                    actor=AuditActor.SYSTEM,
                    action="recommendation_unchanged",
                    case_id=state.case_id,
                    recommendation_id=previous.recommendation_id,
                    reason_codes=("duplicate_recommendation_prevented",),
                )
                return
            lifecycle_version = previous.lifecycle_version + 1 if previous else 1
            recommendation_id = (
                previous.recommendation_id
                if previous
                else shadow_id("recommendation", self.config.shadow_run_id, state.case_id)
            )
            action = "recommendation_revised" if previous else "recommendation_created"
            status = RecommendationStatus.UPDATED if previous else RecommendationStatus.CREATED
            audit_record = audit.append(
                occurred_at=state.as_of,
                actor=AuditActor.SYSTEM,
                action=action,
                case_id=state.case_id,
                recommendation_id=recommendation_id,
                reason_codes=result.reason_codes,
                input_references=(result.evaluation_id, policy.evaluation_id),
                output_references=(recommendation_id,),
            )
            recommendation = Recommendation(
                recommendation_id=recommendation_id,
                shadow_run_id=self.config.shadow_run_id,
                case_id=state.case_id,
                detector_version=self.config.detector_version,
                policy_version=self.config.policy_version,
                recommendation_at=state.as_of,
                source_state_version=state.state_version,
                lifecycle_version=lifecycle_version,
                status=status,
                rationale=result.rationale,
                reason_codes=result.reason_codes,
                relevant_fields=result.relevant_fields,
                source_snapshot_ids=state.source_snapshot_ids,
                confidence=result.confidence or ConfidenceClass.LOW,
                uncertainty_factors=result.uncertainty_factors,
                expires_at=state.as_of + self.config.recommendation_expiry,
                reviewer_role_required=self.config.reviewer_roles[0],
                prohibited_follow_on_actions=PROHIBITED_ACTIONS,
                policy_evaluation_id=policy.evaluation_id,
                audit_record_id=audit_record.audit_id,
                warnings=("recommendation_only_no_workflow_effect",),
            )
            recommendations.append(recommendation)
            active[state.case_id] = recommendation
        elif previous and result.outcome is DetectorOutcome.NO_RECOMMENDATION:
            retracted = previous.model_copy(
                update={
                    "recommendation_at": state.as_of,
                    "source_state_version": state.state_version,
                    "lifecycle_version": previous.lifecycle_version + 1,
                    "status": RecommendationStatus.RETRACTED,
                    "rationale": "New structured information resolved the earlier concern.",
                    "reason_codes": ("structured_concern_resolved",),
                    "source_snapshot_ids": state.source_snapshot_ids,
                }
            )
            recommendations.append(retracted)
            del active[state.case_id]
            audit.append(
                occurred_at=state.as_of,
                actor=AuditActor.SYSTEM,
                action="recommendation_retracted",
                case_id=state.case_id,
                recommendation_id=previous.recommendation_id,
                reason_codes=retracted.reason_codes,
            )

    def _expire_before(
        self,
        cutoff: datetime,
        active: dict[object, Recommendation],
        recommendations: list[Recommendation],
        audit: AuditTrail,
    ) -> None:
        for case_id, recommendation in tuple(active.items()):
            if recommendation.expires_at < cutoff:
                expired = recommendation.model_copy(
                    update={
                        "recommendation_at": recommendation.expires_at,
                        "lifecycle_version": recommendation.lifecycle_version + 1,
                        "status": RecommendationStatus.EXPIRED,
                        "rationale": "The recommendation expired without a recorded review.",
                        "reason_codes": ("review_window_expired",),
                    }
                )
                recommendations.append(expired)
                del active[case_id]
                audit.append(
                    occurred_at=recommendation.expires_at,
                    actor=AuditActor.SYSTEM,
                    action="recommendation_expired",
                    case_id=recommendation.case_id,
                    recommendation_id=recommendation.recommendation_id,
                    reason_codes=expired.reason_codes,
                )

    def _validate_checkpoint(self, checkpoint: ReplayCheckpoint, source_fingerprint: str) -> None:
        if checkpoint.shadow_run_id != self.config.shadow_run_id:
            raise ValueError("checkpoint shadow run does not match configuration")
        if checkpoint.source_fingerprint != source_fingerprint:
            raise ValueError("checkpoint source fingerprint does not match intake snapshots")
        if checkpoint.detector_version != self.config.detector_version:
            raise ValueError("checkpoint detector version is incompatible")
        if checkpoint.policy_version != self.config.policy_version:
            raise ValueError("checkpoint policy version is incompatible")
        content = checkpoint.model_dump(mode="python", exclude={"checkpoint_fingerprint"})
        if shadow_fingerprint(content) != checkpoint.checkpoint_fingerprint:
            raise ValueError("checkpoint fingerprint is invalid")

    def _checkpoint(self, **values: Any) -> ReplayCheckpoint:
        resumable = not values["complete"]
        content = {
            "shadow_run_id": self.config.shadow_run_id,
            "last_source_position": values["position"],
            "source_fingerprint": values["source_fingerprint"],
            "detector_version": self.config.detector_version,
            "policy_version": self.config.policy_version,
            "case_state_fingerprints": {
                str(state.case_id): shadow_fingerprint(state) for state in values["states"]
            },
            "active_recommendation_ids": tuple(
                sorted(item.recommendation_id for item in values["active"].values())
            ),
            "audit_root_fingerprint": values["audit_root"],
            "case_states": values["states"] if resumable else (),
            "recommendations": values["recommendations"] if resumable else (),
            "policy_evaluations": values["policies"] if resumable else (),
            "detector_results": values["results"] if resumable else (),
            "audit_records": values["audit_records"] if resumable else (),
        }
        return ReplayCheckpoint.model_validate(
            {**content, "checkpoint_fingerprint": shadow_fingerprint(content)}
        )

    def _manifest(self, **values: Any) -> ShadowRunManifest:
        recommendations = values["recommendations"]
        results = values["results"]
        policies = values["policies"]
        snapshots = values["snapshots"]
        content = {
            "shadow_mode_version": self.config.shadow_mode_version,
            "shadow_run_id": self.config.shadow_run_id,
            "detector_profile": self.config.detector_profile,
            "detector_version": self.config.detector_version,
            "policy_version": self.config.policy_version,
            "source_dataset_fingerprint": self.config.source_dataset_fingerprint,
            "intake_snapshot_fingerprint": values["source_fingerprint"],
            "opportunity_identifier": "opportunity-7def8c82e8b589e5",
            "opportunity_analysis_fingerprint": self.config.opportunity_analysis_fingerprint,
            "simulation_analysis_fingerprint": self.config.simulation_analysis_fingerprint,
            "source_period_start": snapshots[0].available_at if snapshots else None,
            "source_period_end": snapshots[-1].available_at if snapshots else None,
            "replay_ordering": self.config.availability_ordering,
            "source_items_processed": values["processed"],
            "cases_observed": len(values["states"]),
            "eligible_cases": sum(
                policy.status.value.startswith("permitted") for policy in policies
            ),
            "detector_evaluations": len(results),
            "recommendations": sum(
                item.status is RecommendationStatus.CREATED for item in recommendations
            ),
            "abstentions": sum(item.outcome is DetectorOutcome.ABSTAIN for item in results),
            "revisions": sum(
                item.status is RecommendationStatus.UPDATED for item in recommendations
            ),
            "retractions": sum(
                item.status is RecommendationStatus.RETRACTED for item in recommendations
            ),
            "expiries": sum(
                item.status is RecommendationStatus.EXPIRED for item in recommendations
            ),
            "duplicate_suppressions": sum(
                item.status is RecommendationStatus.UNCHANGED for item in recommendations
            ),
            "reviews": 0,
            "policy_blocks": sum(
                not item.status.value.startswith("permitted") for item in policies
            ),
            "stop_condition_breaches": 0,
            "audit_record_count": len(values["audit_records"]),
            "audit_root_fingerprint": values["audit_root"],
            "run_status": "completed" if values["complete"] else "paused",
            "assumptions": (
                "logical replay time is used; no wall-clock sleeping occurs",
                "intake snapshots and all cases are fictional",
            ),
            "warnings": ("no workflow, event history, routing, or communication is changed",),
            "fictional_data_declaration": "All Northstar cases and intake records are fictional.",
            "recommendation_only_declaration": (
                "Outputs request human review and cannot take action."
            ),
        }
        return ShadowRunManifest.model_validate(
            {**content, "manifest_fingerprint": shadow_fingerprint(content)}
        )
