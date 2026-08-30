// Server-seitiger Client für die Engineering-API, genutzt vom Agent (Route
// Handler laufen außerhalb des Next.js-Rewrite-Kontexts und sprechen daher
// direkt mit dem Flask-Backend statt über einen relativen "/api"-Pfad).

import "server-only";

import { currentAgentProjectId } from "@/lib/agent/request-context";

const DEFAULT_ENGINEERING_BASE = "http://127.0.0.1:15050/api/engineering";
const configuredEngineeringBase =
  process.env.SIMULATOR_ENGINEERING_API_URL ?? process.env.ENGINEERING_API_URL;
const ENGINEERING_BASE = configuredEngineeringBase?.includes("/api/engineering")
  ? configuredEngineeringBase.replace(/\/$/, "")
  : DEFAULT_ENGINEERING_BASE;
const DEFAULT_SIMULATOR_BASE = "http://127.0.0.1:15050/api";
const configuredSimulatorBase = process.env.SIMULATOR_API_URL;
const SIMULATOR_BASE = configuredSimulatorBase?.includes("/api")
  ? configuredSimulatorBase.replace(/\/$/, "")
  : DEFAULT_SIMULATOR_BASE;

type EngineeringRequestInit = RequestInit & { timeoutMs?: number };

async function request<T>(path: string, init?: EngineeringRequestInit): Promise<T> {
  const { timeoutMs = 8000, ...requestInit } = init ?? {};
  const response = await fetch(`${ENGINEERING_BASE}${path}`, {
    ...requestInit,
    headers: {
      "Content-Type": "application/json",
      "X-Project-ID": currentAgentProjectId(),
      ...requestInit.headers,
    },
    cache: "no-store",
    signal: requestInit.signal ?? AbortSignal.timeout(timeoutMs),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { error?: string }).error ?? `Engineering-API-Fehler ${response.status}`);
  }
  return payload as T;
}

export async function listObjects(
  resource: string,
  params: Record<string, string | undefined> = {},
) {
  const pageSize = 500;
  const items: Record<string, unknown>[] = [];
  let offset = Number.parseInt(params.offset ?? "0", 10) || 0;

  for (;;) {
    const query = new URLSearchParams({
      limit: String(pageSize),
      offset: String(offset),
    });
    for (const [key, value] of Object.entries(params)) {
      if (value && key !== "limit" && key !== "offset") query.set(key, value);
    }
    const page = await request<{ items: Record<string, unknown>[]; count: number }>(
      `/${resource}?${query.toString()}`,
    );
    items.push(...page.items);

    if (page.items.length < pageSize) break;
    offset += pageSize;
  }

  return { items, count: items.length };
}

export function getObject(resource: string, id: string) {
  return request<Record<string, unknown>>(`/${resource}/${id}`);
}

