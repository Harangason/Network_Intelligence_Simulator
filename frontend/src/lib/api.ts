import type { Catalog, SimulationJob } from "./types";

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      cache: "no-store",
      signal: controller.signal,
    });
    const payload: unknown = await response.json();
    if (!response.ok) {
      const message = typeof payload === "object" && payload !== null && "error" in payload
        ? String(payload.error)
        : `API-Fehler ${response.status}`;
      throw new Error(message);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Der Server antwortet nicht. Bitte erneut versuchen.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
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
