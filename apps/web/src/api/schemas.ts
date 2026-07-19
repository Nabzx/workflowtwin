import { z } from "zod";

export const demoContextSchema = z.object({
  fictional_data: z.literal(true),
  organisation: z.string(),
  declaration: z.string(),
  artefact_fingerprint: z.string(),
});

export const headlineMetricSchema = z.object({
  key: z.string(),
  label: z.string(),
  value: z.number(),
  unit: z.string(),
  note: z.string().nullable(),
});

export const overviewSchema = z.object({
  context: demoContextSchema,
  proposition: z.string(),
  workflow_summary: z.string(),
  metrics: z.array(headlineMetricSchema),
  journey: z.array(z.string()),
  bottleneck: z.string(),
  opportunity: z.string(),
  simulation_result: z.string(),
  pilot_assessment: z.string(),
  authority: z.array(z.string()),
});

const nodeSchema = z.object({
  id: z.string(), label: z.string(), frequency: z.number(), manual_work_rate: z.number(),
  stage: z.string(), x: z.number(), y: z.number(),
});
const edgeSchema = z.object({
  id: z.string(), source: z.string(), target: z.string(), frequency: z.number(),
  median_delay_hours: z.number(), handoff: z.boolean(), rework: z.boolean(), bottleneck: z.boolean(),
});
const variantSchema = z.object({
  id: z.string(), case_count: z.number(), activities: z.array(z.string()),
  median_duration_hours: z.number(), outcome: z.string(),
});
const conformanceSchema = z.object({
  model: z.string(), fully_conforming_rate: z.number(), average_fitness: z.number(), interpretation: z.string(),
});
export const workflowSchema = z.object({
  context: demoContextSchema,
  nodes: z.array(nodeSchema), edges: z.array(edgeSchema), variants: z.array(variantSchema),
  strict: conformanceSchema, governed: conformanceSchema,
  complexity: z.array(headlineMetricSchema),
  filters: z.object({ service_lines: z.array(z.string()), referral_sources: z.array(z.string()) }),
});

const metricPointSchema = z.object({ cohort: z.string(), case_count: z.number(), value: z.number() });
export const metricSeriesSchema = z.object({
  key: z.string(), label: z.string(), unit: z.string(),
  status: z.enum(["calculated", "estimated"]), denominator: z.number(),
  values: z.array(metricPointSchema),
});
export const metricsSchema = z.object({
  context: demoContextSchema,
  overall: z.array(headlineMetricSchema),
  referral_sources: z.array(metricSeriesSchema),
  service_lines: z.array(metricSeriesSchema),
  quality: z.array(z.object({ label: z.string(), value: z.number(), unit: z.string(), status: z.string() })),
  findings: z.array(z.object({ title: z.string(), cohort: z.string(), observed: z.string(), comparison: z.string(), materiality: z.string() })),
  exclusions: z.array(z.string()),
});

export const opportunityCandidateSchema = z.object({
  id: z.string(), title: z.string(), cohort: z.string(), affected_cases: z.number(),
  priority: z.number(), value: z.number(), readiness: z.number(), risk: z.number(),
  confidence: z.number(), result: z.string(),
});
export const evidenceLinkSchema = z.object({ step: z.string(), title: z.string(), detail: z.string(), provenance: z.string() });
export const opportunitySchema = z.object({
  context: demoContextSchema, selected: opportunityCandidateSchema,
  problem_statement: z.string(), workflow_stage: z.string(), burden: z.array(headlineMetricSchema),
  evidence_chain: z.array(evidenceLinkSchema), controls: z.array(z.string()),
  success_metrics: z.array(z.string()), evidence_gaps: z.array(z.string()),
  candidates: z.array(opportunityCandidateSchema),
});

const scenarioMetricSchema = z.object({
  key: z.string(), label: z.string(), baseline: z.number().nullable(), simulated: z.number(), unit: z.string(),
});
export const simulationSchema = z.object({
  context: demoContextSchema,
  scenarios: z.array(z.object({
    id: z.enum(["conservative", "central", "optimistic", "adverse"]),
    affected_cases: z.number(), review_overhead_hours: z.number(), fallbacks: z.number(),
    failures: z.number(), net_burden_hours: z.number(), decision: z.string(), metrics: z.array(scenarioMetricSchema),
  })),
  selected_scenario: z.string(), finding: z.string(), caveats: z.array(z.string()),
});

export const engineeringSchema = z.object({
  context: demoContextSchema, product_path: z.array(z.string()),
  architecture: z.array(z.object({ name: z.string(), responsibility: z.string(), technology: z.string() })),
  stack: z.array(z.string()), quality: z.array(headlineMetricSchema),
  evaluation_journey: z.array(evidenceLinkSchema), decisions: z.array(z.string()),
  limitations: z.array(z.string()), versions: z.record(z.string(), z.string()),
});

