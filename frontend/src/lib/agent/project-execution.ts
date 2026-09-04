const activeProjects = new Set<string>();

export function isCompletedProjectWorkflowRun(workflow: unknown, runId: string): boolean {
  if (!runId || !workflow || typeof workflow !== "object") return false;
  const context = (workflow as { context?: unknown }).context;
  if (!context || typeof context !== "object") return false;
  const execution = (context as { agent_execution?: unknown }).agent_execution;
  if (!execution || typeof execution !== "object") return false;
  const state = execution as { run_id?: unknown; state?: unknown };
  return String(state.run_id ?? "") === runId && String(state.state ?? "").toUpperCase() === "COMPLETED";
}

export function isCompletedProjectWorkflowTarget(workflow: unknown, target: string): boolean {
  if (!target || !workflow || typeof workflow !== "object") return false;
  const context = (workflow as { context?: unknown }).context;
  if (!context || typeof context !== "object") return false;
  const execution = (context as { agent_execution?: unknown }).agent_execution;
  if (!execution || typeof execution !== "object") return false;
  const state = execution as { state?: unknown; step?: unknown };
  return String(state.step ?? "") === target && String(state.state ?? "").toUpperCase() === "COMPLETED";
}

export async function runExclusiveProjectBuild<T>(projectId: string, build: () => Promise<T>): Promise<T> {
  if (activeProjects.has(projectId)) {
    throw new Error("Fuer dieses Projekt arbeitet bereits ein Agent. Der bestehende Lauf wird fortgesetzt.");
  }
  activeProjects.add(projectId);
  try {
    return await build();
  } finally {
    activeProjects.delete(projectId);
  }
}
