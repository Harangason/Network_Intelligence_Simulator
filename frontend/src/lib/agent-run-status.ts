const RUN_STEPS = ["engineering_model", "routing", "network_editor", "parameters", "capacity_timing", "validation", "simulation", "results_analysis", "data_science_intelligence"] as const;

export type AgentBuildProgress = {
  step: typeof RUN_STEPS[number];
  completed: number;
  total: number;
};

export type AgentRunStatus = AgentBuildProgress & {
  run_id: string;
  state: "RUNNING" | "BLOCKED" | "REVIEW_REQUIRED" | "COMPLETED" | "CANCELED";
  message: string;
  updated_at: string;
};

export function readAgentRunStatus(value: unknown, runId: string): AgentRunStatus | null {
  if (!value || typeof value !== "object" || !runId) return null;
  const item = value as Record<string, unknown>;
  if (item.run_id !== runId
    || !["RUNNING", "BLOCKED", "REVIEW_REQUIRED", "COMPLETED", "CANCELED"].includes(String(item.state))
    || !RUN_STEPS.some((step) => step === item.step)
    || !Number.isFinite(item.completed) || !Number.isFinite(item.total)
    || Number(item.completed) < 0 || Number(item.total) < 0
    || typeof item.message !== "string"
    || typeof item.updated_at !== "string" || !Number.isFinite(Date.parse(item.updated_at))) return null;
  return item as AgentRunStatus;
}

export function agentBuildProgressPercent(progress: AgentBuildProgress) {
  return progress.total > 0
    ? Math.min(100, Math.round(100 * progress.completed / progress.total))
    : 0;
}

export function agentRunIsActive(run: AgentRunStatus | null, now = Date.now()) {
  return run?.state === "RUNNING" && now - Date.parse(run.updated_at) < 120_000;
}
