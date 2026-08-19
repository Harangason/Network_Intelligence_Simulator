import type { Catalog, SimulationJob } from "./types";

function getApiBaseUrl(): string {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/+$/, "");
  }

  if (typeof window === "undefined") {
    return "";
  }

  const { hostname, port, protocol } = window.location;
  const isLocalFrontend =
    (hostname === "127.0.0.1" || hostname === "localhost") && port === "3001";
  if (isLocalFrontend) {
    return "http://127.0.0.1:5050";
  }

  return `${protocol}//${window.location.host}`;
}

function toApiUrl(path: string): string {
  const baseUrl = getApiBaseUrl();
  return baseUrl ? `${baseUrl}${path}` : path;
}

function normalizeSimulationJob(job: SimulationJob): SimulationJob {
  if (!job.artifact_downloads?.length) {
    return job;
  }

  return {
    ...job,
    artifact_downloads: job.artifact_downloads.map((artifact) => ({
      ...artifact,
      url: toApiUrl(artifact.url),
    })),
  };
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(toApiUrl(path), {
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
  ).then(normalizeSimulationJob);
}

export function getSimulation(id: string): Promise<SimulationJob> {
  return apiRequest<SimulationJob>(`/api/simulations/${id}`).then(
    normalizeSimulationJob,
  );
}
