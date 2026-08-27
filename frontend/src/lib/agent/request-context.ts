import "server-only";

import { AsyncLocalStorage } from "node:async_hooks";

type AgentRequestContext = {
  projectId: string;
  requestText: string;
};

const agentRequestContext = new AsyncLocalStorage<AgentRequestContext>();

export function normalizeAgentProjectId(value: unknown): string {
  const normalized = String(value ?? "")
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return normalized || "default";
}

export function runWithAgentProject<T>(projectId: unknown, callback: () => T, requestText: unknown = ""): T {
  return agentRequestContext.run({
    projectId: normalizeAgentProjectId(projectId),
    requestText: String(requestText ?? ""),
  }, callback);
}

export function currentAgentProjectId(): string {
  return agentRequestContext.getStore()?.projectId ?? "default";
}

export function currentAgentRequestText(): string {
  return agentRequestContext.getStore()?.requestText ?? "";
}

export function setCurrentAgentRequestText(value: unknown): void {
  const context = agentRequestContext.getStore();
  if (context) context.requestText = String(value ?? "");
}
