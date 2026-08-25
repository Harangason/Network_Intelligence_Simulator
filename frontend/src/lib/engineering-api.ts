import type {
  EngineeringObject,
  EngineeringRelation,
  EngineeringResource,
  EngineeringSchema,
} from "./types";

const BASE = "/api/engineering";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
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
