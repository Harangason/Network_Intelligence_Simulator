const RUN_STEPS = ["engineering_model", "routing", "network_editor", "parameters", "capacity_timing", "validation", "simulation", "results_analysis", "data_science_intelligence"] as const;

export type AgentBuildProgress = {
  step: typeof RUN_STEPS[number];
  completed: number;
  total: number;
};

export type AgentRunStatus = AgentBuildProgress & {
  run_id: string;
  state: "RUNNING" | "BLOCKED" | "REVIEW_REQUIRED" | "READY_TO_CONTINUE" | "COMPLETED" | "CANCELED";
  message: string;
  updated_at: string;
};

export function readAgentRunStatus(value: unknown, runId: string): AgentRunStatus | null {
  if (!value || typeof value !== "object" || !runId) return null;
  const item = value as Record<string, unknown>;
  if (item.run_id !== runId
    || !["RUNNING", "BLOCKED", "REVIEW_REQUIRED", "READY_TO_CONTINUE", "COMPLETED", "CANCELED"].includes(String(item.state))
    || !RUN_STEPS.some((step) => step === item.step)
    || !Number.isFinite(item.completed) || !Number.isFinite(item.total)
    || Number(item.completed) < 0 || Number(item.total) < 0
    || typeof item.message !== "string"
    || typeof item.updated_at !== "string" || !Number.isFinite(Date.parse(item.updated_at))) return null;
  return item as AgentRunStatus;
}

export function agentBuildProgressPercent(progress: AgentBuildProgress) {
  if (progress.total > 0) {
    return Math.min(100, Math.round(100 * progress.completed / progress.total));
  }
  // A heartbeat proves liveness, not completed work.
  return 0;
}

export function agentReviewStep(run: AgentRunStatus | null) {
  return run?.state === "REVIEW_REQUIRED" ? run.step : null;
}

export function agentRunIsActive(run: AgentRunStatus | null, now = Date.now()) {
  return run?.state === "RUNNING" && now - Date.parse(run.updated_at) < 120_000;
}

export function agentRunHasDurableOutcome(run: AgentRunStatus | null) {
  return run != null && ["REVIEW_REQUIRED", "READY_TO_CONTINUE", "COMPLETED"].includes(run.state);
}

export function resolveAgentRunStep(run: AgentRunStatus | null, statuses: Partial<Record<AgentBuildProgress['step'], string>>) {
  if (!run || !['RUNNING', 'BLOCKED'].includes(run.state)) return run;
  const done = (step: AgentBuildProgress['step']) => ['COMPLETE', 'APPROVED', 'WARNING'].includes(statuses[step] ?? '');
  if (!done(run.step)) return run;
  const next = RUN_STEPS.slice(RUN_STEPS.indexOf(run.step) + 1).find(step => !done(step));
  return next ? { ...run, step: next } : run;
}

export function wizardRunCanRetry(runPaused: boolean, hasResumablePrompt: boolean, run: AgentRunStatus | null) {
  // Retries are explicit user actions. A failed attempt must not turn the
  // durable wizard into a permanent dead end; only cancellation is terminal.
  return runPaused && hasResumablePrompt && run?.state !== "CANCELED";
}
