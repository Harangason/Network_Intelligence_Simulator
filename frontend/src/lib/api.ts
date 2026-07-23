import type { Catalog, SimulationJob } from "./types";

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error ?? `API-Fehler ${response.status}`);
  }
  return payload as T;
}

export function getCatalog(): Promise<Catalog> {
  return apiRequest<Catalog>("/api/technologies");
}

export function createSimulation(
  payload: Record<string, unknown>,
  validateOnly: boolean,
): Promise<SimulationJob> {
  return apiRequest<SimulationJob>(
    validateOnly ? "/api/simulations/validate" : "/api/simulations",
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function getSimulation(id: string): Promise<SimulationJob> {
  return apiRequest<SimulationJob>(`/api/simulations/${id}`);
}
