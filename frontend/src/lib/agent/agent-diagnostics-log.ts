import "server-only";

import { appendFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

export const AGENT_DIAGNOSTIC_LOG_FILES = {
  agent: "agent-events.jsonl",
  error: "agent-errors.txt",
  performance: "agent-performance.txt",
  question: "agent-questions.txt",
  workflow: "workflow-status.txt",
} as const;

export type AgentDiagnosticCategory = keyof typeof AGENT_DIAGNOSTIC_LOG_FILES;

function projectRoot() {
  return path.basename(process.cwd()).toLowerCase() === "frontend"
    ? path.dirname(process.cwd())
    : process.cwd();
}

export function agentDiagnosticsDirectory() {
  return path.join(projectRoot(), "backend", "runtime", "agent-diagnostics");
}

export function agentDiagnosticsFilePath(category: AgentDiagnosticCategory) {
  return path.join(agentDiagnosticsDirectory(), AGENT_DIAGNOSTIC_LOG_FILES[category]);
}

function agentEventLogMarkerPath() {
  return path.join(agentDiagnosticsDirectory(), "agent-events.enabled");
}

export async function agentEventLoggingEnabled() {
  if (process.env.NETWORKIS_AGENT_EVENT_LOG === "1") return true;
  try {
    const marker = await readFile(agentEventLogMarkerPath(), "utf8");
    return marker.trim() === "1";
  } catch {
    return false;
  }
}

export async function setAgentEventLoggingEnabled(enabled: boolean) {
  const directory = agentDiagnosticsDirectory();
  await mkdir(directory, { recursive: true });
  if (enabled) {
    await writeFile(agentEventLogMarkerPath(), "1\n", "utf8");
  } else {
    await rm(agentEventLogMarkerPath(), { force: true });
  }
  return {
    enabled: await agentEventLoggingEnabled(),
    file: agentDiagnosticsFilePath("agent"),
  };
}

function safeToken(value: unknown, fallback: string) {
  const normalized = String(value ?? "").trim().replace(/[^a-zA-Z0-9._-]+/g, "-").slice(0, 120);
  return normalized || fallback;
}

function safeDetails(value: unknown, maximum = 8000) {
  try {
    const serialized = typeof value === "string" ? value : JSON.stringify(value ?? {});
    return serialized.replace(/[\r\n\t]+/g, " ").replace(/\s+/g, " ").trim().slice(0, maximum);
  } catch (error) {
    return `unserializable=${error instanceof Error ? error.message : String(error)}`;
  }
}

export async function appendAgentDiagnostic(
  category: AgentDiagnosticCategory,
  input: { projectId?: unknown; runId?: unknown; step?: unknown; event?: unknown; details?: unknown },
) {
  if (category === "agent" && !(await agentEventLoggingEnabled())) return;
  const directory = agentDiagnosticsDirectory();
  await mkdir(directory, { recursive: true });
  await Promise.all(Object.values(AGENT_DIAGNOSTIC_LOG_FILES).map((file) => appendFile(path.join(directory, file), "", "utf8")));
  const line = JSON.stringify({
    timestamp: new Date().toISOString(),
    project: safeToken(input.projectId, "default"),
    run: safeToken(input.runId, "none"),
    step: safeToken(input.step, "unknown"),
    event: safeToken(input.event, category),
    details: safeDetails(input.details),
  });
  await appendFile(path.join(directory, AGENT_DIAGNOSTIC_LOG_FILES[category]), `${line}\n`, "utf8");
}
