import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

export const queryKeys = {
  overview: ["demo", "overview"] as const,
  workflow: ["demo", "workflow"] as const,
  metrics: ["demo", "metrics"] as const,
  opportunity: ["demo", "opportunity"] as const,
  simulation: ["demo", "simulation"] as const,
  engineering: ["demo", "engineering"] as const,
  pilot: ["pilot"] as const,
  summary: ["pilot", "summary"] as const,
  recommendations: ["pilot", "recommendations"] as const,
  drafts: ["pilot", "drafts"] as const,
  audit: ["pilot", "audit"] as const,
  gates: ["pilot", "gates"] as const,
};

export const useOverview = () => useQuery({ queryKey: queryKeys.overview, queryFn: ({ signal }) => api.overview(signal) });
export const useWorkflow = () => useQuery({ queryKey: queryKeys.workflow, queryFn: ({ signal }) => api.workflow(signal) });
export const useMetrics = () => useQuery({ queryKey: queryKeys.metrics, queryFn: ({ signal }) => api.metrics(signal) });
export const useOpportunity = () => useQuery({ queryKey: queryKeys.opportunity, queryFn: ({ signal }) => api.opportunity(signal) });
export const useSimulation = () => useQuery({ queryKey: queryKeys.simulation, queryFn: ({ signal }) => api.simulation(signal) });
export const useEngineering = () => useQuery({ queryKey: queryKeys.engineering, queryFn: ({ signal }) => api.engineering(signal) });
export const usePilotSummary = () => useQuery({ queryKey: queryKeys.summary, queryFn: ({ signal }) => api.pilotSummary(signal) });
export const useRecommendations = () => useQuery({ queryKey: queryKeys.recommendations, queryFn: ({ signal }) => api.recommendations(signal) });
export const useDrafts = () => useQuery({ queryKey: queryKeys.drafts, queryFn: ({ signal }) => api.drafts(signal) });
export const useAudit = () => useQuery({ queryKey: queryKeys.audit, queryFn: ({ signal }) => api.audit(signal) });
export const useGates = () => useQuery({ queryKey: queryKeys.gates, queryFn: ({ signal }) => api.gates(signal) });

function usePilotMutation<TVariables, TData>(mutationFn: (variables: TVariables) => Promise<TData>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn, onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.pilot }) });
}

export const useReviewRecommendation = () => usePilotMutation((input: { recommendationId: string; payload: Parameters<typeof api.review>[1] }) => api.review(input.recommendationId, input.payload));
export const useEditDraft = () => usePilotMutation((input: { draftId: string; payload: Parameters<typeof api.editDraft>[1] }) => api.editDraft(input.draftId, input.payload));
export const useApproveDraft = () => usePilotMutation((input: { draftId: string; payload: Parameters<typeof api.approveDraft>[1] }) => api.approveDraft(input.draftId, input.payload));
export const useRejectDraft = () => usePilotMutation((input: { draftId: string; payload: Parameters<typeof api.rejectDraft>[1] }) => api.rejectDraft(input.draftId, input.payload));
export const useCancelDraft = () => usePilotMutation((input: { draftId: string; payload: Parameters<typeof api.cancelDraft>[1] }) => api.cancelDraft(input.draftId, input.payload));
export const useRollbackDraft = () => usePilotMutation((input: { draftId: string; payload: Parameters<typeof api.rollbackDraft>[1] }) => api.rollbackDraft(input.draftId, input.payload));

