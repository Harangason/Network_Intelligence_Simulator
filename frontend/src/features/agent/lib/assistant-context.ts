import { readActiveProjectId } from '../../settings/lib/user-settings.ts';
import { readAnalysisWorkspace } from '../../traces/lib/analysis-workspace-browser.ts';
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
  const workspace=readAnalysisWorkspace();
  if (workspace?.ended) return {active_view:window.location.pathname,selected_object_refs:[] as Record<string,string>[]};
  if (workspace && !workspace.ended && workspace.context.project_id===readActiveProjectId()) {
    const c=workspace.context;
    for (const [object_type,id] of [['SimulationRun',c.simulation_run_id],['Trace',c.trace_id],['HardwareNode',c.ecu_id],['Network',c.network_id],['Message',c.message_id],['Signal',c.signal_id],['Finding',c.selected_finding_id]] as const) if(id)refs.push({object_type,id});
    refs.push({object_type:'AnalysisContext',id:workspace.descriptor.workspace_id,project_id:c.project_id,session_id:c.session_id??'',trace_segment_id:c.trace_segment_id??'',event_id:c.event_id??'',time_cursor:c.time_cursor===null?'unknown':String(c.time_cursor),time_start:String(c.time_range[0]),time_end:String(c.time_range[1]),time_basis:c.time_basis??'unknown',filter:c.filter_set.query,analysis_stage:c.analysis_stage,root_cause_id:c.selected_root_cause_id??'',view:workspace.descriptor.view_id,projection:'analysis_only'});
  }
  const parameters = new URLSearchParams(window.location.search);
  if (window.location.pathname.includes('trace') && parameters.get('job')) {
    if (!refs.some(ref=>ref.object_type==='SimulationRun'&&ref.id===parameters.get('job'))) refs.push({ object_type: 'SimulationRun', id: parameters.get('job')! });
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
