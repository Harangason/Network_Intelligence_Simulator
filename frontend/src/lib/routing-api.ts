import type { RoutingEntry, RoutingProposal, RoutingSchema } from "./types";
import { readActiveProjectId } from "./user-settings";

const BASE = "/api/engineering/routing";

const DEV_ROUTING_SCHEMA: RoutingSchema = {
  routing_types: [
    "UNICAST",
    "MULTICAST",
    "BROADCAST",
    "PUBLISH_SUBSCRIBE",
    "REQUEST_RESPONSE",
    "CYCLIC",
    "EVENT_BASED",
    "CONDITIONAL",
    "REDUNDANT",
    "GATEWAY_ROUTED",
  ],
  protocols: [
    "CAN",
    "CAN_FD",
    "CAN_XL",
    "LIN",
    "FLEXRAY",
    "ETHERNET",
    "SOME_IP",
    "TCP",
    "UDP",
    "DDS",
    "ROS_2",
    "OPC_UA",
    "ETHERCAT",
    "PROFINET",
    "MODBUS",
    "ARINC",
    "MIL_STD_1553",
    "CUSTOM",
  ],
  priorities: ["LOW", "NORMAL", "HIGH", "CRITICAL"],
  redundancy_modes: ["NONE", "PRIMARY", "SECONDARY", "BACKUP", "REDUNDANT_ACTIVE", "REDUNDANT_STANDBY"],
  permissions: [
    "ROUTING_READ",
    "ROUTING_CREATE",
    "ROUTING_EDIT",
    "ROUTING_GENERATE",
    "ROUTING_VALIDATE",
    "ROUTING_REVIEW",
    "ROUTING_APPROVE",
    "ROUTING_ADMIN",
  ],
  agent_permissions: ["ROUTING_READ", "ROUTING_GENERATE", "ROUTING_VALIDATE"],
};

function canUseLocalEmptyState(error: unknown): boolean {
  if (typeof window === "undefined" || !["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return false;
  }
  const message = error instanceof Error ? error.message : String(error);
  return message === "Routing-API-Fehler 500";
}

async function localEmptyState<T>(operation: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await operation();
  } catch (error) {
    if (canUseLocalEmptyState(error)) return fallback;
    throw error;
  }
}

async function request<T>(path = "", init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
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
  return localEmptyState(
    async () => (await request<{ items: RoutingEntry[] }>("?limit=500")).items,
    [],
  );
}

export function getRoutingSchema(): Promise<RoutingSchema> {
  return localEmptyState(() => request<RoutingSchema>("/schema"), DEV_ROUTING_SCHEMA);
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
  return localEmptyState(
    async () => (await request<{ items: RoutingProposal[] }>("/proposals?limit=200")).items,
    [],
  );
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
