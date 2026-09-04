import type { RoutingEntry, RoutingProposal, RoutingSchema } from "./types";
import { readActiveProjectId } from "./user-settings";

const BASE = "/api/engineering/routing";

function routingBaseUrl(): string {
  return BASE;
}

async function request<T>(path = "", init?: RequestInit): Promise<T> {
  const response = await fetch(`${routingBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Project-ID": readActiveProjectId(),
      ...init?.headers,
    },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { error?: string }).error ?? `Routing-API-Fehler ${response.status}`);
  }
  return payload as T;
}

export async function listRoutes(): Promise<RoutingEntry[]> {
  const items: RoutingEntry[] = [];
  const pageSize = 500;
  for (let offset = 0; ; offset += pageSize) {
    const page = await request<{ items: RoutingEntry[] }>(`?limit=${pageSize}&offset=${offset}`);
    items.push(...page.items);
    if (page.items.length < pageSize) return items;
  }
}

export function getRoutingSchema(): Promise<RoutingSchema> {
  return request<RoutingSchema>("/schema");
}

export function createRoute(payload: Record<string, unknown>): Promise<RoutingEntry> {
  return request<RoutingEntry>("", { method: "POST", body: JSON.stringify(payload) });
}

export function updateRoute(id: string, payload: Record<string, unknown>): Promise<RoutingEntry> {
  return request<RoutingEntry>(`/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteRoute(id: string): Promise<void> {
  return request<void>(`/${id}?actor=routing-ui`, { method: "DELETE" });
}

export function validateRoute(id: string): Promise<RoutingEntry> {
  return request<RoutingEntry>(`/${id}/validate`, {
    method: "POST",
    body: JSON.stringify({ actor: "routing-ui" }),
  });
}

export function approveRoutes(routeIds: string[]): Promise<{ items: RoutingEntry[]; count: number }> {
  return request("/approve-selected", {
    method: "POST",
    body: JSON.stringify({ route_ids: routeIds, actor: "routing-ui" }),
  });
}

export function approveAllValid(): Promise<{ items: RoutingEntry[]; count: number }> {
  return request("/approve-all-valid", {
    method: "POST",
    body: JSON.stringify({ actor: "routing-ui" }),
  });
}

export function rejectRoutes(routeIds: string[], reason: string): Promise<{ items: RoutingEntry[]; count: number }> {
  return request("/reject-selected", {
    method: "POST",
    body: JSON.stringify({ route_ids: routeIds, reason, actor: "routing-ui" }),
  });
}

export function generateRoutes(payload: Record<string, unknown>): Promise<RoutingProposal> {
  return request<RoutingProposal>("/generate", { method: "POST", body: JSON.stringify(payload) });
}

export async function listRoutingProposals(): Promise<RoutingProposal[]> {
  return (await request<{ items: RoutingProposal[] }>("/proposals?limit=200")).items;
}

export function acceptRoutingProposal(proposalId: string, indexes: number[]): Promise<{ items: RoutingEntry[] }> {
  return request(`/proposals/${proposalId}/accept`, {
    method: "POST",
    body: JSON.stringify({ indexes, actor: "routing-ui" }),
  });
}

export function importRoutes(routes: unknown[]): Promise<{ items: RoutingEntry[]; count: number }> {
  return request("/import", {
    method: "POST",
    body: JSON.stringify({ routes, actor: "routing-ui" }),
  });
}

export function getApprovedRoutingConfig(): Promise<Record<string, unknown>> {
  return request("/approved/config");
}
