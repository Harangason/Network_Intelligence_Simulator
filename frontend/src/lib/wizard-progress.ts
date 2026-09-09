export function parameterProgressTarget(configured: boolean, toolState: string | undefined, statusProgress: number) {
  if (toolState === "input-streaming" || toolState === "input-available") return 90;
  // The workflow status is the canonical completion signal. Default-backed
  // parameters intentionally have no materialized payload, but APPROVED still
  // means that the step is complete.
  if (statusProgress >= 100) return 100;
  if (configured || toolState === "output-available") return statusProgress;
  return 0;
}

export function wizardAnalysisHeading({
  agentPending,
  currentStep,
  executionState,
  modelReviewPending,
  routingReviewPending,
  runPaused,
}: {
  agentPending: boolean;
  currentStep: string;
  executionState?: string;
  modelReviewPending: boolean;
  routingReviewPending: boolean;
  runPaused: boolean;
}) {
  if (agentPending) {
    return currentStep && currentStep !== "Abgeschlossen"
      ? `${currentStep} wird bearbeitet`
      : "Engineering-Auftrag wird verarbeitet";
  }
  if (routingReviewPending || modelReviewPending) return "Analyse bereit zur Freigabe";
  if (executionState === "READY_TO_CONTINUE") return "Modell übernommen · Fortsetzung bereit";
  if (runPaused) return "Auftrag angehalten";
  return "Analyseübersicht";
}

export function symbolicProgressAt(from: number, to: number, elapsedMs: number) {
  const elapsed = Math.max(0, Math.min(1, elapsedMs / 1600));
  const eased = 1 - (1 - elapsed) ** 3;
  return Math.round(Math.max(0, Math.min(100, from + (to - from) * eased)));
}
export function parametersAreWorking(
  pending: boolean,
  execution: { step: string; state: string } | null,
  toolState?: string,
) {
  if (!pending) return false;
  // Persisted execution is authoritative; old tool parts can survive a pause
  // or a transition into another step.
  if (execution) return execution.step === "parameters" && execution.state === "RUNNING";
  return toolState === "input-streaming" || toolState === "input-available";
}
