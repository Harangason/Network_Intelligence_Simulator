// Server-seitiger Client für die Engineering-API, genutzt vom Agent (Route
// Handler laufen außerhalb des Next.js-Rewrite-Kontexts und sprechen daher
// direkt mit dem Flask-Backend statt über einen relativen "/api"-Pfad).

import "server-only";

import { currentAgentProjectId } from "@/lib/agent/request-context";

const DEFAULT_ENGINEERING_BASE = "http://127.0.0.1:5050/api/engineering";
const configuredEngineeringBase =
  process.env.SIMULATOR_ENGINEERING_API_URL ?? process.env.ENGINEERING_API_URL;
const ENGINEERING_BASE = configuredEngineeringBase?.includes("/api/engineering")
  ? configuredEngineeringBase.replace(/\/$/, "")
  : DEFAULT_ENGINEERING_BASE;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${ENGINEERING_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Project-ID": currentAgentProjectId(),
      ...init?.headers,
    },
    cache: "no-store",
    signal: AbortSignal.timeout(8000),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { error?: string }).error ?? `Engineering-API-Fehler ${response.status}`);
  }
  return payload as T;
}

export function listObjects(resource: string, params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return request<{ items: Record<string, unknown>[]; count: number }>(
    `/${resource}${suffix ? `?${suffix}` : ""}`,
  );
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

export function inspectCapacityAnalysis() {
  return request<Record<string, unknown>>("/capacity");
}

export function inspectPreflightAnalysis() {
  return request<Record<string, unknown>>("/preflight");
}

export function inspectIntelligenceAssessment() {
  return request<Record<string, unknown>>("/intelligence");
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
