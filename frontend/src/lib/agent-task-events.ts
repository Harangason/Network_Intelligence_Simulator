export const ENGINEERING_AGENT_TASK_EVENT = "engineering-agent:run-task";
export const ENGINEERING_AGENT_PENDING_TASK_KEY = "networkis:pending-agent-task";
export const ENGINEERING_AGENT_PENDING_WIZARD_KEY = "networkis:pending-engineering-wizard";

export type EngineeringAgentTask = {
  text: string;
  source: "engineering-wizard" | "external";
};

export type EngineeringAgentWizardRequest = {
  projectId: string;
  createdAt: number;
};

export function requestEngineeringAgentWizard(projectId: string) {
  if (typeof window === "undefined") return;
  const request: EngineeringAgentWizardRequest = { projectId, createdAt: Date.now() };
  window.sessionStorage.setItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY, JSON.stringify(request));
}

export function takePendingEngineeringAgentWizard(): EngineeringAgentWizardRequest | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY);
  if (!raw) return null;
  window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_WIZARD_KEY);
  try {
    const request = JSON.parse(raw) as Partial<EngineeringAgentWizardRequest>;
    if (!request.projectId || typeof request.projectId !== "string") return null;
    return { projectId: request.projectId, createdAt: Number(request.createdAt) || Date.now() };
  } catch {
    return null;
  }
}

export function queueEngineeringAgentTask(text: string) {
  const task: EngineeringAgentTask = {
    text: text.trim(),
    source: "engineering-wizard",
  };
  if (!task.text || typeof window === "undefined") return;
  window.sessionStorage.setItem(ENGINEERING_AGENT_PENDING_TASK_KEY, JSON.stringify(task));
  window.dispatchEvent(new CustomEvent<EngineeringAgentTask>(ENGINEERING_AGENT_TASK_EVENT, { detail: task }));
}

export function takePendingEngineeringAgentTask(): EngineeringAgentTask | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
  if (!raw) return null;
  try {
    const task = JSON.parse(raw) as Partial<EngineeringAgentTask>;
    if (!task.text || typeof task.text !== "string") return null;
    window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
    return {
      text: task.text,
      source: task.source === "engineering-wizard" ? "engineering-wizard" : "external",
    };
  } catch {
    window.sessionStorage.removeItem(ENGINEERING_AGENT_PENDING_TASK_KEY);
    return null;
  }
}
