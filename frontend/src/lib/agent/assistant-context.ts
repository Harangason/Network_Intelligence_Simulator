export const ASSISTANT_CONTEXT_EVENT = "engineering:assistant-context";
export type AssistantSelection = { id: string; object_type: string; name: string };
let selection: AssistantSelection | null = null;
export function setAssistantSelection(value: AssistantSelection | null) {
  selection = value;
  window.dispatchEvent(new Event(ASSISTANT_CONTEXT_EVENT));
}
export function readAssistantContext() {
  return { active_view: window.location.pathname, selected_object_refs: selection ? [selection] : [] };
}
export function engineeringContextHref(ref: Record<string, string>, projectId: string) {
  const routes: Record<string, string> = { Routing: "/studio/routing", Route: "/studio/routing", Simulation: "/studio/simulation", Trace: "/studio/trace-analysis", Workspace: "/studio/agent", Capacity: '/studio/capacity' };
  const resources: Record<string, string> = { HardwareNode: "hardware-nodes", HardwareNetworkInterface: "hardware-interfaces", Function: "functions", Interface: "interfaces", Message: "messages", Signal: "signals" };
  const type = ref.object_type ?? ref.type;
  if (!routes[type] && !resources[type]) return null;
  const params = new URLSearchParams({ project: projectId });
  if (resources[type]) params.set("resource", resources[type]);
  if (ref.id) params.set(type === 'Workspace' ? 'response' : "object", ref.id);
  return `${routes[type] ?? "/studio/engineering"}?${params}`;
}
