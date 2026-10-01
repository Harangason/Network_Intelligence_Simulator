import { readActiveProjectId } from '../user-settings.ts';
export const ASSISTANT_CONTEXT_EVENT = "engineering:assistant-context";
export type AssistantSelection = { id: string; object_type: string; name: string };
let selection: AssistantSelection | null = null;
let selectionProject = '';
export function setAssistantSelection(value: AssistantSelection | null) {
  selection = value;
  selectionProject = readActiveProjectId();
  window.dispatchEvent(new Event(ASSISTANT_CONTEXT_EVENT));
}
export function readAssistantContext() {
  const refs: Record<string, string>[] = selection && selectionProject === readActiveProjectId() ? [selection] : [];
  const parameters = new URLSearchParams(window.location.search);
  if (window.location.pathname.includes('trace') && parameters.get('job')) {
    refs.push({ object_type: 'SimulationRun', id: parameters.get('job')! });
  }
  return { active_view: window.location.pathname, selected_object_refs: refs };
}
export function engineeringContextHref(ref: Record<string, string>, projectId: string, returnTo?: string) {
  const routes: Record<string, string> = { Routing: "/studio/routing", Route: "/studio/routing", Simulation: "/studio/simulation", Trace: "/studio/trace-analysis", Workspace: "/studio/agent", Capacity: '/studio/capacity' };
  const resources: Record<string, string> = { HardwareNode: "hardware-nodes", HardwareNetworkInterface: "hardware-interfaces", Function: "functions", Interface: "interfaces", Message: "messages", Signal: "signals" };
  const type = ref.object_type ?? ref.type;
  if (!routes[type] && !resources[type]) return null;
  const params = new URLSearchParams({ project: projectId });
  if (resources[type]) params.set("resource", resources[type]);
  if (ref.id) params.set(type === 'Workspace' ? 'response' : type === 'Route' || type === 'Routing' ? 'route' : "object", ref.id);
  if (type === 'Workspace' && returnTo?.startsWith('/studio/') && !returnTo.startsWith('//') && !returnTo.includes('\\')) {
    const target = new URL(returnTo, 'http://nis.local');
    if (target.origin === 'http://nis.local') {
      target.searchParams.set('project', projectId);
      params.set('back_to', `${target.pathname}${target.search}${target.hash}`);
    }
  }
  return `${routes[type] ?? "/studio/engineering"}?${params}`;
}