const pilotMetricsSchema = z.object({
  incoming_cases: z.number(), detector_positives: z.number(), detector_positive_coverage: z.number(),
  detector_precision: z.number().nullable(), detector_recall: z.number().nullable(),
  recommendations_entering_pilot: z.number(), surfaced_recommendation_coverage: z.number(),
  drafts_created: z.number(), drafts_reviewed: z.number(), drafts_edited: z.number(),
  drafts_approved: z.number(), drafts_rejected: z.number(), fictional_tasks_committed: z.number(),
  rollbacks: z.number(), review_minutes: z.number(), unresolved_drafts: z.number(),
  policy_compliance: z.number(), audit_completeness: z.number(), rollback_success_rate: z.number().nullable(),
  external_communication_attempts: z.number(), operational_workflow_mutations: z.number(),
}).passthrough();
export const gateSchema = z.object({
  gate_id: z.string(), category: z.string(), status: z.enum(["pass", "fail", "not_evaluated"]),
  actual: z.union([z.number(), z.boolean()]).nullable(), threshold: z.union([z.number(), z.boolean()]).nullable(),
  explanation: z.string(),
});
export const pilotSummarySchema = z.object({
  run_id: z.string(), policy_version: z.string(), detector_name: z.string(), detector_lineage: z.string(),
  assessment: z.string(), metrics: pilotMetricsSchema, gates: z.array(gateSchema),
  fictional_declaration: z.string(), no_message_sent: z.literal(true),
});

export const recommendationSchema = z.object({
  recommendation_id: z.string(), detector_evaluation_id: z.string(), case_id: z.string().uuid(),
  snapshot_id: z.string(), detected_at: z.string(), missing_field_ids: z.array(z.string()),
  source_references: z.array(z.string()), requirement_references: z.array(z.string()),
  detector_product_name: z.string(), supported_detector_fingerprint: z.string(),
  original_detector_fingerprint: z.string(), current: z.boolean(),
  unresolved_source_conflict: z.boolean(), recommendation_only: z.literal(true),
});
export const recommendationsSchema = z.array(recommendationSchema);

export const draftRevisionSchema = z.object({
  revision_id: z.string(), previous_revision_id: z.string().nullable(), editor_role: z.string(),
  revised_at: z.string(), change_reason: z.string(), changed_fields: z.array(z.string()),
  heading: z.string(), body: z.string(),
  items: z.array(z.object({ field_id: z.string(), display_name: z.string(), requirement_id: z.string() })),
  audit_reference: z.string(),
});
export const draftSchema = z.object({
  draft_id: z.string(), recommendation_id: z.string(), case_id: z.string().uuid(),
  administrative_recipient_role: z.string(), form_version: z.string(),
  source_snapshot_references: z.array(z.string()), requirements_contract_references: z.array(z.string()),
  created_at: z.string(), expires_at: z.string(), status: z.string(), current_revision_id: z.string(),
  revisions: z.array(draftRevisionSchema), human_review_required: z.literal(true),
  no_message_sent: z.literal(true), fictional_declaration: z.string(),
});
export const draftsSchema = z.array(draftSchema);

export const reviewSchema = z.object({
  review_id: z.string(), draft_id: z.string(), recommendation_id: z.string(), revision_id: z.string(),
  reviewer_role: z.string(), decision: z.string(), decided_at: z.string(), structured_reason: z.string(),
  policy_evaluation_id: z.string(), review_minutes: z.number(),
});
export const actionSchema = z.object({
  action_id: z.string(), idempotency_key: z.string(), recommendation_id: z.string(), draft_id: z.string(),
  revision_id: z.string(), review_id: z.string(), action_type: z.string(), status: z.string(),
  mock_task_id: z.string().nullable(), acted_at: z.string(), actor_role: z.string(),
  no_external_communication: z.literal(true), operational_events_mutated: z.literal(false),
});
export const rollbackSchema = z.object({
  rollback_id: z.string(), action_id: z.string(), mock_task_id: z.string(), actor_role: z.string(),
  reason: z.string(), rolled_back_at: z.string(), restored_status: z.string(), duplicate_request: z.boolean(),
});
export const auditSchema = z.array(z.object({
  audit_id: z.string(), sequence_number: z.number(), occurred_at: z.string(), actor_role: z.string(),
  action: z.string(), object_id: z.string(), input_references: z.array(z.string()),
  output_references: z.array(z.string()), reason_codes: z.array(z.string()),
  previous_record_fingerprint: z.string().nullable(), content_fingerprint: z.string(),
}));
export const gatesSchema = z.array(gateSchema);

export type Overview = z.infer<typeof overviewSchema>;
export type Workflow = z.infer<typeof workflowSchema>;
export type Metrics = z.infer<typeof metricsSchema>;
export type Opportunity = z.infer<typeof opportunitySchema>;
export type Simulation = z.infer<typeof simulationSchema>;
export type Engineering = z.infer<typeof engineeringSchema>;
export type PilotSummary = z.infer<typeof pilotSummarySchema>;
export type Recommendation = z.infer<typeof recommendationSchema>;
export type Draft = z.infer<typeof draftSchema>;
export type AuditRecord = z.infer<typeof auditSchema>[number];

