import type { WorkflowStatus, WorkflowStepId } from "@/lib/workflow-api";

export const ENGINEERING_AGENT_TASK_EVENT = "engineering-agent:run-task";
export const ENGINEERING_AGENT_OPEN_EVENT = "engineering-agent:open";
export const ENGINEERING_AGENT_WIZARD_OPEN_EVENT = "engineering-agent:wizard-open";
export const ENGINEERING_AGENT_WIZARD_SESSION_EVENT = "engineering-agent:wizard-session";
export const ENGINEERING_AGENT_PENDING_TASK_KEY = "networkis:pending-agent-task";
export const ENGINEERING_AGENT_PENDING_WIZARD_KEY = "networkis:pending-engineering-wizard";
export const ENGINEERING_AGENT_WIZARD_SESSION_KEY = "networkis:active-engineering-wizard-session";

const WORKFLOW_STEP_ORDER: WorkflowStepId[] = [
  "engineering_model",
  "routing",
  "network_editor",
  "parameters",
  "capacity_timing",
  "validation",
  "simulation",
  "results_analysis",
  "data_science_intelligence",
];
const COMPLETE_WORKFLOW_STATUSES = new Set<WorkflowStatus>(["COMPLETE", "APPROVED", "WARNING"]);
const ROUTING_CONTINUATION_PROMPT = [
  "Setze den freigegebenen Engineering-Workflow selbststaendig bis Data Science & Intelligence fort.",
  "Erzeuge Netzwerk-Topologie, vollstaendige Parameter, Capacity & Timing, Preflight, eine echte Simulation, Results / Analysis und die abschliessende Intelligence-Bewertung.",
  "Stoppe nur bei einem echten technischen Blocker oder einem weiteren zwingenden Human-Review-Gate.",
].join("\n\n");

export type EngineeringAgentTask = {
  text: string;
  source: "engineering-wizard" | "external";
  gate?: "routing-approval";
  projectId?: string;
  workflowTarget?: WorkflowStepId;
  lastWorkflowSignature?: string;
  lastDispatchAt?: number;
  noProgressRuns?: number;
  paused?: boolean;
};

export type EngineeringAgentWorkflowProgress = {
  complete: boolean;
  blockedStep?: WorkflowStepId;
  currentStep?: WorkflowStepId;
  signature: string;
};

export type EngineeringAgentWizardRequest = {
  projectId: string;
  createdAt: number;
};

export type EngineeringAgentWizardSession = {
  projectId: string;
  activatedAt: number;
};

export function requestEngineeringAgentWizard(projectId: string, options: { dispatch?: boolean } = {}) {
  if (typeof window === "undefined") return;
  const request: EngineeringAgentWizardRequest = { projectId, createdAt: Date.now() };
  window.sessionStorage.setItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY, JSON.stringify(request));
  if (options.dispatch === false) return;
  window.dispatchEvent(new CustomEvent<EngineeringAgentWizardRequest>(ENGINEERING_AGENT_WIZARD_OPEN_EVENT, {
    detail: request,
  }));
}

export function takePendingEngineeringAgentWizard(projectId?: string): EngineeringAgentWizardRequest | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY);
  if (!raw) return null;
  try {
    const request = JSON.parse(raw) as Partial<EngineeringAgentWizardRequest>;
    if (!request.projectId || typeof request.projectId !== "string") {
      window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY);
      return null;
    }
    if (projectId && request.projectId !== projectId) return null;
    window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY);
    return { projectId: request.projectId, createdAt: Number(request.createdAt) || Date.now() };
  } catch {
    window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY);
    return null;
  }
}

export function activateEngineeringAgentWizardSession(projectId: string) {
  if (typeof window === "undefined" || !projectId.trim()) return null;
  const session: EngineeringAgentWizardSession = {
    projectId: projectId.trim(),
    activatedAt: Date.now(),
  };
  window.sessionStorage.setItem(ENGINEERING_AGENT_WIZARD_SESSION_KEY, JSON.stringify(session));
  window.dispatchEvent(new CustomEvent<EngineeringAgentWizardSession>(ENGINEERING_AGENT_WIZARD_SESSION_EVENT, {
    detail: session,
  }));
  return session;
}

