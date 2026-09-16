export type ReasoningResult = {
  reasoning_id: string; simulation_run_id: string; project_id: string; goal: string;
  conclusion: string; confidence: number; validation_status: string; completion_status: string;
  confidence_factors: Record<string, unknown>; completion_checks: Record<string, boolean>;
  observations: { id: string; type: string; timestamp: number; description: string; evidence_refs: string[] }[];
  evidence_refs: { id: string; source_type: string; source_id: string; timestamp: number | null; details: Record<string, unknown> }[];
  hypotheses: { id: string; description: string; status: string; reason: string; confidence: number; evidence_refs: string[] }[];
  causal_chain: { cause: string; effect: string; relation: string; timestamp: number; evidence_refs: string[] }[];
  data_gaps: { code: string; message: string; blocking?: boolean; next_measurement?: string }[];
  recommended_actions: { id: string; type: string; description: string; requires_review: boolean; proposal_supported: boolean }[];
  downstream_effects: Record<string, unknown>[]; findings: { code: string; severity?: string }[];
  continuation: { cursor: number } | null; lineage: Record<string, unknown>;
  time_range?: { start_s: number; end_s: number; focus_s?: number | null };
  comparison: { first_divergence: { timestamp: number; types: string[] } | null; golden_job_id: string } | null;
};

export async function reasoningRequest<T>(project: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/engineering/reasoning${path}`, {
    method: body === undefined ? "GET" : "POST", cache: "no-store",
    headers: { "Content-Type": "application/json", "X-Project-ID": project },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(45000)]) : AbortSignal.timeout(45000),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data) throw new Error(data?.error || `Ursachenanalyse nicht erreichbar (${response.status}).`);
  return data as T;
}

export function traceFocusHref(project: string, job: string, view: string, time: number) {
  if (!["messages", "sequence", "signals", "trace"].includes(view) || !Number.isFinite(time) || time < 0) throw new Error("Ungültiger Trace-Fokus.");
  return `/trace-analysis?${new URLSearchParams({ project, job, view, focus_s: String(time) })}`;
}

export function reasoningFocusTime(result: ReasoningResult | null): number | undefined {
  if (!result) return undefined;
  const causal = result.causal_chain.filter(link => ["INJECTED_CAUSE", "VALIDATED_LATENCY_COMPONENT"].includes(link.relation));
  return causal.length ? Math.min(...causal.map(link => link.timestamp)) : result.observations[0]?.timestamp;
}
