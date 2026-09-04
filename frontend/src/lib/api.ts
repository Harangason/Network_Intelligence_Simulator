import type { Catalog, SimulationJob } from "./types";
import { createLocalSimulation, getLocalSimulation, localCatalog } from "./local-simulator";
import { compactProjectId, readActiveProjectId } from "./user-settings";

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const signal = init?.signal ?? AbortSignal.timeout(10000);
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Project-ID": readActiveProjectId(),
        ...init?.headers,
      },
      cache: "no-store",
      signal,
    });
  } catch (error) {
    if (isRequestTimeout(error)) {
      throw new Error("API-Zeitlimit: Der lokale Simulationsdienst hat innerhalb von 10 s nicht geantwortet. Das passiert meist bei einem nicht gestarteten Backend, einem hängenden Simulationslauf oder einem noch initialisierenden Dienst.");
    }
    throw error;
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error((payload as { error?: string }).error ?? `API-Fehler ${response.status}`);
  return payload as T;
}

function isRequestTimeout(error: unknown) {
  if (typeof DOMException !== "undefined" && error instanceof DOMException) {
    return error.name === "TimeoutError" || error.name === "AbortError";
  }
  return error instanceof Error && /timed out|timeout|aborted/i.test(error.message);
}

function projectPath(path: string, projectId: string) {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}project=${encodeURIComponent(compactProjectId(projectId))}`;
}

function announceMode(mode: "backend" | "browser") {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("simulator-mode", { detail: mode }));
}

export async function getCatalog(): Promise<Catalog> {
  try {
    const catalog = await apiRequest<Catalog>("/api/technologies");
    announceMode("backend");
    return catalog;
  } catch {
    announceMode("browser");
    return localCatalog;
  }
}

export async function createSimulation(payload: Record<string, unknown>, validateOnly: boolean): Promise<SimulationJob> {
  try {
    const job = await apiRequest<SimulationJob>(validateOnly ? "/api/simulations/validate" : "/api/simulations", { method: "POST", body: JSON.stringify(payload) });
    announceMode("backend");
    return job;
  } catch (error) {
    if (payload.workflow_managed) throw error;
    if (error instanceof SyntaxError) throw error;
    announceMode("browser");
    return createLocalSimulation(payload, validateOnly);
  }
}

export async function listSimulations(): Promise<SimulationJob[]> {
  const response = await apiRequest<{ jobs: SimulationJob[] }>("/api/simulations");
  return response.jobs;
}

export async function getSimulation(id: string): Promise<SimulationJob> {
  if (id.startsWith("local-")) {
    announceMode("browser");
    return getLocalSimulation(id);
  }
  return apiRequest<SimulationJob>(`/api/simulations/${id}`);
}

export async function cancelSimulation(id: string): Promise<SimulationJob> {
  return apiRequest<SimulationJob>(`/api/simulations/${id}/cancel`, { method: "POST", body: "{}" });
}

export type FaultProposal = {
  proposal_id: string;
  title: string;
  fault_scope: "SIGNAL" | "MESSAGE" | "NETWORK";
  fault_type: string;
  target: Record<string, unknown>;
  configuration: Record<string, unknown>;
  rationale: string;
  evidence: Array<Record<string, unknown>>;
  model: string;
  status: "AI_GENERATED" | "READY_FOR_REVIEW" | "APPROVED" | "REJECTED" | "SUPERSEDED";
};

export async function saveSimulationScenario(projectId: string, payload: Record<string, unknown>) {
  return apiRequest<Record<string, unknown>>(projectPath("/api/engineering/simulation/scenarios", projectId), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listSimulationFaultProposals(projectId: string) {
  return apiRequest<{ items: FaultProposal[]; count: number }>(projectPath("/api/engineering/simulation/fault-proposals", projectId));
}

export async function createSimulationFaultProposals(projectId: string) {
  return apiRequest<{ items: FaultProposal[]; count: number }>(projectPath("/api/engineering/simulation/fault-proposals", projectId), {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  });
}

export async function reviewSimulationFaultProposal(projectId: string, proposalId: string, action: "ACCEPT" | "EDIT" | "REJECT", changes?: Record<string, unknown>) {
  return apiRequest<FaultProposal>(projectPath(`/api/engineering/simulation/fault-proposals/${proposalId}/review`, projectId), {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, action, changes, actor: "simulation-user" }),
  });
}