export function readEngineeringAgentWizardSession(projectId?: string): EngineeringAgentWizardSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(ENGINEERING_AGENT_WIZARD_SESSION_KEY);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as Partial<EngineeringAgentWizardSession>;
    if (!session.projectId || typeof session.projectId !== "string") {
      window.sessionStorage.removeItem(ENGINEERING_AGENT_WIZARD_SESSION_KEY);
      return null;
    }
    if (projectId && session.projectId !== projectId) return null;
    return {
      projectId: session.projectId,
      activatedAt: Number(session.activatedAt) || Date.now(),
    };
  } catch {
    window.sessionStorage.removeItem(ENGINEERING_AGENT_WIZARD_SESSION_KEY);
    return null;
  }
}

export function finishEngineeringAgentWizardSession(projectId?: string) {
  if (typeof window === "undefined") return false;
  const session = readEngineeringAgentWizardSession(projectId);
  if (!session) return false;
  window.sessionStorage.removeItem(ENGINEERING_AGENT_WIZARD_SESSION_KEY);
  window.dispatchEvent(new CustomEvent(ENGINEERING_AGENT_WIZARD_SESSION_EVENT));
  return true;
}

export function persistEngineeringAgentTask(
  text: string,
  source: EngineeringAgentTask["source"] = "engineering-wizard",
  gate?: EngineeringAgentTask["gate"],
  projectId?: string,
  workflowTarget?: WorkflowStepId,
) {
  const task: EngineeringAgentTask = {
    text: text.trim(),
    source,
    gate,
    projectId: projectId?.trim() || undefined,
    workflowTarget,
  };
  if (!task.text || typeof window === "undefined") return null;
  window.sessionStorage.setItem(ENGINEERING_AGENT_PENDING_TASK_KEY, JSON.stringify(task));
  return task;
}

export function queueEngineeringAgentTask(text: string) {
  const task = persistEngineeringAgentTask(text);
  if (!task || typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<EngineeringAgentTask>(ENGINEERING_AGENT_TASK_EVENT, { detail: task }));
}

export function resumePendingEngineeringAgentTask(projectId?: string) {
  if (typeof window === "undefined") return false;
  const raw = window.sessionStorage.getItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
  if (!raw) return false;
  try {
    const task = normalizeStoredTask(JSON.parse(raw) as Partial<EngineeringAgentTask>);
    if (!task) return false;
    if (task.projectId && projectId && task.projectId !== projectId) return false;
    if (task.gate !== "routing-approval") return false;
    if (task.lastDispatchAt && Date.now() - task.lastDispatchAt < 2_000) return false;
    const dispatchedTask = { ...task, lastDispatchAt: Date.now() };
    updatePendingEngineeringAgentTask(dispatchedTask);
    window.dispatchEvent(new CustomEvent<EngineeringAgentTask>(ENGINEERING_AGENT_TASK_EVENT, {
      detail: dispatchedTask,
    }));
    return true;
  } catch {
    window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
    return false;
  }
}

export function queueEngineeringWorkflowContinuation(projectId?: string) {
  if (typeof window === "undefined") return false;
  const pending = readPendingEngineeringAgentTask(projectId);
  if (pending?.gate === "routing-approval") {
    return resumePendingEngineeringAgentTask(projectId);
  }
  if (pending && !pending.workflowTarget) return false;

  const task = pending ?? persistEngineeringAgentTask(
    ROUTING_CONTINUATION_PROMPT,
    "external",
    undefined,
    projectId,
    "data_science_intelligence",
  );
  if (!task) return false;
  if (task.lastDispatchAt && Date.now() - task.lastDispatchAt < 4_000) return false;

  const dispatchedTask = updatePendingEngineeringAgentTask({
    ...task,
    lastDispatchAt: Date.now(),
  });
  if (!dispatchedTask) return false;
  window.dispatchEvent(new CustomEvent<EngineeringAgentTask>(ENGINEERING_AGENT_TASK_EVENT, {
    detail: dispatchedTask,
  }));
  return true;
}

