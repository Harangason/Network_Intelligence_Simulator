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
  recoverable?: boolean;
  blocking_findings?: Array<{
    code?: string;
    severity?: string;
    message?: string;
    recommendation?: string;
    object_type?: string;
    object_id?: string;
  }>;
  server_pid?: number;
  request_revision?: string;
  model_review_required?: boolean;
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
  if (run.model_review_required) return { ...run, step: 'engineering_model' as const };
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

export function wizardContinuationPrompt({
  automatic,
  runId,
  workflowTarget,
}: {
  automatic: boolean;
  runId: string;
  workflowTarget?: AgentBuildProgress['step'];
}) {
  if (workflowTarget) {
    return `${automatic ? "Automatische Wiederaufnahme nach einem unterbrochenen Backend-Prozess. " : ""}Setze den bestaetigten Engineering-Auftrag am letzten erreichten Schritt fort. Lauf-ID: ${runId}. Ziel: ${workflowTarget}.`;
  }
  return [
    automatic
      ? "Automatische Wiederaufnahme: Der bestätigte Wizard-Lauf wurde durch einen Backend-Prozesswechsel unterbrochen. Keine Human-Review-Entscheidung automatisch treffen."
      : "Fortsetzung-Freigabe: Der Nutzer hat im Popup ausdrücklich Auftrag fortsetzen gewählt.",
    `Lauf-ID: ${runId}.`,
    "Wenn nach der Nachbearbeitung weiterhin reine Soll/Ist-Abweichungen im Geräteumfang bestehen, dokumentiere die fehlenden Teilnehmer im Wizard-Kontext und arbeite genau einmal weiter. Bei technischen Anlagefehlern stoppen. Keine automatische Endlosschleife.",
  ].join("\n");
}

export function wizardRunNeedsAutomaticRecovery({
  runPaused,
  hasResumablePrompt,
  run,
  automaticResumeCount,
  restoredSession,
  now = Date.now(),
}: {
  runPaused: boolean;
  hasResumablePrompt: boolean;
  run: AgentRunStatus | null;
  automaticResumeCount: number;
  restoredSession: boolean;
  now?: number;
}) {
  if (!runPaused || !hasResumablePrompt || automaticResumeCount > 0 || run?.state === "CANCELED") return false;
  if (run?.recoverable === true) return true;
  if (run?.state === "RUNNING") return !agentRunIsActive(run, now);
  // Older interrupted runs may predate the durable agent_execution record.
  return run == null && restoredSession;
}