export function createObject(resource: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/${resource}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateObject(resource: string, id: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/${resource}/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listRelations(params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return request<{ items: Record<string, unknown>[]; count: number }>(
    `/relations${suffix ? `?${suffix}` : ""}`,
  );
}

export function createRelation(payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/relations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createProposal(payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/proposals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createEngineeringWorkload(payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/workloads", {
    method: "POST",
    body: JSON.stringify(payload),
    timeoutMs: 15_000,
  });
}

export function startEngineeringWorkload(id: string, actor = "engineering-chat-agent") {
  return request<Record<string, unknown>>(`/workloads/${id}/start`, {
    method: "POST",
    body: JSON.stringify({ actor }),
    timeoutMs: 60_000,
  });
}

export function getEngineeringWorkload(id: string) {
  return request<Record<string, unknown>>(`/workloads/${id}`);
}

export function getEngineeringWorkloadProgress(id: string) {
  return request<Record<string, unknown>>(`/workloads/${id}/progress`);
}

export function getEngineeringWorkloadObjects(id: string) {
  return request<{ items: Record<string, unknown>[]; count: number }>(`/workloads/${id}/objects`);
}

export function listEngineeringProposals(params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return request<{ items: Record<string, unknown>[]; count: number }>(
    `/proposals${suffix ? `?${suffix}` : ""}`,
  );
}

export function validateEngineeringProposal(id: string, actor = "engineering-chat-agent") {
  return request<Record<string, unknown>>(`/proposals/${id}/validate`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export function approveEngineeringProposal(
  id: string,
  indexes?: number[],
  actor = "engineering-chat-agent",
  timeoutMs = 8000,
) {
  return request<Record<string, unknown>>(`/proposals/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ indexes, actor }),
    timeoutMs,
  });
}

export function approveAllValidEngineeringProposals(actor = "engineering-chat-agent") {
  return request<{ items: Record<string, unknown>[]; count?: number }>("/proposals/approve-all-valid", {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export function listRoutingEntries() {
  return request<{ items: Record<string, unknown>[]; count: number }>("/routing?limit=500");
}

export function getRoutingEntry(id: string) {
  return request<Record<string, unknown>>(`/routing/${id}`);
}

export function findRoutingPaths(source: string, target: string) {
  const query = new URLSearchParams({ source, target });
  return request<{ items: Record<string, unknown>[] }>(`/routing/paths?${query}`);
}

export function generateRoutingProposal(payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/routing/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function validateRoutingEntry(id: string, actor = "engineering-chat-agent") {
  return request<Record<string, unknown>>(`/routing/${id}/validate`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export function getRoutingPath(id: string) {
  return request<Record<string, unknown>>(`/routing/${id}/path`);
}

export function getRoutingEvidence(id: string) {
  return request<Record<string, unknown>>(`/routing/${id}/evidence`);
}

export function getRoutingSchema() {
  return request<Record<string, unknown>>("/routing/schema");
}

export function listRoutingProposals() {
  return request<{ items: Record<string, unknown>[]; count: number }>("/routing/proposals?limit=200");
}

export function updateRoutingProposal(id: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/routing/proposals/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function acceptRoutingProposal(id: string, indexes: number[], actor = "engineering-wizard") {
  return request<{ items: Record<string, unknown>[]; count: number }>(`/routing/proposals/${id}/accept`, {
    method: "POST",
    body: JSON.stringify({ indexes, actor }),
  });
}

export function deleteRoutingProposal(id: string, actor = "engineering-chat-agent") {
  return request<void>(`/routing/proposals/${id}?actor=${encodeURIComponent(actor)}`, { method: "DELETE" });
}

export function validateRoutingTable() {
  return request<Record<string, unknown>>("/routing/validate", {
    method: "POST",
    body: JSON.stringify({ actor: "engineering-chat-agent" }),
  });
}

export function inspectWorkflowState() {
  return request<Record<string, unknown>>("/workflow");
}

export function saveWorkflowContext(context: Record<string, unknown>) {
  return request<Record<string, unknown>>("/workflow/context", {
    method: "PATCH",
    body: JSON.stringify(context),
  });
}

export function saveWorkflowTopology(topology: Record<string, unknown>) {
  return request<Record<string, unknown>>("/workflow/topology", {
    method: "PUT",
    body: JSON.stringify({ topology, actor: "engineering-chat-agent" }),
  });
}

export function saveWorkflowParameters(parameters: Record<string, unknown>) {
  return request<Record<string, unknown>>("/workflow/parameters", {
    method: "PATCH",
    body: JSON.stringify({ parameters, actor: "engineering-chat-agent" }),
  });
}

export function inspectWorkflowSnapshots() {
  return request<Record<string, unknown>>("/workflow/snapshots");
}

export function inspectCapacityAnalysis() {
  return request<Record<string, unknown>>("/capacity");
}

export function calculateCapacityAnalysis(overrides: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>("/capacity/calculate", {
    method: "POST",
    body: JSON.stringify({ overrides }),
  });
}

export function inspectPreflightAnalysis() {
  return request<Record<string, unknown>>("/preflight");
}

export function runPreflightAnalysis() {
  return request<Record<string, unknown>>("/preflight", {
    method: "POST",
    body: "{}",
  });
}

export function createWorkflowSimulationSnapshot(configuration: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>("/workflow/simulation-snapshots", {
    method: "POST",
    body: JSON.stringify({ configuration }),
  });
}

export function inspectSimulationModelCatalog() {
  return request<Record<string, unknown>>("/simulation/catalog");
}

export function inspectSimulationScenarios() {
  return request<{ items: Record<string, unknown>[]; count: number }>("/simulation/scenarios");
}

export function createSimulationScenarioDefinition(payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/simulation/scenarios", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function inspectSimulationFaultProposals() {
  return request<{ items: Record<string, unknown>[]; count: number }>("/simulation/fault-proposals");
}

export function proposeSimulationFaults() {
  return request<{ items: Record<string, unknown>[]; count: number }>("/simulation/fault-proposals", {
    method: "POST",
    body: JSON.stringify({ actor: "engineering-chat-agent" }),
  });
}

export function reviewSimulationFaultProposal(proposalId: string, action: "ACCEPT" | "EDIT" | "REJECT", changes: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>(`/simulation/fault-proposals/${proposalId}/review`, {
    method: "POST",
    body: JSON.stringify({ action, changes, actor: "engineering-chat-agent" }),
  });
}

export function inspectSimulationTraces(jobId?: string) {
  return request<{ items: Record<string, unknown>[]; count: number }>(`/simulation/traces${jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""}`);
}

async function simulatorRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${SIMULATOR_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Project-ID": currentAgentProjectId(),
      ...init?.headers,
    },
    cache: "no-store",
    signal: AbortSignal.timeout(20_000),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { error?: string }).error ?? `Simulator-API-Fehler ${response.status}`);
  }
  return payload as T;
}

export async function startWorkflowSimulation(configuration: Record<string, unknown>) {
  const snapshot = await createWorkflowSimulationSnapshot(configuration);
  const snapshotId = String(snapshot.id ?? "");
  if (!snapshotId) throw new Error("Der Workflow lieferte keine SimulationSnapshot-ID.");
  let job = await simulatorRequest<Record<string, unknown>>("/simulations", {
    method: "POST",
    body: JSON.stringify({
      workflow_managed: true,
      workflow_snapshot_id: snapshotId,
      project_id: currentAgentProjectId(),
      config: configuration,
    }),
  });
  const jobId = String(job.id ?? "");
  if (!jobId) throw new Error("Der Simulator lieferte keine Job-ID.");
  const deadline = Date.now() + 90_000;
  while (!["completed", "failed", "canceled"].includes(String(job.status ?? "").toLowerCase())) {
    if (Date.now() >= deadline) {
      throw new Error(`Simulation ${jobId} laeuft weiter, hat aber das 90-Sekunden-Wartefenster ueberschritten.`);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
    job = await simulatorRequest<Record<string, unknown>>(`/simulations/${jobId}`);
  }
  if (String(job.status).toLowerCase() !== "completed") {
    throw new Error(String(job.error ?? `Simulation ${jobId} endete mit Status ${String(job.status)}.`));
  }
  return { snapshot, job };
}

export function startSimulationCampaign(payload: {
  name: string;
  seeds: number[];
  scenarios: Array<Record<string, unknown>>;
  config: Record<string, unknown>;
}) {
  return simulatorRequest<Record<string, unknown>>("/simulation-campaigns", {
    method: "POST",
    body: JSON.stringify({ ...payload, project_id: currentAgentProjectId() }),
  });
}

export function inspectSimulationCampaign(campaignId: string) {
  return simulatorRequest<Record<string, unknown>>(`/simulation-campaigns/${campaignId}?project_id=${encodeURIComponent(currentAgentProjectId())}`);
}

export function inspectIntelligenceAssessment() {
  return request<Record<string, unknown>>("/intelligence");
}

export function runIntelligenceAssessment() {
  return request<Record<string, unknown>>("/intelligence/assess", {
    method: "POST",
    body: "{}",
  });
}

export function createIntelligenceProposal(payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/intelligence/proposals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function calculateCapacityScenario(overrides: Record<string, unknown>) {
  return request<Record<string, unknown>>("/capacity/scenario", {
    method: "POST",
    body: JSON.stringify({ overrides }),
  });
}

export function optimizeCapacityAnalysis() {
  return request<Record<string, unknown>>("/capacity/optimize", {
    method: "POST",
    body: "{}",
  });
}

export function searchEngineeringKnowledge(payload: {
  query: string;
  selected_object_ids?: string[];
  filters?: Record<string, unknown>;
  limit?: number;
}) {
  return request<{
    count: number;
    items: Array<Record<string, unknown>>;
    context: Record<string, unknown>;
    pipeline: string[];
  }>("/knowledge/search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