export function takePendingEngineeringAgentTask(): EngineeringAgentTask | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
  if (!raw) return null;
  try {
    const task = normalizeStoredTask(JSON.parse(raw) as Partial<EngineeringAgentTask>);
    if (!task) {
      window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
      return null;
    }
    if (task.gate === "routing-approval") return null;
    if (!task.workflowTarget) window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
    return task;
  } catch {
    window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
    return null;
  }
}

export function readPendingEngineeringAgentTask(projectId?: string): EngineeringAgentTask | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
  if (!raw) return null;
  try {
    const task = normalizeStoredTask(JSON.parse(raw) as Partial<EngineeringAgentTask>);
    if (!task) return null;
    if (task.projectId && projectId && task.projectId !== projectId) return null;
    return task;
  } catch {
    window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
    return null;
  }
}

export function updatePendingEngineeringAgentTask(task: EngineeringAgentTask) {
  if (typeof window === "undefined") return null;
  const normalized = normalizeStoredTask(task);
  if (!normalized) return null;
  window.sessionStorage.setItem(ENGINEERING_AGENT_PENDING_TASK_KEY, JSON.stringify(normalized));
  return normalized;
}

export function clearPendingEngineeringAgentTask(projectId?: string) {
  const task = readPendingEngineeringAgentTask(projectId);
  if (!task || typeof window === "undefined") return false;
  window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
  return true;
}

export function engineeringAgentWorkflowProgress(
  task: Pick<EngineeringAgentTask, "workflowTarget">,
  statuses: Record<WorkflowStepId, WorkflowStatus>,
  versions: Record<WorkflowStepId, number>,
): EngineeringAgentWorkflowProgress {
  const targetIndex = task.workflowTarget ? WORKFLOW_STEP_ORDER.indexOf(task.workflowTarget) : -1;
  const requiredSteps = WORKFLOW_STEP_ORDER.slice(0, targetIndex >= 0 ? targetIndex + 1 : 0);
  const signature = requiredSteps
    .map((step) => `${step}:${statuses[step] ?? "EMPTY"}:${Number(versions[step] ?? 0)}`)
    .join("|");
  const erroredStep = requiredSteps.find((step) => statuses[step] === "ERROR");
  const currentStep = requiredSteps.find((step) => !COMPLETE_WORKFLOW_STATUSES.has(statuses[step] ?? "EMPTY"));
  const reviewBlockedStep = currentStep === "engineering_model" || currentStep === "routing"
    ? currentStep
    : undefined;
  return {
    complete: requiredSteps.length > 0 && !currentStep,
    blockedStep: erroredStep ?? reviewBlockedStep,
    currentStep,
    signature,
  };
}

function normalizeStoredTask(task: Partial<EngineeringAgentTask>): EngineeringAgentTask | null {
  if (!task.text || typeof task.text !== "string") return null;
  const legacyRoutingGate = /menschlichen Routing-Freigabe/i.test(task.text);
  const workflowTarget = WORKFLOW_STEP_ORDER.includes(task.workflowTarget as WorkflowStepId)
    ? task.workflowTarget as WorkflowStepId
    : undefined;
  return {
    text: task.text,
    source: task.source === "external" ? "external" : "engineering-wizard",
    gate: task.gate === "routing-approval" || (legacyRoutingGate && !workflowTarget)
      ? "routing-approval"
      : undefined,
    projectId: typeof task.projectId === "string" && task.projectId.trim()
      ? task.projectId.trim()
      : undefined,
    workflowTarget,
    lastWorkflowSignature: typeof task.lastWorkflowSignature === "string"
      ? task.lastWorkflowSignature
      : undefined,
    lastDispatchAt: Number.isFinite(task.lastDispatchAt) ? Number(task.lastDispatchAt) : undefined,
    noProgressRuns: Number.isFinite(task.noProgressRuns)
      ? Math.max(0, Math.floor(Number(task.noProgressRuns)))
      : 0,
    paused: task.paused === true,
  };
}
