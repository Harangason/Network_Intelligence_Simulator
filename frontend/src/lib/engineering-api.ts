import type {
  EngineeringObject,
  EngineeringProposal,
  EngineeringImportPlan,
  EngineeringImportResult,
  EngineeringRelation,
  EngineeringResource,
  EngineeringSchema,
  EngineeringToolRegistryResponse,
  EcuTransferAnalysis,
  EcuTransferDecision,
  SystemDuplicateCandidate,
  SystemMergeResult,
  StructureAssignment,
  StructureEvaluation,
} from "./types";
import type { NetworkTopology, TopologySyncResult } from "./topology";
import { readActiveProjectId } from "./user-settings";

const BASE = "/api/engineering";

function importBaseUrl(): string {
  if (typeof window !== "undefined" && window.location.port === "13500") {
    return "http://127.0.0.1:15050/api/engineering";
  }
  return BASE;
}

async function importRequest<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${importBaseUrl()}${path}`, {
      ...init,
      headers: { "X-Project-ID": readActiveProjectId(), ...init.headers },
      cache: "no-store",
    });
  } catch (error) {
    throw new Error("Der Engineering-Importdienst ist nicht erreichbar.", { cause: error });
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { error?: string }).error ?? `Import-Fehler ${response.status}`);
  }
  return payload as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Project-ID": readActiveProjectId(),
        ...init?.headers,
      },
      cache: "no-store",
      signal: init && "signal" in init ? init.signal : AbortSignal.timeout(5000),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new Error("Die Engineering-API antwortet nicht innerhalb von 5 Sekunden.");
    }
    throw new Error("Die Engineering-API ist nicht erreichbar.", { cause: error });
  }
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { error?: string }).error ?? `API-Fehler ${response.status}`);
  }
  return payload as T;
}

export function getEngineeringSchema(): Promise<EngineeringSchema> {
  return request<EngineeringSchema>("/schema");
}

export async function listEngineeringTools(filters: {
  category?: string;
  industry?: string;
  status?: string;
  approval_required?: boolean;
  workflow_step?: string;
} = {}): Promise<EngineeringToolRegistryResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === "") continue;
    params.set(key, String(value));
  }
  const query = params.toString();
  return request<EngineeringToolRegistryResponse>(`/tools${query ? `?${query}` : ""}`);
}

export function syncEngineeringTopology(
  topology: Pick<NetworkTopology, "nodes" | "edges">,
): Promise<TopologySyncResult> {
  return request<TopologySyncResult>("/topology/sync", {
    method: "POST",
    body: JSON.stringify({
      topology_id: "studio-network",
      ...topology,
      // This call enriches the editor with canonical Engineering IDs. Only the
      // explicit workflow topology endpoint may persist and invalidate builds.
      persist_workflow: false,
    }),
    signal: null,
  });
}

export async function previewEngineeringImport(file: File): Promise<EngineeringImportPlan> {
  const body = new FormData();
  body.append("file", file);
  return importRequest<EngineeringImportPlan>("/imports/preview", { method: "POST", body });
}

export function commitEngineeringImport(
  plan: EngineeringImportPlan,
): Promise<EngineeringImportResult> {
  return importRequest<EngineeringImportResult>("/imports/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(plan),
  });
}

export async function listEngineeringObjects(
  resource: EngineeringResource,
  filters: Record<string, string | undefined> = {},
): Promise<EngineeringObject[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  const { items } = await request<{ items: EngineeringObject[]; count: number }>(
    `/${resource}${query ? `?${query}` : ""}`,
  );
  return items;
}

export async function listAllEngineeringObjects(
  resource: EngineeringResource,
): Promise<EngineeringObject[]> {
  const items: EngineeringObject[] = [];
  const pageSize = 500;
  for (let offset = 0; ; offset += pageSize) {
    const page = await listEngineeringObjects(resource, {
      limit: String(pageSize),
      offset: String(offset),
    });
    items.push(...page);
    if (page.length < pageSize) return items;
  }
}

export function getEngineeringObject(
  resource: EngineeringResource,
  id: string,
): Promise<EngineeringObject> {
  return request<EngineeringObject>(`/${resource}/${id}`);
}

export function createEngineeringObject(
  resource: EngineeringResource,
  payload: Record<string, unknown>,
): Promise<EngineeringObject> {
  return request<EngineeringObject>(`/${resource}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateEngineeringObject(
  resource: EngineeringResource,
  id: string,
  payload: Record<string, unknown>,
): Promise<EngineeringObject> {
  return request<EngineeringObject>(`/${resource}/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteEngineeringObject(resource: EngineeringResource, id: string): Promise<void> {
  return request<void>(`/${resource}/${id}`, { method: "DELETE" });
}

export function listEngineeringObjectVersions(
  resource: EngineeringResource,
  id: string,
): Promise<Record<string, unknown>[]> {
  return request<{ items: Record<string, unknown>[] }>(`/${resource}/${id}/versions`).then(
    (result) => result.items,
  );
}

export async function listEngineeringRelations(filters: {
  object_type?: string;
  object_id?: string;
  relation_type?: string;
} = {}): Promise<EngineeringRelation[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  const { items } = await request<{ items: EngineeringRelation[]; count: number }>(
    `/relations${query ? `?${query}` : ""}`,
  );
  return items;
}

export function createEngineeringRelation(payload: {
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  relation_type: string;
  attributes?: Record<string, unknown>;
}): Promise<EngineeringRelation> {
  return request<EngineeringRelation>("/relations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteEngineeringRelation(id: string): Promise<void> {
  return request<void>(`/relations/${id}`, { method: "DELETE" });
}

export function evaluateEngineeringStructure(
  selections: Record<string, string[]>,
): Promise<StructureEvaluation> {
  return request<StructureEvaluation>("/structure/evaluate", {
    method: "POST",
    body: JSON.stringify({ selections, actor: "structure-tree-reviewer" }),
    signal: null,
  });
}

export function applyEngineeringStructure(payload: {
  proposal_id?: string;
  assignments: StructureAssignment[];
  object_updates?: Array<{
    object_type: string;
    id: string;
    updates: Record<string, unknown>;
  }>;
}): Promise<{ count: number; applied: Array<Record<string, unknown>> }> {
  return request("/structure/apply", {
    method: "POST",
    body: JSON.stringify({ ...payload, actor: "structure-tree-reviewer" }),
    signal: null,
  });
}

export function rejectEngineeringStructureProposal(id: string): Promise<EngineeringProposal> {
  return request<EngineeringProposal>(`/structure/proposals/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor: "structure-tree-reviewer" }),
  });
}

