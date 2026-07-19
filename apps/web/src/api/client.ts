import { type ZodType } from "zod";

import {
  actionSchema, auditSchema, draftSchema, draftsSchema, engineeringSchema, gatesSchema,
  metricsSchema, opportunitySchema, overviewSchema, pilotSummarySchema, recommendationSchema,
  recommendationsSchema, reviewSchema, rollbackSchema, simulationSchema, workflowSchema,
} from "./schemas";

const configuredBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, schema: ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await fetch(`${configuredBase}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Non-JSON upstream errors retain the status-based message.
    }
    throw new ApiError(message, response.status, response.headers.get("x-request-id"));
  }
  return schema.parse(await response.json());
}

const get = <T>(path: string, schema: ZodType<T>, signal?: AbortSignal) => request(path, schema, { signal });
const post = <T>(path: string, schema: ZodType<T>, body: unknown) => request(path, schema, { method: "POST", body: JSON.stringify(body) });

export const api = {
  overview: (signal?: AbortSignal) => get("/api/v1/demo/overview", overviewSchema, signal),
  workflow: (signal?: AbortSignal) => get("/api/v1/demo/workflow", workflowSchema, signal),
  metrics: (signal?: AbortSignal) => get("/api/v1/demo/metrics", metricsSchema, signal),
  opportunity: (signal?: AbortSignal) => get("/api/v1/demo/opportunity", opportunitySchema, signal),
  simulation: (signal?: AbortSignal) => get("/api/v1/demo/simulation", simulationSchema, signal),
  engineering: (signal?: AbortSignal) => get("/api/v1/demo/engineering", engineeringSchema, signal),
  pilotSummary: (signal?: AbortSignal) => get("/api/v1/pilot/summary", pilotSummarySchema, signal),
  recommendations: (signal?: AbortSignal) => get("/api/v1/pilot/recommendations", recommendationsSchema, signal),
  recommendation: (id: string, signal?: AbortSignal) => get(`/api/v1/pilot/recommendations/${encodeURIComponent(id)}`, recommendationSchema, signal),
  drafts: (signal?: AbortSignal) => get("/api/v1/pilot/drafts", draftsSchema, signal),
  draft: (id: string, signal?: AbortSignal) => get(`/api/v1/pilot/drafts/${encodeURIComponent(id)}`, draftSchema, signal),
  gates: (signal?: AbortSignal) => get("/api/v1/pilot/gates", gatesSchema, signal),
  audit: (signal?: AbortSignal) => get("/api/v1/pilot/audit", auditSchema, signal),
  review: (recommendationId: string, payload: ReviewPayload) => post(`/api/v1/pilot/recommendations/${encodeURIComponent(recommendationId)}/review`, reviewSchema, payload),
  editDraft: (draftId: string, payload: EditDraftPayload) => post(`/api/v1/pilot/drafts/${encodeURIComponent(draftId)}/edit`, draftSchema, payload),
  approveDraft: (draftId: string, payload: ApprovalPayload) => post(`/api/v1/pilot/drafts/${encodeURIComponent(draftId)}/approve`, actionSchema, payload),
  rejectDraft: (draftId: string, payload: DecisionPayload) => post(`/api/v1/pilot/drafts/${encodeURIComponent(draftId)}/reject`, reviewSchema, payload),
  cancelDraft: (draftId: string, payload: DecisionPayload) => post(`/api/v1/pilot/drafts/${encodeURIComponent(draftId)}/cancel`, reviewSchema, payload),
  rollbackDraft: (draftId: string, payload: RollbackPayload) => post(`/api/v1/pilot/drafts/${encodeURIComponent(draftId)}/rollback`, rollbackSchema, payload),
};

export interface DecisionPayload {
  revision_id: string;
  reviewer_role: string;
  decided_at: string;
  structured_reason: string;
  review_minutes: number;
}

export interface ApprovalPayload extends DecisionPayload {
  revision_replay?: EditDraftPayload;
}

export interface ReviewPayload extends DecisionPayload {
  decision: "approve" | "approve_with_edits" | "reject" | "cancel" | "mark_unnecessary" | "request_more_context";
}

export interface EditDraftPayload {
  editor_role: string;
  revised_at: string;
  change_reason: string;
  heading?: string;
  body?: string;
}

export interface RollbackPayload {
  actor_role: string;
  rolled_back_at: string;
  reason: string;
  action_replay?: import("./schemas").PilotAction;
}
