/** Presentation references only. Runs, decoded samples and evidence stay in NIS services. */
export type LinkMode = 'FOLLOW_PRIMARY' | 'INDEPENDENT' | 'COMPARE';
export type AnalysisView = 'simulation' | 'session' | 'messages' | 'sequence' | 'signals' | 'trace' | 'load' | 'network' | 'events' | 'findings' | 'root-cause' | 'charts' | 'assistant';
export type AnalysisStage = 'LOAD' | 'FILTER' | 'INSPECT_MESSAGES' | 'FOLLOW_SEQUENCE' | 'INSPECT_SIGNALS' | 'SYNCHRONIZE_TRACE' | 'DETECT_FINDINGS' | 'EXPLORE_CHARTS' | 'EXPLAIN_ROOT_CAUSE';
export type CompareSide = { run_id: string | null; trace_id: string | null; object_id: string | null; time_range: [number, number]; view: AnalysisView };
export type AnalysisContext = {
  project_id: string; session_id: string | null; simulation_run_id: string | null; trace_id: string | null;
  trace_segment_id: string | null; network_id: string | null; ecu_id: string | null;
  message_id: string | null; signal_id: string | null; event_id: string | null;
  time_cursor: number | null; time_range: [number, number]; time_basis: string | null;
  sample_index: number | null; frame_index: number | null; message_index: number | null; sequence_step: number | null;
  filter_set: { query: string }; view_mode: AnalysisView; analysis_stage: AnalysisStage;
  selected_finding_id: string | null; selected_root_cause_id: string | null;
  compare_left: CompareSide | null; compare_right: CompareSide | null;
};
export type WindowDescriptor = {
  window_id: string; workspace_id: string; primary_id: string; project_id: string;
  board_id: 'simulation' | 'trace'; view_id: AnalysisView; link_mode: LinkMode;
  context: AnalysisContext; width: number; height: number; last_position: [number, number];
  created_at: number; last_active_at: number;
};
export type WorkspaceProfile = { version: 1; profile_id: string; name: string; user_id: 'local-session'; project_scope: string; primary_view: AnalysisView; secondary_views: AnalysisView[]; link_modes: LinkMode[]; preferred_window_sizes: [number, number][]; preferred_monitor_roles: string[]; restore_on_start: boolean };
export const ANALYSIS_VIEWS: Record<AnalysisView, string> = { simulation: 'Simulation', session: 'Session', messages: 'Botschaften', sequence: 'Sequenz', signals: 'Signale', trace: 'Trace', load: 'Bus Load', network: 'Network / ECU', events: 'Events', findings: 'Findings / Gaps', 'root-cause': 'Root Cause', charts: 'Diagramme', assistant: 'Analyse-Assistent' };
export const VIEW_STAGES: Partial<Record<AnalysisView, AnalysisStage>> = { session:'LOAD', messages:'INSPECT_MESSAGES', sequence:'FOLLOW_SEQUENCE', signals:'INSPECT_SIGNALS', trace:'SYNCHRONIZE_TRACE', findings:'DETECT_FINDINGS', charts:'EXPLORE_CHARTS', 'root-cause':'EXPLAIN_ROOT_CAUSE' };
/** Opaque view identity, also on HTTP LAN origins where randomUUID is unavailable. */
export function analysisWindowId(): string {
  if(typeof globalThis.crypto?.randomUUID === 'function')return globalThis.crypto.randomUUID();
  const bytes=globalThis.crypto.getRandomValues(new Uint8Array(16));
  return [...bytes].map(b=>b.toString(16).padStart(2,'0')).join('');
}
const stringFields = ['session_id','simulation_run_id','trace_id','trace_segment_id','network_id','ecu_id','message_id','signal_id','event_id','time_basis','selected_finding_id','selected_root_cause_id'] as const;
const indexFields = ['sample_index','frame_index','message_index','sequence_step'] as const;
export function emptyAnalysisContext(project: string): AnalysisContext {
  return { project_id:project, session_id:null, simulation_run_id:null, trace_id:null, trace_segment_id:null, network_id:null, ecu_id:null, message_id:null, signal_id:null, event_id:null, time_cursor:null, time_range:[0,1e15], time_basis:null, sample_index:null, frame_index:null, message_index:null, sequence_step:null, filter_set:{query:''}, view_mode:'session', analysis_stage:'LOAD', selected_finding_id:null, selected_root_cause_id:null, compare_left:null, compare_right:null };
}
const boundedString = (v: unknown) => typeof v === 'string' && v.length <= 4096;
const time = (v: unknown) => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1e15;
export function validRange(v: unknown): v is [number, number] { return Array.isArray(v) && v.length === 2 && v.every(time) && v[0] <= v[1]; }
function validCompare(v: unknown): v is CompareSide | null {
  if (v === null) return true;
  if (!v || typeof v !== 'object') return false;
  const side = v as CompareSide;
  return [side.run_id,side.trace_id,side.object_id].every(x => x === null || boundedString(x)) && validRange(side.time_range) && Object.hasOwn(ANALYSIS_VIEWS,side.view);
}
/** Whitelist and bound cross-window data; never accept arbitrary object/trace payloads. */
export function validatedContext(value: unknown, project: string): AnalysisContext | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const v = value as AnalysisContext, context = emptyAnalysisContext(project);
  if (v.project_id !== project || !boundedString(project) || !validRange(v.time_range) || !(v.time_cursor === null || time(v.time_cursor)) || !Object.hasOwn(ANALYSIS_VIEWS,v.view_mode) || !['LOAD','FILTER','INSPECT_MESSAGES','FOLLOW_SEQUENCE','INSPECT_SIGNALS','SYNCHRONIZE_TRACE','DETECT_FINDINGS','EXPLORE_CHARTS','EXPLAIN_ROOT_CAUSE'].includes(v.analysis_stage)) return null;
  if (!v.filter_set || !boundedString(v.filter_set.query) || !validCompare(v.compare_left) || !validCompare(v.compare_right)) return null;
  for (const field of stringFields) { if (!(v[field] === null || boundedString(v[field]))) return null; context[field] = v[field]; }
  for (const field of indexFields) { if (!(v[field] === null || Number.isSafeInteger(v[field]) && v[field]! >= 0)) return null; context[field] = v[field]; }
  return { ...context, time_cursor:v.time_cursor, time_range:[...v.time_range], filter_set:{query:v.filter_set.query}, view_mode:v.view_mode, analysis_stage:v.analysis_stage, compare_left:v.compare_left && { ...v.compare_left, time_range:[...v.compare_left.time_range] }, compare_right:v.compare_right && { ...v.compare_right, time_range:[...v.compare_right.time_range] } };
}
export function contextWithPatch(current: AnalysisContext, patch: Partial<AnalysisContext>): AnalysisContext | null {
  const next = { ...current, ...patch, project_id:current.project_id };
  // A new source invalidates references to the previous source, including its time basis.
  if (next.simulation_run_id !== current.simulation_run_id || next.trace_id !== current.trace_id) {
    for (const field of [...stringFields.filter(x => !['session_id','simulation_run_id','trace_id'].includes(x)), ...indexFields]) {
      if (!Object.hasOwn(patch,field)) (next as unknown as Record<string,unknown>)[field] = null;
    }
    if (!Object.hasOwn(patch,'time_cursor')) next.time_cursor = null;
  }
  return validatedContext(next,current.project_id);
}
export function analysisViewHref(descriptor: WindowDescriptor): string {
  const c = descriptor.context;
  const p = new URLSearchParams({ project:descriptor.project_id, workspace:descriptor.workspace_id, window:descriptor.window_id, primary:descriptor.primary_id, link:descriptor.link_mode, view:descriptor.view_id });
  if (c.trace_id?.startsWith('import:')) p.set('import',c.trace_id.slice(7));
  else if (c.simulation_run_id) p.set('job',c.simulation_run_id);
  if (c.event_id) p.set('event',c.event_id);
  if (c.signal_id) p.set('signal',c.signal_id);
  if (c.network_id) p.set('network',c.network_id);
  if (c.ecu_id) p.set('ecu',c.ecu_id);
  p.set('start_s',String(c.time_range[0])); p.set('end_s',String(c.time_range[1]));
  if (c.time_cursor !== null) p.set('focus_s',String(c.time_cursor));
  if (c.time_basis) p.set('time_basis',c.time_basis);
  if (c.compare_left) p.set('compare_left',JSON.stringify(c.compare_left));
  if (c.compare_right) p.set('compare_right',JSON.stringify(c.compare_right));
  p.set('q',c.filter_set.query);
  return `${descriptor.view_id === 'simulation' ? '/studio/simulation' : '/trace-analysis'}?${p}`;
}
export function contextFromSearch(project: string, search: string): AnalysisContext {
  const p = new URLSearchParams(search), c = emptyAnalysisContext(project);
  const view = p.get('view'); if (view && Object.hasOwn(ANALYSIS_VIEWS,view)) { c.view_mode = view as AnalysisView; c.analysis_stage = VIEW_STAGES[c.view_mode] ?? 'LOAD'; }
  c.simulation_run_id = p.get('job'); c.trace_id = p.get('import') ? `import:${p.get('import')}` : c.simulation_run_id;
  c.event_id = p.get('event'); c.signal_id = p.get('signal'); c.network_id = p.get('network'); c.ecu_id = p.get('ecu'); c.time_basis = p.get('time_basis');
  const focus = p.get('focus_s'); if (focus !== null && time(Number(focus))) c.time_cursor = Number(focus);
  const range = [Number(p.get('start_s') ?? 0),Number(p.get('end_s') ?? 1e15)]; if (validRange(range)) c.time_range = range;
  c.filter_set.query = (p.get('q') ?? '').slice(0,4096);
  for (const field of ['compare_left','compare_right'] as const) { const raw=p.get(field); if(raw && raw.length<=12000)try { const side=JSON.parse(raw); if(validCompare(side))c[field]=side; }catch { /* An invalid compare link never changes the source context. */ } }
  return validatedContext(c,project) ?? emptyAnalysisContext(project);
}
export function validProfile(value: unknown, project: string): value is WorkspaceProfile {
  if (!value || typeof value !== 'object') return false;
  const p = value as WorkspaceProfile;
  return p.version === 1 && p.project_scope === project && p.user_id === 'local-session' && boundedString(p.profile_id) && boundedString(p.name) && Object.hasOwn(ANALYSIS_VIEWS,p.primary_view) && Array.isArray(p.secondary_views) && p.secondary_views.length <= 6 && p.secondary_views.every(v => Object.hasOwn(ANALYSIS_VIEWS,v)) && Array.isArray(p.link_modes) && p.link_modes.length === p.secondary_views.length && p.link_modes.every(v => ['FOLLOW_PRIMARY','INDEPENDENT','COMPARE'].includes(v)) && Array.isArray(p.preferred_window_sizes) && p.preferred_window_sizes.length === p.secondary_views.length && p.preferred_window_sizes.every(s => Array.isArray(s) && s.length === 2 && s.every(n => Number.isFinite(n) && n >= 320 && n <= 7680)) && Array.isArray(p.preferred_monitor_roles) && p.preferred_monitor_roles.length <= 6 && p.preferred_monitor_roles.every(boundedString) && typeof p.restore_on_start === 'boolean';
}
export function validatedDescriptor(value: unknown, project: string): WindowDescriptor | null {
  if (!value || typeof value!=='object')return null;
  const d=value as WindowDescriptor,c=validatedContext(d.context,project);
  if(!c || d.project_id!==project || ![d.window_id,d.workspace_id,d.primary_id].every(id=>typeof id==='string'&&/^[a-zA-Z0-9_-]{1,100}$/.test(id)) || !['simulation','trace'].includes(d.board_id) || !Object.hasOwn(ANALYSIS_VIEWS,d.view_id) || !['FOLLOW_PRIMARY','INDEPENDENT','COMPARE'].includes(d.link_mode) || ![d.width,d.height].every(n=>Number.isFinite(n)&&n>=0&&n<=20000) || !Array.isArray(d.last_position) || d.last_position.length!==2 || !d.last_position.every(Number.isFinite) || !Number.isFinite(d.created_at) || !Number.isFinite(d.last_active_at))return null;
  return {window_id:d.window_id,workspace_id:d.workspace_id,primary_id:d.primary_id,project_id:project,board_id:d.board_id,view_id:d.view_id,link_mode:d.link_mode,context:c,width:d.width,height:d.height,last_position:[...d.last_position],created_at:d.created_at,last_active_at:d.last_active_at};
}