export function analyzeEcuStructureTransfer(
  sourceHardwareId: string,
  targetHardwareIds: string[],
): Promise<EcuTransferAnalysis> {
  return request<EcuTransferAnalysis>("/structure/transfer/analyze", {
    method: "POST",
    body: JSON.stringify({
      source_hardware_id: sourceHardwareId,
      target_hardware_ids: targetHardwareIds,
      actor: "structure-transfer-reviewer",
    }),
    signal: null,
  });
}

export function applyEcuStructureTransfer(id: string, decisions: EcuTransferDecision[]): Promise<{
  created: number;
  reused: number;
  skipped: number;
  already_applied: boolean;
}> {
  return request(`/structure/transfer/${id}/apply`, {
    method: "POST",
    body: JSON.stringify({ actor: "structure-transfer-reviewer", decisions }),
    signal: null,
  });
}

export async function listSystemDuplicateCandidates(): Promise<SystemDuplicateCandidate[]> {
  const result = await request<{ count: number; items: SystemDuplicateCandidate[] }>(
    "/structure/system-duplicates",
  );
  return result.items;
}

export function mergeSystemDuplicate(candidate: SystemDuplicateCandidate): Promise<SystemMergeResult> {
  return request<SystemMergeResult>("/structure/system-duplicates/merge", {
    method: "POST",
    body: JSON.stringify({
      candidate_key: candidate.candidate_key,
      canonical_hardware_id: candidate.canonical_hardware.id,
      duplicate_hardware_id: candidate.duplicate_hardware.id,
      actor: "structure-tree-reviewer",
    }),
    signal: null,
  });
}

export function rejectEcuStructureTransfer(id: string): Promise<EngineeringProposal> {
  return request<EngineeringProposal>(`/structure/transfer/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor: "structure-transfer-reviewer" }),
  });
}

export async function listEngineeringProposals(): Promise<EngineeringProposal[]> {
  const result = await request<{ items: EngineeringProposal[]; count: number }>("/proposals?limit=200");
  return result.items;
}

export function updateEngineeringProposal(
  id: string,
  proposedObjects: Array<Record<string, unknown>>,
): Promise<EngineeringProposal> {
  return request<EngineeringProposal>(`/proposals/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ proposed_objects: proposedObjects, actor: "human-reviewer" }),
  });
}

export function validateEngineeringProposal(id: string): Promise<EngineeringProposal> {
  return request<EngineeringProposal>(`/proposals/${id}/validate`, {
    method: "POST",
    body: JSON.stringify({ actor: "human-reviewer" }),
  });
}

export function approveEngineeringProposal(id: string, indexes: number[]): Promise<EngineeringProposal> {
  return request<EngineeringProposal>(`/proposals/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ indexes, actor: "human-reviewer" }),
  });
}

export function approveAllValidEngineeringProposals(): Promise<{ items: EngineeringProposal[]; count: number }> {
  return request<{ items: EngineeringProposal[]; count: number }>("/proposals/approve-all-valid", {
    method: "POST",
    body: JSON.stringify({ actor: "human-reviewer" }),
  });
}

export function rejectEngineeringProposal(id: string): Promise<EngineeringProposal> {
  return request<EngineeringProposal>(`/proposals/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ actor: "human-reviewer" }),
  });
}

export const RESOURCE_LABELS: Record<EngineeringResource, string> = {
  "hardware-nodes": "Hardware-Knoten",
  functions: "Funktionen",
  interfaces: "Interfaces",
  messages: "Nachrichten",
  signals: "Signale",
};

export const RESOURCE_TO_OBJECT_TYPE: Record<EngineeringResource, string> = {
  "hardware-nodes": "HardwareNode",
  functions: "Function",
  interfaces: "Interface",
  messages: "Message",
  signals: "Signal",
};
